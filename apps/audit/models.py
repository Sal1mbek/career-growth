# Аудит
from django.db import models


class AuditLog(models.Model):
    """Журнал аудита"""
    class ActionType(models.TextChoices):
        CREATE = 'CREATE', 'Создание'
        UPDATE = 'UPDATE', 'Изменение'
        DELETE = 'DELETE', 'Удаление'
        VIEW = 'VIEW', 'Просмотр'
        LOGIN = 'LOGIN', 'Вход'
        LOGOUT = 'LOGOUT', 'Выход'

    actor = models.ForeignKey('users.CustomUser', on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=20, choices=ActionType.choices)
    object_type = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    diff_json = models.JSONField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['actor', 'created_at']),
        ]
