from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import CustomUser, OfficerProfile, CommanderProfile, HRProfile, CommanderAssignment

@admin.register(CustomUser)
class UserAdmin(DjangoUserAdmin):
    model = CustomUser
    list_display = ("id","email","role","is_active","email_verified","is_blocked","twofa_enabled","last_login")
    list_filter  = ("role","is_active","email_verified","is_blocked")
    ordering     = ("id",)
    search_fields= ("email",)
    fieldsets = (
        (None, {"fields": ("email","password","role")}),
        ("Permissions", {"fields": ("is_active","is_staff","is_superuser","groups","user_permissions")}),
        ("Security", {"fields": ("email_verified","is_blocked","twofa_enabled","twofa_secret",
                                 "failed_login_attempts","last_failed_login","password_changed_at")}),
        ("Important dates", {"fields": ("last_login","date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",),
                "fields": ("email","password1","password2","role","is_staff","is_superuser")}),
    )
    # username отсутствует
    readonly_fields = ("last_login","date_joined","password_changed_at","last_failed_login","failed_login_attempts")

@admin.register(OfficerProfile)
class OfficerProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "full_name", "rank", "unit","current_position","service_start_date")
    search_fields= ("user__email","full_name")
    list_filter  = ("rank","unit","current_position")

@admin.register(CommanderProfile)
class CommanderProfileAdmin(admin.ModelAdmin):
    list_display = ("id","user","unit")
    search_fields= ("user__email",)

@admin.register(HRProfile)
class HRProfileAdmin(admin.ModelAdmin):
    list_display = ("id","user",)
    filter_horizontal = ("responsible_units",)

@admin.register(CommanderAssignment)
class CommanderAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id","commander","officer","since","until")
    search_fields= ("commander__user__email","officer__user__email")
    list_filter  = ("since","until")
