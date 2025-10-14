from rest_framework import serializers
from apps.users.serializers import UserSerializer, OfficerProfileSerializer
from .models import Reward, Sanction


class BaseMeasureSerializer(serializers.ModelSerializer):
    initiator = UserSerializer(read_only=True)
    officer_data = OfficerProfileSerializer(source='officer', read_only=True)

    class Meta:
        fields = [
            "id", "target_type", "officer", "officer_data", "unit", "is_collective",
            "title", "description", "status",
            "initiator", "approved_by", "approved_at", "approval_comment",
            "order_number", "order_date",
            "effective_from", "effective_to",
            "created_at", "updated_at"
        ]
        read_only_fields = ("status", "initiator", "approved_by", "approved_at", "created_at", "updated_at")

    def validate(self, attrs):
        target_type = attrs.get("target_type") or getattr(self.instance, "target_type", None)
        officer = attrs.get("officer", getattr(self.instance, "officer", None))
        unit = attrs.get("unit", getattr(self.instance, "unit", None))

        if target_type == "OFFICER" and not officer:
            raise serializers.ValidationError({"officer": "Для типа OFFICER офицер обязателен"})
        if target_type == "UNIT" and not unit:
            raise serializers.ValidationError({"unit": "Для типа UNIT подразделение обязательно"})
        return attrs


class RewardSerializer(BaseMeasureSerializer):
    class Meta(BaseMeasureSerializer.Meta):
        model = Reward
        fields = BaseMeasureSerializer.Meta.fields + ["reward_type", "linked_sanction"]


class SanctionSerializer(BaseMeasureSerializer):
    class Meta(BaseMeasureSerializer.Meta):
        model = Sanction
        fields = BaseMeasureSerializer.Meta.fields + ["sanction_type", "lifted_at"]
