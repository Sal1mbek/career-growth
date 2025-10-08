import sys
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.forms.models import model_to_dict
from django.conf import settings

from .utils import log_event

AUDIT_EXCLUDE_MODELS = getattr(settings, "AUDIT_EXCLUDE_MODELS", set())
AUDIT_SKIP_DURING_MIGRATIONS = getattr(settings, "AUDIT_SKIP_DURING_MIGRATIONS", True)


def _skip_now() -> bool:
    # Во время миграций сигналы шумят данными, а таблиц может не быть
    if not AUDIT_SKIP_DURING_MIGRATIONS:
        return False
    argv = " ".join(sys.argv)
    return (" migrate" in argv) or (" makemigrations" in argv) or (" loaddata" in argv)


def _model_label(instance):
    m = instance.__class__
    return f"{m._meta.app_label}.{m._meta.model_name}"


@receiver(post_save)
def audit_post_save(sender, instance, created, **kwargs):
    if _skip_now():
        return
    label = _model_label(instance)
    if label in AUDIT_EXCLUDE_MODELS or label == "audit.auditlog":
        return

    try:
        data = model_to_dict(instance)
    except Exception:
        data = None

    log_event(
        actor=None,
        action="CREATE" if created else "UPDATE",
        obj=instance,
        diff_json={"after": data}
    )


@receiver(post_delete)
def audit_post_delete(sender, instance, **kwargs):
    if _skip_now():
        return
    label = _model_label(instance)
    if label in AUDIT_EXCLUDE_MODELS or label == "audit.auditlog":
        return

    try:
        data = model_to_dict(instance)
    except Exception:
        data = None

    log_event(
        actor=None,
        action="DELETE",
        obj=instance,
        diff_json={"before": data}
    )