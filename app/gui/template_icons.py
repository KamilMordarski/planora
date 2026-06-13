from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap


INK = QColor("#20364d")
PAPER = QColor("#ffffff")
BACKGROUNDS = {
    "public_talk_watchtower": QColor("#e8f1fb"),
    "cleaning_attendants": QColor("#edf6f1"),
    "midweek_meeting": QColor("#fff3e2"),
    "field_service_groups": QColor("#f1edf8"),
}
ACCENTS = {
    "public_talk_watchtower": QColor("#3979b7"),
    "cleaning_attendants": QColor("#3f8061"),
    "midweek_meeting": QColor("#d18423"),
    "field_service_groups": QColor("#76619b"),
}


def template_icon(template_id: str, size: int = 96) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    scale = size / 96
    painter.scale(scale, scale)
    painter.setPen(QPen(INK, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(BACKGROUNDS.get(template_id, QColor("#eef3f8")))
    painter.drawRoundedRect(QRectF(4, 4, 88, 88), 22, 22)
    painter.setBrush(PAPER)
    painter.drawRoundedRect(QRectF(18, 18, 60, 60), 13, 13)
    painter.setBrush(Qt.NoBrush)

    accent = ACCENTS.get(template_id, QColor("#3979b7"))
    if template_id == "public_talk_watchtower":
        _public_talk(painter, accent)
    elif template_id == "cleaning_attendants":
        _cleaning(painter, accent)
    elif template_id == "midweek_meeting":
        _midweek(painter, accent)
    elif template_id == "field_service_groups":
        _groups(painter, accent)
    else:
        _midweek(painter, accent)
    painter.end()
    return pixmap


def _public_talk(painter: QPainter, accent: QColor):
    painter.setBrush(accent)
    painter.drawEllipse(QPointF(48, 32), 8, 8)
    painter.drawRoundedRect(QRectF(36, 43, 24, 8), 4, 4)
    painter.setBrush(Qt.NoBrush)
    painter.drawLine(QPointF(31, 55), QPointF(65, 55))
    painter.drawLine(QPointF(35, 55), QPointF(39, 72))
    painter.drawLine(QPointF(61, 55), QPointF(57, 72))
    painter.drawLine(QPointF(39, 72), QPointF(57, 72))
    painter.drawLine(QPointF(62, 34), QPointF(70, 27))
    painter.drawLine(QPointF(70, 27), QPointF(74, 32))


def _cleaning(painter: QPainter, accent: QColor):
    painter.setPen(QPen(INK, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawLine(QPointF(35, 26), QPointF(56, 64))
    painter.setBrush(accent)
    painter.setPen(QPen(accent, 2))
    painter.drawRoundedRect(QRectF(47, 61, 25, 9), 4, 4)
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(INK, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawLine(QPointF(28, 37), QPointF(28, 65))
    painter.drawArc(QRectF(21, 57, 14, 14), 180 * 16, 180 * 16)
    painter.setBrush(accent)
    painter.drawEllipse(QPointF(67, 33), 4, 4)
    painter.drawEllipse(QPointF(73, 43), 3, 3)


def _midweek(painter: QPainter, accent: QColor):
    painter.setBrush(accent)
    painter.setPen(QPen(accent, 3))
    painter.drawEllipse(QPointF(38, 40), 13, 13)
    painter.setPen(QPen(PAPER, 3, Qt.SolidLine, Qt.RoundCap))
    painter.drawLine(QPointF(38, 40), QPointF(38, 32))
    painter.drawLine(QPointF(38, 40), QPointF(45, 44))
    painter.setPen(QPen(INK, 3, Qt.SolidLine, Qt.RoundCap))
    for y in (31, 42, 53, 64):
        painter.drawLine(QPointF(58, y), QPointF(70, y))
    painter.setBrush(INK)
    for y in (31, 42, 53, 64):
        painter.drawEllipse(QPointF(52, y), 2, 2)


def _groups(painter: QPainter, accent: QColor):
    painter.setPen(QPen(INK, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    for x, y, radius in ((48, 31, 7), (31, 43, 6), (65, 43, 6)):
        painter.setBrush(accent if x == 48 else PAPER)
        painter.drawEllipse(QPointF(x, y), radius, radius)
    painter.setBrush(Qt.NoBrush)
    painter.drawArc(QRectF(35, 42, 26, 24), 0, 180 * 16)
    painter.drawArc(QRectF(20, 53, 22, 19), 0, 180 * 16)
    painter.drawArc(QRectF(54, 53, 22, 19), 0, 180 * 16)
