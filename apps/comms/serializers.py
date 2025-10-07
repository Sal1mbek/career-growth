from rest_framework import serializers
from .models import Notification, SupportTicket, TicketMessage


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "user", "notification_type", "payload", "read_at", "created_at"]
        read_only_fields = ["id", "user", "created_at", "read_at"]


class SupportTicketSerializer(serializers.ModelSerializer):
    author_email = serializers.CharField(source="author.email", read_only=True)

    class Meta:
        model = SupportTicket
        fields = ["id", "author", "author_email", "subject", "body",
                  "status", "priority", "created_at"]
        read_only_fields = ["id", "author", "created_at"]


class TicketMessageSerializer(serializers.ModelSerializer):
    author_email = serializers.CharField(source="author.email", read_only=True)

    class Meta:
        model = TicketMessage
        fields = ["id", "ticket", "author", "author_email", "body", "created_at"]
        read_only_fields = ["id", "author", "created_at"]
