from django.contrib import admin
from .models import Reward, Sanction, MeasureStatus, RewardType, SanctionType


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = (
    "id", "reward_type", "title", "officer", "unit", "status", "order_number", "order_date", "created_at")
    list_filter = ("reward_type", "status", "order_date", "created_at")
    search_fields = ("title", "description", "order_number", "officer__full_name", "officer__user__email")
    autocomplete_fields = ("officer", "unit", "initiator", "approved_by", "linked_sanction")
    readonly_fields = ("created_at", "updated_at", "initiator", "approved_by", "approved_at")
    exclude = ("initiator",)

    def save_model(self, request, obj, form, change):
        if not change and not obj.initiator_id:
            obj.initiator = request.user
        super().save_model(request, obj, form, change)


@admin.register(Sanction)
class SanctionAdmin(admin.ModelAdmin):
    list_display = (
    "id", "sanction_type", "title", "officer", "unit", "status", "order_number", "order_date", "lifted_at",
    "created_at")
    list_filter = ("sanction_type", "status", "order_date", "lifted_at", "created_at")
    search_fields = ("title", "description", "order_number", "officer__full_name", "officer__user__email")
    autocomplete_fields = ("officer", "unit", "initiator", "approved_by")
    readonly_fields = ("created_at", "updated_at", "initiator", "approved_by", "approved_at")
    exclude = ("initiator",)

    def save_model(self, request, obj, form, change):
        if not change and not obj.initiator_id:
            obj.initiator = request.user
        super().save_model(request, obj, form, change)
