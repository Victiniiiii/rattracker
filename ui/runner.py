"""QProcess wrapper around the Python tracker backend.

The frozen executable re-launches itself with ``--backend`` so there is only
one bundle and one copy of OpenCV. In development it launches ``app_qt.py``.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

from .config import hex_to_rgb_string
from .resources import is_frozen


def backend_command() -> list[str]:
    if is_frozen():
        # Nuitka reports a sibling "python" that is not shipped. The running
        # executable is argv[0], so re-launch that to reach the backend branch.
        candidate = Path(sys.argv[0])
        if not candidate.is_absolute():
            found = shutil.which(sys.argv[0])
            if found:
                candidate = Path(found)
        exe = candidate.resolve()
        if not exe.exists():
            exe = Path(sys.executable).resolve()
        return [str(exe), "--backend"]
    entry = Path(__file__).resolve().parent.parent / "app_qt.py"
    return [sys.executable, str(entry), "--backend"]


def build_args(video: str, cfg: dict, start: str = "", end: str = "",
               radius: str = "60") -> list[str]:
    args = ["--video", video, "--language", cfg.get("language", "en")]
    if start not in ("", None):
        args += ["--start", str(start)]
    if end not in ("", None):
        args += ["--end", str(end)]
    args += ["--pool_radius_cm", str(radius or "60")]
    args += ["--mog2_history_s", str(cfg.get("mog2_history_s", 4.0))]
    args += ["--mog2_threshold", str(cfg.get("mog2_threshold", 32))]
    if cfg.get("mog2_detect_shadow"):
        args.append("--mog2_detect_shadow")
    args += ["--morph_open_k", str(cfg.get("morph_open_k", 3))]
    args += ["--morph_close_k", str(cfg.get("morph_close_k", 15))]
    args += ["--min_contour_area", str(cfg.get("min_contour_area", 300))]
    args += ["--max_contour_area", str(cfg.get("max_contour_area", 12000))]
    args += ["--trail_s", str(cfg.get("trail_s", 2.0))]
    args += ["--debug_frames", str(cfg.get("debug_frames", 0))]
    for key in ("pool_west", "pool_north", "pool_east", "pool_south",
                "platform_nw", "platform_ne", "platform_se", "platform_sw"):
        if cfg.get(key):
            args += [f"--{key}", str(cfg[key])]
    if cfg.get("quadrantcross"):
        args.append("--quadrantcross")
    if cfg.get("platformcross"):
        args.append("--platformcross")
    if cfg.get("paraplatform_enabled"):
        args += ["--paraplatform", str(cfg.get("paraplatform_scale", 4))]
    if cfg.get("proximity"):
        args.append("--proximity")
    if cfg.get("latency"):
        args.append("--latency")
    if cfg.get("tracemapcolor_enabled") and cfg.get("tracemapcolor"):
        args += ["--tracemapcolor", hex_to_rgb_string(cfg["tracemapcolor"])]
    if cfg.get("ratcolor_enabled") and cfg.get("ratcolor"):
        args += ["--ratcolor", hex_to_rgb_string(cfg["ratcolor"])]
    learning = cfg.get("mog2_learning_rate")
    if learning is not None and float(learning) != -1.0:
        args += ["--mog2_learning_rate", str(learning)]
    gap = cfg.get("max_interp_gap")
    if gap is not None and int(gap) != 0:
        args += ["--max_interp_gap", str(gap)]
    sigma = cfg.get("heatmap_sigma")
    if sigma is not None and float(sigma) != 0:
        args += ["--heatmap_sigma", str(sigma)]
    if cfg.get("autoconfig"):
        args.append("--autoconfig")
    if cfg.get("colorall"):
        args.append("--colorall")
    args.append("--appmode")
    return args


class BackendRunner(QObject):
    progress = Signal(float, int)
    status = Signal(str)
    calibration = Signal(dict)
    done = Signal(dict)
    failed = Signal(int, str)
    cancelled = Signal()
    started = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process: QProcess | None = None
        self._stdout = b""
        self._stderr_lines: list[str] = []
        self._done_payload: dict | None = None
        self._was_cancelled = False
        self._auto_confirm = os.environ.get("RATTRACKER_AUTOCONFIRM") == "1"
        self._log_path = os.environ.get("RATTRACKER_LOG", "")

    def _log(self, text: str) -> None:
        if not self._log_path:
            return
        try:
            with open(self._log_path, "a", encoding="utf-8") as handle:
                handle.write(text.rstrip() + "\n")
        except OSError:
            pass

    def is_running(self) -> bool:
        return self.process is not None and self.process.state() != QProcess.ProcessState.NotRunning

    def start(self, video: str, cfg: dict, start: str = "", end: str = "",
              radius: str = "60") -> None:
        if self.is_running():
            return
        self._stdout = b""
        self._stderr_lines = []
        self._done_payload = None
        self._was_cancelled = False
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._read_stdout)
        self.process.readyReadStandardError.connect(self._read_stderr)
        self.process.finished.connect(self._on_finished)
        self.process.errorOccurred.connect(self._on_error)
        env = self.process.processEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        self.process.setProcessEnvironment(env)
        args = build_args(video, cfg, start, end, radius)
        command = backend_command()
        self.process.start(command[0], command[1:] + args)
        self.started.emit()

    def respond(self, payload: dict) -> None:
        self._write(payload)

    def _write(self, payload: dict) -> None:
        if self.process is None:
            return
        data = (json.dumps(payload) + "\n").encode("utf-8")
        self.process.write(data)

    def _auto_points(self, message: dict) -> dict:
        # Test hook only: use saved/prefilled coordinates or known fixture points.
        points = message.get("points") or {}
        if message.get("existing_pool"):
            points = {**message["existing_pool"], **points}
        if not points:
            points = {
                "pool_west": "274,128", "pool_north": "665,92",
                "pool_east": "730,382", "pool_south": "349,443",
            }
        if message.get("require_platform") and "platform_nw" not in points:
            points.update({
                "platform_nw": "328,16", "platform_ne": "744,30",
                "platform_se": "754,473", "platform_sw": "318,480",
            })
        return points

    def cancel(self) -> None:
        if self.process is None:
            return
        self._was_cancelled = True
        self.process.kill()

    def _read_stdout(self) -> None:
        if self.process is None:
            return
        self._stdout += bytes(self.process.readAllStandardOutput())
        while b"\n" in self._stdout:
            line, self._stdout = self._stdout.split(b"\n", 1)
            text = line.decode("utf-8", errors="replace").strip()
            if text:
                self._handle_line(text)

    def _read_stderr(self) -> None:
        if self.process is None:
            return
        data = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line.strip():
                self._stderr_lines.append(line.rstrip())
                self._log("stderr: " + line.rstrip())

    def _handle_line(self, text: str) -> None:
        self._log(text)
        try:
            payload = json.loads(text)
        except ValueError:
            trimmed = text.strip()
            if trimmed.startswith("[autoconfig]"):
                self.status.emit(trimmed.replace("[autoconfig]", "").strip())
            elif trimmed.startswith("[speed-adaptive]"):
                self.status.emit(trimmed.replace("[speed-adaptive]", "").strip())
            else:
                self._stderr_lines.append(trimmed)
            return

        if payload.get("needs_calib") or payload.get("needs_confirm"):
            if self._auto_confirm:
                if payload.get("needs_confirm"):
                    self._write({"confirmed": True})
                else:
                    self._write(self._auto_points(payload))
            else:
                self.calibration.emit(payload)
            return
        if "progress" in payload:
            self.progress.emit(float(payload.get("progress", 0.0)), int(payload.get("eta", 0) or 0))
            return
        if payload.get("done"):
            self._done_payload = payload
            self.done.emit(payload)

    def _on_error(self, error) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self.failed.emit(-1, "Backend failed to start. Is Python available?")

    def _on_finished(self, code: int, _status) -> None:
        self._read_stdout()
        self._read_stderr()
        payload = self._done_payload
        was_cancelled = self._was_cancelled
        self.process = None
        if was_cancelled:
            self.cancelled.emit()
            return
        if payload is not None:
            return
        detail = "\n".join(self._stderr_lines[-80:])
        if not detail:
            detail = "The analysis engine stopped without producing a result."
        self._log(f"failed: exit {code}\n{detail}")
        self.failed.emit(code, detail)
