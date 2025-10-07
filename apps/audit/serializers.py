from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source="actor.email", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id", "actor", "actor_email", "action", "object_type", "object_id",
            "diff_json", "ip", "user_agent", "created_at"
        ]
        read_only_fields = fields
