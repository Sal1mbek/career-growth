from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from core.permissions import IsOfficer, IsCommanderOrHR, IsAdminOrRoot
from core.responses import APIResponse
from drf_spectacular.utils import extend_schema, OpenApiExample
from core.schemas import PayloadTemplatesResponseSerializer
from core.json_payloads import RECOMMENDATION_TEMPLATES, RECOMMENDATION_SCHEMA

from .models import CareerTrajectory, PlanStep, Recommendation
from .serializers import CareerTrajectorySerializer, PlanStepSerializer, RecommendationSerializer


class CareerTrajectoryViewSet(viewsets.ModelViewSet):
    queryset = CareerTrajectory.objects.all()
    serializer_class = CareerTrajectorySerializer
    permission_classes = [IsAuthenticated & (IsOfficer | IsCommanderOrHR | IsAdminOrRoot)]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'OFFICER':
            return self.queryset.filter(officer__user=user)
        elif user.role in ['COMMANDER', 'HR']:
            return self.queryset.select_related('officer', 'target_position')
        return self.queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return APIResponse.created(serializer.data)
        return APIResponse.validation_error(serializer.errors)


class PlanStepViewSet(viewsets.ModelViewSet):
    queryset = PlanStep.objects.all()
    serializer_class = PlanStepSerializer
    permission_classes = [IsAuthenticated & (IsOfficer | IsCommanderOrHR | IsAdminOrRoot)]


class RecommendationViewSet(viewsets.ModelViewSet):
    queryset = Recommendation.objects.all()
    serializer_class = RecommendationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'OFFICER':
            return self.queryset.filter(officer__user=user)
        return self.queryset

    @extend_schema(
        summary="Создать рекомендацию (HR/COMMANDER/ADMIN/ROOT)",
        examples=[
            OpenApiExample(
                "TRAINING payload",
                value={
                    "officer": 15,
                    "kind": "TRAINING",
                    "payload": {
                        "training_id": 12,
                        "training_title": "Курс лидерства",
                        "reason": "Повышение позиции",
                        "link": "/trainings/12/",
                        "payload_version": 1
                    }
                }
            )
        ],
    )
    def create(self, request, *args, **kwargs):
        # Разрешим создавать только HR/COMMANDER/ADMIN/ROOT
        if request.user.role not in ('HR', 'COMMANDER', 'ADMIN', 'ROOT'):
            return APIResponse.forbidden("Создавать рекомендации могут HR/Командир/Администратор/ROOT")
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return APIResponse.created(ser.data)

    def update(self, request, *args, **kwargs):
        if request.user.role not in ('HR', 'COMMANDER', 'ADMIN', 'ROOT'):
            return APIResponse.forbidden("Изменять рекомендации могут HR/Командир/Администратор/ROOT")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if request.user.role not in ('HR', 'COMMANDER', 'ADMIN', 'ROOT'):
            return APIResponse.forbidden("Удалять рекомендации могут HR/Командир/Администратор/ROOT")
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Шаблоны payload и JSON-schema для Recommendation",
        responses={200: PayloadTemplatesResponseSerializer},
        examples=[
            OpenApiExample(
                'TRAINING recommendation template',
                value={
                    "version": 1,
                    "schema": RECOMMENDATION_SCHEMA,
                    "templates": {
                        "TRAINING": {
                            "training_id": 12,
                            "training_title": "Курс лидерства",
                            "reason": "Закрываем пробел",
                            "link": "/trainings/{training_id}/",
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
        return Response({"version": 1, "schema": RECOMMENDATION_SCHEMA, "templates": RECOMMENDATION_TEMPLATES})
