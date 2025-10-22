import base64, os
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import Q
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.shortcuts import get_object_or_404
from apps.directory.models import Rank, Unit, Position
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import viewsets, mixins, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser

from core.permissions import (
    IsAdminOrRoot, IsOwnUser, IsOwnProfile, IsCommander, CanViewSubordinates, IsOfficer, IsStaffish, IsHR,
    ReadOnlyOrStaffish
)
from .models import OfficerProfile, CommanderProfile, HRProfile, CommanderAssignment, OfficerLanguage, CommanderLanguage

from .serializers import (
    UserRegistrationSerializer, UserSerializer,
    OfficerProfileSerializer, OfficerProfileUpdateSerializer,
    CommanderProfileSerializer, HRProfileSerializer,
    CommanderAssignmentSerializer, PasswordResetSerializer, PasswordResetConfirmSerializer,
    PasswordChangeSerializer, OfficerLanguageSerializer, CommanderProfileUpdateSerializer, CommanderLanguageSerializer
)
from .utils import send_verification_email

User = get_user_model()


# -------- Аутентификация / регистрация --------
class AuthViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    @action(detail=False, methods=["post"])
    def register(self, request):
        ser = UserRegistrationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()

        link = f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')}/verify-email/{user.id}"
        try:
            send_verification_email(user, request)
        except Exception:
            pass

        return Response(
            {"message": "Пользователь зарегистрирован. Проверьте email для подтверждения."},
            status=status.HTTP_201_CREATED
        )


    @action(detail=False, methods=["post"])
    def reset_password(self, request):
        ser = PasswordResetSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"]
        # токены пока опустим
        try:
            user = User.objects.get(email=email)
            link = f"{getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')}/reset-password/{user.id}"
            send_mail(
                "Восстановление пароля",
                f"Установите новый пароль: {link}",
                getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                [email],
                fail_silently=True
            )
        except User.DoesNotExist:
            pass
        return Response({"message": "Если адрес существует — письмо отправлено"})

    @action(detail=False, methods=["post"])
    def reset_password_confirm(self, request):
        user_id = request.data.get("user_id")
        ser = PasswordResetConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"detail": "Пользователь не найден"}, status=404)

        user.set_password(ser.validated_data["new_password"])
        user.password_changed_at = timezone.now()
        user.save(update_fields=["password", "password_changed_at"])
        return Response({"message": "Пароль изменён"})


