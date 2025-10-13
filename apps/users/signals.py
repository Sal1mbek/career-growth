from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import OfficerProfile, CommanderProfile, HRProfile

User = get_user_model()


@receiver(post_save, sender=User)
def ensure_profile_exists(sender, instance, created, **kwargs):
    """Автоматически создаёт профиль при создании юзера с соответствующей ролью"""
    if instance.role == User.UserRole.OFFICER:
        OfficerProfile.objects.get_or_create(user=instance)
    elif instance.role == User.UserRole.COMMANDER:
        CommanderProfile.objects.get_or_create(user=instance)
    elif instance.role == User.UserRole.HR:
        HRProfile.objects.get_or_create(user=instance)