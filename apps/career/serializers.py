from rest_framework import serializers
from .models import CareerTrajectory, PlanStep, Recommendation


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
