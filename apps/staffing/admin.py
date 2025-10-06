from django.contrib import admin
from .models import Vacancy, CandidateMatch, Assignment


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ("id", "position", "unit", "status", "open_from", "open_to")
    search_fields = ("position__title", "unit__name")
    list_filter = ("status", "unit", "position")
    autocomplete_fields = ("position", "unit")


@admin.register(CandidateMatch)
class CandidateMatchAdmin(admin.ModelAdmin):
    list_display = ("id", "vacancy", "officer", "match_score", "created_at")
    search_fields = ("officer__full_name", "officer__user__email", "vacancy__position__title")
    list_filter = ("vacancy", "created_at")
    autocomplete_fields = ("vacancy", "officer")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "vacancy", "officer", "state", "decided_at")
    list_filter = ("state", "vacancy")
    search_fields = ("officer__full_name", "officer__user__email", "vacancy__position__title")
    autocomplete_fields = ("vacancy", "officer")
