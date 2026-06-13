import os
import tempfile
from math import ceil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from app.templates.field_service_groups.default_project import ROLE_ASSISTANT, ROLE_LEADER


PAGE_W, PAGE_H = 3508, 2480
MARGIN_X = 120
TOP = 105
BOTTOM = 100
TITLE_H = 230
GROUP_HEADER_H = 95
ROW_H = 82
NUMBER_W = 105
MAX_GROUPS_PER_PAGE = 5
MAX_ROWS_PER_PAGE = (PAGE_H - TOP - TITLE_H - GROUP_HEADER_H - BOTTOM) // ROW_H

INK = (31, 42, 51)
MUTED = (91, 105, 116)
GRID = (113, 126, 136)
HEADER = (60, 74, 87)
LEADER_FILL = (211, 224, 231)
ASSISTANT_FILL = (237, 242, 245)
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


class FieldServiceGroupsRenderer:
    @staticmethod
    def _size(draw, text, selected_font):
        box = draw.textbbox((0, 0), str(text), font=selected_font)
        return box[2] - box[0], box[3] - box[1]

    @classmethod
    def _fit_font(cls, draw, text, width, start_size, bold=False, minimum=17):
        size = start_size
        while size > minimum:
            selected = _font(size, bold)
            if cls._size(draw, text, selected)[0] <= width:
                return selected
            size -= 1
        return _font(minimum, bold)

    @classmethod
    def _center(cls, draw, box, text, size, bold=False, fill=INK):
        x1, y1, x2, y2 = box
        selected = cls._fit_font(draw, str(text), x2 - x1 - 18, size, bold)
        width, height = cls._size(draw, text, selected)
        draw.text((x1 + (x2 - x1 - width) / 2, y1 + (y2 - y1 - height) / 2 - 3), str(text), font=selected, fill=fill)

    @classmethod
    def _member_cell(cls, draw, box, value):
        role = value.get("role", "member") if isinstance(value, dict) else "member"
        name = value.get("name", "") if isinstance(value, dict) else ""
        if role == ROLE_LEADER:
            fill, bold, role_label = LEADER_FILL, True, "GRUPOWY"
        elif role == ROLE_ASSISTANT:
            fill, bold, role_label = ASSISTANT_FILL, True, "ASYSTENT"
        else:
            fill, bold, role_label = WHITE, False, ""
        draw.rectangle(box, fill=fill, outline=GRID, width=2)
        x1, y1, x2, y2 = box
        if role_label and name:
            selected = cls._fit_font(draw, name, x2 - x1 - 18, 29, bold)
            width, height = cls._size(draw, name, selected)
            draw.text((x1 + (x2 - x1 - width) / 2, y1 + 12), name, font=selected, fill=INK)
            role_font = _font(14, True)
            role_width, _ = cls._size(draw, role_label, role_font)
            draw.text((x1 + (x2 - x1 - role_width) / 2, y2 - 24), role_label, font=role_font, fill=MUTED)
        else:
            cls._center(draw, box, name, 29, bold)

    @classmethod
    def _page_specs(cls, groups):
        if not groups:
            return [([], 0)]
        specs = []
        for start in range(0, len(groups), MAX_GROUPS_PER_PAGE):
            chunk = groups[start : start + MAX_GROUPS_PER_PAGE]
            longest = max((len(group.get("members", [])) for group in chunk), default=0)
            page_count = max(1, ceil(longest / MAX_ROWS_PER_PAGE))
            for page in range(page_count):
                specs.append((chunk, page * MAX_ROWS_PER_PAGE))
        return specs

    @classmethod
    def render_pages(cls, project):
        pages = []
        congregation = project.get("congregation", "")
        title = project.get("title", "")
        for groups, row_offset in cls._page_specs(project.get("groups", [])):
            image = Image.new("RGB", (PAGE_W, PAGE_H), WHITE)
            draw = ImageDraw.Draw(image)
            cls._center(draw, (MARGIN_X, TOP, PAGE_W - MARGIN_X, TOP + 105), congregation, 62, True)
            cls._center(draw, (MARGIN_X, TOP + 110, PAGE_W - MARGIN_X, TOP + TITLE_H), title, 45, False)

            table_top = TOP + TITLE_H
            table_width = PAGE_W - MARGIN_X * 2
            draw.rectangle((MARGIN_X, table_top, MARGIN_X + NUMBER_W, table_top + GROUP_HEADER_H), fill=ASSISTANT_FILL, outline=GRID, width=2)
            cls._center(draw, (MARGIN_X, table_top, MARGIN_X + NUMBER_W, table_top + GROUP_HEADER_H), "Lp.", 25, True)
            group_width = (table_width - NUMBER_W) / max(1, len(groups))
            for group_index, group_value in enumerate(groups):
                x1 = round(MARGIN_X + NUMBER_W + group_index * group_width)
                x2 = round(MARGIN_X + NUMBER_W + (group_index + 1) * group_width)
                draw.rectangle((x1, table_top, x2, table_top + GROUP_HEADER_H), fill=HEADER, outline=GRID, width=2)
                suffix = " (cd.)" if row_offset else ""
                cls._center(draw, (x1, table_top, x2, table_top + GROUP_HEADER_H), group_value.get("name", "") + suffix, 34, True, WHITE)

            for row_index in range(MAX_ROWS_PER_PAGE):
                y1 = table_top + GROUP_HEADER_H + row_index * ROW_H
                y2 = y1 + ROW_H
                draw.rectangle((MARGIN_X, y1, MARGIN_X + NUMBER_W, y2), fill=WHITE, outline=GRID, width=2)
                cls._center(draw, (MARGIN_X, y1, MARGIN_X + NUMBER_W, y2), row_offset + row_index + 1, 25, True)
                for group_index, group_value in enumerate(groups):
                    x1 = round(MARGIN_X + NUMBER_W + group_index * group_width)
                    x2 = round(MARGIN_X + NUMBER_W + (group_index + 1) * group_width)
                    members = group_value.get("members", [])
                    member = members[row_offset + row_index] if row_offset + row_index < len(members) else {}
                    cls._member_cell(draw, (x1, y1, x2, y2), member)
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
        page_size = landscape(A4)
        pdf = canvas.Canvas(path, pagesize=page_size)
        for image in cls.render_pages(project):
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp:
                temp_path = temp.name
            try:
                image.save(temp_path, quality=95)
                pdf.drawImage(temp_path, 0, 0, width=page_size[0], height=page_size[1])
                pdf.showPage()
            finally:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
        pdf.save()
