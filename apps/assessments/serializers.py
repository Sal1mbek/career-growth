from rest_framework import serializers
from apps.assessments.models import (
    Assessment, AssessmentItem, CompetencyRating, Rater, Feedback360
)


class AssessmentItemSerializer(serializers.ModelSerializer):
    competency_name = serializers.CharField(source="competency.name", read_only=True)

    class Meta:
        model = AssessmentItem
        fields = ["id", "competency", "competency_name", "score", "comment"]


class AssessmentSerializer(serializers.ModelSerializer):
    officer_email = serializers.CharField(source="officer.user.email", read_only=True)
    created_by_email = serializers.CharField(source="created_by.email", read_only=True)
    items = AssessmentItemSerializer(many=True, required=False)

    class Meta:
        model = Assessment
        fields = [
            "id", "officer", "officer_email", "cycle", "assessment_type",
            "created_by", "created_by_email", "created_at", "items"
        ]
        read_only_fields = ["created_by", "created_at"]

    def create(self, validated_data):
        items = validated_data.pop("items", [])
        assessment = Assessment.objects.create(**validated_data)
        for it in items:
            AssessmentItem.objects.create(assessment=assessment, **it)
        return assessment

    def update(self, instance, validated_data):
        items = validated_data.pop("items", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        if items is not None:
            instance.items.all().delete()
            for it in items:
                AssessmentItem.objects.create(assessment=instance, **it)
        return instance


class RaterSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = Rater
        fields = ["id", "user", "user_email", "relation"]


class Feedback360Serializer(serializers.ModelSerializer):
    rater_email = serializers.CharField(source="rater.user.email", read_only=True)

    class Meta:
        model = Feedback360
        fields = ["id", "assessment", "rater", "rater_email", "payload", "is_anonymous", "created_at"]
        read_only_fields = ["created_at"]


class CompetencyRatingSerializer(serializers.ModelSerializer):
    competency_name = serializers.CharField(source="competency.name", read_only=True)
    officer_email = serializers.CharField(source="officer.user.email", read_only=True)

    class Meta:
        model = CompetencyRating
        fields = ["id", "officer", "officer_email", "competency", "competency_name", "score", "source", "assessed_at"]
        read_only_fields = ["assessed_at"]
