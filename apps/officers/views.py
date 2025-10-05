from django.http import FileResponse, Http404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import IsOwnProfile, CanViewSubordinates, IsAdminOrRoot
from apps.users.models import OfficerProfile
from .models import PositionHistory, OfficerDocument, CourseEnrollment, Certificate
from .serializers import (
    PositionHistorySerializer, OfficerDocumentSerializer,
    CourseEnrollmentSerializer, CertificateSerializer
)
from .services import add_position_history


def officer_queryset_for_user(user):
    """
    Ограничение видимости офицеров:
    - OFFICER: только свой профиль
    - COMMANDER: только подчинённые (по CommanderAssignment, действующие)
    - HR/ADMIN/ROOT: все
    """
    qs = OfficerProfile.objects.select_related("user", "rank", "unit", "current_position")
    role = getattr(user, "role", None)
    if role == "OFFICER":
        return qs.filter(user=user)
    if role == "COMMANDER":
        from apps.users.models import CommanderAssignment
        sub_ids = CommanderAssignment.objects.filter(
            commander__user=user, until__isnull=True
        ).values_list("officer_id", flat=True)
        return qs.filter(id__in=sub_ids)
    # HR/ADMIN/ROOT
    return qs


# -------- PositionHistory --------
class PositionHistoryViewSet(viewsets.ModelViewSet):
    serializer_class = PositionHistorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["officer", "position"]
    ordering_fields = ["start_date", "end_date"]
    ordering = ["-start_date"]

    def get_queryset(self):
        visible_officers = officer_queryset_for_user(self.request.user)
        return PositionHistory.objects.select_related("position", "officer", "officer__user").filter(
            officer__in=visible_officers
        )

    def perform_create(self, serializer):
        # офицер может создавать запись только себе; остальные — кому угодно
        user = self.request.user
        officer = serializer.validated_data.get("officer")
        if getattr(user, "role", None) == "OFFICER":
            try:
                me = OfficerProfile.objects.get(user=user)
            except OfficerProfile.DoesNotExist:
                raise Http404("Officer profile not found")
            officer = me
        serializer.save(officer=officer)

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated])
    def set_current(self, request):
        """
        Удобный эндпоинт: установить текущую должность (автозакрытие прошлой).
        body: { "officer": <id>|optional, "position": <id>, "start_date": "YYYY-MM-DD", "result": "" }
        OFFICER — только себе (officer игнорируется).
        """
        data = request.data
        role = getattr(request.user, "role", None)

        if role == "OFFICER":
            try:
                officer = OfficerProfile.objects.get(user=request.user)
            except OfficerProfile.DoesNotExist:
                return Response({"detail": "Officer profile not found"}, status=404)
        else:
            try:
                officer = OfficerProfile.objects.get(id=data.get("officer"))
            except OfficerProfile.DoesNotExist:
                return Response({"detail": "Officer not found"}, status=404)

        from apps.directory.models import Position
        try:
            position = Position.objects.get(id=data.get("position"))
        except Position.DoesNotExist:
            return Response({"detail": "Position not found"}, status=404)

        ph = add_position_history(
            officer=officer, position=position,
            start_date=data.get("start_date"),
            result=data.get("result", "")
        )
        return Response(PositionHistorySerializer(ph).data, status=201)


# -------- OfficerDocument --------
class OfficerDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = OfficerDocumentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["officer", "document_type"]
    search_fields = ["title"]
    ordering = ["-issued_at"]

    def get_queryset(self):
        visible_officers = officer_queryset_for_user(self.request.user)
        return OfficerDocument.objects.select_related("officer", "officer__user").filter(
            officer__in=visible_officers
        )

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, "role", None) == "OFFICER":
            officer = OfficerProfile.objects.get(user=user)
            serializer.save(officer=officer)
        else:
            serializer.save()

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def download(self, request, pk=None):
        doc = self.get_object()
        # офицер может скачивать только свои файлы
        if request.user.role == "OFFICER" and doc.officer.user_id != request.user.id:
            return Response({"detail": "Forbidden"}, status=403)
        if not doc.file:
            raise Http404
        return FileResponse(open(doc.file.path, "rb"), as_attachment=True, filename=doc.file.name.rsplit("/", 1)[-1])


# -------- Enrollments --------
class CourseEnrollmentViewSet(viewsets.ModelViewSet):
    serializer_class = CourseEnrollmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["officer", "course", "status"]
    ordering = ["-enrolled_at"]

    def get_queryset(self):
        visible_officers = officer_queryset_for_user(self.request.user)
        return CourseEnrollment.objects.select_related("officer", "officer__user", "course").filter(
            officer__in=visible_officers
        )

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == "OFFICER":
            officer = OfficerProfile.objects.get(user=user)
            serializer.save(officer=officer)
        else:
            serializer.save()

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def complete(self, request, pk=None):
        """
        Пометить обучение завершённым (и опционально создать сертификат)
        body: { "issue_certificate": true }
        """
        obj = self.get_object()
        if request.user.role == "OFFICER" and obj.officer.user_id != request.user.id:
            return Response({"detail": "Forbidden"}, status=403)
        obj.status = "COMPLETED"
        obj.completed_at = obj.completed_at or obj.enrolled_at
        obj.save(update_fields=["status", "completed_at"])

        if request.data.get("issue_certificate"):
            Certificate.objects.get_or_create(
                officer=obj.officer, course=obj.course,
                defaults={"issued_at": obj.completed_at}
            )
        return Response(CourseEnrollmentSerializer(obj).data)


# -------- Certificates --------
class CertificateViewSet(viewsets.ModelViewSet):
    serializer_class = CertificateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["officer", "course"]
    ordering = ["-issued_at"]

    def get_queryset(self):
        visible_officers = officer_queryset_for_user(self.request.user)
        return Certificate.objects.select_related("officer", "officer__user", "course").filter(
            officer__in=visible_officers
        )

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == "OFFICER":
            officer = OfficerProfile.objects.get(user=user)
            serializer.save(officer=officer)
        else:
            serializer.save()
