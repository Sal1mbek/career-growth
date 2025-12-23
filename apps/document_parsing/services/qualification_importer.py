from typing import List, Dict
from django.db import transaction
from apps.directory.models import Position, PositionQualification


class QualificationImporter:

    @staticmethod
    @transaction.atomic
    def import_from_parsed(
        parsed_items: List[Dict],
        *,
        unit,
        source: str = "docx"
    ):
        created = 0

        for item in parsed_items:
            code = QualificationImporter._make_code(item["position_title"])

            position, _ = Position.objects.get_or_create(
                unit=unit,
                code=code,
                defaults={
                    "title": item["position_title"]
                }
            )

            # защита от дублей требований
            PositionQualification.objects.filter(
                position=position,
                category=item["category"],
                order=item["order"],
            ).delete()

            PositionQualification.objects.create(
                position=position,
                category=item["category"],
                text=item["text"],
                order=item["order"],
                source=source,
            )

            created += 1

        return created

    @staticmethod
    def _make_code(title: str) -> str:
        return (
            title.upper()
            .replace(" ", "_")
            .replace("(", "")
            .replace(")", "")
        )[:50]