# -------- Пользователи --------
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdminOrRoot]

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        return Response(UserSerializer(request.user).data)

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated])
    def change_password(self, request):
        ser = PasswordChangeSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        user = request.user
        user.set_password(ser.validated_data["new_password"])
        user.password_changed_at = timezone.now()
        user.save(update_fields=["password", "password_changed_at"])
        return Response({"message": "Пароль изменён"})

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, (IsHR | IsAdminOrRoot)])
    def promote_to_commander(self, request):
        """
        HR/ADMIN/ROOT: повысить пользователя до командира и назначить на unit.
        payload: {"user_id": <id>, "unit": <unit_id>, "appointed_at": "YYYY-MM-DD", "force": true|false}
        HR-ограничение: unit должен входить в его responsible_units.
        """
        user_id = request.data.get("user_id")
        unit_id = request.data.get("unit")
        if not user_id or not unit_id:
            return Response({"detail": "user_id и unit обязательны"}, status=400)

        user = get_object_or_404(User, id=user_id)
        unit = get_object_or_404(Unit, id=unit_id)

        # HR может работать только в своих юнитах
        if getattr(request.user, "role", "") == "HR":
            hrp = HRProfile.objects.filter(user=request.user).first()
            if not hrp or unit.id not in set(hrp.responsible_units.values_list("id", flat=True)):
                return Response({"detail": "Недостаточно прав для данного подразделения"}, status=403)

        appointed_at = request.data.get("appointed_at") or timezone.now().date()
        force = str(request.data.get("force", "false")).lower() in ("1", "true", "yes")

        # Контроль единственного активного командира на unit
        active = CommanderProfile.objects.filter(unit=unit, relieved_at__isnull=True).exclude(user=user).first()
        if active and not force:
            return Response(
                {
                    "detail": f"В {unit.name} уже есть активный командир (user_id={active.user_id}). Укажите force=true или снимите действующего."},
                status=409
            )
        if active and force:
            active.relieved_at = appointed_at
            active.save(update_fields=["relieved_at"])

        # выдать/обновить роль
        if user.role != User.UserRole.COMMANDER:
            user.role = User.UserRole.COMMANDER
            user.save(update_fields=["role"])

        # профили
        cp, _ = CommanderProfile.objects.get_or_create(user=user)
        cp.unit = unit
        cp.appointed_at = appointed_at
        cp.relieved_at = None
        cp.save(update_fields=["unit", "appointed_at", "relieved_at"])

        # офицерский профиль — оставить как есть (командир тоже офицер в системе)
        OfficerProfile.objects.get_or_create(user=user)

        return Response({"message": "Назначен командиром", "user_id": user.id, "unit": unit.id})

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, (IsHR | IsAdminOrRoot)])
    def relieve_commander(self, request):
        """
        HR/ADMIN/ROOT: снять командира с должности (закрыть его активность на unit).
        payload: {"user_id": <id>, "relieved_at": "YYYY-MM-DD", "downgrade_role": false}
        HR-ограничение: unit командира должен входить в его responsible_units.
        """
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"detail": "user_id обязателен"}, status=400)

        user = get_object_or_404(User, id=user_id)
        cp = CommanderProfile.objects.filter(user=user, relieved_at__isnull=True).first()
        if not cp:
            return Response({"detail": "Активное командование не найдено"}, status=404)

        # HR-проверка зон ответственности
        if getattr(request.user, "role", "") == "HR":
            hrp = HRProfile.objects.filter(user=request.user).first()
            if not hrp or cp.unit_id not in set(hrp.responsible_units.values_list("id", flat=True)):
                return Response({"detail": "Недостаточно прав для данного подразделения"}, status=403)

        dt = request.data.get("relieved_at") or timezone.now().date()
        cp.relieved_at = dt
        cp.save(update_fields=["relieved_at"])

        # по политике: опционально понизить роль обратно до OFFICER
        downgrade = str(request.data.get("downgrade_role", "false")).lower() in ("1", "true", "yes")
        if downgrade:
            user.role = User.UserRole.OFFICER
            user.save(update_fields=["role"])

        return Response({"message": "Командир снят", "user_id": user.id, "relieved_at": str(dt)})

    @action(detail=True, methods=["patch"], permission_classes=[IsAuthenticated, IsAdminOrRoot])
    def set_role(self, request, pk=None):
        """
        ADMIN/ROOT: выставить роль пользователю с опциональными побочными действиями.
        payload:
          {
            "role": "OFFICER|HR|COMMANDER|ADMIN|ROOT",
            # если делаем HR:
            "responsible_units": [<unit_id>, ...],   # опционально
            # если делаем COMMANDER:
            "unit": <unit_id>,                       # опционально
            "appointed_at": "YYYY-MM-DD",            # опционально, иначе today
            "force": true|false,                     # для вытеснения активного командира юнита
            # если снимаем командование (меняем с COMMANDER на другую роль):
            "relieved_at": "YYYY-MM-DD"              # опционально, иначе today
          }
        """
        user = get_object_or_404(User, pk=pk)
        new_role = request.data.get("role")
        if new_role not in [r[0] for r in User.UserRole.choices]:
            return Response({"detail": "Некорректная роль"}, status=400)

        # 1) Безопасности: не позволяем снять последнего ROOT'а
        if user.role == User.UserRole.ROOT and new_role != User.UserRole.ROOT:
            # посчитаем остальных рутов
            roots_cnt = User.objects.filter(role=User.UserRole.ROOT, is_active=True).exclude(id=user.id).count()
            if roots_cnt == 0:
                return Response({"detail": "Нельзя понизить последнего активного ROOT пользователя"}, status=403)

        # 2) Если уходим ИЗ COMMANDER в другую роль — аккуратно закрыть активное командование
        if user.role == User.UserRole.COMMANDER and new_role != User.UserRole.COMMANDER:
            cp_active = CommanderProfile.objects.filter(user=user, relieved_at__isnull=True).first()
            if cp_active:
                relieved_at = request.data.get("relieved_at") or timezone.now().date()
                cp_active.relieved_at = relieved_at
                cp_active.save(update_fields=["relieved_at"])

        # 3) Установка роли
        user.role = new_role
        user.save(update_fields=["role"])

        # 4) Обеспечиваем профили
        OfficerProfile.objects.get_or_create(user=user)  # офицерский нужен всем
        if new_role == User.UserRole.HR:
            hrp, _ = HRProfile.objects.get_or_create(user=user)
            # если прислали зоны ответственности — применим
            if "responsible_units" in request.data:
                unit_ids = request.data.get("responsible_units") or []
                # валидация существования ID по желанию
                hrp.responsible_units.set(unit_ids)

        if new_role == User.UserRole.COMMANDER:
            cp, _ = CommanderProfile.objects.get_or_create(user=user)
            unit_id = request.data.get("unit")
            if unit_id:
                unit = get_object_or_404(Unit, id=unit_id)
                appointed_at = request.data.get("appointed_at") or timezone.now().date()
                force = str(request.data.get("force", "false")).lower() in ("1", "true", "yes")

                # проверка единственного активного командира в unit
                active = CommanderProfile.objects.filter(unit=unit, relieved_at__isnull=True).exclude(user=user).first()
                if active and not force:
                    return Response(
                        {"detail": f"В {unit.name} уже есть активный командир (user_id={active.user_id}). "
                                   f"Укажите force=true или снимите действующего."},
                        status=409
                    )
                if active and force:
                    active.relieved_at = appointed_at
                    active.save(update_fields=["relieved_at"])

                cp.unit = unit
                cp.appointed_at = appointed_at
                cp.relieved_at = None
                cp.save(update_fields=["unit", "appointed_at", "relieved_at"])

        # Ничего не удаляем (история важна): CommanderProfile/HRProfile остаются, но «закрыты» по датам/без юнита
        return Response({"message": "Роль обновлена", "user_id": user.id, "role": new_role})

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated])
    def twofa_toggle(self, request):
        """
        Включить/выключить 2FA для текущего пользователя.
        body: {"enabled": true|false}
        Возвращает otpauth URL, если включаем впервые (для QR).
        """
        user = request.user
        enabled = str(request.data.get("enabled", "")).lower() in ("1", "true", "yes")

        otpauth = None
        if enabled:
            # если секрета нет — сгенерим
            if not user.twofa_secret:
                # 20 байт -> base32 для TOTP
                user.twofa_secret = base64.b32encode(os.urandom(20)).decode("utf-8").rstrip("=")
            user.twofa_enabled = True
            # otpauth-ссылка для генерации QR в приложении-аутентификаторе
            issuer = "CareerGrowth"
            label = user.email
            otpauth = f"otpauth://totp/{issuer}:{label}?secret={user.twofa_secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"
        else:
            user.twofa_enabled = False
            # при желании можно чистить секрет:
            # user.twofa_secret = ""

        user.save(update_fields=["twofa_enabled", "twofa_secret"])
        resp = {"twofa_enabled": user.twofa_enabled}
        if otpauth:
            resp["otpauth_url"] = otpauth
        return Response(resp)


