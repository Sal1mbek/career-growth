from django.contrib import admin
from .models import PositionHistory, OfficerDocument, CourseEnrollment, Certificate

@admin.register(PositionHistory)
class PositionHistoryAdmin(admin.ModelAdmin):
    list_display = ("id","officer","position","start_date","end_date")
    list_filter  = ("position","start_date","end_date")
    search_fields= ("officer__user__email","officer__full_name")

@admin.register(OfficerDocument)
class OfficerDocumentAdmin(admin.ModelAdmin):
    list_display = ("id","officer","document_type","title","issued_at")
    list_filter  = ("document_type","issued_at")
    search_fields= ("title","officer__user__email")

@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("id","officer","course","status","enrolled_at","completed_at")
    list_filter  = ("status","course")
    search_fields= ("officer__user__email","course__title")

@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ("id","officer","course","issued_at","expires_at")
    list_filter  = ("issued_at","expires_at")
    search_fields= ("officer__user__email","course__title")
