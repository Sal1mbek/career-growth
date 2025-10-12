from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django_fsm import TransitionNotAllowed

from core.permissions import IsAdminOrRoot, IsCommanderOrHR
from core.responses import APIResponse
from .models import Vacancy, CandidateMatch, Assignment
from .serializers import VacancySerializer, CandidateMatchSerializer, AssignmentSerializer
from .services import build_matches_for_vacancy


class VacancyViewSet(viewsets.ModelViewSet):
    queryset = Vacancy.objects.select_related("position", "unit").all()
    serializer_class = VacancySerializer
    permission_classes = [IsAuthenticated & (IsCommanderOrHR | IsAdminOrRoot)]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ["unit", "position", "status"]
    ordering_fields = ["open_from", "open_to"]
    search_fields = ["position__title", "unit__name"]

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated & (IsCommanderOrHR | IsAdminOrRoot)])
    def generate_matches(self, request, pk=None):
        vacancy = self.get_object()
        try:
            objs = build_matches_for_vacancy(vacancy)
        except Exception as e:
            return APIResponse.error(f"Не удалось пересчитать кандидатов: {e}", status=400)
        data = CandidateMatchSerializer(objs, many=True, context={"request": request}).data
        return APIResponse.success(data, message="Кандидаты пересчитаны")

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def candidates(self, request, pk=None):
        qs = CandidateMatch.objects.select_related("officer", "officer__rank").filter(vacancy_id=pk).order_by(
            "-match_score")
        return APIResponse.success(CandidateMatchSerializer(qs, many=True).data)


class CandidateMatchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CandidateMatch.objects.select_related("vacancy", "officer", "officer__rank").all()
    serializer_class = CandidateMatchSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ["vacancy", "officer"]
    ordering = ["-match_score"]
    search_fields = ["officer__full_name", "officer__user__email"]


class AssignmentViewSet(viewsets.ModelViewSet):
    queryset = Assignment.objects.select_related("vacancy", "officer").all()
    serializer_class = AssignmentSerializer
    permission_classes = [IsAuthenticated & (IsCommanderOrHR | IsAdminOrRoot)]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ["state", "vacancy", "officer"]
    ordering = ["-id"]
    search_fields = ["vacancy__position__title", "officer__full_name", "officer__user__email"]

    # FSM actions
    @action(detail=True, methods=["post"])
    def recommend(self, request, pk=None):
        obj = self.get_object()
        try:
            obj.recommend(request.user)
            obj.save()
        except TransitionNotAllowed:
            return Response(
                {"detail": f"Нельзя перевести из '{obj.state}' в 'recommended'"},
                status=400
            )
        return APIResponse.success(AssignmentSerializer(obj).data, "recommended")

    @action(detail=True, methods=["post"])
    def send_to_hr(self, request, pk=None):
        obj = self.get_object()
        try:
            obj.send_to_hr(request.user)
            obj.save()
        except TransitionNotAllowed:
            return Response(
                {"detail": f"Нельзя перевести из '{obj.state}' в 'hr_review'"},
                status=400
            )
        return APIResponse.success(AssignmentSerializer(obj).data, "hr_review")

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        obj = self.get_object()
        try:
            obj.approve(request.user)
            obj.save()
        except TransitionNotAllowed:
            return Response(
                {"detail": f"Нельзя перевести из '{obj.state}' в 'approved'"},
                status=400
            )
        return APIResponse.success(AssignmentSerializer(obj).data, "approved")

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        obj = self.get_object()
        try:
            obj.reject(request.user)
            obj.save()
        except TransitionNotAllowed:
            return Response(
                {"detail": f"Нельзя перевести из '{obj.state}' в 'rejected'"},
                status=400
            )
        return APIResponse.success(AssignmentSerializer(obj).data, "rejected")

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        obj = self.get_object()
        try:
            obj.assign(request.user)
            obj.save()
        except TransitionNotAllowed:
            return Response(
                {"detail": f"Нельзя перевести из '{obj.state}' в 'assigned'"},
                status=400
            )
        return APIResponse.success(AssignmentSerializer(obj).data, "assigned")
