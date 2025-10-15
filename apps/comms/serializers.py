from rest_framework import serializers
from .models import Notification, SupportTicket, TicketMessage
from core.json_payloads import NOTIFICATION_TEMPLATES, NOTIFICATION_SCHEMA
from core.validators import validate_json_payload


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "user", "notification_type", "payload", "read_at", "created_at"]
        read_only_fields = ["id", "user", "created_at", "read_at"]

    def validate_payload(self, value):
        # 1) Общая схема
        validate_json_payload(NOTIFICATION_SCHEMA, value, path="payload")
        # 2) Тип-специфическая проверка
        t = self.initial_data.get("notification_type") or getattr(self.instance, "notification_type", None)
        if t in ("ASSESSMENT", "TRAINING", "CAREER", "VACANCY"):
            data = (value or {}).get("data") or {}
            required_ids = {
                "ASSESSMENT": ["assessment_id"],
                "TRAINING": ["course_id"],
                "CAREER": ["trajectory_id"],
                "VACANCY": ["vacancy_id"],
            }[t]
            missing = [k for k in required_ids if k not in data]
            if missing:
                raise serializers.ValidationError({"payload": f"data.{', '.join(missing)} обязательны для {t}"})
        return value


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
