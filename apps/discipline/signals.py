from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Reward, Sanction, MeasureStatus
from django.utils import timezone


@receiver(post_save, sender=Sanction)
def update_officer_sanctions(sender, instance, **kwargs):
    # при EXECUTED/REVOKED/LIFTED можно обновлять кэш-поля профиля офицера (если их добавишь)
    pass
