"""QApplication bootstrap and dark theme."""

from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .resources import app_icon_path

STYLE = """
QWidget { background: #17181c; color: #e6e6e6; font-size: 10pt; }
QMainWindow, QDialog { background: #17181c; }
QLabel { background: transparent; }
QLabel#appTitle { font-size: 16pt; font-weight: 700; }
QLabel#versionLabel { color: #8b909a; }
QLabel#inlineLabel { color: #b9bec7; }
QLabel#fileLabel { color: #aab0ba; }
QPushButton {
    background: #2a2c33; color: #e6e6e6; border: 1px solid #3a3d46;
    border-radius: 6px; padding: 6px 12px;
}
QPushButton:hover { background: #353842; }
QPushButton:pressed { background: #24262c; }
QPushButton:disabled { color: #6b7079; background: #202127; border-color: #2b2d34; }
QPushButton#primary { background: #2f6fed; border-color: #2f6fed; font-weight: 600; }
QPushButton#primary:hover { background: #3d7bf5; }
QPushButton#primary:disabled { background: #2a2c33; border-color: #3a3d46; color: #6b7079; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #202228; border: 1px solid #3a3d46; border-radius: 5px;
    padding: 4px 6px; selection-background-color: #2f6fed;
}
QComboBox QAbstractItemView { background: #202228; selection-background-color: #2f6fed; }
QProgressBar { background: #202228; border: 1px solid #3a3d46; border-radius: 5px; height: 14px; }
QProgressBar::chunk { background: #2f6fed; border-radius: 4px; }
QTabWidget::pane { border: 1px solid #2f3038; border-radius: 6px; top: -1px; }
QTabBar::tab {
    background: #1d1e24; color: #aab0ba; padding: 7px 14px;
    border: 1px solid #2f3038; border-bottom: none;
    border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px;
}
QTabBar::tab:selected { background: #2a2c33; color: #ffffff; }
QTabBar::tab:disabled { color: #5c616a; }
QGroupBox {
    border: 1px solid #2f3038; border-radius: 7px; margin-top: 12px;
    padding-top: 8px; font-weight: 600;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
QScrollArea { border: none; }
QTableView { background: #1b1c21; alternate-background-color: #202228; gridline-color: #2b2d34; }
QHeaderView::section { background: #262830; padding: 4px; border: none; }
QPlainTextEdit { background: #1b1c21; border: 1px solid #2f3038; border-radius: 5px; }
QSlider::groove:horizontal { height: 4px; background: #2f3038; border-radius: 2px; }
QSlider::handle:horizontal { width: 12px; background: #2f6fed; margin: -5px 0; border-radius: 6px; }
QStatusBar { color: #8b909a; }
QToolTip { background: #262830; color: #e6e6e6; border: 1px solid #3a3d46; }
"""


def main() -> int:
    QCoreApplication.setOrganizationName("RatTracker")
    QCoreApplication.setApplicationName("RatTracker")
    QCoreApplication.setApplicationVersion("1.1.0")
    app = QApplication(sys.argv)
    app.setApplicationDisplayName("Morris Water Maze Analysis")
    icon_path = app_icon_path()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    app.setStyleSheet(STYLE)
    from .main_window import MainWindow
    window = MainWindow()
    window.show()
    return app.exec()
