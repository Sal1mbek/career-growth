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
            # Командир видит только своих подчинённых (активные назначения)
            try:
                me = CommanderProfile.objects.get(user=u)
            except CommanderProfile.DoesNotExist:
                return qs.none()
            active_ids = CommanderAssignment.objects.filter(
                commander=me
            ).filter(
                Q(until__isnull=True) | Q(until__gte=timezone.now().date())
            ).values_list("officer_id", flat=True)
            return qs.filter(id__in=active_ids)

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
        if self.action in ("subordinates", "assign", "unassign"):
            return [IsAuthenticated(), (IsCommander | IsAdminOrRoot)()]
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
        me = CommanderProfile.objects.filter(user=request.user).first()
        if not me:
            return Response({"detail": "Профиль командира не найден"}, status=404)

        active_ids = CommanderAssignment.objects.filter(
            commander=me
        ).filter(
            Q(until__isnull=True) | Q(until__gte=timezone.now().date())
        ).values_list("officer_id", flat=True)

        qs = OfficerProfile.objects.filter(id__in=active_ids).select_related(
            "user", "rank", "unit", "current_position"
        ).order_by("full_name")

        page = self.paginate_queryset(qs)
        ser = OfficerProfileSerializer(
            page or qs, many=True, context={"request": request}
        )
        return self.get_paginated_response(ser.data) if page else Response(ser.data)

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, IsCommander | IsAdminOrRoot])
    def assign(self, request):
        """Назначить офицера подчинённым
        Payload: {"officer_id": <id>, "since": "2025-10-01"}
        """
        me = CommanderProfile.objects.filter(user=request.user).first()
        if not me:
            return Response({"detail": "Профиль командира не найден"}, status=404)

        officer_id = request.data.get("officer_id")
        since = request.data.get("since") or timezone.now().date()

        if not officer_id:
            return Response({"detail": "officer_id обязателен"}, status=400)

        try:
            officer = OfficerProfile.objects.get(id=officer_id)
        except OfficerProfile.DoesNotExist:
            return Response({"detail": "Офицер не найден"}, status=404)

        ca, created = CommanderAssignment.objects.get_or_create(
            commander=me, officer=officer, since=since
        )
        return Response(
            {"message": "Назначено", "id": ca.id},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated, IsCommander | IsAdminOrRoot])
    def unassign(self, request):
        """Снять офицера (установить until)
        Payload: {"officer_id": <id>, "until": "2025-12-01"}
        """
        me = CommanderProfile.objects.filter(user=request.user).first()
        if not me:
            return Response({"detail": "Профиль командира не найден"}, status=404)

        officer_id = request.data.get("officer_id")
        if not officer_id:
            return Response({"detail": "officer_id обязателен"}, status=400)

        ca = CommanderAssignment.objects.filter(
            commander=me, officer_id=officer_id
        ).filter(
            Q(until__isnull=True) | Q(until__gte=timezone.now().date())
        ).order_by("-since").first()

        if not ca:
            return Response({"detail": "Активное назначение не найдено"}, status=404)

        ca.until = request.data.get("until") or timezone.now().date()
        ca.save(update_fields=["until"])
        return Response({"message": "Снято"})


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


class CommanderAssignmentViewSet(viewsets.ModelViewSet):
    queryset = CommanderAssignment.objects.select_related("commander__user",
                                                          "officer__user").all()
    serializer_class = CommanderAssignmentSerializer
    permission_classes = [IsAuthenticated, IsAdminOrRoot]