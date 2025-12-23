from docx import Document
from typing import List, Dict, Optional
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph
import re


CATEGORY_MAP = {
    "образование": "EDUCATION",
    "опыт": "EXPERIENCE",
    "функцион": "FUNCTIONS",
    "компетен": "COMPETENCY",
}

BAD_TITLE_PATTERNS = [
    "квалификацион",
    "к воинским должностям",
    "(наименование должности)",
    "требования",
]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def detect_category(cell_text: str) -> Optional[str]:
    t = normalize(cell_text)
    for key, category in CATEGORY_MAP.items():
        if key in t:
            return category
    return None


def is_valid_position_title(text: str) -> bool:
    if not text:
        return False

    t = normalize(text)

    for bad in BAD_TITLE_PATTERNS:
        if bad in t:
            return False

    if len(text) > 120:
        return False

    if text.isupper():
        return False

    return True


def iter_blocks(doc: Document):
    """
    Итерация по элементам документа в правильном порядке:
    Paragraph / Table
    """
    for child in doc.element.body.iterchildren():
        if isinstance(child, CT_P):
            p = Paragraph(child, doc)
            yield ("paragraph", p)
        elif isinstance(child, CT_Tbl):
            t = Table(child, doc)
            yield ("table", t)


def parse_docx_to_json(path: str) -> List[Dict]:
    doc = Document(path)
    results: List[Dict] = []

    current_position_title: Optional[str] = None

    for block_type, block in iter_blocks(doc):

        # 1️⃣ Нашли должность
        if block_type == "paragraph":
            text = block.text.strip()
            if is_valid_position_title(text):
                current_position_title = text

        # 2️⃣ Нашли таблицу — она ПРИНАДЛЕЖИТ предыдущей должности
        elif block_type == "table" and current_position_title:
            order = 1

            for row in block.rows:
                if len(row.cells) < 2:
                    continue

                left = row.cells[0].text.strip()
                right = row.cells[1].text.strip()

                if not left or not right:
                    continue

                category = detect_category(left)
                if not category:
                    continue

                results.append({
                    "position_title": current_position_title,
                    "category": category,
                    "order": order,
                    "text": right,
                    "source": "docx",
                })

                order += 1

    return results
