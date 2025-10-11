from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import (
    OfficerProfile, CommanderProfile, HRProfile, CommanderAssignment
)

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Регистрация нового пользователя (роль назначит админ; по умолчанию OFFICER)"""
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "password", "password_confirm"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Пароли должны совпадать"})
        try:
            validate_password(attrs["password"])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            role=getattr(User.UserRole, "OFFICER", "OFFICER")
        )


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "role", "email_verified", "is_blocked", "is_active", "twofa_enabled", "date_joined",
                  "last_login"]
        read_only_fields = fields


class OfficerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    rank_name = serializers.CharField(source="rank.name", read_only=True)
    unit_name = serializers.CharField(source="unit.name", read_only=True)
    position_title = serializers.CharField(source="current_position.title", read_only=True)

    class Meta:
        model = OfficerProfile
        fields = [
            "id", "user", "full_name", "birth_date", "phone",
            "rank", "rank_name", "unit", "unit_name",
            "current_position", "position_title", "service_start_date"
        ]


class OfficerProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfficerProfile
        fields = [
            "full_name", "birth_date", "phone"
        ]


class CommanderProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    unit_name = serializers.CharField(source="unit.name", read_only=True)

    class Meta:
        model = CommanderProfile
        fields = ["id", "user", "unit", "unit_name"]


class HRProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    responsible_units_names = serializers.SerializerMethodField()

    class Meta:
        model = HRProfile
        fields = ["id", "user", "responsible_units", "responsible_units_names"]

    def get_responsible_units_names(self, obj):
        return list(obj.responsible_units.values_list("name", flat=True))


class CommanderAssignmentSerializer(serializers.ModelSerializer):
    commander_name = serializers.SerializerMethodField()
    officer_name = serializers.SerializerMethodField()

    class Meta:
        model = CommanderAssignment
        fields = ["id", "commander", "commander_name", "officer", "officer_name", "since", "until"]

    def get_commander_name(self, obj): return obj.commander.user.email

    def get_officer_name(self, obj):   return obj.officer.full_name or obj.officer.user.email


# Пароли / восстановление
class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError("Пароли должны совпадать")
        try:
            validate_password(attrs["new_password"])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Неверный текущий пароль")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError("Новые пароли должны совпадать")
        try:
            validate_password(attrs["new_password"])
        except DjangoValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})
        return attrs
