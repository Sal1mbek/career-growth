from django.contrib import admin
from .models import Notification, SupportTicket, TicketMessage


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "notification_type", "created_at", "read_at")
    list_filter = ("notification_type", "created_at")
    search_fields = ("user__email",)
    autocomplete_fields = ("user",)


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
