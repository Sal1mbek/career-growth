import json
from django.contrib import admin
from .models import Notification, SupportTicket, TicketMessage
from core.json_payloads import NOTIFICATION_TEMPLATES

from django import forms
from django_json_widget.widgets import JSONEditorWidget


# ----- FORMS -----

class NotificationForm(forms.ModelForm):
    class Meta:
        model = Notification
        fields = "__all__"
        widgets = {
            "payload": JSONEditorWidget(options={"mode": "tree", "modes": ["tree", "code"]}),
        }

    class Media:
        js = ("admin/payload_templates.js",)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    form = NotificationForm
    list_display = ("id", "user", "notification_type", "created_at", "read_at")
    list_filter = ("notification_type", "created_at")
    search_fields = ("user__email",)
    autocomplete_fields = ("user",)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial["payload"] = NOTIFICATION_TEMPLATES.get("SYSTEM", {})
        return initial

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        field = context["adminform"].form.fields["payload"].widget
        field.attrs["data-notification-templates"] = json.dumps(NOTIFICATION_TEMPLATES, ensure_ascii=False)
        return super().render_change_form(request, context, add, change, form_url, obj)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "subject", "status", "priority", "created_at")
    list_filter = ("status", "priority", "created_at")
    search_fields = ("author__email", "subject")
    autocomplete_fields = ("author",)


@admin.register(TicketMessage)
class TicketMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "ticket", "author", "created_at")
    list_filter = ("created_at",)
    search_fields = ("ticket__subject", "author__email")
    autocomplete_fields = ("ticket", "author")
