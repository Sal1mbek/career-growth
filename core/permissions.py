from typing import Iterable
from django.contrib.auth import get_user_model
from rest_framework import permissions

User = get_user_model()


# ---- базовые роли ----
class HasAnyRole(permissions.BasePermission):
    """Пользователь аутентифицирован и его роль входит в допустимые"""
    allowed: Iterable[str] = ()

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role in self.allowed)
        )


# Готовые классы под роли
class IsOfficer(HasAnyRole):
    allowed = ("OFFICER",)


class IsCommander(HasAnyRole):
    allowed = ("COMMANDER",)


class IsHR(HasAnyRole):
    allowed = ("HR",)


class IsAdmin(HasAnyRole):
    allowed = ("ADMIN",)


class IsRoot(HasAnyRole):
    allowed = ("ROOT",)


class IsAdminOrRoot(HasAnyRole):
    allowed = ("ADMIN", "ROOT")


class IsCommanderOrHR(HasAnyRole):
    allowed = ("COMMANDER", "HR")


class IsStaffish(HasAnyRole):
    allowed = ("COMMANDER", "HR", "ADMIN", "ROOT")


# ---- объектные права ----
class IsOwnUser(permissions.BasePermission):
    """Сам о себе (для объектов CustomUser)"""

    def has_object_permission(self, request, view, obj) -> bool:
        return request.user.is_authenticated and getattr(obj, "pk", None) == request.user.pk


class IsOwnProfile(permissions.BasePermission):
    """Объект имеет .user и он равен request.user"""

    def has_object_permission(self, request, view, obj) -> bool:
        return request.user.is_authenticated and hasattr(obj, "user") and obj.user_id == request.user.id


class CanViewSubordinates(permissions.BasePermission):
    """Командир может видеть только своих подчинённых (OfficerProfile/obj)"""

    def has_object_permission(self, request, view, obj) -> bool:
        if not (request.user.is_authenticated and request.user.role == "COMMANDER"):
            return False
        # lazy import чтобы избежать циклов
        from apps.users.models import CommanderAssignment, CommanderProfile, OfficerProfile
        if isinstance(obj, OfficerProfile):
            return CommanderAssignment.objects.filter(
                commander__user=request.user, officer=obj, until__isnull=True
            ).exists()
        # если на уровне списка/детали просто офицер id
        return False


class ReadOnly(permissions.BasePermission):
    def has_permission(self, request, view) -> bool:
        return request.method in permissions.SAFE_METHODS


class ReadOnlyOrStaffish(permissions.BasePermission):
    """SAFE методы всем аутентифицированным; изменять могут командиры/HR/ADMIN/ROOT"""
    staff_roles = {"COMMANDER", "HR", "ADMIN", "ROOT"}

    def has_permission(self, request, view) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        return request.user.is_authenticated and getattr(request.user, "role", None) in self.staff_roles