import os
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


PAGE_W, PAGE_H = 2480, 3508
MARGIN_X = 235
TITLE_Y = 245
CONTENT_TOP = 505
TABLE_W = 2010
COL1_W = 435
COL2_W = 930
COL3_W = TABLE_W - COL1_W - COL2_W
ROW_H = 88
AFTER_TABLE_GAP = 62
SPECIAL_H = 330
LINE_COLOR = (120, 120, 120)


def find_font() -> str:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


FONT_PATH = find_font()


def font(size: int):
    if FONT_PATH:
        return ImageFont.truetype(FONT_PATH, size=size)
    return ImageFont.load_default()


F_TITLE = font(58)
F_DATE = font(48)
F_CELL = font(48)
F_SPECIAL = font(48)


class PublicTalkWatchtowerRenderer:
    @staticmethod
    def text_size(draw, text, selected_font):
        box = draw.textbbox((0, 0), text, font=selected_font)
        return box[2] - box[0], box[3] - box[1]

    @classmethod
    def draw_center(cls, draw, box, text, selected_font, fill=(0, 0, 0), line_spacing=12):
        x1, y1, x2, y2 = box
        lines = str(text).split("\n")
        total_h = sum(cls.text_size(draw, line, selected_font)[1] for line in lines)
        total_h += line_spacing * (len(lines) - 1)
        y = y1 + (y2 - y1 - total_h) / 2 - 4
        for line in lines:
            width, height = cls.text_size(draw, line, selected_font)
            draw.text((x1 + (x2 - x1 - width) / 2, y), line, font=selected_font, fill=fill)
            y += height + line_spacing

    @classmethod
    def draw_left(cls, draw, box, text, selected_font, pad=14, fill=(0, 0, 0)):
        x1, y1, _x2, y2 = box
        lines = str(text).split("\n")
        height = sum(cls.text_size(draw, line, selected_font)[1] for line in lines)
        height += 10 * (len(lines) - 1)
        y = y1 + (y2 - y1 - height) / 2 - 4
        for line in lines:
            draw.text((x1 + pad, y), line, font=selected_font, fill=fill)
            y += cls.text_size(draw, line, selected_font)[1] + 10

    @classmethod
    def draw_right(cls, draw, box, text, selected_font, pad=10, fill=(0, 0, 0)):
        _x1, y1, x2, y2 = box
        width, height = cls.text_size(draw, text, selected_font)
        draw.text((x2 - pad - width, y1 + (y2 - y1 - height) / 2 - 4), text, font=selected_font, fill=fill)

    @classmethod
    def wrap_text(cls, draw, text, selected_font, max_width):
        out = []
        for paragraph in str(text).split("\n"):
            words = paragraph.split()
            if not words:
                out.append("")
                continue
            line = words[0]
            for word in words[1:]:
                test = line + " " + word
                if cls.text_size(draw, test, selected_font)[0] <= max_width:
                    line = test
                else:
                    out.append(line)
                    line = word
            out.append(line)
        return "\n".join(out)

    @staticmethod
    def paginate(weeks):
        pages, page, y = [], [], CONTENT_TOP
        for week in weeks:
            content_height = SPECIAL_H if week.get("type") == "special" else ROW_H * 4
            needed = 85 + content_height + AFTER_TABLE_GAP
            if page and y + needed > PAGE_H - 210:
                pages.append(page)
                page, y = [], CONTENT_TOP
            page.append(week)
            y += needed
        if page:
            pages.append(page)
        return pages or [[]]

    @classmethod
    def render_page(cls, title: str, weeks: list[dict[str, Any]]) -> Image.Image:
        image = Image.new("RGB", (PAGE_W, PAGE_H), "white")
        draw = ImageDraw.Draw(image)
        cls.draw_center(draw, (0, TITLE_Y, PAGE_W, TITLE_Y + 80), title, F_TITLE)
        y = CONTENT_TOP
        x = MARGIN_X

        for week in weeks:
            draw.text((x, y), week.get("date", ""), font=F_DATE, fill=(0, 0, 0))
            y += 83
            if week.get("type") == "special":
                cls.draw_center(
                    draw,
                    (x, y + 65, x + TABLE_W, y + SPECIAL_H - 50),
                    week.get("special_text", ""),
                    F_SPECIAL,
                    line_spacing=16,
                )
                y += SPECIAL_H + AFTER_TABLE_GAP
                continue

            table_y = y
            row_heights = [ROW_H, ROW_H, ROW_H * 1.75, ROW_H]
            total_h = int(sum(row_heights))
            draw.rectangle((x, table_y, x + TABLE_W, table_y + total_h), outline=LINE_COLOR, width=2)
            draw.line((x + COL1_W, table_y, x + COL1_W, table_y + total_h), fill=LINE_COLOR, width=2)
            draw.line(
                (x + COL1_W + COL2_W, table_y, x + COL1_W + COL2_W, table_y + total_h),
                fill=LINE_COLOR,
                width=2,
            )
            yy = table_y
            for row_height in row_heights[:-1]:
                yy += int(row_height)
                draw.line((x, yy, x + TABLE_W, yy), fill=LINE_COLOR, width=2)

            labels = ["Przewodniczący:", "Wykład:", "Strażnica:", "Lektor:"]
            middle_values = ["", week.get("lecture_topic", ""), week.get("watchtower_topic", ""), ""]
            right_values = [
                week.get("chairman", ""),
                week.get("lecturer", ""),
                week.get("watchtower_conductor", ""),
                week.get("reader", ""),
            ]
            yy = table_y
            for index, row_height in enumerate(row_heights):
                row_height = int(row_height)
                left_box = (x, yy, x + COL1_W, yy + row_height)
                middle_box = (x + COL1_W, yy, x + COL1_W + COL2_W, yy + row_height)
                right_box = (x + COL1_W + COL2_W, yy, x + TABLE_W, yy + row_height)
                cls.draw_right(draw, left_box, labels[index], F_CELL)
                wrapped = cls.wrap_text(draw, middle_values[index], F_CELL, COL2_W - 40)
                cls.draw_center(draw, middle_box, wrapped, F_CELL, line_spacing=10)
                cls.draw_left(draw, right_box, right_values[index], F_CELL)
                yy += row_height
            y += total_h + AFTER_TABLE_GAP
        return image

    @classmethod
    def export_jpg(cls, path: str, project: dict):
        pages = cls.paginate(project.get("weeks", []))
        if len(pages) == 1:
            cls.render_page(project.get("title", ""), pages[0]).save(path, quality=95)
            return
        base = Path(path)
        for index, page in enumerate(pages, start=1):
            output = base.with_name(f"{base.stem}_strona_{index}{base.suffix}")
            cls.render_page(project.get("title", ""), page).save(output, quality=95)

    @classmethod
    def export_pdf(cls, path: str, project: dict):
        pdf = canvas.Canvas(path, pagesize=A4)
        for page in cls.paginate(project.get("weeks", [])):
            image = cls.render_page(project.get("title", ""), page)
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