# -------- Профили --------
class OfficerProfileViewSet(viewsets.ModelViewSet):
    queryset = OfficerProfile.objects.select_related("user", "rank", "unit", "current_position").all()
    serializer_class = OfficerProfileSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["unit", "rank", "current_position", "marital_status", "combat_participation"]
    search_fields = ["full_name", "iin", "user__email"]
    ordering = ["full_name"]

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user

        if u.role == "OFFICER":
            # Офицер видит только себя
            return qs.filter(user=u)

        if u.role == "COMMANDER":
            try:
                me = CommanderProfile.objects.select_related("unit").get(user=u)
            except CommanderProfile.DoesNotExist:
                return qs.none()

            today = timezone.now().date()

            # 1) Все офицеры его подразделения
            qs_unit = OfficerProfile.objects.filter(unit=me.unit)

            # 2) Оверрайды (активные назначения)
            include_ids = CommanderAssignment.objects.filter(
                commander=me
            ).filter(
                Q(until__isnull=True) | Q(until__gte=today)
            ).values_list("officer_id", flat=True)

            qs_override = OfficerProfile.objects.filter(id__in=include_ids)

            return (qs_unit | qs_override).distinct()

        if u.role == "HR":
            # HR видит офицеров в своих подразделениях
            try:
                hrp = HRProfile.objects.get(user=u)
            except HRProfile.DoesNotExist:
                return qs.none()
            return qs.filter(unit__in=hrp.responsible_units.all())

        # ADMIN/ROOT видят всех
        return qs

    def get_permissions(self):
        # офицер может читать/править только свой профиль
        # командир/HR/admin/root — читать соответственно своим правам
        if self.action in ("update", "partial_update"):
            return [IsAuthenticated(), IsOwnProfile()]
        if self.action in ("retrieve", "me", "me_update", "upload_photo"):
            # доступ офицеру к себе + командиру к подчинённому + staffish
            return [IsAuthenticated()]
        return [IsAuthenticated(), ReadOnlyOrStaffish()]  # ReadOnly из core.permissions если подключишь

    def get_serializer_class(self):
        # OFFICER при update/partial_update редактирует только безопасные поля
        if self.action in ("update", "partial_update", "me_update"):
            u = getattr(self.request, "user", None)
            if u and getattr(u, "role", None) == "OFFICER":
                return OfficerProfileUpdateSerializer
        return super().get_serializer_class()

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        if request.user.role == "OFFICER" and obj.user_id != request.user.id:
            if request.user.role in ("HR", "ADMIN", "ROOT", "COMMANDER"):
                pass
            else:
                return Response({"detail": "Доступ запрещён"}, status=403)
        return Response(self.get_serializer(obj).data)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        try:
            obj = OfficerProfile.objects.get(user=request.user)
        except OfficerProfile.DoesNotExist:
            return Response({"detail": "Профиль офицера не найден"}, status=404)
        return Response(self.get_serializer(obj).data)

    @action(detail=False, methods=["patch"], permission_classes=[IsAuthenticated])
    def me_update(self, request):
        try:
            obj = OfficerProfile.objects.get(user=request.user)
        except OfficerProfile.DoesNotExist:
            return Response({"detail": "Профиль офицера не найден"}, status=404)
        ser = OfficerProfileUpdateSerializer(instance=obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(OfficerProfileSerializer(obj, context={'request': request}).data)

    @action(detail=True, methods=["post"],
            permission_classes=[IsAuthenticated, IsHR | IsAdminOrRoot])
    def set_service_info(self, request, pk=None):
        """
        HR/ADMIN/ROOT выставляют служебные поля офицера:
        payload: { "rank": <id>, "unit": <id>, "current_position": <id>, "service_start_date": "YYYY-MM-DD" }
        """
        obj = self.get_object()
        data = request.data
        changed = []

        was_rank_none = obj.rank_id is None
        was_unit_none = obj.unit_id is None
        was_pos_none = obj.current_position_id is None

        # решаем по входу, будет ли установка значений
        def _nullish(x):
            return x in (None, "", 0, "0")

        will_set_rank = ("rank" in data) and not _nullish(data.get("rank"))
        will_set_unit = ("unit" in data) and not _nullish(data.get("unit"))
        will_set_pos = ("current_position" in data) and not _nullish(data.get("current_position"))
        first_assignment_happened = (was_rank_none and will_set_rank) or \
                                    (was_unit_none and will_set_unit) or \
                                    (was_pos_none and will_set_pos)

        # разберём дату (если пришла)
        explicit_ssd = data.get("service_start_date")
        parsed_ssd = None
        if explicit_ssd not in (None, ""):
            parsed_ssd = parse_date(explicit_ssd)
            if not parsed_ssd:
                return Response({"detail": "service_start_date должен быть в формате YYYY-MM-DD"}, status=400)

        try:
            with transaction.atomic():
                # rank
                if "rank" in data:
                    rid = data.get("rank")
                    obj.rank = None if _nullish(rid) else get_object_or_404(Rank, pk=rid)
                    changed.append("rank")

                # unit
                if "unit" in data:
                    uid = data.get("unit")
                    obj.unit = None if _nullish(uid) else get_object_or_404(Unit, pk=uid)
                    changed.append("unit")

                # current_position
                if "current_position" in data:
                    pid = data.get("current_position")
                    obj.current_position = None if _nullish(pid) else get_object_or_404(Position, pk=pid)
                    changed.append("current_position")

                # service_start_date
                if parsed_ssd:
                    obj.service_start_date = parsed_ssd
                    changed.append("service_start_date")
                elif first_assignment_happened and not obj.service_start_date:
                    obj.service_start_date = timezone.now().date()
                    changed.append("service_start_date")

                if changed:
                    # уберём дубли полей на всякий
                    obj.save(update_fields=list(dict.fromkeys(changed)))
                    obj.refresh_from_db()

        except IntegrityError:
            return Response(
                {"detail": "Неверные идентификаторы (rank/unit/current_position). Проверьте, что записи существуют."},
                status=400
            )

        return Response(OfficerProfileSerializer(obj, context={'request': request}).data)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def upload_photo(self, request):
        profile = OfficerProfile.objects.get(user=request.user)
        file = request.FILES.get('photo')
        if not file:
            return Response({'detail': 'photo is required'}, status=400)
        profile.photo = file
        profile.save(update_fields=['photo'])
        return Response({'photo_url': request.build_absolute_uri(profile.photo.url)})


# ---- Языки ----
class OfficerLanguageViewSet(viewsets.ModelViewSet):
    """
    OFFICER может управлять только своими языками.
    COMMANDER/HR/ADMIN/ROOT — без ограничений (при необходимости можно ужесточить).
    """
    queryset = OfficerLanguage.objects.select_related('officer', 'officer__user')
    serializer_class = OfficerLanguageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ["officer", "language"]
    search_fields = ["language"]
    ordering = ["language"]

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        if getattr(u, 'role', None) == 'OFFICER':
            try:
                me = OfficerProfile.objects.get(user=u)
            except OfficerProfile.DoesNotExist:
                return qs.none()
            return qs.filter(officer=me)
        return qs

    def perform_create(self, serializer):
        u = self.request.user
        if getattr(u, 'role', None) == 'OFFICER':
            officer = OfficerProfile.objects.get(user=u)
            serializer.save(officer=officer)
        else:
            serializer.save()


class CommanderProfileViewSet(viewsets.ModelViewSet):
    queryset = CommanderProfile.objects.select_related("user", "rank", "unit", "current_position").all()
    serializer_class = CommanderProfileSerializer
    permission_classes = [IsAuthenticated, IsCommander | IsAdminOrRoot]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["full_name", "iin", "user__email"]
    ordering = ["full_name"]

    def get_permissions(self):
        if self.action in ("update", "partial_update"):
            return [IsAuthenticated(), (IsOwnProfile | IsAdminOrRoot)()]
        if self.action in ("retrieve",):
            return [IsAuthenticated()]
        if self.action in ("subordinates",):
            # видеть подчинённых может сам командир (и админ/рут)
            return [IsAuthenticated(), (IsCommander | IsAdminOrRoot)()]
        if self.action in ("assign", "unassign"):
            # назначать/снимать оверрайды может HR (и админ/рут)
            return [IsAuthenticated(), (IsHR | IsAdminOrRoot)()]
        return [IsAuthenticated(), ReadOnlyOrStaffish()]

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated, IsCommander | IsAdminOrRoot])
    def me(self, request):
        try:
            obj = CommanderProfile.objects.get(user=request.user)
        except CommanderProfile.DoesNotExist:
            return Response({"detail": "Профиль командира не найден"}, status=404)
        return Response(self.get_serializer(obj, context={'request': request}).data)

    @action(detail=False, methods=["patch"], permission_classes=[IsAuthenticated, IsCommander | IsAdminOrRoot])
    def me_update(self, request):
        try:
            obj = CommanderProfile.objects.get(user=request.user)
        except CommanderProfile.DoesNotExist:
            return Response({"detail": "Профиль командира не найден"}, status=404)
        ser = CommanderProfileUpdateSerializer(instance=obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(CommanderProfileSerializer(obj, context={'request': request}).data)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated, IsCommander | IsAdminOrRoot])
    def subordinates(self, request):
        """Получить список активных подчинённых командира"""
        me = CommanderProfile.objects.filter(user=request.user).select_related("unit").first()
        if not me:
            return Response({"detail": "Профиль командира не найден"}, status=404)

        today = timezone.now().date()

        # 1) По подразделению
        qs_unit = OfficerProfile.objects.filter(unit=me.unit)

        # 2) Позитивные оверрайды (активные назначения)
        include_ids = CommanderAssignment.objects.filter(
            commander=me
        ).filter(
            Q(until__isnull=True) | Q(until__gt=today)
        ).values_list("officer_id", flat=True)

        qs_override = OfficerProfile.objects.filter(id__in=include_ids)

        qs = (qs_unit | qs_override).select_related("user", "rank", "unit", "current_position").distinct().order_by(
            "full_name")

        page = self.paginate_queryset(qs)
        ser = OfficerProfileSerializer(
            page or qs, many=True, context={"request": request}
        )
        return self.get_paginated_response(ser.data) if page else Response(ser.data)

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, (IsHR | IsAdminOrRoot)])
    def assign(self, request):
        """
        HR/ADMIN/ROOT: назначить офицера подчинённым (оверрайд).
        Payload: {"commander_id": <id>, "officer_id": <id>, "since": "YYYY-MM-DD" (optional)}
        """
        commander_id = request.data.get("commander_id")
        officer_id = request.data.get("officer_id")
        since = request.data.get("since") or timezone.now().date()

        if not commander_id or not officer_id:
            return Response({"detail": "commander_id и officer_id обязательны"}, status=400)

        commander = get_object_or_404(CommanderProfile, id=commander_id)
        officer = get_object_or_404(OfficerProfile, id=officer_id)

        # HR ограничиваем его зонами ответственности
        if getattr(request.user, "role", "") == "HR":
            hrp = HRProfile.objects.filter(user=request.user).first()
            if not hrp:
                return Response({"detail": "Профиль HR не найден"}, status=404)
            # HR может работать только если и командир, и офицер относятся к его юнитам
            allowed_units = set(hrp.responsible_units.values_list("id", flat=True))
            if (commander.unit_id not in allowed_units) or (officer.unit_id not in allowed_units):
                return Response({"detail": "Недостаточно прав для выбранных подразделений"}, status=403)

        ca, created = CommanderAssignment.objects.get_or_create(
            commander=commander, officer=officer, since=since
        )
        return Response({"message": "Назначено", "id": ca.id},
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, (IsHR | IsAdminOrRoot)])
    def unassign(self, request):
        """
        HR/ADMIN/ROOT: снять оверрайд.
        Payload: {"commander_id": <id>, "officer_id": <id>, "until": "YYYY-MM-DD" (optional)}
        """
        commander_id = request.data.get("commander_id")
        officer_id = request.data.get("officer_id")
        if not commander_id or not officer_id:
            return Response({"detail": "commander_id и officer_id обязательны"}, status=400)

        commander = get_object_or_404(CommanderProfile, id=commander_id)
        # HR-проверка зоны ответственности — аналогично assign()
        if getattr(request.user, "role", "") == "HR":
            hrp = HRProfile.objects.filter(user=request.user).first()
            if not hrp:
                return Response({"detail": "Профиль HR не найден"}, status=404)
            allowed_units = set(hrp.responsible_units.values_list("id", flat=True))
            if commander.unit_id not in allowed_units:
                return Response({"detail": "Недостаточно прав для данного подразделения"}, status=403)

        ca = CommanderAssignment.objects.filter(
            commander=commander, officer_id=officer_id
        ).filter(Q(until__isnull=True) | Q(until__gte=timezone.now().date())
                 ).order_by("-since").first()

        if not ca:
            return Response({"detail": "Активное назначение не найдено"}, status=404)

        ca.until = request.data.get("until") or timezone.now().date()
        ca.save(update_fields=["until"])
        return Response({"message": "Снято"})

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsHR | IsAdminOrRoot],
            parser_classes=[JSONParser, FormParser, MultiPartParser])
    def set_service_info(self, request, pk=None):
        """
        HR/ADMIN/ROOT: установить служебные поля командира (звание, подразделение, должность, даты).
        payload: { "rank": <id>, "unit": <id>, "current_position": <id>,
                   "service_start_date": "YYYY-MM-DD",
                   "appointed_at": "YYYY-MM-DD", "relieved_at": "YYYY-MM-DD" }
        """
        obj = self.get_object()
        data = request.data
        from django.utils.dateparse import parse_date
        changed = []

        def _nullish(x):
            return x in (None, "", 0, "0")

        # справочники
        if "rank" in data:
            rid = data.get("rank")
            obj.rank = None if _nullish(rid) else get_object_or_404(Rank, pk=rid);
            changed.append("rank")
        if "unit" in data:
            uid = data.get("unit")
            obj.unit = None if _nullish(uid) else get_object_or_404(Unit, pk=uid);
            changed.append("unit")
        if "current_position" in data:
            pid = data.get("current_position")
            obj.current_position = None if _nullish(pid) else get_object_or_404(Position, pk=pid);
            changed.append("current_position")

        # даты
        for field in ("service_start_date", "appointed_at", "relieved_at"):
            if field in data and data.get(field) not in (None, ""):
                dt = parse_date(data.get(field))
                if not dt: return Response({"detail": f"{field} должен быть в формате YYYY-MM-DD"}, status=400)
                setattr(obj, field, dt);
                changed.append(field)

        if changed:
            obj.save(update_fields=list(dict.fromkeys(changed)))

        return Response(CommanderProfileSerializer(obj, context={'request': request}).data)


