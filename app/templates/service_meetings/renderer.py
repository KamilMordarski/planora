import os
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


PAGE_W, PAGE_H = 2480, 3508
MARGIN_X = 175
CONTENT_W = PAGE_W - MARGIN_X * 2
TOP = 210
TITLE_H = 105
PERIOD_H = 75
TABLE_GAP = 85
HEADER_H = 105
ROW_H = 118
NOTE_GAP = 55
NOTE_H = 120
BOTTOM = 180
MAX_ROWS_PER_PAGE = 18
COLUMN_WIDTHS = [570, 300, 720, CONTENT_W - 1590]

FALLBACK_COLORS = {
    "header_fill": (66, 84, 102),
    "header_text": (255, 255, 255),
    "accent_fill": (219, 231, 238),
    "note_fill": (237, 243, 246),
    "text": (31, 42, 51),
    "grid": (115, 128, 140),
}
WHITE = (255, 255, 255)


def _find_font(candidates):
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return ""


REGULAR_PATH = _find_font(
    [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
)
BOLD_PATH = _find_font(
    [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
)


def _font(size, bold=False):
    path = BOLD_PATH if bold else REGULAR_PATH
    return ImageFont.truetype(path, size=size) if path else ImageFont.load_default()


def _color(value, fallback):
    text = str(value or "").strip().lstrip("#")
    if len(text) == 6:
        try:
            return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))
        except ValueError:
            pass
    return fallback


class ServiceMeetingsRenderer:
    @staticmethod
    def _size(draw, text, selected_font):
        box = draw.textbbox((0, 0), str(text), font=selected_font)
        return box[2] - box[0], box[3] - box[1]

    @classmethod
    def _fit_font(cls, draw, text, max_width, max_height, start_size, bold=False, minimum=18):
        lines = str(text).split("\n")
        for size in range(start_size, minimum - 1, -1):
            selected = _font(size, bold)
            widths = [cls._size(draw, line, selected)[0] for line in lines]
            heights = [cls._size(draw, line or "Ag", selected)[1] for line in lines]
            if max(widths or [0]) <= max_width and sum(heights) + max(0, len(lines) - 1) * 6 <= max_height:
                return selected
        return _font(minimum, bold)

    @classmethod
    def _center(cls, draw, box, text, size, bold=False, fill=(31, 42, 51)):
        x1, y1, x2, y2 = box
        text = str(text or "")
        selected = cls._fit_font(draw, text, x2 - x1 - 24, y2 - y1 - 18, size, bold)
        lines = text.split("\n")
        heights = [cls._size(draw, line or "Ag", selected)[1] for line in lines]
        total = sum(heights) + max(0, len(lines) - 1) * 6
        y = y1 + (y2 - y1 - total) / 2 - 3
        for line, height in zip(lines, heights):
            width, _ = cls._size(draw, line, selected)
            draw.text((x1 + (x2 - x1 - width) / 2, y), line, font=selected, fill=fill)
            y += height + 6

    @classmethod
    def _left(cls, draw, box, text, size, bold=False, fill=(31, 42, 51)):
        x1, y1, x2, y2 = box
        lines = str(text or "").split("\n")
        selected = cls._fit_font(draw, text, x2 - x1 - 34, y2 - y1 - 18, size, bold)
        heights = [cls._size(draw, line or "Ag", selected)[1] for line in lines]
        total = sum(heights) + max(0, len(lines) - 1) * 6
        y = y1 + (y2 - y1 - total) / 2 - 3
        for line, height in zip(lines, heights):
            draw.text((x1 + 17, y), line, font=selected, fill=fill)
            y += height + 6

    @classmethod
    def _draw_table(cls, draw, project, rows, y, colors):
        headers = project.get("headers", {})
        header_values = [
            headers.get("date", ""),
            headers.get("time", ""),
            headers.get("place", ""),
            headers.get("conductor", ""),
        ]
        x = MARGIN_X
        for width, value in zip(COLUMN_WIDTHS, header_values):
            box = (x, y, x + width, y + HEADER_H)
            draw.rectangle(box, fill=colors["header_fill"], outline=colors["grid"], width=3)
            cls._center(draw, box, value, 35, True, colors["header_text"])
            x += width
        y += HEADER_H

        for row in rows:
            values = [row.get("date", ""), row.get("time", ""), row.get("place", ""), row.get("conductor", "")]
            x = MARGIN_X
            for index, (width, value) in enumerate(zip(COLUMN_WIDTHS, values)):
                box = (x, y, x + width, y + ROW_H)
                fill = _color(row.get("date_color"), colors["accent_fill"]) if index == 0 else WHITE
                draw.rectangle(box, fill=fill, outline=colors["grid"], width=3)
                if index == 2:
                    cls._left(draw, box, value, 31, False, colors["text"])
                else:
                    cls._center(draw, box, value, 31, index in (0, 1), colors["text"])
                x += width
            y += ROW_H
        return y

    @classmethod
    def render_pages(cls, project):
        source_colors = project.get("colors", {})
        colors = {key: _color(source_colors.get(key), fallback) for key, fallback in FALLBACK_COLORS.items()}
        rows = list(project.get("meetings", []))
        chunks = [rows[index : index + MAX_ROWS_PER_PAGE] for index in range(0, len(rows), MAX_ROWS_PER_PAGE)] or [[]]
        pages = []
        for page_index, chunk in enumerate(chunks):
            image = Image.new("RGB", (PAGE_W, PAGE_H), WHITE)
            draw = ImageDraw.Draw(image)
            cls._center(draw, (MARGIN_X, TOP, PAGE_W - MARGIN_X, TOP + TITLE_H), project.get("title", ""), 61, True, colors["text"])
            period = project.get("period", "")
            if len(chunks) > 1:
                period = f"{period} · strona {page_index + 1} z {len(chunks)}".strip(" ·")
            cls._center(
                draw,
                (MARGIN_X, TOP + TITLE_H, PAGE_W - MARGIN_X, TOP + TITLE_H + PERIOD_H),
                period,
                38,
                True,
                colors["text"],
            )
            y = TOP + TITLE_H + PERIOD_H + TABLE_GAP
            y = cls._draw_table(draw, project, chunk, y, colors)
            note = project.get("note", "")
            if note and page_index == len(chunks) - 1:
                note_box = (MARGIN_X, y + NOTE_GAP, PAGE_W - MARGIN_X, min(PAGE_H - BOTTOM, y + NOTE_GAP + NOTE_H))
                draw.rounded_rectangle(note_box, radius=18, fill=colors["note_fill"])
                cls._left(draw, note_box, note, 30, True, colors["text"])
            pages.append(image)
        return pages

    @classmethod
    def export_jpg(cls, path, project):
        pages = cls.render_pages(project)
        base = Path(path)
        for index, image in enumerate(pages, start=1):
            output = base if len(pages) == 1 else base.with_name(f"{base.stem}_strona_{index}{base.suffix}")
            image.save(output, quality=95)

    @classmethod
    def export_pdf(cls, path, project):
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
