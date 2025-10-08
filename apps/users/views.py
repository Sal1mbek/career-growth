from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from core.permissions import (
    IsAdminOrRoot, IsOwnUser, IsOwnProfile, IsCommander, CanViewSubordinates, IsOfficer, IsStaffish, IsHR,
    ReadOnlyOrStaffish
)
from .models import OfficerProfile, CommanderProfile, HRProfile, CommanderAssignment
from .serializers import (
    UserRegistrationSerializer, UserSerializer,
    OfficerProfileSerializer, OfficerProfileUpdateSerializer,
    CommanderProfileSerializer, HRProfileSerializer,
    CommanderAssignmentSerializer, PasswordResetSerializer, PasswordResetConfirmSerializer,
    PasswordChangeSerializer
)
from .utils import send_verification_email

User = get_user_model()


# -------- Аутентификация / регистрация --------
class AuthViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

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

    def get_permissions(self):
        # офицер может читать/править только свой профиль
        # командир/HR/admin/root — читать соответственно своим правам
        if self.action in ("update", "partial_update"):
            return [IsAuthenticated(), IsOwnProfile()]
        if self.action in ("retrieve",):
            # доступ офицеру к себе + командиру к подчинённому + staffish
            return [IsAuthenticated()]
        return [IsAuthenticated(), ReadOnlyOrStaffish()]  # ReadOnly из core.permissions если подключишь

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        # собственный профиль всегда ок
        if request.user.role == "OFFICER" and obj.user_id != request.user.id:
            # если командир — проверяем подчинённость
            from core.permissions import CanViewSubordinates
            if request.user.role == "COMMANDER" and CanViewSubordinates().has_object_permission(request, self, obj):
                pass
            elif request.user.role in ("HR", "ADMIN", "ROOT"):
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
        return Response(OfficerProfileSerializer(obj).data)


class CommanderProfileViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CommanderProfile.objects.select_related("user", "unit").all()
    serializer_class = CommanderProfileSerializer
    permission_classes = [IsAuthenticated, IsCommander | IsAdminOrRoot]


class HRProfileViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HRProfile.objects.select_related("user").prefetch_related("responsible_units").all()
    serializer_class = HRProfileSerializer
    permission_classes = [IsAuthenticated, IsHR | IsAdminOrRoot]


class CommanderAssignmentViewSet(viewsets.ModelViewSet):
    queryset = CommanderAssignment.objects.select_related("commander__user",
                                                          "officer__user").all()
    serializer_class = CommanderAssignmentSerializer
    permission_classes = [IsAuthenticated, IsAdminOrRoot]
