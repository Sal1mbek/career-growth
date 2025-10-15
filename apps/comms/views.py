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
from .models import Notification, SupportTicket, TicketMessage
from .serializers import (
    NotificationSerializer, SupportTicketSerializer, TicketMessageSerializer
)


def is_staffish(user):
    return getattr(user, "role", None) in ("HR", "ADMIN", "ROOT", "COMMANDER")


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
    HR/COMMANDER/ADMIN/ROOT — видят все тикеты, могут менять статус.
    """
    serializer_class = SupportTicketSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ["status", "priority", "author"]
    ordering = ["-created_at"]
    search_fields = ["subject", "body", "author__email"]

    def get_queryset(self):
        user = self.request.user
        if is_staffish(user):
            return SupportTicket.objects.select_related("author").all()
        return SupportTicket.objects.select_related("author").filter(author=user)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def update(self, request, *args, **kwargs):
        ticket = self.get_object()
        if not is_staffish(request.user) and ticket.author_id != request.user.id:
            return APIResponse.forbidden("Можно редактировать только свой тикет")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        ticket = self.get_object()
        if not is_staffish(request.user) and ticket.author_id != request.user.id:
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
        # доступ: автор или staffish
        if not (is_staffish(request.user) or ticket.author_id == request.user.id):
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
        if not (is_staffish(request.user) or ticket.author_id == request.user.id):
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
        # не staff: видит сообщения только своих тикетов
        return qs.filter(Q(ticket__author=user))
