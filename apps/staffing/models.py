# Укомплектование
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django_fsm import FSMField, transition
from django.utils import timezone


class Vacancy(models.Model):
    """Вакансия"""
    class VacancyStatus(models.TextChoices):
        OPEN = 'OPEN', 'Открыта'
        IN_PROGRESS = 'IN_PROGRESS', 'В работе'
        CLOSED = 'CLOSED', 'Закрыта'

    position = models.ForeignKey('directory.Position', on_delete=models.CASCADE)
    unit = models.ForeignKey('directory.Unit', on_delete=models.CASCADE)
    open_from = models.DateField()
    open_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=VacancyStatus.choices, default=VacancyStatus.OPEN)

    def __str__(self):
        pos = self.position.title if self.position else "—"
        unit = self.unit.name if self.unit else "—"
        return f"{pos} • {unit} • {self.get_status_display()}"

    class Meta:
        indexes = [models.Index(fields=['status'])]


class CandidateMatch(models.Model):
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name='candidates')
    officer = models.ForeignKey('users.OfficerProfile', on_delete=models.CASCADE)
    match_score = models.DecimalField(max_digits=5, decimal_places=2,
                                      validators=[MinValueValidator(0), MaxValueValidator(100)])
    gaps = models.JSONField(default=list, blank=True)  # список {competency, current, required}
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        officer = self.officer.full_name or self.officer.user.email
        pos = self.vacancy.position.title if self.vacancy and self.vacancy.position else "—"
        return f"{officer} ↔ {pos} ({self.match_score}%)"

    class Meta:
        unique_together = ('vacancy', 'officer')


class Assignment(models.Model):
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE)
    officer = models.ForeignKey('users.OfficerProfile', on_delete=models.CASCADE)
    state = FSMField(default='draft', protected=True)
    decision_chain = models.JSONField(default=list)
    decided_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        officer = self.officer.full_name or self.officer.user.email
        pos = self.vacancy.position.title if self.vacancy and self.vacancy.position else "—"
        return f"{pos} → {officer} [{self.state}]"

    @transition(field=state, source='draft', target='recommended')
    def recommend(self, by_user):
        self.decision_chain.append(
            {'actor': getattr(by_user, 'email', ''), 'action': 'recommended', 'at': timezone.now().isoformat()})

    @transition(field=state, source='recommended', target='hr_review')
    def send_to_hr(self, by_user):
        self.decision_chain.append(
            {'actor': getattr(by_user, 'email', ''), 'action': 'hr_review', 'at': timezone.now().isoformat()})

    @transition(field=state, source='hr_review', target='approved')
    def approve(self, by_user):
        self.decision_chain.append(
            {'actor': getattr(by_user, 'email', ''), 'action': 'approved', 'at': timezone.now().isoformat()})

    @transition(field=state, source='hr_review', target='rejected')
    def reject(self, by_user):
        self.decision_chain.append(
            {'actor': getattr(by_user, 'email', ''), 'action': 'rejected', 'at': timezone.now().isoformat()})

    @transition(field=state, source='approved', target='assigned')
    def assign(self, by_user):
        self.decided_at = timezone.now()
        self.decision_chain.append(
            {'actor': getattr(by_user, 'email', ''), 'action': 'assigned', 'at': timezone.now().isoformat()})
