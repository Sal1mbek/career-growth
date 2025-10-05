from django.db import transaction
from django.utils import timezone
from apps.officers.models import PositionHistory
from apps.users.models import OfficerProfile
from apps.directory.models import Position

@transaction.atomic
def add_position_history(officer: OfficerProfile, position: Position, start_date, result: str = "") -> PositionHistory:
    """
    Добавляет запись истории. Если есть текущая (end_date is null) — закрывает её на день раньше.
    """
    last = PositionHistory.objects.filter(officer=officer, end_date__isnull=True).order_by("-start_date").first()
    if last:
        if last.start_date >= start_date:
            # гарантируем монотонность
            last.end_date = last.start_date
        else:
            last.end_date = start_date
        last.save(update_fields=["end_date"])

    ph = PositionHistory.objects.create(
        officer=officer, position=position, start_date=start_date, result=result
    )
    # синхронизируем current_position
    officer.current_position = position
    officer.save(update_fields=["current_position"])
    return ph
