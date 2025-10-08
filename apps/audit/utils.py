from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.utils import ProgrammingError, OperationalError
from .models import AuditLog
from django.core.serializers.json import DjangoJSONEncoder
import json


def _contenttypes_ready() -> bool:
    """Проверяем, что таблица django_content_type существует (важно при migrate)."""
    try:
        return 'django_content_type' in connection.introspection.table_names()
    except Exception:
        return False


def _jsonable(payload):
    """Гарантируем, что payload сериализуем (дату/время и т.п. делаем строкой)."""
    if payload is None:
        return None
    try:
        json.dumps(payload, cls=DjangoJSONEncoder)
        return payload
    except TypeError:
        # прогоняем через dumps/loads с DjangoJSONEncoder
        return json.loads(json.dumps(payload, cls=DjangoJSONEncoder))


def log_event(*, actor, action: str, obj=None, object_type: str = None, object_id=None,
              diff_json=None, ip=None, user_agent: str = ""):
    """
    Универсальный логгер. Можно вызывать вручную из вьюх.
    action: 'CREATE'|'UPDATE'|'DELETE'|'VIEW'|'LOGIN'|'LOGOUT'
    obj: экземпляр модели (опционально)
    """
    if obj is not None and (object_type is None or object_id is None):
        object_id = getattr(obj, "pk", None)

        # Пытаемся получить app_label.model через ContentType, но только если таблица готова
        if _contenttypes_ready():
            try:
                ct = ContentType.objects.get_for_model(obj.__class__)
                object_type = f"{ct.app_label}.{ct.model}"
            except (ProgrammingError, OperationalError, LookupError):
                # fallback без ContentType
                object_type = getattr(obj._meta, "label_lower", obj.__class__.__name__.lower())
        else:
            object_type = getattr(obj._meta, "label_lower", obj.__class__.__name__.lower())

    AuditLog.objects.create(
        actor=actor if getattr(actor, "id", None) else None,
        action=action,
        object_type=object_type or "",
        object_id=object_id,
        diff_json=_jsonable(diff_json),
        ip=ip,
        user_agent=(user_agent or "")[:500],
        created_at=timezone.now()
    )