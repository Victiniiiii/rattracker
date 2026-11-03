"""Headless Qt tests for the desktop rewrite.

Run with:  QT_QPA_PLATFORM=offscreen venv/bin/python -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RATTRACKER_AUTOCONFIRM", "1")

from PySide6.QtCore import QCoreApplication, QEventLoop, QPoint, QTimer, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.calibration import CalibrationDialog, ellipse_from_nsew
from ui.config import (DEFAULTS, ConfigStore, config_dir, config_to_share_string,
                       share_string_to_config)
from ui.i18n import EN, TR
from ui.main_window import MainWindow
from ui.runner import build_args
from ui.settings_dialog import SettingsDialog

APP = QApplication.instance() or QApplication([])
QCoreApplication.setOrganizationName("RatTrackerTests")
QCoreApplication.setApplicationName("RatTrackerTests")

POINTS = {
    "pool_west": "274,128", "pool_north": "665,92",
    "pool_east": "730,382", "pool_south": "349,443",
    "platform_nw": "328,16", "platform_ne": "744,30",
    "platform_se": "754,473", "platform_sw": "318,480",
}

FEATURES = {
    "quadrantcross": True, "platformcross": True,
    "paraplatform_enabled": True, "paraplatform_scale": 4,
    "proximity": True, "latency": True,
}


def make_store(tmp: Path) -> ConfigStore:
    store = ConfigStore(tmp / "profiles.json")
    cfg = store.config()
    cfg.update(POINTS)
    cfg.update(FEATURES)
    store.set_config(cfg)
    return store


def sample_video() -> Path:
    fixture = ROOT / "tests" / "fixtures" / "1.mp4"
    return fixture if fixture.exists() else ROOT / "input" / "1.mp4"


class ConfigTests(unittest.TestCase):
    def test_defaults_and_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            self.assertEqual(store.active, "Default")
            self.assertTrue(store.create("Lab A"))
            self.assertEqual(store.active, "Lab A")
            self.assertTrue(store.rename("Lab B"))
            self.assertEqual(store.active, "Lab B")
            self.assertTrue(store.delete())
            self.assertEqual(store.active, "Default")
            self.assertFalse(store.delete())

    def test_share_string_roundtrip(self):
        cfg = dict(DEFAULTS)
        cfg.update(POINTS)
        cfg.update(FEATURES)
        cfg.update({
            "tracemapcolor_enabled": True, "tracemapcolor": "#12ab34",
            "ratcolor_enabled": True, "ratcolor": "#ff0000",
            "mog2_learning_rate": 0.001, "max_interp_gap": 10,
            "heatmap_sigma": 3.5, "colorall": True, "mog2_detect_shadow": True,
        })
        text = config_to_share_string(cfg, "Lab A")
        parsed, name = share_string_to_config(text)
        self.assertEqual(name, "Lab A")
        for key in POINTS:
            self.assertEqual(parsed[key], cfg[key])
        for key in ("quadrantcross", "platformcross", "proximity", "latency",
                    "colorall", "mog2_detect_shadow", "tracemapcolor_enabled",
                    "ratcolor_enabled", "paraplatform_enabled"):
            self.assertTrue(parsed[key], key)
        self.assertEqual(parsed["tracemapcolor"], "#12ab34")
        self.assertAlmostEqual(parsed["mog2_learning_rate"], 0.001)
        self.assertEqual(parsed["max_interp_gap"], 10)
        self.assertAlmostEqual(parsed["heatmap_sigma"], 3.5)

    def test_i18n_tables_match(self):
        missing = [key for key in EN if key not in TR]
        self.assertEqual(missing, [])
        for key, value in EN.items():
            self.assertTrue(value, key)
            self.assertTrue(TR[key], key)

    def test_config_dir_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"RATTRACKER_CONFIG_DIR": tmp}):
                self.assertEqual(config_dir(), Path(tmp))


class CalibrationTests(unittest.TestCase):
    def test_ellipse_matches_backend(self):
        from tracker.geometry import pool_ellipse_from_nsew
        cases = [
            ((274, 128), (665, 92), (730, 382), (349, 443)),
            ((100, 100), (400, 100), (400, 400), (100, 400)),
            ((50, 300), (300, 50), (550, 300), (300, 550)),
        ]
        for points in cases:
            backend = pool_ellipse_from_nsew(*points)
            ui = ellipse_from_nsew(*points)
            self.assertEqual(ui[:4], backend[:4])
            if ui[2] == ui[3]:
                continue
            diff = abs((ui[4] - backend[4]) % 180.0)
            self.assertTrue(min(diff, 180.0 - diff) < 0.01, (ui, backend))

    def test_click_mapping_and_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "preview.jpg"
            image = QImage(800, 600, QImage.Format.Format_RGB32)
            image.fill(QColor("#223344"))
            self.assertTrue(image.save(str(image_path)))

            message = {"needs_calib": True, "require_platform": True,
                       "preview": {"path": str(image_path), "w": 800, "h": 600}}
            dialog = CalibrationDialog(message, "en")
            dialog.resize(1000, 760)
            dialog.show()
            APP.processEvents()
            canvas = dialog.canvas
            targets = [(120, 150), (680, 160), (700, 470), (140, 480),
                       (300, 220), (500, 220), (500, 400), (300, 400)]
            for target in targets:
                widget_point = canvas.image_to_widget(target)
                QTest.mouseClick(canvas, Qt.MouseButton.LeftButton,
                                 pos=QPoint(round(widget_point.x()), round(widget_point.y())))
                APP.processEvents()
            self.assertTrue(canvas.pool_ready())
            self.assertTrue(canvas.platform_ready())
            self.assertTrue(dialog.confirm_button.isEnabled())
            dialog._on_confirm()
            self.assertEqual(dialog.payload["pool_west"], "120,150")
            self.assertEqual(dialog.payload["pool_east"], "700,470")
            self.assertEqual(dialog.payload["platform_nw"], "300,220")
            self.assertEqual(dialog.payload["platform_sw"], "300,400")
            dialog.close()

    def test_confirm_mode_payload(self):
        message = {
            "needs_confirm": True, "confirm_type": "pool",
            "points": {
                "pool_west": [274, 128], "pool_north": [665, 92],
                "pool_east": [730, 382], "pool_south": [349, 443],
            },
        }
        dialog = CalibrationDialog(message, "en")
        self.assertTrue(dialog.canvas.locked)
        self.assertEqual(len(dialog.canvas.pool_points), 4)
        dialog._on_confirm()
        self.assertEqual(dialog.payload, {"confirmed": True})
        dialog.close()

    def test_existing_pool_starts_platform_phase(self):
        message = {
            "needs_calib": True, "require_platform": True,
            "existing_pool": {
                "pool_west": [274, 128], "pool_north": [665, 92],
                "pool_east": [730, 382], "pool_south": [349, 443],
            },
        }
        dialog = CalibrationDialog(message, "en")
        dialog.resize(1000, 760)
        dialog.show()
        APP.processEvents()
        self.assertEqual(dialog.canvas.phase, "platform")
        self.assertEqual(dialog.canvas.pool_step, 4)
        for target in [(300, 220), (500, 220), (500, 400), (300, 400)]:
            widget_point = dialog.canvas.image_to_widget(target)
            QTest.mouseClick(dialog.canvas, Qt.MouseButton.LeftButton,
                             pos=QPoint(round(widget_point.x()), round(widget_point.y())))
            APP.processEvents()
        self.assertTrue(dialog.confirm_button.isEnabled())
        dialog._on_confirm()
        self.assertEqual(dialog.payload["pool_west"], "274,128")
        self.assertEqual(dialog.payload["platform_nw"], "300,220")
        self.assertEqual(dialog.payload["platform_sw"], "300,400")
        dialog.close()


class SettingsTests(unittest.TestCase):
    def test_populate_and_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            dialog = SettingsDialog(store, "en")
            self.assertIn("pool_west", dialog.widgets)
            cfg = dialog.read_config()
            self.assertEqual(cfg["pool_west"], "274,128")
            self.assertTrue(cfg["quadrantcross"])
            dialog.widgets["pool_west"].setText("1,2")
            self.assertEqual(dialog.read_config()["pool_west"], "1,2")
            dialog.close()

    def test_validation_rejects_even_kernel_and_bad_points(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(Path(tmp))
            dialog = SettingsDialog(store, "en")
            dialog.widgets["morph_open_k"].setValue(4)
            with patch("ui.settings_dialog.QMessageBox.warning", return_value=None):
                self.assertFalse(dialog._validate())
            dialog.widgets["morph_open_k"].setValue(3)
            dialog.widgets["pool_west"].setText("bad")
            with patch("ui.settings_dialog.QMessageBox.warning", return_value=None):
                self.assertFalse(dialog._validate())
            dialog.widgets["pool_west"].setText("10,20")
            self.assertTrue(dialog._validate())
            dialog.close()


class RunnerTests(unittest.TestCase):
    def test_build_args(self):
        cfg = dict(DEFAULTS)
        cfg.update(POINTS)
        cfg.update(FEATURES)
        cfg.update({"autoconfig": True, "colorall": True,
                    "tracemapcolor_enabled": True, "tracemapcolor": "#00ffff"})
        args = build_args("video.mp4", cfg, "1.5", "10", "60")
        self.assertEqual(args[0], "--video")
        self.assertIn("--quadrantcross", args)
        self.assertIn("--platformcross", args)
        self.assertIn("--paraplatform", args)
        self.assertIn("--proximity", args)
        self.assertIn("--latency", args)
        self.assertIn("--autoconfig", args)
        self.assertIn("--colorall", args)
        self.assertIn("0,255,255", args)
        self.assertEqual(args[-1], "--appmode")
        self.assertIn("--pool_west", args)

    def test_backend_parity(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "1.mp4"
            shutil.copy(sample_video(), video)
            args = [sys.executable, str(ROOT / "app_qt.py"), "--backend",
                    "--video", str(video), "--appmode", "--language", "en",
                    "--pool_radius_cm", "60"]
            for key, value in POINTS.items():
                args += [f"--{key}", value]
            args += ["--quadrantcross", "--platformcross", "--paraplatform", "4",
                     "--proximity", "--latency"]
            payload = ('{"confirmed": true}\n{"confirmed": true}\n').encode()
            proc = subprocess.run(args, input=payload, capture_output=True, timeout=180)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode())
            lines = [json.loads(line) for line in proc.stdout.decode().splitlines()
                     if line.startswith("{")]
            done = [line for line in lines if line.get("done")][-1]
            self.assertEqual(done["total_frames"], 243)
            self.assertEqual(done["total_dist_cm"], 1238.42)
            self.assertEqual(
                Path(done["csv_out"]).read_bytes(),
                (ROOT / "tests" / "baseline" / "coordinates.csv").read_bytes(),
            )
            summary = Path(done["summary_out"]).read_text(encoding="utf-8")
            summary = summary.replace(str(video), "input/1.mp4")
            baseline = (ROOT / "tests" / "baseline" / "summary.txt").read_text(encoding="utf-8")
            self.assertEqual(summary, baseline)
            preview = [line for line in lines if line.get("needs_confirm")][0]["preview"]
            self.assertFalse(Path(preview["path"]).exists())
            for key in ("video_out", "csv_out", "summary_out", "tracemap_out", "heatmap_out"):
                self.assertTrue(Path(done[key]).exists(), key)


class WindowTests(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "1.mp4"
            shutil.copy(sample_video(), video)
            store = make_store(tmp_path)
            os.environ["RATTRACKER_AUTOCONFIRM"] = "1"
            window = MainWindow(store)
            window.selected_file = str(video)
            window._set_file_label()
            loop = QEventLoop()
            state = {}

            def on_done(payload):
                state["done"] = payload
                QTimer.singleShot(50, loop.quit)

            window.runner.done.connect(on_done)
            window.runner.failed.connect(lambda code, detail: (state.update(failed=detail), loop.quit()))
            window._run()
            QTimer.singleShot(180000, loop.quit)
            loop.exec()
            self.assertNotIn("failed", state)
            self.assertIn("done", state)
            payload = state["done"]
            self.assertEqual(payload["total_frames"], 243)
            self.assertTrue(window.tabs.isEnabled())
            self.assertEqual(window.csv_tab.model.rowCount(), 243)
            self.assertGreater(len(window.summary_tab.toPlainText()), 1000)
            self.assertFalse(window.tracemap_tab.pixmap.isNull())
            self.assertFalse(window.heatmap_tab.pixmap.isNull())
            self.assertIsNotNone(window.video_tab.player.capture)
            self.assertEqual(window.video_tab.player.total, 243)
            self.assertTrue(window.run_button.isEnabled())
            self.assertFalse(window.cancel_button.isEnabled())
            QTest.qWait(500)
            self.assertFalse(window.runner.is_running())
            window.close()

    def test_cancel_stops_backend(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "1.mp4"
            shutil.copy(sample_video(), video)
            store = make_store(tmp_path)
            window = MainWindow(store)
            window.selected_file = str(video)
            window._set_file_label()
            loop = QEventLoop()
            state = {}

            def on_progress(_percent, _eta):
                if not state.get("cancel_requested"):
                    state["cancel_requested"] = True
                    window._cancel()

            window.runner.progress.connect(on_progress)
            window.runner.cancelled.connect(lambda: (state.update(cancelled=True), loop.quit()))
            window.runner.failed.connect(lambda code, detail: (state.update(failed=detail), loop.quit()))
            window.runner.done.connect(lambda payload: (state.update(done=True), loop.quit()))
            window._run()
            QTimer.singleShot(60000, loop.quit)
            loop.exec()
            self.assertTrue(state.get("cancelled"), state)
            self.assertFalse(window.runner.is_running())
            self.assertTrue(window.run_button.isEnabled())
            self.assertFalse(window.cancel_button.isEnabled())
            window.close()

    def test_interactive_calibration_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video = tmp_path / "1.mp4"
            shutil.copy(sample_video(), video)
            store = ConfigStore(tmp_path / "profiles.json")
            cfg = store.config()
            cfg.update(FEATURES)
            store.set_config(cfg)

            previous = os.environ.get("RATTRACKER_AUTOCONFIRM")
            os.environ["RATTRACKER_AUTOCONFIRM"] = "0"
            try:
                window = MainWindow(store)
                window.selected_file = str(video)
                window._set_file_label()
                window.runner.calibration.disconnect(window._on_calibration)
                loop = QEventLoop()
                state = {}

                def on_calibration(message):
                    preview = message.get("preview") or {}
                    state["preview"] = preview
                    self.assertTrue(preview.get("path"), message)
                    self.assertTrue(Path(preview["path"]).exists(), message)
                    dialog = CalibrationDialog(message, "en")
                    dialog.resize(1000, 760)
                    dialog.show()
                    APP.processEvents()
                    targets = [
                        (274, 128), (665, 92), (730, 382), (349, 443),
                        (328, 16), (744, 30), (754, 473), (318, 480),
                    ]
                    for target in targets:
                        widget_point = dialog.canvas.image_to_widget(target)
                        QTest.mouseClick(
                            dialog.canvas, Qt.MouseButton.LeftButton,
                            pos=QPoint(round(widget_point.x()), round(widget_point.y())),
                        )
                        APP.processEvents()
                    self.assertTrue(dialog.confirm_button.isEnabled(), message)
                    dialog._on_confirm()
                    window.runner.respond(dialog.payload)
                    dialog.close()

                window.runner.calibration.connect(on_calibration)
                window.runner.failed.connect(
                    lambda code, detail: (state.update(failed=detail), loop.quit()))
                window.runner.done.connect(
                    lambda payload: (state.update(done=payload), loop.quit()))
                window._run()
                QTimer.singleShot(180000, loop.quit)
                loop.exec()
                self.assertNotIn("failed", state)
                self.assertIn("done", state)
                self.assertEqual(state["done"]["total_frames"], 243)
                self.assertFalse(Path(state["preview"]["path"]).exists())
                self.assertTrue(window.tabs.isEnabled())
                QTest.qWait(500)
                self.assertFalse(window.runner.is_running())
                window.close()
            finally:
                if previous is None:
                    os.environ.pop("RATTRACKER_AUTOCONFIRM", None)
                else:
                    os.environ["RATTRACKER_AUTOCONFIRM"] = previous


if __name__ == "__main__":
    unittest.main()
