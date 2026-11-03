"""Main application window."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QDoubleValidator, QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .calibration import CalibrationDialog
from .config import ConfigStore
from .i18n import LANGUAGES, translate
from .resources import app_icon_path, asset_path
from .results import CsvTab, ImageTab, SummaryTab, VideoTab
from .runner import BackendRunner
from .settings_dialog import SettingsDialog

APP_VERSION = "1.1.0"


class MainWindow(QMainWindow):
    def __init__(self, store: ConfigStore | None = None):
        super().__init__()
        self.store = store or ConfigStore()
        self.cfg = self.store.config()
        self.lang = self.cfg.get("language", "en")
        self.selected_file = ""
        self.last_payload: dict | None = None
        self.runner = BackendRunner(self)
        self.runner.progress.connect(self._on_progress)
        self.runner.status.connect(self._on_status)
        self.runner.calibration.connect(self._on_calibration)
        self.runner.done.connect(self._on_done)
        self.runner.failed.connect(self._on_failed)
        self.runner.cancelled.connect(self._on_cancelled)

        self.setWindowIcon(QIcon(str(app_icon_path())))
        self.resize(1180, 820)
        self._build_ui()
        self.retranslate()
        self._set_running(False)
        self.tabs.setEnabled(False)
        autorun = os.environ.get("RATTRACKER_AUTORUN")
        if autorun:
            QTimer.singleShot(0, lambda: self._autorun(autorun))

    def _autorun(self, path: str):
        self.selected_file = path
        self._set_file_label()
        self.run_button.setEnabled(True)
        self._run()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        top = QHBoxLayout()
        self.title_label = QLabel()
        self.title_label.setObjectName("appTitle")
        top.addWidget(self.title_label)
        top.addStretch(1)
        self.lang_combo = QComboBox()
        for code, name, flag in LANGUAGES:
            self.lang_combo.addItem(QIcon(str(asset_path(flag))), name, code)
        self.lang_combo.currentIndexChanged.connect(self._on_language)
        top.addWidget(self.lang_combo)
        self.version_label = QLabel(f"v{APP_VERSION}")
        self.version_label.setObjectName("versionLabel")
        top.addWidget(self.version_label)
        self.settings_button = QPushButton()
        self.settings_button.setIcon(QIcon(str(asset_path("settings.svg"))))
        self.settings_button.setFixedSize(34, 30)
        self.settings_button.clicked.connect(self._open_settings)
        top.addWidget(self.settings_button)
        layout.addLayout(top)

        row = QHBoxLayout()
        self.select_button = QPushButton()
        self.select_button.clicked.connect(self._select_file)
        row.addWidget(self.select_button)
        self.file_label = QLabel()
        self.file_label.setObjectName("fileLabel")
        self.file_label.setMinimumWidth(220)
        self.file_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(self.file_label, 1)

        self.start_edit = QLineEdit()
        self.start_edit.setValidator(QDoubleValidator(0.0, 1e9, 3))
        self.start_edit.setFixedWidth(84)
        self.end_edit = QLineEdit()
        self.end_edit.setValidator(QDoubleValidator(0.0, 1e9, 3))
        self.end_edit.setFixedWidth(84)
        self.radius_spin = QDoubleSpinBox()
        self.radius_spin.setRange(1.0, 10000.0)
        self.radius_spin.setDecimals(1)
        self.radius_spin.setValue(60.0)
        self.radius_spin.setFixedWidth(96)
        self.start_label = QLabel()
        self.end_label = QLabel()
        self.radius_label = QLabel()
        for label in (self.start_label, self.end_label, self.radius_label):
            label.setObjectName("inlineLabel")
        row.addWidget(self.start_label)
        row.addWidget(self.start_edit)
        row.addWidget(self.end_label)
        row.addWidget(self.end_edit)
        row.addWidget(self.radius_label)
        row.addWidget(self.radius_spin)
        layout.addLayout(row)

        row2 = QHBoxLayout()
        self.run_button = QPushButton()
        self.run_button.setObjectName("primary")
        self.run_button.clicked.connect(self._run)
        self.cancel_button = QPushButton()
        self.cancel_button.clicked.connect(self._cancel)
        self.progress_text = QLabel()
        self.progress_text.setMinimumWidth(130)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedWidth(260)
        self.eta_label = QLabel()
        self.eta_label.setMinimumWidth(90)
        self.open_folder_button = QPushButton()
        self.open_folder_button.clicked.connect(self._open_output_folder)
        row2.addWidget(self.run_button)
        row2.addWidget(self.cancel_button)
        row2.addWidget(self.progress_text)
        row2.addWidget(self.progress_bar)
        row2.addWidget(self.eta_label)
        row2.addStretch(1)
        row2.addWidget(self.open_folder_button)
        layout.addLayout(row2)

        self.tabs = QTabWidget()
        self.video_tab = VideoTab(self.lang, self)
        self.csv_tab = CsvTab(self)
        self.summary_tab = SummaryTab(self)
        self.tracemap_tab = ImageTab(self)
        self.heatmap_tab = ImageTab(self)
        self.tabs.addTab(self.video_tab, "")
        self.tabs.addTab(self.csv_tab, "")
        self.tabs.addTab(self.summary_tab, "")
        self.tabs.addTab(self.tracemap_tab, "")
        self.tabs.addTab(self.heatmap_tab, "")
        layout.addWidget(self.tabs, 1)

        self.setCentralWidget(central)
        self.statusBar().showMessage("")

    def retranslate(self):
        self.lang = self.cfg.get("language", "en")
        lang = self.lang
        self.setWindowTitle(translate(lang, "app_name"))
        self.title_label.setText(translate(lang, "app_name"))
        self.select_button.setText(translate(lang, "select_video"))
        self.start_label.setText(translate(lang, "start_time"))
        self.end_label.setText(translate(lang, "end_time"))
        self.radius_label.setText(translate(lang, "pool_radius"))
        self.run_button.setText(translate(lang, "run"))
        self.cancel_button.setText(translate(lang, "cancel"))
        self.open_folder_button.setText(translate(lang, "open_folder"))
        self.settings_button.setToolTip(translate(lang, "settings"))
        self.tabs.setTabText(0, translate(lang, "tab_video"))
        self.tabs.setTabText(1, translate(lang, "tab_csv"))
        self.tabs.setTabText(2, translate(lang, "tab_summary"))
        self.tabs.setTabText(3, translate(lang, "tab_tracemap"))
        self.tabs.setTabText(4, translate(lang, "tab_heatmap"))
        self.video_tab.retranslate(lang)
        self._set_file_label()
        index = self.lang_combo.findData(lang)
        if index >= 0 and index != self.lang_combo.currentIndex():
            self.lang_combo.blockSignals(True)
            self.lang_combo.setCurrentIndex(index)
            self.lang_combo.blockSignals(False)
        if not self.runner.is_running():
            self.progress_text.setText(translate(lang, "ready"))

    def _on_language(self, index: int):
        code = self.lang_combo.itemData(index)
        if not code:
            return
        self.cfg["language"] = code
        self.store.set_config(self.cfg)
        self.retranslate()

    def _set_file_label(self):
        if not self.selected_file:
            self.file_label.setText(translate(self.lang, "no_file"))
            self.file_label.setToolTip("")
            return
        self.file_label.setToolTip(self.selected_file)
        metrics = self.file_label.fontMetrics()
        text = metrics.elidedText(self.selected_file, Qt.TextElideMode.ElideMiddle,
                                  max(220, self.file_label.width() - 8))
        self.file_label.setText(text)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._set_file_label()

    # -------------------------------------------------------------- actions
    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, translate(self.lang, "select_video"), "",
            "Video (*.mp4 *.mov *.avi *.mkv *.webm);;All files (*)",
        )
        if path:
            self.selected_file = path
            self._set_file_label()
            self.run_button.setEnabled(True)

    def _open_settings(self):
        dialog = SettingsDialog(self.store, self.lang, self)
        dialog.saved.connect(self._on_settings_saved)
        dialog.exec()

    def _on_settings_saved(self, cfg: dict):
        self.cfg = dict(cfg)
        self.store.set_config(self.cfg)
        self.retranslate()

    def _set_running(self, running: bool):
        self.select_button.setEnabled(not running)
        self.settings_button.setEnabled(not running)
        self.lang_combo.setEnabled(not running)
        self.start_edit.setEnabled(not running)
        self.end_edit.setEnabled(not running)
        self.radius_spin.setEnabled(not running)
        self.run_button.setEnabled((not running) and bool(self.selected_file))
        self.cancel_button.setEnabled(running)

    def _run(self):
        if not self.selected_file:
            return
        self.last_payload = None
        self.progress_bar.setValue(0)
        self.progress_text.setText(translate(self.lang, "launching"))
        self.eta_label.setText("")
        self.tabs.setEnabled(False)
        self._set_running(True)
        self.runner.start(
            self.selected_file, self.cfg,
            self.start_edit.text().strip(), self.end_edit.text().strip(),
            f"{self.radius_spin.value():g}",
        )

    def _cancel(self):
        self.runner.cancel()

    def _on_progress(self, percent: float, eta: int):
        self.progress_bar.setValue(max(0, min(100, int(round(percent)))))
        self.progress_text.setText(translate(self.lang, "progress").replace("%1", f"{percent:.1f}"))
        self.eta_label.setText(
            translate(self.lang, "eta").replace("%1", str(eta)) if eta > 0 else ""
        )

    def _on_status(self, text: str):
        self.progress_text.setText(text)

    def _on_calibration(self, message: dict):
        self.progress_text.setText(translate(self.lang, "calibrating"))
        dialog = CalibrationDialog(message, self.lang, self)
        dialog.exec()
        payload = dialog.payload or {"aborted": True}
        if payload.get("aborted"):
            self.runner.cancel()
            return
        self.runner.respond(payload)

    def _on_done(self, payload: dict):
        self.last_payload = payload
        for key in ("pool_west", "pool_north", "pool_east", "pool_south",
                    "platform_nw", "platform_ne", "platform_se", "platform_sw"):
            if payload.get(key):
                self.cfg[key] = payload[key]
        mapping = {
            "ac_mog2_threshold": "mog2_threshold",
            "ac_morph_open_k": "morph_open_k",
            "ac_morph_close_k": "morph_close_k",
            "ac_mog2_history_s": "mog2_history_s",
        }
        for source, target in mapping.items():
            if payload.get(source) is not None:
                self.cfg[target] = payload[source]
        if payload.get("ac_mog2_threshold") is not None:
            self.cfg["autoconfig"] = False
        self.store.set_config(self.cfg)

        def resolve(path: str) -> str:
            return str(Path(path).resolve()) if path else ""

        self.video_tab.load(resolve(payload.get("video_out", "")))
        self.csv_tab.load(resolve(payload.get("csv_out", "")))
        self.summary_tab.load(resolve(payload.get("summary_out", "")))
        self.tracemap_tab.load(resolve(payload.get("tracemap_out", "")))
        self.heatmap_tab.load(resolve(payload.get("heatmap_out", "")))
        self.tabs.setEnabled(True)
        self.tabs.setCurrentIndex(0)
        self.progress_bar.setValue(100)
        self.progress_text.setText(translate(self.lang, "progress").replace("%1", "100.0"))
        self.eta_label.setText("")
        self._set_running(False)
        if os.environ.get("RATTRACKER_AUTOEXIT") == "1":
            QTimer.singleShot(800, self.close)

    def _on_failed(self, code: int, detail: str):
        self._set_running(False)
        self.progress_text.setText("")
        if os.environ.get("RATTRACKER_AUTOEXIT") == "1":
            QTimer.singleShot(100, lambda: QCoreApplication.exit(1))
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(translate(self.lang, "error_title"))
        box.setText(translate(self.lang, "error_title"))
        box.setInformativeText(f"Process exited with code {code}")
        box.setDetailedText(detail)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def _on_cancelled(self):
        self._set_running(False)
        self.progress_bar.setValue(0)
        self.progress_text.setText(translate(self.lang, "ready"))
        self.eta_label.setText("")

    def _open_output_folder(self):
        if not self.selected_file:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.selected_file).parent)))

    def closeEvent(self, event):
        if self.runner.is_running():
            self.runner.cancel()
        self.video_tab.stop()
        super().closeEvent(event)
