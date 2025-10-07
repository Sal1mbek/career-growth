from django.contrib import admin
from django.utils.html import format_html, mark_safe
from django.utils.safestring import mark_safe
from django.urls import reverse

from .models import AuditLog


def _pretty_json(data):
    import json
    try:
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        return str(data)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    # Список
    list_display = (
        "id",
        "created_at",
        "action",
        "actor_link",
        "object_type",
        "object_id",
        "short_diff",
        "ip",
    )
    list_filter = ("action", "object_type", "created_at")
    search_fields = ("actor__email", "object_type", "user_agent", "ip")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 50

    # Деталка
    readonly_fields = (
        "created_at",
        "action",
        "actor",
        "object_type",
        "object_id",
        "ip",
        "user_agent",
        "diff_pretty",
    )
    fieldsets = (
        (None, {
            "fields": ("created_at", "action", "actor")
        }),
        ("Объект", {
            "fields": ("object_type", "object_id")
        }),
        ("Клиент", {
            "fields": ("ip", "user_agent")
        }),
        ("Изменения (diff_json)", {
            "fields": ("diff_pretty",)
        }),
    )

    # ----- helpers -----
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # read-only
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def actor_link(self, obj: AuditLog):
        if obj.actor_id:
            url = reverse("admin:users_customuser_change", args=[obj.actor_id])
            email = getattr(obj.actor, "email", obj.actor_id)
            return format_html('<a href="{}">{}</a>', url, email)
        return "—"

    actor_link.short_description = "Пользователь"

    def short_diff(self, obj: AuditLog):
        text = _pretty_json(obj.diff_json) if obj.diff_json else ""
        if not text:
            return "—"
        # обрежем длинное
        if len(text) > 140:
            text = text[:140] + "…"
        return text

    short_diff.short_description = "Diff"

    def diff_pretty(self, obj: AuditLog):
        if not obj.diff_json:
            return "—"
        return mark_safe(f"<pre style='white-space:pre-wrap;margin:0'>{_pretty_json(obj.diff_json)}</pre>")

    diff_pretty.short_description = "diff_json (pretty)"
