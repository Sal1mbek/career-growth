from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from .models import AuditLog


def log_event(*, actor, action: str, obj=None, object_type: str = None, object_id=None,
              diff_json=None, ip=None, user_agent: str = ""):
    """
    Универсальный логгер. Можно вызывать вручную из вьюх.
    action: 'CREATE'|'UPDATE'|'DELETE'|'VIEW'|'LOGIN'|'LOGOUT'
    obj: экземпляр модели (опционально)
    """
    if obj is not None and (object_type is None or object_id is None):
        ct = ContentType.objects.get_for_model(obj.__class__)
        object_type = f"{ct.app_label}.{ct.model}"
        object_id = getattr(obj, "pk", None)

    AuditLog.objects.create(
        actor=actor if getattr(actor, "id", None) else None,
        action=action,
        object_type=object_type or "",
        object_id=object_id,
        diff_json=diff_json,
        ip=ip,
        user_agent=(user_agent or "")[:500],
        created_at=timezone.now()
    )
