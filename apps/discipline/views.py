from django.utils import timezone
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.users.models import OfficerProfile, CommanderProfile, HRProfile, CommanderAssignment
from core.permissions import IsAdminOrRoot, IsHR, IsCommander
from .models import Reward, Sanction, MeasureStatus
from .serializers import RewardSerializer, SanctionSerializer


def _filter_queryset_by_role(request, qs):
    u = request.user
    if u.role == "OFFICER":
        try:
            me = OfficerProfile.objects.get(user=u)
        except OfficerProfile.DoesNotExist:
            return qs.none()
        return qs.filter(officer=me)
    if u.role == "COMMANDER":
        try:
            me = CommanderProfile.objects.get(user=u)
        except CommanderProfile.DoesNotExist:
            return qs.none()
        active_ids = CommanderAssignment.objects.filter(
            commander=me
        ).filter(Q(until__isnull=True) | Q(until__gte=timezone.now().date())
                 ).values_list("officer_id", flat=True)
        return qs.filter(Q(officer_id__in=active_ids) | Q(unit=me.unit))
    if u.role == "HR":
        try:
            hr = HRProfile.objects.get(user=u)
        except HRProfile.DoesNotExist:
            return qs.none()
        return qs.filter(Q(unit__in=hr.responsible_units.all()) | Q(officer__unit__in=hr.responsible_units.all()))
    return qs  # ADMIN/ROOT


class _BaseMeasureViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "description", "order_number", "officer__full_name", "officer__user__email"]
    filterset_fields = [
        "status", "officer", "unit", "order_date",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = super().get_queryset().select_related("officer", "officer__user", "unit", "initiator", "approved_by")
        return _filter_queryset_by_role(self.request, qs)

    def perform_create(self, serializer):
        serializer.save(initiator=self.request.user)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        obj = self.get_object()
        if obj.status != MeasureStatus.DRAFT:
            return Response({"detail": "Можно отправить только из статуса DRAFT"}, status=400)
        obj.status = MeasureStatus.SUBMITTED
        obj.save(update_fields=["status"])
        return Response({"message": "Отправлено на утверждение"})

    @action(detail=True, methods=["post"],
            permission_classes=[permissions.IsAuthenticated, IsCommander | IsAdminOrRoot | IsHR])
    def approve(self, request, pk=None):
        obj = self.get_object()
        if obj.status != MeasureStatus.SUBMITTED:
            return Response({"detail": "Можно утвердить только из SUBMITTED"}, status=400)
        obj.status = MeasureStatus.APPROVED
        obj.approved_by = request.user
        obj.approved_at = timezone.now()
        obj.approval_comment = request.data.get("comment", "")
        obj.save(update_fields=["status", "approved_by", "approved_at", "approval_comment"])
        return Response({"message": "Утверждено"})

    @action(detail=True, methods=["post"],
            permission_classes=[permissions.IsAuthenticated, IsCommander | IsAdminOrRoot | IsHR])
    def reject(self, request, pk=None):
        obj = self.get_object()
        if obj.status not in [MeasureStatus.SUBMITTED, MeasureStatus.APPROVED]:
            return Response({"detail": "Можно отклонить из SUBMITTED/APPROVED"}, status=400)
        obj.status = MeasureStatus.REJECTED
        obj.approval_comment = request.data.get("comment", "")
        obj.approved_by = request.user
        obj.approved_at = timezone.now()
        obj.save(update_fields=["status", "approved_by", "approved_at", "approval_comment"])
        return Response({"message": "Отклонено"})

    @action(detail=True, methods=["post"],
            permission_classes=[permissions.IsAuthenticated, IsHR | IsAdminOrRoot | IsCommander])
    def execute(self, request, pk=None):
        """Фиксация приказа: order_number, order_date"""
        obj = self.get_object()
        if obj.status != MeasureStatus.APPROVED:
            return Response({"detail": "Исполнить можно только из APPROVED"}, status=400)
        obj.order_number = request.data.get("order_number", "")
        obj.order_date = request.data.get("order_date", timezone.now().date())
        obj.status = MeasureStatus.EXECUTED
        obj.save(update_fields=["order_number", "order_date", "status"])
        return Response({"message": "Исполнено (приказ оформлен)"})

    @action(detail=True, methods=["post"],
            permission_classes=[permissions.IsAuthenticated, IsAdminOrRoot | IsCommander])
    def revoke(self, request, pk=None):
        obj = self.get_object()
        if obj.status not in [MeasureStatus.APPROVED, MeasureStatus.EXECUTED]:
            return Response({"detail": "Отменить можно из APPROVED/EXECUTED"}, status=400)
        obj.status = MeasureStatus.REVOKED
        obj.save(update_fields=["status"])
        return Response({"message": "Отменено"})


class RewardViewSet(_BaseMeasureViewSet):
    queryset = Reward.objects.all()
    serializer_class = RewardSerializer

    @action(detail=True, methods=["post"],
            permission_classes=[permissions.IsAuthenticated, IsCommander | IsAdminOrRoot])
    def lift_sanction(self, request, pk=None):
        """Спец-действие: если reward_type=LIFT_SANCTION и есть linked_sanction — снять её."""
        reward = self.get_object()
        if reward.reward_type != 'LIFT_SANCTION' or not reward.linked_sanction_id:
            return Response({"detail": "Поощрение не является снятием взыскания"}, status=400)
        s = reward.linked_sanction
        if s.lifted_at:
            return Response({"detail": "Взыскание уже снято"}, status=400)
        s.lifted_at = timezone.now().date()
        s.save(update_fields=["lifted_at"])
        return Response({"message": "Взыскание снято"})


class SanctionViewSet(_BaseMeasureViewSet):
    queryset = Sanction.objects.all()
    serializer_class = SanctionSerializer
