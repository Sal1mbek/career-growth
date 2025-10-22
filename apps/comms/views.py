from django.utils import timezone
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse, OpenApiTypes
from core.schemas import PayloadTemplatesResponseSerializer
from core.json_payloads import NOTIFICATION_TEMPLATES, NOTIFICATION_SCHEMA

from core.responses import APIResponse
from core.permissions import IsAdminOrRoot, IsCommanderOrHR
from apps.users.models import CommanderProfile, OfficerProfile, CommanderAssignment
from .models import Notification, SupportTicket, TicketMessage
from .serializers import (
    NotificationSerializer, SupportTicketSerializer, TicketMessageSerializer
)


def is_staffish(user):
    return getattr(user, "role", None) in ("HR", "ADMIN", "ROOT")

def _commander_visible_user_ids(user) -> set[int]:
    """
    Возвращает множество user.id: сам командир + все офицеры его состава.
    Состав = офицеры с тем же unit, что и у командира, плюс активные оверрайды CommanderAssignment.
    """
    if getattr(user, "role", None) != "COMMANDER":
        return set()
    me = CommanderProfile.objects.filter(user=user).select_related("unit").first()
    if not me or not me.unit_id:
        return {user.id}
    today = timezone.now().date()
    # 1) офицеры его подразделения
    qs_unit = OfficerProfile.objects.filter(unit_id=me.unit_id).values_list("user_id", flat=True)
    # 2) активные оверрайды
    include_officer_ids = CommanderAssignment.objects.filter(
        commander=me
    ).filter(
        Q(until__isnull=True) | Q(until__gte=today)
    ).values_list("officer_id", flat=True)
    qs_override = OfficerProfile.objects.filter(id__in=include_officer_ids).values_list("user_id", flat=True)
    ids = set(qs_unit) | set(qs_override) | {user.id}
    return ids


# ---------- Notifications ----------
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Список уведомлений пользователя + действия:
    - mark_read(id) — пометить одно
    - mark_all_read() — пометить все
    - unread_count() — количество непрочитанных
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["notification_type", "read_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by("-created_at")

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        obj = self.get_object()
        if obj.user_id != request.user.id:
            return APIResponse.forbidden("Чужие уведомления нельзя менять")
        if not obj.read_at:
            obj.read_at = timezone.now()
            obj.save(update_fields=["read_at"])
        return APIResponse.success(NotificationSerializer(obj).data, "Помечено прочитанным")

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        qs = self.get_queryset().filter(read_at__isnull=True)
        qs.update(read_at=timezone.now())
        return APIResponse.success({"updated": qs.count()}, "Все уведомления помечены")

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        count = self.get_queryset().filter(read_at__isnull=True).count()
        return APIResponse.success({"count": count})

    @extend_schema(
        summary="Получить JSON-schema и шаблоны payload для Notification",
        responses={200: PayloadTemplatesResponseSerializer},
        examples=[
            OpenApiExample(
                'ASSESSMENT payload template',
                value={
                    "version": 1,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "link": {"type": "string"},
                            "message": {"type": "string"},
                            "severity": {"type": "string", "enum": ["info", "warning", "critical"]},
                            "data": {"type": "object"},
                            "payload_version": {"type": "number"}
                        },
                        "additionalProperties": True
                    },
                    "templates": {
                        "ASSESSMENT": {
                            "title": "Аттестация назначена",
                            "link": "/assessments/{assessment_id}/",
                            "data": {
                                "assessment_id": 0,
                                "officer": "",
                                "status": "PLANNED",
                                "due_date": "YYYY-MM-DD"
                            },
                            "payload_version": 1
                        }
                    }
                },
                response_only=True
            )
        ],
    )

    @action(detail=False, methods=["get"], url_path="payload-templates")
    def payload_templates(self, request):
        return Response({"version": 1, "schema": NOTIFICATION_SCHEMA, "templates": NOTIFICATION_TEMPLATES})


