import os
import tempfile
from datetime import date
from math import ceil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


PAGE_W, PAGE_H = 2480, 3508
INK = (14, 69, 108)
GRID = (20, 20, 20)
WHITE = (255, 255, 255)
MARGIN_X = 175
TABLE_W = PAGE_W - MARGIN_X * 2
TOP_Y = 175
TITLE_H = 215
TOP_HEADER_H = 155
WEEK_ROW_H = 112
SECTION_TITLE_H = 105
ATTENDANT_HEADER_H = 88
ATTENDANT_ROW_H = 65
MAX_WEEK_ROWS = 10
MAX_ATTENDANT_ROWS = 20

MONTHS = {
    1: "Styczeń",
    2: "Luty",
    3: "Marzec",
    4: "Kwiecień",
    5: "Maj",
    6: "Czerwiec",
    7: "Lipiec",
    8: "Sierpień",
    9: "Wrzesień",
    10: "Październik",
    11: "Listopad",
    12: "Grudzień",
}


def _find_font(candidates: list[str]) -> str:
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return ""


SERIF = _find_font(
    [
        "C:/Windows/Fonts/georgia.ttf",
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    ]
)
SERIF_BOLD_ITALIC = _find_font(
    [
        "C:/Windows/Fonts/georgiaz.ttf",
        "/System/Library/Fonts/Supplemental/Georgia Bold Italic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-BoldItalic.ttf",
    ]
)


def _font(size: int, bold_italic=False):
    path = SERIF_BOLD_ITALIC if bold_italic else SERIF
    return ImageFont.truetype(path, size=size) if path else ImageFont.load_default()


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _date_range_text(start_value: str, end_value: str) -> str:
    start = _parse_date(start_value)
    end = _parse_date(end_value)
    if not start or not end:
        return ""
    if start > end:
        start, end = end, start
    if start.month == end.month:
        return f"{start.day:02d}-{end.day:02d}\n{MONTHS[end.month]}"
    return f"{start.day:02d}-{end.day:02d}\n{MONTHS[start.month]}/{MONTHS[end.month]}"


def _meeting_date_text(value: str) -> str:
    parsed = _parse_date(value)
    return f"{parsed.month}/{parsed.day}/{parsed.year}" if parsed else ""


