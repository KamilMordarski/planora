from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QMessageBox
from PIL import ImageEnhance, ImageFilter, ImageOps
from PIL.ImageQt import ImageQt


def _load_print_settings(settings: dict | None = None) -> dict:
    if settings is not None:
        return dict(settings)
    try:
        from app.core.project_io import ProjectIO

        return ProjectIO.load_settings()
    except Exception:
        return {}


def _normalized_print_settings(settings: dict | None = None) -> dict:
    settings = _load_print_settings(settings)
    return {
        "print_text_weight": settings.get("print_text_weight", "normal"),
        "print_contrast": max(80, min(150, int(settings.get("print_contrast", 100)))),
        "print_scale": max(80, min(100, int(settings.get("print_scale", 100)))),
        "print_grayscale": bool(settings.get("print_grayscale", False)),
        "print_smooth_scaling": bool(settings.get("print_smooth_scaling", True)),
    }


def _prepare_print_image(image, settings: dict | None = None):
    options = _normalized_print_settings(settings)
    prepared = image.convert("RGB")
    if options["print_grayscale"]:
        prepared = ImageOps.grayscale(prepared).convert("RGB")

    contrast = options["print_contrast"]
    if contrast != 100:
        prepared = ImageEnhance.Contrast(prepared).enhance(contrast / 100)

    weight = options["print_text_weight"]
    passes = {"normal": 0, "bold": 1, "extra_bold": 2}.get(weight, 0)
    for _ in range(passes):
        prepared = prepared.filter(ImageFilter.MinFilter(3))
    return prepared


def print_pages(parent, pages, title="Planora", settings: dict | None = None) -> bool:
    pages = list(pages)
    if not pages:
        QMessageBox.information(parent, "Drukowanie", "Dokument nie zawiera stron do wydrukowania.")
        return False

    options = _normalized_print_settings(settings)
    printer = QPrinter(QPrinter.HighResolution)
    printer.setDocName(title)
    dialog = QPrintDialog(printer, parent)
    dialog.setWindowTitle("Drukuj dokument")
    if dialog.exec() != QPrintDialog.Accepted:
        return False

    painter = QPainter()
    if not painter.begin(printer):
        QMessageBox.warning(parent, "Błąd drukowania", "Nie udało się rozpocząć drukowania.")
        return False
    try:
        painter.setRenderHint(QPainter.SmoothPixmapTransform, options["print_smooth_scaling"])
        page_rect = printer.pageLayout().paintRectPixels(printer.resolution())
        scale = options["print_scale"] / 100
        for index, image in enumerate(pages):
            prepared = _prepare_print_image(image, options)
            pixmap = QPixmap.fromImage(ImageQt(prepared.convert("RGBA")))
            scaled = pixmap.size().scaled(page_rect.size(), Qt.KeepAspectRatio)
            scaled = QSize(max(1, round(scaled.width() * scale)), max(1, round(scaled.height() * scale)))
            target = QRect(
                page_rect.x() + (page_rect.width() - scaled.width()) // 2,
                page_rect.y() + (page_rect.height() - scaled.height()) // 2,
                scaled.width(),
                scaled.height(),
            )
            painter.drawPixmap(target, pixmap)
            if index < len(pages) - 1:
                printer.newPage()
    finally:
        painter.end()
    return True


def print_project(parent, renderer, project: dict, title="Planora", settings: dict | None = None) -> bool:
    try:
        return print_pages(parent, renderer.render_pages(project), title, settings)
    except Exception as exc:
        QMessageBox.warning(parent, "Błąd drukowania", str(exc))
        return False
