from django.contrib import admin
from .models import CareerTrajectory, PlanStep, Recommendation

@admin.register(CareerTrajectory)
class CareerTrajectoryAdmin(admin.ModelAdmin):
    list_display = ('officer', 'target_position', 'status', 'horizon_months', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('officer__full_name', 'target_position__title')
    autocomplete_fields = ('officer', 'target_position')


@admin.register(PlanStep)
class PlanStepAdmin(admin.ModelAdmin):
    list_display = ('trajectory', 'title', 'step_type', 'due_date', 'completed_at')
    list_filter = ('step_type',)
    search_fields = ('trajectory__officer__full_name', 'title')
    autocomplete_fields = ('trajectory',)


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ('officer', 'kind', 'created_at')
    list_filter = ('kind',)
    search_fields = ('officer__full_name',)
    autocomplete_fields = ('officer',)
