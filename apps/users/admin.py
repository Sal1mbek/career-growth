from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django import forms
from django.contrib.admin.sites import NotRegistered
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import CustomUser, OfficerProfile, CommanderProfile, HRProfile, CommanderAssignment, OfficerLanguage, \
    CommanderLanguage


@admin.register(CustomUser)
class UserAdmin(DjangoUserAdmin):
    model = CustomUser
    list_display = ("id", "email", "role", "is_active", "email_verified", "is_blocked", "twofa_enabled", "last_login")
    list_filter = ("role", "is_active", "email_verified", "is_blocked")
    ordering = ("id",)
    search_fields = ("email",)
    fieldsets = (
        (None, {"fields": ("email", "password", "role")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Security", {"fields": ("email_verified", "is_blocked", "twofa_enabled", "twofa_secret",
                                 "failed_login_attempts", "last_failed_login", "password_changed_at")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",),
                "fields": ("email", "password1", "password2", "role", "is_staff", "is_superuser")}),
    )
    # username отсутствует
    readonly_fields = ("last_login", "date_joined", "password_changed_at", "last_failed_login", "failed_login_attempts")


User = get_user_model()


class OfficerProfileAdminForm(forms.ModelForm):
    class Meta:
        model = OfficerProfile
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # пользователи с ролью OFFICER без созданного officerprofile
        qs = User.objects.filter(role=getattr(User.UserRole, "OFFICER", "OFFICER"))
        qs = qs.filter(officerprofile__isnull=True)
        self.fields["user"].queryset = qs

    def clean_user(self):
        u = self.cleaned_data["user"]
        if getattr(u, "role", None) != getattr(User.UserRole, "OFFICER", "OFFICER"):
            raise ValidationError("У выбранного пользователя роль должна быть OFFICER.")
        if OfficerProfile.objects.filter(user=u).exists():
            raise ValidationError("Для этого пользователя профиль офицера уже существует.")
        return u


class CommanderProfileAdminForm(forms.ModelForm):
    class Meta:
        model = CommanderProfile
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # пользователи с ролью COMMANDER без созданного commanderprofile
        qs = User.objects.filter(role=getattr(User.UserRole, "COMMANDER", "COMMANDER"))
        qs = qs.filter(commanderprofile__isnull=True)
        self.fields["user"].queryset = qs

    def clean_user(self):
        u = self.cleaned_data["user"]
        if getattr(u, "role", None) != getattr(User.UserRole, "COMMANDER", "COMMANDER"):
            raise ValidationError("У выбранного пользователя роль должна быть COMMANDER.")
        if CommanderProfile.objects.filter(user=u).exists():
            raise ValidationError("Для этого пользователя профиль командира уже существует.")
        return u


class OfficerLanguageInline(admin.TabularInline):
    model = OfficerLanguage
    extra = 1
    fields = ('language', 'level')


@admin.register(OfficerProfile)
class OfficerProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "full_name", "iin", "personal_number", "rank", "rank_assignment_info", "unit",
                    "current_position", "service_start_date", "children_count", "combat_participation")
    search_fields = ("user__email", "full_name", "iin", "personal_number")
    list_filter = ("rank", "unit", "current_position", "marital_status", "combat_participation")
    inlines = [OfficerLanguageInline]
    fieldsets = (
        ("Пользователь", {"fields": ("user",)}),
        ("Основная информация", {
            "fields": ("full_name", "birth_date", "phone", "iin", "personal_number")
        }),
        ("Личные данные", {
            "fields": ("birth_place", "nationality", "children_count", "marital_status")
        }),
        ("Служба", {
            "fields": ("rank", "rank_assignment_info", "unit", "current_position", "service_start_date",
                       "service_history")
        }),
        ("Образование", {
            "fields": ("education_civil", "education_military")
        }),
        ("Награды / Взыскания", {
            "fields": ("awards", "penalties")
        }),
        ("Боевая подготовка", {
            "fields": ("combat_participation", "combat_notes")
        }),
        ("Фото", {
            "fields": ("photo",)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        # при добавлении (obj is None) — user редактируемый; при изменении — только для чтения
        return ('user',) if obj else ()


class CommanderLanguageInline(admin.TabularInline):
    model = CommanderLanguage
    extra = 1
    fields = ('language', 'level')


@admin.register(CommanderProfile)
class CommanderProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "full_name", "iin", "rank", "unit", "current_position",
        "service_start_date", "command_title", "command_scope",
        "appointed_at", "relieved_at", "staff_position", "subordinates_expected"
    )
    search_fields = ("user__email", "full_name", "iin")
    list_filter = ("rank", "unit", "current_position", "marital_status", "combat_participation", "command_scope", "staff_position")
    inlines = [CommanderLanguageInline]
    fieldsets = (
        ("Пользователь", {"fields": ("user",)}),
        ("Основная информация", {
            "fields": ("full_name", "birth_date", "phone", "iin")
        }),
        ("Личные данные", {
            "fields": ("birth_place", "nationality", "marital_status")
        }),
        ("Служба", {
            "fields": ("rank", "unit", "current_position", "service_start_date")
        }),
        ("Боевая подготовка", {
            "fields": ("combat_participation", "combat_notes")
        }),
        ("Командование (уникально для Командира)", {
            "fields": ("command_title", "command_scope", "appointed_at", "relieved_at", "staff_position", "subordinates_expected")
        }),
        ("Фото", {
            "fields": ("photo",)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        return ('user',) if obj else ()

    # Хочешь автоматически проставлять роль командиру при сохранении — раскомментируй:
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.user and getattr(obj.user, "role", None) != getattr(User.UserRole, "COMMANDER", "COMMANDER"):
            obj.user.role = getattr(User.UserRole, "COMMANDER", "COMMANDER")
            obj.user.save(update_fields=["role"])


@admin.register(HRProfile)
class HRProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user",)
    filter_horizontal = ("responsible_units",)


@admin.register(CommanderAssignment)
class CommanderAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "commander", "officer", "since", "until")
    search_fields = ("commander__user__email", "officer__user__email")
    list_filter = ("since", "until")
    readonly_fields = ("since",)
    fieldsets = (
        (None, {"fields": ("commander", "officer", "since")}),
        ("Период", {"fields": ("until",)}),
    )
