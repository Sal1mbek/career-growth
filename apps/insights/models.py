# Аналитика и прогнозы
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class TrajectoryForecast(models.Model):
    """Прогноз карьерной траектории (ИИ)"""
    officer = models.ForeignKey('users.OfficerProfile', on_delete=models.CASCADE)
    target_position = models.ForeignKey('directory.Position', on_delete=models.PROTECT)
    probability = models.DecimalField(max_digits=5, decimal_places=2,
                                      validators=[MinValueValidator(0), MaxValueValidator(100)])
    horizon_months = models.PositiveSmallIntegerField()
    model_version = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
