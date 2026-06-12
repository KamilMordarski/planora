from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget


class DocumentPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._source = QPixmap()
        self._page_count = 1
        self._zoom = 1.0
        self._fit = True
        self._render_pending = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        controls = QHBoxLayout()
        self.info = QLabel("Podgląd")
        self.info.setObjectName("helpText")
        self.zoom_label = QLabel()
        zoom_out = QPushButton("−")
        zoom_out.setToolTip("Pomniejsz podgląd")
        fit = QPushButton("Dopasuj stronę")
        zoom_in = QPushButton("+")
        zoom_in.setToolTip("Powiększ podgląd")
        zoom_out.clicked.connect(lambda: self.change_zoom(-0.1))
        zoom_in.clicked.connect(lambda: self.change_zoom(0.1))
        fit.clicked.connect(self.fit_page)
        controls.addWidget(self.info)
        controls.addStretch()
        controls.addWidget(zoom_out)
        controls.addWidget(self.zoom_label)
        controls.addWidget(zoom_in)
        controls.addWidget(fit)
        root.addLayout(controls)

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setObjectName("documentPreviewPage")
        self.scroll = QScrollArea()
        self.scroll.setAlignment(Qt.AlignCenter)
        self.scroll.setWidget(self.label)
        self.scroll.viewport().installEventFilter(self)
        root.addWidget(self.scroll, 1)

    def set_image(self, image, page_count: int = 1):
        rgb = image.convert("RGB")
        data = rgb.tobytes("raw", "RGB")
        qimage = QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format_RGB888).copy()
        self._source = QPixmap.fromImage(qimage)
        self._page_count = max(1, page_count)
        self._schedule_render()

    def set_error(self, message: str):
        self._source = QPixmap()
        self.label.setText(message)
        self.label.adjustSize()
        self.info.setText("Nie udało się przygotować podglądu")

    def change_zoom(self, delta: float):
        self._fit = False
        self._zoom = max(0.2, min(2.5, self._zoom + delta))
        self._render()

    def fit_page(self):
        self._fit = True
        self._schedule_render()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit:
            self._schedule_render()

    def showEvent(self, event):
        super().showEvent(event)
        if self._fit:
            self._schedule_render()

    def eventFilter(self, watched, event):
        if watched is self.scroll.viewport() and event.type() == QEvent.Resize and self._fit:
            self._schedule_render()
        return super().eventFilter(watched, event)

    def _schedule_render(self):
        if self._render_pending:
            return
        self._render_pending = True
        QTimer.singleShot(0, self._render)

    def _render(self):
        self._render_pending = False
        if self._source.isNull():
            return
        if self._fit:
            viewport = self.scroll.viewport().size()
            target_width = max(240, viewport.width() - 24)
            target_height = max(240, viewport.height() - 24)
            pixmap = self._source.scaled(
                target_width,
                target_height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            percent = round(100 * pixmap.width() / self._source.width())
            mode = "dopasowano"
        else:
            width = max(1, round(self._source.width() * self._zoom))
            pixmap = self._source.scaledToWidth(width, Qt.SmoothTransformation)
            percent = round(self._zoom * 100)
            mode = "powiększenie"
        self.label.setText("")
        self.label.setPixmap(pixmap)
        self.label.resize(pixmap.size())
        self.zoom_label.setText(f"{percent}%")
        self.info.setText(f"Strona 1 z {self._page_count} · {mode}")
