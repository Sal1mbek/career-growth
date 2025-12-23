from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser

import tempfile
import os

from apps.directory.models import Unit
from .services.docx_parser import parse_docx_to_json
from .services.qualification_importer import QualificationImporter


class DocumentParsingViewSet(viewsets.ViewSet):
    """
    Парсинг DOCX → JSON
    Парсинг DOCX → БД (PositionQualification)
    """
    parser_classes = [MultiPartParser]

    @action(detail=False, methods=["post"], url_path="parse-docx")
    def parse_docx(self, request):
        """
        Только парсинг, без сохранения
        """
        file = request.FILES.get("file")

        if not file:
            return Response(
                {"detail": "Файл не передан"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not file.name.lower().endswith(".docx"):
            return Response(
                {"detail": "Поддерживаются только .docx файлы"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tmp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".docx",
                delete=False
            ) as tmp:
                tmp_path = tmp.name
                for chunk in file.chunks():
                    tmp.write(chunk)

            parsed_data = parse_docx_to_json(tmp_path)

            return Response({
                "count": len(parsed_data),
                "results": parsed_data,
            })

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    # ================================
    # 🔥 ГЛАВНЫЙ ENDPOINT
    # ================================
    @action(detail=False, methods=["post"], url_path="parse-and-save-docx")
    def parse_and_save_docx(self, request):
        """
        Парсинг DOCX → сохранение в PositionQualification
        """
        file = request.FILES.get("file")
        unit_id = request.data.get("unit")

        if not file:
            return Response(
                {"detail": "Файл не передан"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not unit_id:
            return Response(
                {"detail": "Не передан unit"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not file.name.lower().endswith(".docx"):
            return Response(
                {"detail": "Поддерживаются только .docx файлы"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            unit = Unit.objects.get(id=unit_id)
        except Unit.DoesNotExist:
            return Response(
                {"detail": "Unit не найден"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tmp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".docx",
                delete=False
            ) as tmp:
                tmp_path = tmp.name
                for chunk in file.chunks():
                    tmp.write(chunk)

            parsed_data = parse_docx_to_json(tmp_path)

            created = QualificationImporter.import_from_parsed(
                parsed_data,
                unit=unit,
                source=file.name,
            )

            return Response({
                "positions": len(set(i["position_title"] for i in parsed_data)),
                "created_qualifications": created,
            })

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