# ---------- Support Tickets ----------
class SupportTicketViewSet(viewsets.ModelViewSet):
    """
    Автор (любой пользователь) — видит и управляет только своими тикетами.
    HR/ADMIN/ROOT — видят все тикеты, могут менять статус.
    """
    serializer_class = SupportTicketSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ["status", "priority", "author"]
    ordering = ["-created_at"]
    search_fields = ["subject", "body", "author__email"]

    def get_queryset(self):
        user = self.request.user
        base = SupportTicket.objects.select_related("author")
        if is_staffish(user):
            return base.all()
        if getattr(user, "role", None) == "COMMANDER":
            allowed_ids = _commander_visible_user_ids(user)
            return base.filter(author_id__in=allowed_ids)
        # прочие — только свои
        return base.filter(author=user)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def update(self, request, *args, **kwargs):
        ticket = self.get_object()

        user = request.user
        if is_staffish(user):
            return super().update(request, *args, **kwargs)

        if getattr(user, "role", None) == "COMMANDER":
            if ticket.author_id in _commander_visible_user_ids(user):
                return super().update(request, *args, **kwargs)
            return APIResponse.forbidden("Нет доступа (не ваш состав)")

        if ticket.author_id != user.id:
            return APIResponse.forbidden("Можно редактировать только свой тикет")

        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        ticket = self.get_object()
        user = request.user
        if is_staffish(user):
            return super().destroy(request, *args, **kwargs)

        if getattr(user, "role", None) == "COMMANDER":
            if ticket.author_id in _commander_visible_user_ids(user):
                return super().destroy(request, *args, **kwargs)
            return APIResponse.forbidden("Нет доступа (не ваш состав)")

        if ticket.author_id != user.id:
            return APIResponse.forbidden("Можно удалять только свой тикет")

        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def my(self, request):
        qs = SupportTicket.objects.filter(author=request.user).order_by("-created_at")
        return APIResponse.success(SupportTicketSerializer(qs, many=True).data)

    @extend_schema(
        summary="Ответить в тикете",
        examples=[OpenApiExample("Пример", value={"body": "Текст ответа"})],
        responses={201: TicketMessageSerializer}
    )
    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        """
        Добавить сообщение в тикет.
        body: {"body": "текст"}
        """
        ticket = self.get_object()
        user = request.user
        # доступ: HR/ADMIN/ROOT; или автор; или COMMANDER в пределах состава
        if not (
            is_staffish(user)
            or ticket.author_id == user.id
            or (getattr(user, "role", None) == "COMMANDER" and ticket.author_id in _commander_visible_user_ids(user))
        ):
            return APIResponse.forbidden("Нет доступа к тикету")

        text = request.data.get("body", "").strip()
        if not text:
            return APIResponse.validation_error({"body": ["Сообщение не может быть пустым"]})
        msg = TicketMessage.objects.create(ticket=ticket, author=request.user, body=text)
        return APIResponse.created(TicketMessageSerializer(msg).data, "Сообщение добавлено")

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def close(self, request, pk=None):
        """
        Автор может закрыть свой тикет, staff — тоже.
        """
        ticket = self.get_object()
        user = request.user
        if not (
            is_staffish(user)
            or ticket.author_id == user.id
            or (getattr(user, "role", None) == "COMMANDER" and ticket.author_id in _commander_visible_user_ids(user))
        ):
            return APIResponse.forbidden("Нет доступа")
        ticket.status = SupportTicket.TicketStatus.CLOSED
        ticket.save(update_fields=["status"])
        return APIResponse.success(SupportTicketSerializer(ticket).data, "Тикет закрыт")

    @extend_schema(
        summary="Изменить статус тикета (HR/ADMIN/ROOT/COMMANDER)",
        examples=[OpenApiExample("Пример", value={"status": "IN_PROGRESS"})],
        responses={200: SupportTicketSerializer}
    )
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated & (IsCommanderOrHR | IsAdminOrRoot)])
    def set_status(self, request, pk=None):
        """
        Изменить статус (только для HR/ADMIN/ROOT/COMMANDER).
        body: {"status": "IN_PROGRESS" | "WAITING" | "RESOLVED" | "CLOSED"}
        """
        ticket = self.get_object()
        if getattr(request.user, "role", None) == "COMMANDER":
            if ticket.author_id not in _commander_visible_user_ids(request.user):
                return APIResponse.forbidden("Командир может менять статус только в тикетах своего состава")
        status_value = request.data.get("status")
        valid = [c[0] for c in SupportTicket.TicketStatus.choices]
        if status_value not in valid:
            return APIResponse.validation_error({"status": [f"Недопустимое значение. Допустимо: {valid}"]})
        ticket.status = status_value
        ticket.save(update_fields=["status"])
        return APIResponse.success(SupportTicketSerializer(ticket).data, "Статус обновлён")


# ---------- Ticket Messages (Read-only list) ----------
class TicketMessageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TicketMessageSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["ticket"]
    ordering = ["created_at"]

    def get_queryset(self):
        user = self.request.user
        qs = TicketMessage.objects.select_related("ticket", "author", "ticket__author")
        if is_staffish(user):
            return qs
        if getattr(user, "role", None) == "COMMANDER":
            allowed_ids = _commander_visible_user_ids(user)
            return qs.filter(ticket__author_id__in=allowed_ids)
        # не staff и не командир: только свои тикеты
        return qs.filter(ticket__author=user)
