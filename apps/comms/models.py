# Коммуникации
from django.db import models


class Notification(models.Model):
    """Уведомления"""
    class NotificationType(models.TextChoices):
        ASSESSMENT = 'ASSESSMENT', 'Аттестация'
        TRAINING = 'TRAINING', 'Обучение'
        CAREER = 'CAREER', 'Карьера'
        VACANCY = 'VACANCY', 'Вакансия'
        SYSTEM = 'SYSTEM', 'Системное'

    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NotificationType.choices, db_index=True)
    payload = models.JSONField(default=dict)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class SupportTicket(models.Model):
    class TicketStatus(models.TextChoices):
        NEW = 'NEW', 'Новый'
        IN_PROGRESS = 'IN_PROGRESS', 'В работе'
        WAITING = 'WAITING', 'Ожидает'
        RESOLVED = 'RESOLVED', 'Решён'
        CLOSED = 'CLOSED', 'Закрыт'

    class TicketPriority(models.TextChoices):
        LOW = 'LOW', 'Низкий'
        MEDIUM = 'MEDIUM', 'Средний'
        HIGH = 'HIGH', 'Высокий'
        CRITICAL = 'CRITICAL', 'Критичный'

    author = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=TicketStatus.choices, default=TicketStatus.NEW, db_index=True)
    priority = models.CharField(max_length=20, choices=TicketPriority.choices, default=TicketPriority.MEDIUM,
                                db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.id}] {self.subject or 'Без темы'} ({self.get_status_display()})"


class TicketMessage(models.Model):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        author = self.author.email if self.author else "Система"
        return f"{author}: {self.text[:50]}..."

    class Meta:
        ordering = ['created_at']
