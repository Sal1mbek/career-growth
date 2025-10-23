# Данные офицеров
from django.db import models


class PositionHistory(models.Model):
    """История назначений офицера"""
    officer = models.ForeignKey('users.OfficerProfile', on_delete=models.CASCADE, related_name='position_history')
    position = models.ForeignKey('directory.Position', on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    result = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date']


class OfficerDocument(models.Model):
    class DocumentType(models.TextChoices):
        DIPLOMA = 'DIPLOMA', 'Диплом'
        CERTIFICATE = 'CERTIFICATE', 'Сертификат'
        OFFICER_ID = 'OFFICER_ID', 'Удостоверение офицера'
        PERSONAL_ID = 'PERSONAL_ID', 'Удостоверение личности'
        PASSPORT = 'PASSPORT', 'Паспорт'
        DRIVING_LICENSE = 'DRIVING_LICENSE', 'Водительское удостоверение'
        MARRIAGE_CERT = 'MARRIAGE_CERT', 'Свидетельство о браке'
        CHILD_BIRTH_CERT = 'CHILD_BIRTH_CERT', 'Свидетельство о рождении ребёнка'
        OTHER = 'OTHER', 'Прочее'

    officer = models.ForeignKey('users.OfficerProfile', on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='officer_docs/')
    meta = models.JSONField(default=dict, blank=True)
    issued_at = models.DateField()


class CourseEnrollment(models.Model):
    class EnrollmentStatus(models.TextChoices):
        ENROLLED = 'ENROLLED', 'Зачислен'
        IN_PROGRESS = 'IN_PROGRESS', 'В процессе'
        COMPLETED = 'COMPLETED', 'Завершён'
        FAILED = 'FAILED', 'Не завершён'

    officer = models.ForeignKey('users.OfficerProfile', on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey('directory.TrainingCourse', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=EnrollmentStatus.choices, default=EnrollmentStatus.ENROLLED)
    enrolled_at = models.DateField(auto_now_add=True)
    completed_at = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['officer', 'course'], name='uniq_enrollment_officer_course')
        ]


class Certificate(models.Model):
    officer = models.ForeignKey('users.OfficerProfile', on_delete=models.CASCADE, related_name='certificates')
    course = models.ForeignKey('directory.TrainingCourse', on_delete=models.SET_NULL, null=True, blank=True)
    file = models.FileField(upload_to='certificates/')
    issued_at = models.DateField()
    expires_at = models.DateField(null=True, blank=True)
