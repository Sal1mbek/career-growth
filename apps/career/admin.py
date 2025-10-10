import json
from django.contrib import admin
from django import forms
from django_json_widget.widgets import JSONEditorWidget

from .models import CareerTrajectory, PlanStep, Recommendation
from core.json_payloads import RECOMMENDATION_TEMPLATES


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


class RecommendationForm(forms.ModelForm):
    class Meta:
        model = Recommendation
        fields = "__all__"
        widgets = {
            "payload": JSONEditorWidget(options={"mode": "tree", "modes": ["tree", "code"]}),
        }

    class Media:
        js = ("admin/payload_templates.js",)

@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    form = RecommendationForm
    list_display = ('officer', 'kind', 'created_at')
    list_filter = ('kind',)
    search_fields = ('officer__full_name',)
    autocomplete_fields = ('officer',)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial["payload"] = RECOMMENDATION_TEMPLATES.get("TRAINING", {})
        return initial

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        field = context["adminform"].form.fields["payload"].widget
        field.attrs["data-recommendation-templates"] = json.dumps(RECOMMENDATION_TEMPLATES, ensure_ascii=False)
        return super().render_change_form(request, context, add, change, form_url, obj)