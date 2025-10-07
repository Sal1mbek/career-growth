from django.contrib import admin
from .models import TrajectoryForecast


@admin.register(TrajectoryForecast)
class TrajectoryForecastAdmin(admin.ModelAdmin):
    list_display = ("id", "officer", "target_position", "probability", "horizon_months", "model_version", "created_at")
    list_filter = ("model_version", "horizon_months", "created_at")
    search_fields = ("officer__user__email", "target_position__title", "model_version")
