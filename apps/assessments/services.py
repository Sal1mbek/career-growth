from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from apps.assessments.models import Assessment, AssessmentItem, Feedback360, CompetencyRating
from apps.users.models import OfficerProfile


def _avg(nums):
    if not nums:
        return None
    return float(Decimal(sum(nums) / len(nums)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def aggregate_assessment_to_ratings(assessment: Assessment) -> list[CompetencyRating]:
    """
    Строим агрегированные CompetencyRating из:
    - AssessmentItem (обычно выставляет командир / комиссия)
    - Feedback360.payload (dict: {competency_id: score})
    - Самооценку можно передавать как items с источником (в нашем дизайне источник — в CompetencyRating)
    """
    # 1) базовые оценки из items
    scores = defaultdict(list)  # competency_id -> [scores...]
    for it in AssessmentItem.objects.filter(assessment=assessment):
        scores[it.competency_id].append(it.score)

    # 2) 360 payload
    for fb in Feedback360.objects.filter(assessment=assessment):
        for cid, sc in (fb.payload or {}).items():
            try:
                cid_int = int(cid)
                scores[cid_int].append(int(sc))
            except Exception:
                continue

    # 3) записываем агрегаты в CompetencyRating (source='360' если были 360, иначе 'COMMANDER')
    created = []
    officer: OfficerProfile = assessment.officer
    for cid, lst in scores.items():
        avg = _avg(lst)
        if avg is None:
            continue
        created.append(
            CompetencyRating.objects.create(
                officer=officer,
                competency_id=cid,
                score=avg,
                source=CompetencyRating.RatingSource.FEEDBACK_360 if Feedback360.objects.filter(
                    assessment=assessment).exists()
                else CompetencyRating.RatingSource.COMMANDER
            )
        )
    return created