class CleaningAttendantsRenderer:
    @staticmethod
    def _text_size(draw, text, selected_font):
        box = draw.textbbox((0, 0), str(text), font=selected_font)
        return box[2] - box[0], box[3] - box[1]

    @classmethod
    def _fit_font(cls, draw, text, max_width, max_height, start_size, bold_italic=False):
        size = start_size
        while size > 18:
            selected = _font(size, bold_italic)
            lines = str(text).split("\n")
            widths = [cls._text_size(draw, line, selected)[0] for line in lines]
            heights = [cls._text_size(draw, line or "Ag", selected)[1] for line in lines]
            if max(widths or [0]) <= max_width and sum(heights) + max(0, len(lines) - 1) * 5 <= max_height:
                return selected
            size -= 2
        return _font(size, bold_italic)

    @classmethod
    def _center_text(cls, draw, box, text, size=36, bold_italic=False, fill=INK):
        x1, y1, x2, y2 = box
        text = str(text)
        selected = cls._fit_font(draw, text, x2 - x1 - 20, y2 - y1 - 12, size, bold_italic)
        lines = text.split("\n")
        heights = [cls._text_size(draw, line or "Ag", selected)[1] for line in lines]
        total_height = sum(heights) + max(0, len(lines) - 1) * 5
        y = y1 + (y2 - y1 - total_height) / 2 - 2
        for line, height in zip(lines, heights):
            width, _ = cls._text_size(draw, line, selected)
            draw.text((x1 + (x2 - x1 - width) / 2, y), line, font=selected, fill=fill)
            y += height + 5

    @staticmethod
    def _rect(draw, box, width=3):
        draw.rectangle(box, outline=GRID, width=width)

    @classmethod
    def _draw_row(cls, draw, y, height, widths, values, font_size=34, bold_columns=()):
        x = MARGIN_X
        for index, (width, value) in enumerate(zip(widths, values)):
            box = (x, y, x + width, y + height)
            cls._rect(draw, box, width=2)
            cls._center_text(draw, box, value or "-", font_size, index in bold_columns)
            x += width

    @classmethod
    def _draw_top_table(cls, draw, project, rows, y):
        title = project.get("title", "PLAN SPRZĄTANIA SALI KRÓLESTWA\nI OBSŁUGI NAGŁOŚNIENIA")
        cls._rect(draw, (MARGIN_X, y, MARGIN_X + TABLE_W, y + TITLE_H), width=3)
        cls._center_text(draw, (MARGIN_X, y, MARGIN_X + TABLE_W, y + TITLE_H), title, 66, True)
        y += TITLE_H

        widths = [360, 350, 500, 430, 500]
        headers = ["DATA", "GRUPA", "SPRZĄTANIE\nSALI", "KONSOLA\nZOOM", "MIKROFONY"]
        cls._draw_row(draw, y, TOP_HEADER_H, widths, headers, 47, bold_columns=range(5))
        y += TOP_HEADER_H

        for row in rows:
            microphones = "\n".join(
                value for value in (row.get("microphone_1", ""), row.get("microphone_2", "")) if value
            )
            values = [
                _date_range_text(row.get("start_date", ""), row.get("end_date", "")),
                row.get("group", ""),
                row.get("cleaning_person", ""),
                row.get("console_person", ""),
                microphones,
            ]
            cls._draw_row(draw, y, WEEK_ROW_H, widths, values, 34, bold_columns=(1,))
            y += WEEK_ROW_H
        return y

    @classmethod
    def _draw_attendant_table(cls, draw, project, rows, y):
        title = project.get("attendant_title", "PLAN SŁUŻBY PORZĄDKOWEJ")
        cls._rect(draw, (MARGIN_X, y, MARGIN_X + TABLE_W, y + SECTION_TITLE_H), width=3)
        cls._center_text(draw, (MARGIN_X, y, MARGIN_X + TABLE_W, y + SECTION_TITLE_H), title, 61, True)
        y += SECTION_TITLE_H

        widths = [360, 890, 890]
        headers = ["DATA", "PORZĄDKOWY HOL", "PORZĄDKOWY SALA"]
        cls._draw_row(draw, y, ATTENDANT_HEADER_H, widths, headers, 43, bold_columns=range(3))
        y += ATTENDANT_HEADER_H
        for row in rows:
            values = [
                _meeting_date_text(row.get("date", "")),
                row.get("lobby_attendant", ""),
                row.get("hall_attendant", ""),
            ]
            cls._draw_row(draw, y, ATTENDANT_ROW_H, widths, values, 31)
            y += ATTENDANT_ROW_H
        return y

    @classmethod
    def render_pages(cls, project: dict) -> list[Image.Image]:
        weekly = project.get("weekly_assignments", [])
        attendants = project.get("attendant_assignments", [])
        page_count = max(1, ceil(len(weekly) / MAX_WEEK_ROWS), ceil(len(attendants) / MAX_ATTENDANT_ROWS))
        pages = []
        for page_index in range(page_count):
            image = Image.new("RGB", (PAGE_W, PAGE_H), WHITE)
            draw = ImageDraw.Draw(image)
            week_rows = weekly[page_index * MAX_WEEK_ROWS : (page_index + 1) * MAX_WEEK_ROWS]
            attendant_rows = attendants[
                page_index * MAX_ATTENDANT_ROWS : (page_index + 1) * MAX_ATTENDANT_ROWS
            ]
            y = cls._draw_top_table(draw, project, week_rows, TOP_Y)
            y += 22
            cls._draw_attendant_table(draw, project, attendant_rows, y)
            pages.append(image)
        return pages

    @classmethod
    def export_jpg(cls, path: str, project: dict):
        pages = cls.render_pages(project)
        base = Path(path)
        for index, image in enumerate(pages, start=1):
            output = base if len(pages) == 1 else base.with_name(f"{base.stem}_strona_{index}{base.suffix}")
            image.save(output, quality=95)

    @classmethod
    def export_pdf(cls, path: str, project: dict):
        pdf = canvas.Canvas(path, pagesize=A4)
        for image in cls.render_pages(project):
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp:
                temp_path = temp.name
            try:
                image.save(temp_path, quality=95)
                pdf.drawImage(temp_path, 0, 0, width=A4[0], height=A4[1])
                pdf.showPage()
            finally:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
        pdf.save()
