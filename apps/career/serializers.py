from rest_framework import serializers
from .models import CareerTrajectory, PlanStep, Recommendation
from core.json_payloads import RECOMMENDATION_SCHEMA
from core.validators import validate_json_payload


class PlanStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanStep
        fields = '__all__'
        read_only_fields = ['id', 'completed_at']


class CareerTrajectorySerializer(serializers.ModelSerializer):
    steps = PlanStepSerializer(many=True, read_only=True)
    target_position_title = serializers.CharField(source='target_position.title', read_only=True)

    class Meta:
        model = CareerTrajectory
        fields = ['id', 'officer', 'target_position', 'target_position_title',
                  'horizon_months', 'status', 'steps', 'created_at']
        read_only_fields = ['id', 'created_at']


class RecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recommendation
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

    def validate_payload(self, value):
        validate_json_payload(RECOMMENDATION_SCHEMA, value)
        kind = self.initial_data.get("kind") or getattr(self.instance, "kind", None)
        if kind == "TRAINING":
            for k in ["training_id", "training_title"]:
                if k not in (value or {}):
                    raise serializers.ValidationError(f"{k} обязателен для TRAINING")
        elif kind == "COMPETENCY_GAP":
            for k in ["competency", "target_score", "current_score"]:
                if k not in (value or {}):
                    raise serializers.ValidationError(f"{k} обязателен для COMPETENCY_GAP")
        elif kind == "POSITION":
            for k in ["target_position"]:
                if k not in (value or {}):
                    raise serializers.ValidationError(f"{k} обязателен для POSITION")
        return value
