from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsOfficer, IsCommanderOrHR, IsAdminOrRoot
from core.responses import APIResponse
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


class RecommendationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Recommendation.objects.all()
    serializer_class = RecommendationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'OFFICER':
            return self.queryset.filter(officer__user=user)
        return self.queryset
