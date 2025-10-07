from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.forms.models import model_to_dict
from django.conf import settings

from .utils import log_event

AUDIT_EXCLUDE_MODELS = getattr(settings, "AUDIT_EXCLUDE_MODELS", set())


def _model_label(instance):
    m = instance.__class__
    return f"{m._meta.app_label}.{m._meta.model_name}"


@receiver(post_save)
def audit_post_save(sender, instance, created, **kwargs):
    label = _model_label(instance)
    if label in AUDIT_EXCLUDE_MODELS:
        return
    # Не логируем сам AuditLog, чтобы не зациклиться
    if label == "audit.auditlog":
        return

    # Без актёра (actor) — это системное событие (например, фикстуры). Актёра подставим из middleware, если нужно.
    action = "CREATE" if created else "UPDATE"
    try:
        data = model_to_dict(instance)
    except Exception:
        data = None

    log_event(
        actor=None, action=action, obj=instance,
        diff_json={"after": data} if created else {"after": data}
    )


@receiver(post_delete)
def audit_post_delete(sender, instance, **kwargs):
    label = _model_label(instance)
    if label in AUDIT_EXCLUDE_MODELS or label == "audit.auditlog":
        return

    try:
        data = model_to_dict(instance)
    except Exception:
        data = None

    log_event(
        actor=None, action="DELETE", obj=instance,
        diff_json={"before": data}
    )
