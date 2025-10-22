from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django_fsm import TransitionNotAllowed

from core.permissions import IsAdminOrRoot, IsCommanderOrHR, IsHR
from core.responses import APIResponse
from apps.users.models import CommanderProfile, HRProfile
from apps.directory.models import Unit
from .models import Vacancy, CandidateMatch, Assignment
from .serializers import VacancySerializer, CandidateMatchSerializer, AssignmentSerializer
from .services import build_matches_for_vacancy


class VacancyViewSet(viewsets.ModelViewSet):
    queryset = Vacancy.objects.select_related("position", "unit").all()
    serializer_class = VacancySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ["unit", "position", "status"]
    ordering_fields = ["open_from", "open_to"]
    search_fields = ["position__title", "unit__name"]

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, (IsHR | IsAdminOrRoot)])
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

    def get_permissions(self):
        # SAFE: всем аутентифицированным (дальше отфильтруем queryset)
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        # UNSAFE: только HR или ADMIN/ROOT
        return [IsAuthenticated(), (IsHR | IsAdminOrRoot)()]

    def get_queryset(self):
        qs = super().get_queryset()
        u = self.request.user
        # ADMIN/ROOT — всё
        if IsAdminOrRoot().has_permission(self.request, self):
            return qs
        # HR — только в своих юнитах
        if getattr(u, "role", "") == "HR":
            hrp = HRProfile.objects.filter(user=u).first()
            if not hrp:
                return qs.none()
            return qs.filter(unit__in=hrp.responsible_units.all())

        # COMMANDER — только свой unit
        if getattr(u, "role", "") == "COMMANDER":
            me = CommanderProfile.objects.filter(user=u).select_related("unit").first()
            return qs.filter(unit=me.unit_id) if me and me.unit_id else qs.none()

        # OFFICER и прочие — ничего
        return qs.none()

    def _hr_must_own_unit_or_admin(self, unit_id: int):
        """Бросаем 403 если HR пытается трогать чужой юнит. ADMIN/ROOT — можно всё."""
        if IsAdminOrRoot().has_permission(self.request, self):
            return

        user = self.request.user
        if getattr(user, "role", "") != "HR":
        # на всякий случай: командиру и офицеру менять нельзя
            raise PermissionError("Недостаточно прав")

        hrp = HRProfile.objects.filter(user=user).first()
        allowed = set(hrp.responsible_units.values_list("id", flat=True)) if hrp else set()
        if unit_id not in allowed:
            raise PermissionError("Недостаточно прав для выбранного подразделения")

    def perform_create(self, serializer):
        unit_id = serializer.validated_data["unit"].id
        try:
            self._hr_must_own_unit_or_admin(unit_id)
        except PermissionError as e:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(str(e))
        serializer.save()

    def perform_update(self, serializer):
        # запрещаем HR перемещать вакансию в чужой юнит
        instance: Vacancy = self.get_object()
        new_unit = serializer.validated_data.get("unit", instance.unit)
        try:
            self._hr_must_own_unit_or_admin(new_unit.id)
        except PermissionError as e:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(str(e))
        serializer.save()

    def perform_destroy(self, instance):
        try:
            self._hr_must_own_unit_or_admin(instance.unit_id)
        except PermissionError as e:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(str(e))
        instance.delete()


class CandidateMatchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CandidateMatch.objects.select_related("vacancy", "officer", "officer__rank").all()
    serializer_class = CandidateMatchSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ["vacancy", "officer"]
    ordering = ["-match_score"]
    search_fields = ["officer__full_name", "officer__user__email"]

    def get_queryset(self):
        qs = super().get_queryset()
        req = self.request
        u = req.user
        # ADMIN/ROOT — всё
        if IsAdminOrRoot().has_permission(req, self):
            return qs

        # HR — только по вакансиям в своих юнитах
        if getattr(u, "role", "") == "HR":
            hrp = HRProfile.objects.filter(user=u).first()
            if not hrp:
                return qs.none()
            return qs.filter(vacancy__unit__in=hrp.responsible_units.all())

        # COMMANDER — только по вакансиям в его unit
        if getattr(u, "role", "") == "COMMANDER":
            me = CommanderProfile.objects.filter(user=u).select_related("unit").first()
            return qs.filter(vacancy__unit=me.unit_id) if me and me.unit_id else qs.none()

        # OFFICER — ничего
        return qs.none()


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
