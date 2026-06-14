from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QMessageBox
from PIL.ImageQt import ImageQt


def print_pages(parent, pages, title="Planora") -> bool:
    pages = list(pages)
    if not pages:
        QMessageBox.information(parent, "Drukowanie", "Dokument nie zawiera stron do wydrukowania.")
        return False

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
        page_rect = printer.pageLayout().paintRectPixels(printer.resolution())
        for index, image in enumerate(pages):
            pixmap = QPixmap.fromImage(ImageQt(image.convert("RGBA")))
            scaled = pixmap.size().scaled(page_rect.size(), Qt.KeepAspectRatio)
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


def print_project(parent, renderer, project: dict, title="Planora") -> bool:
    try:
        return print_pages(parent, renderer.render_pages(project), title)
    except Exception as exc:
        QMessageBox.warning(parent, "Błąd drukowania", str(exc))
        return False
