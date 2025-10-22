# Справочники
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class Rank(models.Model):
    """Воинские звания"""
    name = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(unique=True)  # иерархия
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self): return self.name


class Unit(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    level = models.PositiveSmallIntegerField(null=True, blank=True)  # можно вычислять сигналом
    is_active = models.BooleanField(default=True)

    def __str__(self): return self.name


class Position(models.Model):
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        unit = self.unit.name if self.unit else ""
        return f"{self.title} ({unit})"


class PositionRequirement(models.Model):
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='requirements')
    min_rank = models.ForeignKey(Rank, on_delete=models.CASCADE)
    min_service_years = models.PositiveSmallIntegerField(default=0)
    required_education = models.CharField(max_length=255, blank=True)


class Competency(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    group = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} [{self.code}]"


class CompetencyRequirement(models.Model):
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='competency_requirements')
    competency = models.ForeignKey(Competency, on_delete=models.CASCADE)
    min_score = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    is_mandatory = models.BooleanField(default=True)

    class Meta:
        unique_together = ('position', 'competency')


class Provider(models.Model):
    name = models.CharField(max_length=255)
    accreditations = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)


class TrainingCourse(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    hours = models.PositiveIntegerField(default=0)
    tags = models.JSONField(default=list, blank=True)
    related_competencies = models.ManyToManyField(Competency, related_name='training_courses', blank=True)
    is_active = models.BooleanField(default=True)
