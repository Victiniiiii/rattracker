"""Embedded video player.

Decoding uses OpenCV, which the app already ships. This keeps the bundle small
and avoids a Qt Multimedia / codec dependency. Playback is intentionally simple:
play, pause and seek. The tracker outputs are short maze recordings.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class VideoSurface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = QImage()
        self.message = ""
        self.setMinimumHeight(280)
        self.setSizePolicy(self.sizePolicy().horizontalPolicy(), self.sizePolicy().verticalPolicy())

    def set_frame(self, image: QImage):
        self.image = image
        self.message = ""
        self.update()

    def set_message(self, text: str):
        self.image = QImage()
        self.message = text
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#101014"))
        if self.image.isNull():
            painter.setPen(QColor("#c8c8c8"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.message)
            return
        scaled = self.image.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        painter.drawImage(x, y, scaled)


class VideoPlayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.capture = None
        self.fps = 4.0
        self.total = 0
        self.current = 0
        self.playing = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._seeking = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.surface = VideoSurface(self)
        layout.addWidget(self.surface, 1)

        controls = QHBoxLayout()
        self.play_button = QPushButton("▶")
        self.play_button.setFixedWidth(44)
        self.play_button.clicked.connect(self.toggle)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderPressed.connect(self._start_seek)
        self.slider.sliderReleased.connect(self._end_seek)
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setMinimumWidth(110)
        controls.addWidget(self.play_button)
        controls.addWidget(self.slider, 1)
        controls.addWidget(self.time_label)
        layout.addLayout(controls)

    def load(self, path: str, missing_text: str = "Video could not be opened.") -> bool:
        self.stop()
        self.surface.set_message("")
        try:
            import cv2  # lazy: keeps UI startup free of the CV stack
        except Exception:
            self.surface.set_message(missing_text)
            return False
        capture = cv2.VideoCapture(path)
        if not capture.isOpened():
            capture.release()
            self.surface.set_message(missing_text)
            return False
        self.capture = capture
        self.fps = float(capture.get(cv2.CAP_PROP_FPS) or 25.0)
        if self.fps <= 0.1:
            self.fps = 25.0
        self.total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.current = 0
        self.slider.setRange(0, max(0, self.total - 1))
        self.slider.setValue(0)
        self._read_frame()
        self._update_time()
        return True

    def _read_frame(self):
        if self.capture is None:
            return False
        import cv2
        ok, frame = self.capture.read()
        if not ok or frame is None:
            return False
        height, width = frame.shape[:2]
        image = QImage(frame.data, width, height, frame.strides[0],
                       QImage.Format.Format_BGR888)
        self.surface.set_frame(image.copy())
        self.current = int(self.capture.get(cv2.CAP_PROP_POS_FRAMES))
        return True

    def toggle(self):
        if self.playing:
            self.pause()
        else:
            self.play()

    def play(self):
        if self.capture is None:
            return
        self.playing = True
        self.play_button.setText("⏸")
        self.timer.start(max(15, int(1000.0 / self.fps)))

    def pause(self):
        self.playing = False
        self.play_button.setText("▶")
        self.timer.stop()

    def stop(self):
        self.pause()
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        self.total = 0
        self.current = 0
        self.slider.setRange(0, 0)
        self.time_label.setText("0:00 / 0:00")

    def _tick(self):
        if not self._read_frame():
            self.pause()
            return
        self.slider.setValue(min(self.current, self.slider.maximum()))
        self._update_time()

    def _start_seek(self):
        self._seeking = True

    def _end_seek(self):
        self._seeking = False
        if self.capture is None:
            return
        import cv2
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, self.slider.value())
        self.current = self.slider.value()
        self._read_frame()
        self._update_time()

    def _update_time(self):
        seconds = self.current / self.fps if self.fps > 0 else 0.0
        total_seconds = self.total / self.fps if self.fps > 0 else 0.0
        self.time_label.setText(f"{_fmt(seconds)} / {_fmt(total_seconds)}")


def _fmt(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"
