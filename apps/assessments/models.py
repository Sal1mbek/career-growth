# Аттестации и оценки
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Assessment(models.Model):
    """Аттестация офицера"""
    class AssessmentType(models.TextChoices):
        ANNUAL = 'ANNUAL', 'Годовая'
        PROBATION = 'PROBATION', 'Испытательный срок'
        EXTRAORDINARY = 'EXTRAORDINARY', 'Внеочередная'

    officer = models.ForeignKey('users.OfficerProfile', on_delete=models.CASCADE, related_name='assessments')
    cycle = models.CharField(max_length=50)
    assessment_type = models.CharField(max_length=20, choices=AssessmentType.choices)
    created_by = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AssessmentItem(models.Model):
    """Оценка по компетенции в рамках аттестации"""
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='items')
    competency = models.ForeignKey('directory.Competency', on_delete=models.PROTECT)
    score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)


class CompetencyRating(models.Model):
    class RatingSource(models.TextChoices):
        SELF = 'SELF', 'Самооценка'
        COMMANDER = 'COMMANDER', 'Командир'
        FEEDBACK_360 = '360', '360°'
        TEST = 'TEST', 'Тест'

    officer = models.ForeignKey('users.OfficerProfile', on_delete=models.CASCADE, related_name='competency_ratings')
    competency = models.ForeignKey('directory.Competency', on_delete=models.PROTECT)
    score = models.DecimalField(max_digits=3, decimal_places=1, validators=[MinValueValidator(1), MaxValueValidator(5)])
    source = models.CharField(max_length=20, choices=RatingSource.choices)
    assessed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('officer', 'competency', 'source', 'assessed_at')


class Rater(models.Model):
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    relation = models.CharField(max_length=20, choices=[
        ('COMMANDER', 'Командир'), ('COLLEAGUE', 'Коллега'), ('SUBORDINATE', 'Подчинённый')
    ])


class Feedback360(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='feedback_360')
    rater = models.ForeignKey(Rater, on_delete=models.CASCADE)
    payload = models.JSONField(default=dict)
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
