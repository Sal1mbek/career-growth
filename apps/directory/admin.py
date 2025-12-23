from django.contrib import admin
from .models import (
    Rank, Unit, Position, PositionRequirement, Competency, CompetencyRequirement, Provider, TrainingCourse,
    PositionQualification
)


@admin.register(Rank)
class RankAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "order", "is_active")
    list_editable = ("order", "is_active")
    ordering = ("order",)


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code", "parent", "level", "is_active")
    search_fields = ("name", "code")
    list_filter = ("is_active",)


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "code", "unit", "is_active")
    search_fields = ("title", "code")
    list_filter = ("unit", "is_active")


@admin.register(PositionRequirement)
class PositionRequirementAdmin(admin.ModelAdmin):
    list_display = ("id", "position", "min_rank", "min_service_years", "required_education")
    list_filter = ("min_rank",)


@admin.register(Competency)
class CompetencyAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "group", "is_active")
    search_fields = ("code", "name", "group")
    list_filter = ("group", "is_active")


@admin.register(CompetencyRequirement)
class CompetencyRequirementAdmin(admin.ModelAdmin):
    list_display = ("id", "position", "competency", "min_score", "is_mandatory")
    list_filter = ("position", "competency", "min_score", "is_mandatory")


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active")
    search_fields = ("name",)


@admin.register(TrainingCourse)
class TrainingCourseAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "title", "provider", "hours", "is_active")
    search_fields = ("code", "title", "provider__name")
    list_filter = ("provider", "is_active")


@admin.register(PositionQualification)
class PositionQualificationAdmin(admin.ModelAdmin):
    list_display = ("id", "position", "category", "order")
    list_filter = ("category",)
    search_fields = ("text", "position__title")
    ordering = ("category", "order")
