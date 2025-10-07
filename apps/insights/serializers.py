from rest_framework import serializers
from .models import TrajectoryForecast


class TrajectoryForecastSerializer(serializers.ModelSerializer):
    officer_email = serializers.CharField(source="officer.user.email", read_only=True)
    target_position_title = serializers.CharField(source="target_position.title", read_only=True)

    class Meta:
        model = TrajectoryForecast
        fields = [
            "id", "officer", "officer_email",
            "target_position", "target_position_title",
            "probability", "horizon_months", "model_version", "created_at"
        ]
        read_only_fields = ["id", "created_at", "model_version"]
