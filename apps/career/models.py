# Карьерное планирование
from django.db import models


class CareerTrajectory(models.Model):
    """Карьерная траектория"""
    class TrajectoryStatus(models.TextChoices):
        DRAFT = 'DRAFT', 'Черновик'
        ACTIVE = 'ACTIVE', 'Активна'
        COMPLETED = 'COMPLETED', 'Завершена'
        CANCELLED = 'CANCELLED', 'Отменена'

    officer = models.ForeignKey('users.OfficerProfile', on_delete=models.CASCADE, related_name='trajectories')
    target_position = models.ForeignKey('directory.Position', on_delete=models.PROTECT)
    horizon_months = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=TrajectoryStatus.choices, default=TrajectoryStatus.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.officer.full_name} → {self.target_position.title} ({self.get_status_display()})"

    class Meta:
        indexes = [models.Index(fields=['status'])]


class PlanStep(models.Model):
    class StepType(models.TextChoices):
        TRAINING = 'TRAINING', 'Обучение'
        COMPETENCY = 'COMPETENCY', 'Развитие компетенции'
        POSITION = 'POSITION', 'Назначение'
        ASSESSMENT = 'ASSESSMENT', 'Аттестация'

    trajectory = models.ForeignKey(CareerTrajectory, on_delete=models.CASCADE, related_name='steps')
    step_type = models.CharField(max_length=20, choices=StepType.choices)
    title = models.CharField(max_length=255)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateField(null=True, blank=True)
    required_min_score = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({self.get_step_type_display()})"

    class Meta:
        indexes = [models.Index(fields=['due_date'])]


class Recommendation(models.Model):
    class RecommendationKind(models.TextChoices):
        TRAINING = 'TRAINING', 'Обучение'
        COMPETENCY_GAP = 'COMPETENCY_GAP', 'Закрыть пробел'
        POSITION = 'POSITION', 'Позиция'

    officer = models.ForeignKey('users.OfficerProfile', on_delete=models.CASCADE, related_name='recommendations')
    kind = models.CharField(max_length=20, choices=RecommendationKind.choices)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.officer.full_name} → {self.get_kind_display()}"
