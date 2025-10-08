from rest_framework import serializers
from .models import Vacancy, CandidateMatch, Assignment


class VacancySerializer(serializers.ModelSerializer):
    position_title = serializers.CharField(source="position.title", read_only=True)
    unit_name = serializers.CharField(source="unit.name", read_only=True)

    class Meta:
        model = Vacancy
        fields = ["id", "position", "position_title", "unit", "unit_name",
                  "open_from", "open_to", "status"]


class CandidateMatchSerializer(serializers.ModelSerializer):
    officer_name = serializers.SerializerMethodField()
    rank_name = serializers.CharField(source="officer.rank.name", read_only=True)

    class Meta:
        model = CandidateMatch
        fields = ["id", "vacancy", "officer", "officer_name", "rank_name",
                  "match_score", "gaps", "created_at"]
        read_only_fields = ["match_score", "gaps", "created_at"]

    def get_officer_name(self, obj):
        return obj.officer.full_name or obj.officer.user.email


class AssignmentSerializer(serializers.ModelSerializer):
    vacancy_title = serializers.CharField(source="vacancy.position.title", read_only=True)
    officer_name = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = ["id", "vacancy", "vacancy_title", "officer", "officer_name",
                  "state", "decision_chain", "decided_at"]
        read_only_fields = ["state", "decision_chain", "decided_at"]

    def get_officer_name(self, obj):
        return obj.officer.full_name or obj.officer.user.email
