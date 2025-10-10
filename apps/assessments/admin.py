import json
from django.contrib import admin
from django import forms
from django_json_widget.widgets import JSONEditorWidget

from .models import Assessment, AssessmentItem, CompetencyRating, Rater, Feedback360
from core.json_payloads import FEEDBACK360_TEMPLATE


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


class Feedback360Form(forms.ModelForm):
    class Meta:
        model = Feedback360
        fields = "__all__"
        widgets = {
            # БЕЗ collapsed=..., только options
            "payload": JSONEditorWidget(options={"mode": "tree", "modes": ["tree", "code"]}),
        }


class Feedback360Admin(admin.ModelAdmin):
    form = Feedback360Form
    list_display = ("id", "assessment", "rater", "is_anonymous", "created_at")
    search_fields = ("assessment__officer__user__email", "rater__user__email")
    list_filter = ("is_anonymous", "created_at")
    autocomplete_fields = ("assessment", "rater")

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial["payload"] = FEEDBACK360_TEMPLATE
        return initial


admin.site.register(Feedback360, Feedback360Admin)
