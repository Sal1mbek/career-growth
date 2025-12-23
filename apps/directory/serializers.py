from rest_framework import serializers
from .models import (
    Rank, Unit, Position, PositionRequirement, Competency, CompetencyRequirement, Provider, TrainingCourse, PositionQualification
)


class RankSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rank
        fields = ["id", "name", "order", "is_active"]


class UnitSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source="parent.name", read_only=True)

    class Meta:
        model = Unit
        fields = ["id", "name", "code", "parent", "parent_name", "level", "is_active"]


class PositionSerializer(serializers.ModelSerializer):
    unit_name = serializers.CharField(source="unit.name", read_only=True)

    class Meta:
        model = Position
        fields = ["id", "title", "code", "unit", "unit_name", "description", "is_active"]


class PositionRequirementSerializer(serializers.ModelSerializer):
    position_title = serializers.CharField(source="position.title", read_only=True)
    min_rank_name = serializers.CharField(source="min_rank.name", read_only=True)

    class Meta:
        model = PositionRequirement
        fields = ["id", "position", "position_title", "min_rank", "min_rank_name", "min_service_years", "required_education"]


class CompetencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Competency
        fields = ["id", "code", "name", "group", "description", "is_active"]


class CompetencyRequirementSerializer(serializers.ModelSerializer):
    position_title = serializers.CharField(source="position.title", read_only=True)
    competency_name = serializers.CharField(source="competency.name", read_only=True)

    class Meta:
        model = CompetencyRequirement
        fields = ["id", "position", "position_title", "competency", "competency_name", "min_score", "is_mandatory"]


class ProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provider
        fields = ["id", "name", "accreditations", "is_active"]


class TrainingCourseSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.name", read_only=True)
    related_competencies_ids = serializers.PrimaryKeyRelatedField(many=True, source="related_competencies", read_only=True)

    class Meta:
        model = TrainingCourse
        fields = ["id", "title", "code", "provider", "provider_name", "hours", "tags", "related_competencies_ids", "is_active"]


class PositionQualificationSerializer(serializers.ModelSerializer):
    position_title = serializers.CharField(source="position.title", read_only=True)

    class Meta:
        model = PositionQualification
        fields = [
            "id",
            "position",
            "position_title",
            "category",
            "text",
            "order",
            "source",
        ]
