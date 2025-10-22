from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS

from core.permissions import IsAdminOrRoot, ReadOnlyOrStaffish, IsHR
from .models import (
    Rank, Unit, Position, PositionRequirement,
    Competency, CompetencyRequirement, Provider, TrainingCourse
)
from .serializers import (
    RankSerializer, UnitSerializer, PositionSerializer, PositionRequirementSerializer,
    CompetencySerializer, CompetencyRequirementSerializer, ProviderSerializer, TrainingCourseSerializer
)
from apps.users.models import CommanderProfile


class BaseCatalogViewSet(viewsets.ModelViewSet):
    """Базовый каталог: чтение для всех аутентифицированных, запись — только ADMIN/ROOT"""
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = "__all__"
    ordering = ["id"]

    def get_permissions(self):
        # read-only всем
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        # запись: HR или ADMIN/ROOT
        return [IsAuthenticated(), (IsHR | IsAdminOrRoot)()]


class RankViewSet(BaseCatalogViewSet):
    queryset = Rank.objects.all()
    serializer_class = RankSerializer
    filterset_fields = ["is_active"]
    search_fields = ["name"]


class UnitViewSet(BaseCatalogViewSet):
    queryset = Unit.objects.select_related("parent").all()
    serializer_class = UnitSerializer
    filterset_fields = ["is_active", "parent"]
    search_fields = ["name", "code"]

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        # Командир видит только свой юнит
        if getattr(u, "role", "") == "COMMANDER":
            me = CommanderProfile.objects.filter(user=u).select_related("unit").first()
            return qs.filter(id=me.unit_id) if me and me.unit_id else qs.none()
        return qs


class PositionViewSet(BaseCatalogViewSet):
    queryset = Position.objects.select_related("unit").all()
    serializer_class = PositionSerializer
    filterset_fields = ["is_active", "unit"]
    search_fields = ["title", "code", "unit__name"]


class PositionRequirementViewSet(BaseCatalogViewSet):
    queryset = PositionRequirement.objects.select_related("position", "min_rank").all()
    serializer_class = PositionRequirementSerializer
    filterset_fields = ["position", "min_rank"]
    search_fields = ["position__title", "required_education"]

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        # Командир видит должности только своего юнита
        if getattr(u, "role", "") == "COMMANDER":
            me = CommanderProfile.objects.filter(user=u).select_related("unit").first()
            return qs.filter(unit_id=me.unit_id) if me and me.unit_id else qs.none()
        return qs


class CompetencyViewSet(BaseCatalogViewSet):
    queryset = Competency.objects.all()
    serializer_class = CompetencySerializer
    filterset_fields = ["is_active", "group"]
    search_fields = ["code", "name", "group"]


class CompetencyRequirementViewSet(BaseCatalogViewSet):
    queryset = CompetencyRequirement.objects.select_related("position", "competency").all()
    serializer_class = CompetencyRequirementSerializer
    filterset_fields = ["position", "competency", "is_mandatory", "min_score"]
    search_fields = ["position__title", "competency__name"]


class ProviderViewSet(BaseCatalogViewSet):
    queryset = Provider.objects.all()
    serializer_class = ProviderSerializer
    filterset_fields = ["is_active"]
    search_fields = ["name", "accreditations"]


class TrainingCourseViewSet(BaseCatalogViewSet):
    queryset = TrainingCourse.objects.select_related("provider").prefetch_related("related_competencies").all()
    serializer_class = TrainingCourseSerializer
    filterset_fields = ["is_active", "provider", "hours"]
    search_fields = ["title", "code", "provider__name", "tags"]