class CommanderLanguageViewSet(viewsets.ModelViewSet):
    queryset = CommanderLanguage.objects.select_related('commander', 'commander__user')
    serializer_class = CommanderLanguageSerializer
    permission_classes = [IsAuthenticated, IsCommander | IsAdminOrRoot]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ["commander", "language"]
    search_fields = ["language"]
    ordering = ["language"]

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        # Командир — видит и правит только свои языки
        if getattr(u, 'role', None) == 'COMMANDER':
            try:
                me = CommanderProfile.objects.get(user=u)
            except CommanderProfile.DoesNotExist:
                return qs.none()
            return qs.filter(commander=me)
        return qs

    def perform_create(self, serializer):
        u = self.request.user
        if getattr(u, 'role', None) == 'COMMANDER':
            commander = CommanderProfile.objects.get(user=u)
            serializer.save(commander=commander)
        else:
            serializer.save()


class HRProfileViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HRProfile.objects.select_related("user").prefetch_related("responsible_units").all()
    serializer_class = HRProfileSerializer
    permission_classes = [IsAuthenticated, IsHR | IsAdminOrRoot]

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated, IsHR | IsAdminOrRoot])
    def officers(self, request):
        hrp = HRProfile.objects.filter(user=request.user).first()
        if not hrp:
            # если это админ/рут — показываем всех офицеров
            if IsAdminOrRoot().has_permission(request, self):
                qs = OfficerProfile.objects.select_related("user", "rank", "unit", "current_position").order_by("full_name")
                page = self.paginate_queryset(qs)
                ser = OfficerProfileSerializer(page or qs, many=True, context={"request": request})
                return self.get_paginated_response(ser.data) if page else Response(ser.data)
            return Response({"detail": "Профиль HR не найден"}, status=404)

        qs = OfficerProfile.objects.select_related(
            "user", "rank", "unit", "current_position"
        ).filter(
            unit__in=hrp.responsible_units.all()
        ).order_by("full_name")

        page = self.paginate_queryset(qs)
        ser = OfficerProfileSerializer(
            page or qs, many=True, context={"request": request}
        )
        return self.get_paginated_response(ser.data) if page else Response(ser.data)

    @action(detail=True, methods=["patch"], permission_classes=[IsAuthenticated, IsAdminOrRoot])
    def set_units(self, request, pk=None):
        """ADMIN/ROOT: задать список подразделений, за которые отвечает HR."""
        obj = self.get_object()
        unit_ids = request.data.get("responsible_units", [])

        # 1. Проверка, что входные данные — это список
        if not isinstance(unit_ids, list):
            return Response(
                {"responsible_units": "Список ID подразделений должен быть передан в виде списка."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Проверка существования всех ID
        input_set = set(unit_ids)

        # Получаем ID, которые реально существуют в базе
        existing_unit_ids = Unit.objects.filter(pk__in=input_set).values_list('id', flat=True)
        existing_set = set(existing_unit_ids)

        # Находим ID, которые были переданы, но не найдены в базе
        non_existent_ids = list(input_set - existing_set)

        # 3. Возвращаем 400 ошибку, если есть несуществующие ID
        if non_existent_ids:
            # Сортируем для более удобного чтения ошибки
            non_existent_ids.sort()
            return Response(
                {
                    "responsible_units": (
                        f"Подразделения с ID: {non_existent_ids} не существуют. "
                        f"Не удалось обновить список ответственных подразделений."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # 4. Если все ID существуют, выполняем атомарную операцию
        try:
            with transaction.atomic():
                # Метод set принимает список существующих ID.
                # Мы передаем ему те ID, которые прошли нашу проверку.
                obj.responsible_units.set(unit_ids)

                # Обновление и возврат данных
            obj.refresh_from_db()
            return Response(HRProfileSerializer(obj).data)

        except Exception as e:
            # Эта ветка на всякий случай, если ошибка возникнет на другом уровне
            # (хотя после проверки ID это маловероятно)
            return Response(
                {"detail": f"Произошла ошибка при сохранении: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CommanderAssignmentViewSet(viewsets.ModelViewSet):
    queryset = CommanderAssignment.objects.select_related("commander__user",
                                                          "officer__user").all()
    serializer_class = CommanderAssignmentSerializer
    permission_classes = [IsAuthenticated, IsAdminOrRoot]