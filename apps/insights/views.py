from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import IsAdminOrRoot, IsCommanderOrHR
from core.responses import APIResponse
from .models import TrajectoryForecast
from .serializers import TrajectoryForecastSerializer
from .services import forecast_officer_to_position, MODEL_VERSION
from apps.users.models import OfficerProfile
from apps.directory.models import Position


def _visible_officers(user):
    # такие же правила видимости, как в других аппах
    role = getattr(user, "role", None)
    qs = OfficerProfile.objects.select_related("user")
    if role == "OFFICER":
        return qs.filter(user=user)
    if role == "COMMANDER":
        from apps.users.models import CommanderAssignment
        ids = CommanderAssignment.objects.filter(commander__user=user, until__isnull=True) \
            .values_list("officer_id", flat=True)
        return qs.filter(id__in=list(ids))
    return qs  # HR/ADMIN/ROOT


class TrajectoryForecastViewSet(viewsets.ModelViewSet):
    """
    Read: OFFICER видит свои; командир — подчинённых; HR/ADMIN/ROOT — всё.
    Create/generate: только HR/ADMIN/ROOT/COMMANDER.
    """
    serializer_class = TrajectoryForecastSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ["officer", "target_position", "model_version"]
    ordering = ["-created_at"]
    search_fields = ["officer__user__email", "target_position__title", "model_version"]

    def get_queryset(self):
        officers = _visible_officers(self.request.user)
        return TrajectoryForecast.objects.select_related("officer", "officer__user", "target_position") \
            .filter(officer__in=officers)

    def create(self, request, *args, **kwargs):
        # ограничим создание прогнозов только staffish (командир/HR/ADMIN/ROOT)
        if request.user.role not in ("COMMANDER", "HR", "ADMIN", "ROOT"):
            return APIResponse.forbidden("Только персонал может создавать прогнозы")
        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        """
        Генерация прогноза по офицеру и целевой позиции.
        body: {"officer": <id>, "target_position": <id>}
        - OFFICER: запрещено генерировать (только чтение)
        - COMMANDER/HR/ADMIN/ROOT: можно
        """
        if request.user.role not in ("COMMANDER", "HR", "ADMIN", "ROOT"):
            return APIResponse.forbidden("Недостаточно прав для генерации")

        officer_id = request.data.get("officer")
        pos_id = request.data.get("target_position")
        if not officer_id or not pos_id:
            return APIResponse.validation_error(
                {"officer": ["обязательное поле"], "target_position": ["обязательное поле"]})

        try:
            officer = OfficerProfile.objects.get(id=officer_id)
        except OfficerProfile.DoesNotExist:
            return APIResponse.not_found("Офицер не найден")

        try:
            position = Position.objects.get(id=pos_id)
        except Position.DoesNotExist:
            return APIResponse.not_found("Позиция не найдена")

        # Командир может генерить только для своих подчинённых
        if request.user.role == "COMMANDER":
            from apps.users.models import CommanderAssignment
            if not CommanderAssignment.objects.filter(commander__user=request.user, officer=officer,
                                                      until__isnull=True).exists():
                return APIResponse.forbidden("Можно генерировать только для подчинённых")

        prob, horizon = forecast_officer_to_position(officer, position)
        obj = TrajectoryForecast.objects.create(
            officer=officer,
            target_position=position,
            probability=prob,
            horizon_months=horizon,
            model_version=MODEL_VERSION
        )
        return APIResponse.created(TrajectoryForecastSerializer(obj).data, "Прогноз создан")
