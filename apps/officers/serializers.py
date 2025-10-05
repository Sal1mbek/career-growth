from rest_framework import serializers
from apps.officers.models import PositionHistory, OfficerDocument, CourseEnrollment, Certificate


class PositionHistorySerializer(serializers.ModelSerializer):
    position_title = serializers.CharField(source="position.title", read_only=True)

    class Meta:
        model = PositionHistory
        fields = ["id", "officer", "position", "position_title", "start_date", "end_date", "result"]
        read_only_fields = ["officer"]


class OfficerDocumentSerializer(serializers.ModelSerializer):
    filename = serializers.SerializerMethodField()

    class Meta:
        model = OfficerDocument
        fields = ["id", "officer", "document_type", "title", "file", "filename", "meta", "issued_at"]
        read_only_fields = ["officer"]

    def get_filename(self, obj):  # удобно в UI
        return obj.file.name.rsplit("/", 1)[-1] if obj.file else None


class CourseEnrollmentSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)

    class Meta:
        model = CourseEnrollment
        fields = ["id", "officer", "course", "course_title", "status", "enrolled_at", "completed_at"]
        read_only_fields = ["officer", "enrolled_at", "completed_at"]


class CertificateSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)

    class Meta:
        model = Certificate
        fields = ["id", "officer", "course", "course_title", "file", "issued_at", "expires_at"]
        read_only_fields = ["officer"]
