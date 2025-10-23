from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from datetime import date
from django.utils.dateparse import parse_date

from .models import (
    OfficerProfile, CommanderProfile, HRProfile, CommanderAssignment, OfficerLanguage, CommanderLanguage
)

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Регистрация нового пользователя (роль назначит админ; по умолчанию OFFICER)"""
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    # ---- Доп. поля профиля офицера (опционально при регистрации) ----
    full_name = serializers.CharField(required=False, allow_blank=True)
    birth_date = serializers.DateField(required=False, allow_null=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    iin = serializers.CharField(required=False, allow_blank=True, max_length=12)
    birth_place = serializers.CharField(required=False, allow_blank=True)
    nationality = serializers.CharField(required=False, allow_blank=True)
    marital_status = serializers.CharField(required=False, allow_blank=True)
    combat_participation = serializers.BooleanField(required=False, default=False)
    combat_notes = serializers.CharField(required=False, allow_blank=True)
    photo = serializers.ImageField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = User
        fields = [
            "email", "password", "password_confirm",
            "full_name", "birth_date", "phone", "iin", "birth_place", "nationality",
            "marital_status", "combat_participation", "combat_notes", "photo"
        ]

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
        photo = validated_data.pop("photo", None)
        profile_fields = {k: validated_data.pop(k, None) for k in [
            "full_name", "birth_date", "phone", "iin", "birth_place",
            "nationality", "marital_status", "combat_participation", "combat_notes",
        ]}
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            role=getattr(User.UserRole, "OFFICER", "OFFICER")
        )
        # профиль создаётся сигналом; тут — мягкое обновление
        from .models import OfficerProfile
        prof, _ = OfficerProfile.objects.get_or_create(user=user)
        for k, v in profile_fields.items():
            if v not in (None, "", []):
                setattr(prof, k, v)
        if photo:
            prof.photo = photo
        prof.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "role", "email_verified", "is_blocked", "is_active", "twofa_enabled", "date_joined",
                  "last_login"]
        read_only_fields = fields


class OfficerLanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfficerLanguage
        fields = ['id', 'language', 'level']


class OfficerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    rank_name = serializers.CharField(source="rank.name", read_only=True)
    unit_name = serializers.CharField(source="unit.name", read_only=True)
    position_title = serializers.CharField(source="current_position.title", read_only=True)

    languages = OfficerLanguageSerializer(many=True, read_only=True)
    photo_url = serializers.SerializerMethodField()

    age = serializers.SerializerMethodField()
    service_years = serializers.SerializerMethodField()

    class Meta:
        model = OfficerProfile
        fields = [
            "id", "user", "full_name", "birth_date", "phone",
            "photo", "photo_url", "iin", "birth_place", "nationality",
            "marital_status", "combat_participation", "combat_notes",
            "rank", "rank_name", "unit", "unit_name",
            "current_position", "position_title", "service_start_date",
            # NEW:
            "rank_assignment_info",
            "personal_number", "children_count", "awards", "penalties",
            "education_civil", "education_military",
            "service_history",
            "languages", "age", "service_years",
        ]
        extra_kwargs = {"photo": {"write_only": True, "required": False}}

    def get_photo_url(self, obj):
        if obj.photo:
            request = self.context.get("request")
            return request.build_absolute_uri(obj.photo.url) if request else obj.photo.url
        return None

    def get_age(self, obj):
        if not obj.birth_date:
            return None
        today = date.today()
        return today.year - obj.birth_date.year - (
                (today.month, today.day) < (obj.birth_date.month, obj.birth_date.day)
        )

    def get_service_years(self, obj):
        ssd = obj.service_start_date
        if not ssd:
            return None
        # если по какой-то причине пришла строка — аккуратно распарсим
        if isinstance(ssd, str):
            ssd = parse_date(ssd)
        if not ssd:
            return None
        today = date.today()
        return today.year - ssd.year - ((today.month, today.day) < (ssd.month, ssd.day))

    def get_fields(self):
        fields = super().get_fields()
        req = self.context.get("request")
        if req and getattr(req.user, "role", None) == "OFFICER":
            for f in ("rank", "unit", "current_position"):
                if f in fields:
                    fields[f].read_only = True
        return fields


class OfficerProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfficerProfile
        fields = [
            "full_name", "birth_date", "phone",
            "photo", "iin", "birth_place", "nationality",
            "marital_status", "combat_participation", "combat_notes",
            "service_start_date",
            "rank_assignment_info",
            "personal_number", "children_count", "awards", "penalties",
            "education_civil", "education_military",
            "service_history",
        ]


class CommanderLanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommanderLanguage
        fields = ['id', 'language', 'level']


class CommanderProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    rank_name = serializers.CharField(source="rank.name", read_only=True)
    unit_name = serializers.CharField(source="unit.name", read_only=True)
    position_title = serializers.CharField(source="current_position.title", read_only=True)
    languages = CommanderLanguageSerializer(many=True, read_only=True)
    photo_url = serializers.SerializerMethodField()
    age = serializers.SerializerMethodField()
    service_years = serializers.SerializerMethodField()

    class Meta:
        model = CommanderProfile
        fields = [
            "id", "user", "full_name", "birth_date", "phone",
            "photo", "photo_url", "iin", "birth_place", "nationality",
            "marital_status", "combat_participation", "combat_notes",
            "rank", "rank_name", "unit", "unit_name",
            "current_position", "position_title", "service_start_date",
            # Уникальные поля командира
            "command_title", "command_scope", "appointed_at", "relieved_at",
            "staff_position", "subordinates_expected",
            "languages", "age", "service_years",
        ]
        extra_kwargs = {"photo": {"write_only": True, "required": False}}

    def get_photo_url(self, obj):
        if obj.photo:
            request = self.context.get("request")
            return request.build_absolute_uri(obj.photo.url) if request else obj.photo.url
        return None

    def get_age(self, obj):
        if not obj.birth_date:
            return None
        today = date.today()
        return today.year - obj.birth_date.year - (
                (today.month, today.day) < (obj.birth_date.month, obj.birth_date.day)
        )

    def get_service_years(self, obj):
        if not obj.service_start_date:
            return None
        today = date.today()
        return today.year - obj.service_start_date.year - (
                (today.month, today.day) < (obj.service_start_date.month, obj.service_start_date.day)
        )


class CommanderProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommanderProfile
        fields = [
            "full_name", "birth_date", "phone",
            "photo", "iin", "birth_place", "nationality",
            "marital_status", "combat_participation", "combat_notes",
            "service_start_date",
            "command_title", "command_scope", "appointed_at", "relieved_at",
            "staff_position", "subordinates_expected",
        ]


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
