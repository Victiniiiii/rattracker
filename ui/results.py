"""Result tabs: video, CSV table, summary text, tracemap and heatmap."""

from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .i18n import translate
from .player import VideoPlayer


class CsvModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.headers: list[str] = []
        self.rows: list[list[str]] = []

    def load(self, path: str) -> None:
        self.beginResetModel()
        self.headers = []
        self.rows = []
        try:
            with open(path, newline="", encoding="utf-8") as handle:
                reader = csv.reader(handle)
                self.headers = next(reader, [])
                self.rows = [row for row in reader]
        except OSError:
            pass
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            try:
                return self.rows[index.row()][index.column()]
            except IndexError:
                return ""
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.headers[section] if section < len(self.headers) else ""
        return str(section + 1)


class ImageTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap = QPixmap()
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setMinimumSize(200, 150)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)

    def load(self, path: str) -> None:
        self.pixmap = QPixmap(path)
        self._rescale()

    def _rescale(self):
        if self.pixmap.isNull():
            self.label.clear()
            self.label.setText("")
            return
        scaled = self.pixmap.scaled(
            self.label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rescale()


class VideoTab(QWidget):
    def __init__(self, lang: str = "en", parent=None):
        super().__init__(parent)
        self.lang = lang
        self.path = ""
        self.player = VideoPlayer(self)
        self.external = QPushButton(translate(lang, "open_external"))
        self.external.clicked.connect(self._open_external)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.external)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.player, 1)
        layout.addLayout(row)

    def load(self, path: str) -> None:
        self.path = path
        self.player.load(path, translate(self.lang, "video_missing"))

    def _open_external(self):
        if self.path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.path))

    def retranslate(self, lang: str):
        self.lang = lang
        self.external.setText(translate(lang, "open_external"))

    def stop(self):
        self.player.stop()


class SummaryTab(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def load(self, path: str) -> None:
        try:
            self.setPlainText(Path(path).read_text(encoding="utf-8"))
        except OSError:
            self.setPlainText("")


class CsvTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = CsvModel(self)
        self.view = QTableView(self)
        self.view.setModel(self.model)
        self.view.setAlternatingRowColors(True)
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.setSortingEnabled(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

    def load(self, path: str) -> None:
        self.model.load(path)
        self.view.resizeColumnsToContents()
