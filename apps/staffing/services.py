from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from apps.staffing.models import CandidateMatch, Vacancy
from apps.users.models import OfficerProfile
from apps.directory.models import PositionRequirement, CompetencyRequirement
from apps.assessments.models import CompetencyRating


def _years_between(d1: date, d2: date) -> float:
    return (d2 - d1).days / 365.25


def _round2(x: float) -> float:
    return float(Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def score_officer_for_vacancy(officer: OfficerProfile, vacancy: Vacancy) -> tuple[float, list]:
    """
    Простой скоринг:
    - Базовый блок требований (ранг, выслуга) = 50%
    - Компетенции по позиции = 50%
    Гэпы накапливаем в списке.
    """
    pos = vacancy.position
    today = date.today()
    gaps = []

    # --- базовые требования
    base_req = PositionRequirement.objects.filter(position=pos).first()
    base_score = 0.0
    base_parts = 0

    if base_req:
        # ранг: сравниваем order
        if officer.rank and base_req.min_rank:
            base_parts += 1
            ok = officer.rank.order >= base_req.min_rank.order
            base_score += 1.0 if ok else 0.0
            if not ok:
                gaps.append({"type": "RANK", "required": base_req.min_rank.name,
                             "current": officer.rank.name if officer.rank else None})

        # стаж
        if officer.service_start_date:
            base_parts += 1
            years = _years_between(officer.service_start_date, today)
            ok = years >= base_req.min_service_years
            base_score += 1.0 if ok else (years / max(1, base_req.min_service_years))
            if not ok:
                gaps.append({"type": "SERVICE_YEARS", "required": base_req.min_service_years,
                             "current": round(years, 1)})

    base_score = (base_score / base_parts) if base_parts else 1.0

    # --- компетенции
    comp_reqs = list(CompetencyRequirement.objects.filter(position=pos))
    if comp_reqs:
        # последние рейтинги офицера
        own = {r.competency_id: float(r.score) for r in
               CompetencyRating.objects.filter(officer=officer).order_by("-assessed_at")}
        got = 0.0
        for cr in comp_reqs:
            req = cr.min_score
            cur = own.get(cr.competency_id, 0.0)
            # нормируем 1..5
            part = min(cur / max(1, req), 1.0)
            got += part
            if cur < req:
                gaps.append({"type": "COMPETENCY", "competency": cr.competency.name,
                             "required": req, "current": cur, "mandatory": cr.is_mandatory})
        comp_score = got / len(comp_reqs)
    else:
        comp_score = 1.0

    # финальный вес
    final = 0.5 * base_score + 0.5 * comp_score
    return _round2(final * 100.0), gaps


def build_matches_for_vacancy(vacancy: Vacancy) -> list[CandidateMatch]:
    """
    Пересчитать CandidateMatch для вакансии по всем офицерам из того же юнита.
    """
    qs = OfficerProfile.objects.filter(unit=vacancy.unit)
    created = []
    for off in qs:
        score, gaps = score_officer_for_vacancy(off, vacancy)
        obj, _ = CandidateMatch.objects.update_or_create(
            vacancy=vacancy, officer=off,
            defaults={"match_score": score, "gaps_json": gaps}
        )
        created.append(obj)
    return created
