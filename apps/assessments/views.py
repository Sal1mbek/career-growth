from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import IsAdminOrRoot
from apps.users.models import OfficerProfile, CustomUser, CommanderAssignment
from apps.assessments.models import (
    Assessment, AssessmentItem, CompetencyRating, Rater, Feedback360
)
from .serializers import (
    AssessmentSerializer, AssessmentItemSerializer, CompetencyRatingSerializer,
    RaterSerializer, Feedback360Serializer
)
from .services import aggregate_assessment_to_ratings


def visible_officers_for(user: CustomUser):
    role = getattr(user, "role", None)
    base = OfficerProfile.objects.select_related("user")
    if role == "OFFICER":
        return base.filter(user=user)
    if role == "COMMANDER":
        subs = CommanderAssignment.objects.filter(
            commander__user=user, until__isnull=True
        ).values_list("officer_id", flat=True)
        return base.filter(id__in=list(subs))
    # HR/ADMIN/ROOT
    return base


# ---------- Assessments ----------
class AssessmentViewSet(viewsets.ModelViewSet):
    serializer_class = AssessmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["officer", "assessment_type", "cycle"]
    search_fields = ["cycle", "officer__user__email"]
    ordering = ["-created_at"]

    def get_queryset(self):
        officers = visible_officers_for(self.request.user)
        return Assessment.objects.select_related("officer", "officer__user", "created_by").filter(officer__in=officers)

    def perform_create(self, serializer):
        """
        Создавать оценки могут:
        - HR/ADMIN/ROOT — для любого офицера
        - Командир — только для своих подчинённых
        - OFFICER — не может (видит свои, но не создаёт)
        """
        user = self.request.user
        role = getattr(user, "role", None)
        officer = serializer.validated_data["officer"]

        if role == "OFFICER":
            raise PermissionError("Офицер не может создавать аттестацию")
        if role == "COMMANDER":
            if not CommanderAssignment.objects.filter(commander__user=user, officer=officer,
                                                      until__isnull=True).exists():
                raise PermissionError("Командир может аттестовать только подчинённых")

        serializer.save(created_by=user)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def add_items(self, request, pk=None):
        """
        Добавить/заменить набор оценок по компетенциям (удаляет старые items).
        Командир/HR/ADMIN/ROOT.
        body: { items: [{competency, score, comment?}, ...] }
        """
        assessment = self.get_object()
        user = request.user
        if user.role == "OFFICER":
            return Response({"detail": "Forbidden"}, status=403)

        items = request.data.get("items", [])
        if not isinstance(items, list):
            return Response({"detail": "items must be a list"}, status=400)

        assessment.items.all().delete()
        for it in items:
            ser = AssessmentItemSerializer(data=it)
            ser.is_valid(raise_exception=True)
            ser.save(assessment=assessment)

        return Response(AssessmentSerializer(assessment).data, status=200)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def add_feedback360(self, request, pk=None):
        """
        Добавить запись 360 (оценивает любой Rater из boundary: командир/коллега/подчинённый).
        body: {"rater": <id>, "payload": {"<competency_id>": score, ...}, "is_anonymous": false}
        OFFICER может передать 360 для себя, но только от зарегистрированного Rater.
        """
        assessment = self.get_object()
        ser = Feedback360Serializer(data={
            "assessment": assessment.id,
            "rater": request.data.get("rater"),
            "payload": request.data.get("payload"),
            "is_anonymous": request.data.get("is_anonymous", False)
        })
        ser.is_valid(raise_exception=True)

        # валидация принадлежности: rater должен существовать
        rater = Rater.objects.get(id=ser.validated_data["rater"].id)
        # офицер не может подставлять чужих ратеров без логики — принимаем как есть,
        # но можно усилить проверку по подразделению при необходимости.

        obj = ser.save()
        return Response(Feedback360Serializer(obj).data, status=201)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def aggregate(self, request, pk=None):
        """
        Агрегирует оценки в CompetencyRating (пересоздаёт новые записи для данного офицера).
        """
        assessment = self.get_object()
        created = aggregate_assessment_to_ratings(assessment)
        return Response(CompetencyRatingSerializer(created, many=True).data, status=201)


# ---------- Raters ----------
class RaterViewSet(viewsets.ModelViewSet):
    queryset = Rater.objects.select_related("user").all()
    serializer_class = RaterSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["user__email", "relation"]
    ordering = ["id"]

    def get_permissions(self):
        # создавать/редактировать — только staff/admin/root; читать — всем аутентифицированным
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsAdminOrRoot()]
        return super().get_permissions()


# ---------- Ratings (read-only) ----------
class CompetencyRatingViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CompetencyRatingSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["officer", "competency", "source"]
    search_fields = ["officer__user__email", "competency__name"]
    ordering = ["-assessed_at"]

    def get_queryset(self):
        officers = visible_officers_for(self.request.user)
        return CompetencyRating.objects.select_related("officer", "officer__user", "competency").filter(
            officer__in=officers)
