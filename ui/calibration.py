"""Calibration dialog and canvas.

Pure Qt painting so the UI process never imports OpenCV. The ellipse preview
uses the same north/south/east/west math as ``tracker.geometry``.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .i18n import translate

POOL_STEPS = ["WEST", "NORTH", "EAST", "SOUTH"]
PLATFORM_STEPS = ["NW", "NE", "SE", "SW"]
POOL_COLORS = {"WEST": "#ff8c00", "NORTH": "#32cd32", "EAST": "#1e90ff", "SOUTH": "#ee3a8c"}
PLATFORM_COLORS = {"NW": "#ff64c8", "NE": "#64c8ff", "SE": "#c8ff64", "SW": "#ffc864"}
COORD_KEYS = {
    "WEST": "pool_west", "NORTH": "pool_north", "EAST": "pool_east", "SOUTH": "pool_south",
    "NW": "platform_nw", "NE": "platform_ne", "SE": "platform_se", "SW": "platform_sw",
}


def _line_intersection(p1, p2, p3, p4):
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-9:
        return None
    det1 = x1 * y2 - y1 * x2
    det2 = x3 * y4 - y3 * x4
    return ((det1 * (x3 - x4) - (x1 - x2) * det2) / denom,
            (det1 * (y3 - y4) - (y1 - y2) * det2) / denom)


def ellipse_from_nsew(west, north, east, south):
    center = _line_intersection(west, east, north, south)
    if center is None:
        cx = (west[0] + east[0] + north[0] + south[0]) / 4.0
        cy = (west[1] + east[1] + north[1] + south[1]) / 4.0
    else:
        cx, cy = center
    r1x, r1y = east[0] - cx, east[1] - cy
    r2x, r2y = north[0] - cx, north[1] - cy
    m00 = r1x * r1x + r2x * r2x
    m01 = r1x * r1y + r2x * r2y
    m11 = r1y * r1y + r2y * r2y
    trace = m00 + m11
    det = m00 * m11 - m01 * m01
    disc = math.sqrt(max(0.0, trace * trace / 4.0 - det))
    lam1 = trace / 2.0 + disc
    lam2 = trace / 2.0 - disc
    rx = round(math.sqrt(max(0.0, lam1)))
    ry = round(math.sqrt(max(0.0, lam2)))
    angle = math.degrees(math.atan2(lam1 - m00, m01)) if abs(m01) > 1e-9 else 0.0
    return round(cx), round(cy), rx, ry, angle


class CalibrationCanvas(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = QImage()
        self.pool_points: dict[str, QPointF] = {}
        self.platform_points: dict[str, QPointF] = {}
        self.phase = "pool"
        self.pool_step = 0
        self.platform_step = 0
        self.require_platform = False
        self.locked = False
        self.lang = "en"
        self.setMinimumSize(640, 420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def load_preview(self, path: str | None) -> None:
        if not path:
            return
        image = QImage(path)
        if not image.isNull():
            self.image = image
        self.update()

    def has_image(self) -> bool:
        return not self.image.isNull()

    def image_size(self):
        if self.image.isNull():
            return (1280, 720)
        return (self.image.width(), self.image.height())

    def _fit(self):
        width, height = self.image_size()
        if width <= 0 or height <= 0:
            width, height = 1280, 720
        scale = min(self.width() / width, self.height() / height)
        draw_w = width * scale
        draw_h = height * scale
        off_x = (self.width() - draw_w) / 2.0
        off_y = (self.height() - draw_h) / 2.0
        return scale, off_x, off_y

    def widget_to_image(self, point: QPointF) -> QPointF | None:
        scale, off_x, off_y = self._fit()
        if scale <= 0:
            return None
        return QPointF((point.x() - off_x) / scale, (point.y() - off_y) / scale)

    def image_to_widget(self, point) -> QPointF:
        scale, off_x, off_y = self._fit()
        return QPointF(point[0] * scale + off_x, point[1] * scale + off_y)

    def mousePressEvent(self, event):
        if self.locked or event.button() != Qt.MouseButton.LeftButton:
            return
        mapped = self.widget_to_image(event.position())
        if mapped is None:
            return
        width, height = self.image_size()
        if not (0 <= mapped.x() <= width and 0 <= mapped.y() <= height):
            return
        point = QPointF(round(mapped.x()), round(mapped.y()))
        if self.phase == "pool":
            if self.pool_step >= len(POOL_STEPS):
                return
            self.pool_points[POOL_STEPS[self.pool_step]] = point
            self.pool_step += 1
            if self.pool_step == len(POOL_STEPS) and self.require_platform:
                self.phase = "platform"
        else:
            if self.platform_step >= len(PLATFORM_STEPS):
                return
            self.platform_points[PLATFORM_STEPS[self.platform_step]] = point
            self.platform_step += 1
        self.update()
        self.changed.emit()

    def reset_points(self):
        self.pool_points.clear()
        self.platform_points.clear()
        self.phase = "pool"
        self.pool_step = 0
        self.platform_step = 0
        self.update()
        self.changed.emit()

    def prefill(self, points: dict):
        for key, value in points.items():
            if key.startswith("pool_"):
                cardinal = {v: k for k, v in COORD_KEYS.items()}[key]
                self.pool_points[cardinal] = QPointF(value[0], value[1])
        if len(self.pool_points) == 4:
            self.pool_step = 4
        for key, value in points.items():
            if key.startswith("platform_"):
                cardinal = {v: k for k, v in COORD_KEYS.items()}[key]
                self.platform_points[cardinal] = QPointF(value[0], value[1])
        if len(self.platform_points) == 4:
            self.platform_step = 4

    def pool_ready(self) -> bool:
        return len(self.pool_points) == 4

    def platform_ready(self) -> bool:
        return len(self.platform_points) == 4

    def _draw_dot(self, painter: QPainter, point, color: str, label: str):
        mapped = self.image_to_widget((point.x(), point.y()))
        painter.save()
        painter.setPen(QPen(QColor("white"), 1.5))
        painter.setBrush(QColor(color))
        painter.drawEllipse(mapped, 7, 7)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(mapped, 9, 9)
        painter.setPen(QColor(color))
        font = QFont(self.font())
        font.setBold(True)
        font.setPointSizeF(max(8.0, font.pointSizeF()))
        painter.setFont(font)
        painter.drawText(mapped + QPointF(12, 5), label)
        painter.restore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor("#1b1b1f"))

        width, height = self.image_size()
        scale, off_x, off_y = self._fit()
        target = QRectF(off_x, off_y, width * scale, height * scale)

        if not self.image.isNull():
            painter.drawImage(target, self.image)
        else:
            painter.setPen(QColor("#c8c8c8"))
            font = QFont(self.font())
            font.setPointSizeF(max(10.0, font.pointSizeF()))
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             translate(self.lang, "no_preview"))

        labels = {
            "WEST": translate(self.lang, "west"),
            "NORTH": translate(self.lang, "north"),
            "EAST": translate(self.lang, "east"),
            "SOUTH": translate(self.lang, "south"),
        }

        if len(self.pool_points) == 4:
            w = self.pool_points["WEST"]
            n = self.pool_points["NORTH"]
            e = self.pool_points["EAST"]
            s = self.pool_points["SOUTH"]
            painter.save()
            pen = QPen(QColor("#64ffb4"), 1.0, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(self.image_to_widget((n.x(), n.y())),
                             self.image_to_widget((s.x(), s.y())))
            painter.drawLine(self.image_to_widget((w.x(), w.y())),
                             self.image_to_widget((e.x(), e.y())))
            cx, cy, rx, ry, angle = ellipse_from_nsew(
                (w.x(), w.y()), (n.x(), n.y()), (e.x(), e.y()), (s.x(), s.y()))
            center = self.image_to_widget((cx, cy))
            painter.translate(center)
            painter.rotate(angle)
            painter.setPen(QPen(QColor("#64ffb4"), 2.0))
            painter.drawEllipse(QPointF(0, 0), rx * scale, ry * scale)
            painter.restore()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#64ffb4"))
            painter.drawEllipse(center, 4, 4)

        for key, point in self.pool_points.items():
            self._draw_dot(painter, point, POOL_COLORS[key], labels[key])

        platform_keys = [key for key in PLATFORM_STEPS if key in self.platform_points]
        if len(platform_keys) >= 2:
            polygon = QPolygonF([
                self.image_to_widget((self.platform_points[key].x(), self.platform_points[key].y()))
                for key in platform_keys
            ])
            painter.save()
            painter.setPen(QPen(QColor("#c8c832"), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolygon(polygon)
            painter.restore()

        for key in platform_keys:
            point = self.platform_points[key]
            self._draw_dot(painter, point, PLATFORM_COLORS[key], key)

        painter.end()


class CalibrationDialog(QDialog):
    def __init__(self, message: dict, lang: str = "en", parent=None):
        super().__init__(parent)
        self.lang = lang
        self.message = message
        self.payload: dict = {}
        self.is_confirm = bool(message.get("needs_confirm"))
        self.confirm_type = message.get("confirm_type")
        self.require_platform = bool(message.get("require_platform"))
        self.setWindowTitle(translate(lang, "calib_pool_title"))
        self.setModal(True)
        self.resize(1000, 760)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QHBoxLayout()
        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        header.addWidget(self.title_label, 1)
        self.redo_button = QPushButton(translate(lang, "redo"))
        self.confirm_button = QPushButton(translate(lang, "confirm"))
        self.cancel_button = QPushButton(translate(lang, "cancel"))
        self.confirm_button.setDefault(True)
        for button in (self.redo_button, self.confirm_button, self.cancel_button):
            header.addWidget(button)
        layout.addLayout(header)

        self.instruction = QLabel()
        self.instruction.setWordWrap(True)
        self.instruction.setMinimumHeight(38)
        layout.addWidget(self.instruction)

        self.canvas = CalibrationCanvas(self)
        self.canvas.lang = lang
        self.canvas.require_platform = self.require_platform
        self.canvas.changed.connect(self._refresh)
        layout.addWidget(self.canvas, 1)

        self.redo_button.clicked.connect(self._on_redo)
        self.confirm_button.clicked.connect(self._on_confirm)
        self.cancel_button.clicked.connect(self._on_cancel)

        preview = message.get("preview") or {}
        self.canvas.load_preview(preview.get("path"))

        if self.is_confirm:
            self.canvas.locked = True
            self.canvas.prefill(message.get("points") or {})
            self.canvas.update()
        else:
            existing = message.get("existing_pool")
            if existing:
                self.canvas.prefill({key: list(value) for key, value in existing.items()})
                self.canvas.phase = "platform" if self.require_platform else "pool"
                self.canvas.update()
            self.canvas.setFocus()

        self._refresh()

    def _refresh(self):
        lang = self.lang
        if self.is_confirm:
            key = "calib_saved_pool" if self.confirm_type == "pool" else "calib_saved_platform"
            self.title_label.setText(translate(lang, key))
            self.instruction.setText(translate(lang, "calib_use_saved"))
            self.confirm_button.setEnabled(True)
            self.redo_button.setText(translate(lang, "redo"))
            return

        if self.canvas.phase == "pool":
            step = self.canvas.pool_step
            self.title_label.setText(
                f"{translate(lang, 'calib_pool_title')} — {translate(lang, 'calib_step').replace('%1', str(min(step + 1, 4)))}")
            if step < len(POOL_STEPS):
                label = translate(lang, POOL_STEPS[step].lower())
                color = POOL_COLORS[POOL_STEPS[step]]
                self.instruction.setText(
                    translate(lang, "calib_click_pool").replace("%1", f"<b style='color:{color}'>{label}</b>"))
                self.confirm_button.setEnabled(False)
            else:
                self.instruction.setText(translate(lang, "calib_all_pool"
                                                   if not self.require_platform else "calib_pool_first"))
                self.confirm_button.setEnabled(not self.require_platform)
        else:
            step = self.canvas.platform_step
            self.title_label.setText(
                f"{translate(lang, 'calib_platform_title')} — {translate(lang, 'calib_step').replace('%1', str(min(step + 1, 4)))}")
            if step < len(PLATFORM_STEPS):
                key = PLATFORM_STEPS[step]
                color = PLATFORM_COLORS[key]
                self.instruction.setText(
                    translate(lang, "calib_click_platform").replace("%1", f"<b style='color:{color}'>{key}</b>"))
                self.confirm_button.setEnabled(False)
            else:
                self.instruction.setText(translate(lang, "calib_all_platform"))
                self.confirm_button.setEnabled(True)

    def _on_redo(self):
        if self.is_confirm:
            self.payload = {"confirmed": False}
            self.accept()
            return
        self.canvas.reset_points()
        self._refresh()

    def _on_confirm(self):
        if self.is_confirm:
            self.payload = {"confirmed": True}
            self.accept()
            return
        if not self.canvas.pool_ready():
            return
        if self.require_platform and not self.canvas.platform_ready():
            return
        payload = {}
        for cardinal, point in self.canvas.pool_points.items():
            payload[COORD_KEYS[cardinal]] = f"{int(point.x())},{int(point.y())}"
        if self.require_platform:
            for cardinal, point in self.canvas.platform_points.items():
                payload[COORD_KEYS[cardinal]] = f"{int(point.x())},{int(point.y())}"
        self.payload = payload
        self.accept()

    def _on_cancel(self):
        self.payload = {"aborted": True}
        self.reject()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.confirm_button.isEnabled():
                self._on_confirm()
            return
        if key == Qt.Key.Key_Escape:
            self._on_cancel()
            return
        if key == Qt.Key.Key_R:
            self._on_redo()
            return
        super().keyPressEvent(event)
