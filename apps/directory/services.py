from typing import Dict, List, Tuple
from django.db.models import Prefetch
from apps.directory.models import Position, CompetencyRequirement
from apps.users.models import OfficerProfile

def check_basic_position_requirements(officer: OfficerProfile, position: Position) -> Dict:
    """
    Проверка базовых требований позиции: минимальный ранг, стаж.
    Возвращает dict с passed: bool и деталями.
    """
    req = position.positionrequirement_set.first()
    if not req:
        return {"passed": True, "details": "Нет базовых требований"}
    passed_rank = (officer.rank_id is not None and officer.rank.order >= req.min_rank.order)
    # стаж в годах
    service_years = max(0, (officer.service_start_date and (officer.service_start_date.year)) and (  # упрощенно
                         (position.pk and 0) or 0))
    # Лучше считать через dateutil.relativedelta; здесь отдаём флаг, без вычисления точных лет:
    passed = passed_rank  # и стаж можешь добавить, когда будет точный расчёт
    return {
        "passed": passed,
        "min_rank": req.min_rank.name,
        "officer_rank": getattr(officer.rank, "name", None),
        "note": "Проверка стажа добавить при интеграции точного расчёта"
    }

def compute_competency_gaps(officer_scores: Dict[int, float], position: Position) -> List[Dict]:
    """
    officer_scores: {competency_id: score}
    Возвращает список пробелов по компетенциям для позиции.
    """
    gaps = []
    reqs = CompetencyRequirement.objects.filter(position=position).select_related("competency")
    for r in reqs:
        curr = officer_scores.get(r.competency_id, 0)
        if curr < r.min_score:
            gaps.append({
                "competency_id": r.competency_id,
                "competency": r.competency.name,
                "current": curr,
                "required": r.min_score
            })
    return gaps
