from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from apps.users.models import OfficerProfile
from apps.directory.models import Position, PositionRequirement, CompetencyRequirement
from apps.assessments.models import CompetencyRating

MODEL_VERSION = "v0.1-heuristic"

def _round2(x: float) -> float:
    return float(Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def _years(d1, d2) -> float:
    return (d2 - d1).days / 365.25

def forecast_officer_to_position(officer: OfficerProfile, position: Position) -> tuple[float, int]:
    """Возвращает (probability %, horizon_months)."""
    today = date.today()

    # --- Блок 1. Базовые требования (50%)
    base_req = PositionRequirement.objects.filter(position=position).first()
    base_score = 1.0
    if base_req:
        parts = 0
        got = 0.0
        # ранг
        if officer.rank and base_req.min_rank:
            parts += 1
            got += 1.0 if officer.rank.order >= base_req.min_rank.order else 0.6  # чуть штрафуем
        # стаж
        if officer.service_start_date and base_req.min_service_years:
            parts += 1
            y = _years(officer.service_start_date, today)
            if y >= base_req.min_service_years:
                got += 1.0
            else:
                got += max(0.3, y / max(1, base_req.min_service_years))  # не ниже 0.3
        base_score = (got / parts) if parts else 1.0

    # --- Блок 2. Компетенции (50%)
    comp_reqs = list(CompetencyRequirement.objects.filter(position=position))
    comp_score = 1.0
    if comp_reqs:
        latest = {r.competency_id: float(r.score)
                  for r in CompetencyRating.objects.filter(officer=officer).order_by("-assessed_at")}
        got = 0.0
        for cr in comp_reqs:
            req = float(cr.min_score or 1)
            cur = latest.get(cr.competency_id, 0.0)
            part = min(cur / req, 1.0)
            # обязательные компетенции весим чуть выше
            got += part * (1.2 if cr.is_mandatory else 1.0)
        max_total = sum(1.2 if cr.is_mandatory else 1.0 for cr in comp_reqs)
        comp_score = got / max_total if max_total else 1.0

    prob = _round2((0.5 * base_score + 0.5 * comp_score) * 100.0)

    # --- Горизонт (чем хуже соответствие, тем длиннее)
    if prob >= 85:
        horizon = 3
    elif prob >= 70:
        horizon = 6
    elif prob >= 50:
        horizon = 12
    else:
        horizon = 18
    return prob, horizon
