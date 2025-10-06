from django.contrib import admin
from .models import Assessment, AssessmentItem, CompetencyRating, Rater, Feedback360


class AssessmentItemInline(admin.TabularInline):
    model = AssessmentItem
    extra = 0


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("id", "officer", "cycle", "assessment_type", "created_by", "created_at")
    list_filter = ("assessment_type", "cycle", "created_at")
    search_fields = ("officer__user__email", "officer__full_name")
    autocomplete_fields = ("officer", "created_by")
    inlines = [AssessmentItemInline]


@admin.register(CompetencyRating)
class CompetencyRatingAdmin(admin.ModelAdmin):
    list_display = ("id", "officer", "competency", "score", "source", "assessed_at")
    list_filter = ("source", "competency", "assessed_at")
    search_fields = ("officer__user__email", "officer__full_name", "competency__name")
    autocomplete_fields = ("officer", "competency")


admin.site.register(Rater,
                    type("RaterAdmin", (admin.ModelAdmin,), {
                        "list_display": ("id", "user", "relation"),
                        "search_fields": ("user__email",),
                        "list_filter": ("relation",),
                        "autocomplete_fields": ("user",),  # <—
                    })
                    )

admin.site.register(Feedback360,
                    type("Feedback360Admin", (admin.ModelAdmin,), {
                        "list_display": ("id", "assessment", "rater", "is_anonymous", "created_at"),
                        "search_fields": ("assessment__officer__user__email", "rater__user__email"),
                        "list_filter": ("is_anonymous", "created_at"),
                        "autocomplete_fields": ("assessment", "rater"),  # <—
                    })
                    )
