import os
import re
import tempfile
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


PAGE_W, PAGE_H = 2480, 3508
MARGIN_X = 225
TOP = 180
BOTTOM = 190
CONTENT_W = PAGE_W - MARGIN_X * 2
TIME_W = 155
PERSON_W = 525
BLACK = (25, 25, 25)
GRAY = (90, 90, 90)
MANUAL_NUMBER_PREFIX = re.compile(r"^\s*\d+\.\s*")


def _find_font(names):
    for name in names:
        if os.path.exists(name):
            return name
    return ""


REGULAR_PATH = _find_font(
    [
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
)
BOLD_PATH = _find_font(
    [
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
)


def _font(size, bold=False):
    path = BOLD_PATH if bold else REGULAR_PATH
    return ImageFont.truetype(path, size) if path else ImageFont.load_default()


F_TITLE = _font(56, True)
F_HEADER = _font(38, True)
F_META = _font(29)
F_META_BOLD = _font(29, True)
F_SECTION = _font(29, True)
F_ITEM = _font(29)
F_ROLE = _font(20)
F_SPECIAL_TITLE = _font(92, True)
F_SPECIAL_SUBTITLE = _font(55)

POLISH_WEEKDAYS = {
    0: "poniedziałek",
    1: "wtorek",
    2: "środa",
    3: "czwartek",
    4: "piątek",
    5: "sobota",
    6: "niedziela",
}
POLISH_MONTHS = {
    1: "stycznia",
    2: "lutego",
    3: "marca",
    4: "kwietnia",
    5: "maja",
    6: "czerwca",
    7: "lipca",
    8: "sierpnia",
    9: "września",
    10: "października",
    11: "listopada",
    12: "grudnia",
}


def _parse_date(value):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _date_text(value):
    parsed = _parse_date(value)
    if not parsed:
        return str(value)
    return f"{POLISH_WEEKDAYS[parsed.weekday()]}, {parsed.day} {POLISH_MONTHS[parsed.month]} {parsed.year}"


def numbered_program_title(number: int, title: str) -> str:
    """Add the displayed program number without changing project data."""
    clean_title = MANUAL_NUMBER_PREFIX.sub("", str(title or ""), count=1).strip()
    return f"{number}. {clean_title}".rstrip()


class MidweekMeetingRenderer:
    @staticmethod
    def _size(draw, text, selected_font):
        box = draw.textbbox((0, 0), str(text), font=selected_font)
        return box[2] - box[0], box[3] - box[1]

    @classmethod
    def _right(cls, draw, x, y, text, selected_font, fill=BLACK):
        width, _ = cls._size(draw, text, selected_font)
        draw.text((x - width, y), str(text), font=selected_font, fill=fill)

    @staticmethod
    def _hex_color(value):
        value = str(value or "#666666").lstrip("#")
        try:
            return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))
        except ValueError:
            return (102, 102, 102)

    @classmethod
    def _draw_people(cls, draw, y, item):
        x = MARGIN_X + CONTENT_W - PERSON_W
        people = [
            (item.get("role_1", ""), item.get("participant_1", "")),
            (item.get("role_2", ""), item.get("participant_2", "")),
        ]
        line_y = y
        for index, (role, person) in enumerate(people):
            if not person:
                continue
            if role:
                draw.text((x, line_y + 7), role, font=F_ROLE, fill=GRAY)
                draw.text((x + 225, line_y), person, font=F_ITEM, fill=BLACK)
            else:
                prefix = "+ " if index == 1 else ""
                draw.text((x, line_y), prefix + person, font=F_ITEM, fill=BLACK)
            line_y += 35

    @classmethod
    def _normal_height(cls, meeting):
        item_count = sum(len(section.get("items", [])) for section in meeting.get("sections", []))
        return 285 + len(meeting.get("sections", [])) * 58 + item_count * 70 + 150

    @staticmethod
    def _special_height(meeting):
        return 1260 if meeting.get("image_path") else 650

    @classmethod
    def _meeting_height(cls, meeting):
        return cls._special_height(meeting) if meeting.get("type") == "special" else cls._normal_height(meeting)

    @classmethod
    def _draw_document_header(cls, draw, project, y):
        draw.text((MARGIN_X, y), project.get("congregation", ""), font=F_HEADER, fill=BLACK)
        cls._right(draw, MARGIN_X + CONTENT_W, y - 8, project.get("document_title", ""), F_TITLE)
        y += 62
        draw.line((MARGIN_X, y, MARGIN_X + CONTENT_W, y), fill=BLACK, width=4)
        return y + 28

    @classmethod
    def _draw_standard_line(cls, draw, y, time, title, participant_1="", participant_2="", role_1="", role_2=""):
        draw.text((MARGIN_X, y), time, font=F_META_BOLD, fill=BLACK)
        draw.text((MARGIN_X + TIME_W, y), title, font=F_ITEM, fill=BLACK)
        cls._draw_people(
            draw,
            y,
            {
                "participant_1": participant_1,
                "participant_2": participant_2,
                "role_1": role_1,
                "role_2": role_2,
            },
        )
        return y + 68

    @classmethod
    def _draw_normal(cls, draw, project, meeting, y):
        date_line = _date_text(meeting.get("date", ""))
        bible = meeting.get("bible_reading", "")
        if bible:
            date_line += f" | {bible}"
        draw.text((MARGIN_X, y), date_line, font=F_META_BOLD, fill=BLACK)
        cls._draw_people(
            draw,
            y - 8,
            {
                "participant_1": meeting.get("chairman", ""),
                "participant_2": meeting.get("opening_prayer", ""),
                "role_1": "Przewodniczący:",
                "role_2": "Modlitwa początkowa:",
            },
        )
        y += 65
        y = cls._draw_standard_line(
            draw, y, meeting.get("opening_song_time", ""), meeting.get("opening_song", "")
        )
        y = cls._draw_standard_line(
            draw, y, meeting.get("opening_comments_time", ""), meeting.get("opening_comments", "")
        )

        item_number = 1
        for section in meeting.get("sections", []):
            color = cls._hex_color(section.get("color"))
            draw.rectangle((MARGIN_X, y, MARGIN_X + CONTENT_W - PERSON_W - 15, y + 54), fill=color)
            draw.text((MARGIN_X + 12, y + 9), section.get("title", ""), font=F_SECTION, fill="white")
            y += 66
            for item in section.get("items", []):
                y = cls._draw_standard_line(
                    draw,
                    y,
                    item.get("time", ""),
                    numbered_program_title(item_number, item.get("title", "")),
                    item.get("participant_1", ""),
                    item.get("participant_2", ""),
                    item.get("role_1", ""),
                    item.get("role_2", ""),
                )
                item_number += 1
                draw.line(
                    (MARGIN_X + TIME_W, y - 8, MARGIN_X + CONTENT_W, y - 8),
                    fill=(150, 150, 150),
                    width=1,
                )

        y = cls._draw_standard_line(
            draw, y, meeting.get("closing_comments_time", ""), meeting.get("closing_comments", "")
        )
        y = cls._draw_standard_line(
            draw,
            y,
            meeting.get("closing_song_time", ""),
            meeting.get("closing_song", ""),
            meeting.get("closing_prayer", ""),
            "",
            "Modlitwa:",
            "",
        )
        draw.line((MARGIN_X, y, MARGIN_X + CONTENT_W, y), fill=BLACK, width=4)
        return y + 35

    @classmethod
    def _draw_special(cls, draw, project, meeting, y):
        draw.text((MARGIN_X, y), _date_text(meeting.get("date", "")), font=F_META_BOLD, fill=BLACK)
        y += 105
        title = meeting.get("special_title", "")
        width, _ = cls._size(draw, title, F_SPECIAL_TITLE)
        draw.text((MARGIN_X + (CONTENT_W - width) / 2, y), title, font=F_SPECIAL_TITLE, fill=BLACK)
        y += 135
        subtitle = meeting.get("special_subtitle", "")
        width, _ = cls._size(draw, subtitle, F_SPECIAL_SUBTITLE)
        draw.text((MARGIN_X + (CONTENT_W - width) / 2, y), subtitle, font=F_SPECIAL_SUBTITLE, fill=BLACK)
        y += 105

        image_path = Path(str(meeting.get("image_path", "")))
        if image_path.is_file():
            try:
                with Image.open(image_path) as source:
                    source = ImageOps.exif_transpose(source).convert("RGB")
                    target_w, target_h = CONTENT_W - 110, 820
                    source.thumbnail((target_w, target_h))
                    x = MARGIN_X + (CONTENT_W - source.width) // 2
                    canvas_y = int(y)
                    draw._image.paste(source, (x, canvas_y))
                    y += source.height + 35
            except OSError:
                pass
        return y + 40

    @classmethod
    def render_pages(cls, project):
        pages = []
        image = Image.new("RGB", (PAGE_W, PAGE_H), "white")
        draw = ImageDraw.Draw(image)
        y = cls._draw_document_header(draw, project, TOP)
        has_content = False

        for meeting in project.get("meetings", []):
            needed = cls._meeting_height(meeting)
            if has_content and y + needed > PAGE_H - BOTTOM:
                pages.append(image)
                image = Image.new("RGB", (PAGE_W, PAGE_H), "white")
                draw = ImageDraw.Draw(image)
                y = cls._draw_document_header(draw, project, TOP)
            if meeting.get("type") == "special":
                y = cls._draw_special(draw, project, meeting, y)
            else:
                y = cls._draw_normal(draw, project, meeting, y)
            has_content = True
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
