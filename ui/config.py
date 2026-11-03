"""Configuration profiles and the share-string format.

The JSON layout and the ``--flag value`` share string are compatible with the
old Tauri UI, so profiles exported by older builds still import.
"""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path

from PySide6.QtCore import QStandardPaths

DEFAULT_PROFILE_NAME = "Default"

DEFAULTS = {
    "mog2_history_s": 4.0,
    "mog2_threshold": 32,
    "mog2_detect_shadow": False,
    "morph_open_k": 3,
    "morph_close_k": 15,
    "min_contour_area": 300,
    "max_contour_area": 12000,
    "trail_s": 2.0,
    "debug_frames": 0,
    "pool_west": "",
    "pool_north": "",
    "pool_east": "",
    "pool_south": "",
    "platform_nw": "",
    "platform_ne": "",
    "platform_se": "",
    "platform_sw": "",
    "quadrantcross": False,
    "platformcross": False,
    "paraplatform_enabled": False,
    "paraplatform_scale": 4,
    "proximity": False,
    "latency": False,
    "tracemapcolor_enabled": False,
    "tracemapcolor": "#00ffff",
    "ratcolor_enabled": False,
    "ratcolor": "#ff0000",
    "mog2_learning_rate": -1.0,
    "max_interp_gap": 0,
    "heatmap_sigma": 0,
    "language": "en",
    "autoconfig": False,
    "colorall": False,
}

POINT_KEYS = (
    "pool_west", "pool_north", "pool_east", "pool_south",
    "platform_nw", "platform_ne", "platform_se", "platform_sw",
)


def config_dir() -> Path:
    override = os.environ.get("RATTRACKER_CONFIG_DIR")
    if override:
        path = Path(override)
    else:
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
        if not base:
            base = str(Path.home() / ".config" / "rattracker")
        path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def hex_to_rgb_string(value: str) -> str:
    clean = (value or "").lstrip("#")
    try:
        number = int(clean, 16)
    except ValueError:
        return "0,255,255"
    return f"{(number >> 16) & 255},{(number >> 8) & 255},{number & 255}"


def rgb_string_to_hex(value: str) -> str:
    parts = value.split(",")
    if len(parts) != 3:
        return "#00ffff"
    try:
        return "#" + "".join(f"{int(part):02x}" for part in parts)
    except ValueError:
        return "#00ffff"


def config_to_share_string(cfg: dict, profile_name: str = "") -> str:
    parts: list[str] = []
    if profile_name:
        parts.append(f'--profilename "{profile_name}"')
    parts.append(f"--mog2_history_s {cfg['mog2_history_s']}")
    parts.append(f"--mog2_threshold {cfg['mog2_threshold']}")
    if cfg.get("mog2_detect_shadow"):
        parts.append("--mog2_detect_shadow")
    parts.append(f"--morph_open_k {cfg['morph_open_k']}")
    parts.append(f"--morph_close_k {cfg['morph_close_k']}")
    parts.append(f"--min_contour_area {cfg['min_contour_area']}")
    parts.append(f"--max_contour_area {cfg['max_contour_area']}")
    parts.append(f"--trail_s {cfg['trail_s']}")
    parts.append(f"--debug_frames {cfg['debug_frames']}")
    for key in POINT_KEYS:
        if cfg.get(key):
            parts.append(f"--{key} {cfg[key]}")
    if cfg.get("quadrantcross"):
        parts.append("--quadrantcross")
    if cfg.get("platformcross"):
        parts.append("--platformcross")
    if cfg.get("paraplatform_enabled"):
        parts.append(f"--paraplatform {cfg.get('paraplatform_scale', 4)}")
    if cfg.get("proximity"):
        parts.append("--proximity")
    if cfg.get("latency"):
        parts.append("--latency")
    if cfg.get("tracemapcolor_enabled") and cfg.get("tracemapcolor"):
        parts.append(f"--tracemapcolor {hex_to_rgb_string(cfg['tracemapcolor'])}")
    if cfg.get("ratcolor_enabled") and cfg.get("ratcolor"):
        parts.append(f"--ratcolor {hex_to_rgb_string(cfg['ratcolor'])}")
    learning = cfg.get("mog2_learning_rate")
    if learning is not None and float(learning) != -1.0:
        parts.append(f"--mog2_learning_rate {learning}")
    gap = cfg.get("max_interp_gap")
    if gap is not None and int(gap) != 0:
        parts.append(f"--max_interp_gap {gap}")
    sigma = cfg.get("heatmap_sigma")
    if sigma is not None and float(sigma) != 0:
        parts.append(f"--heatmap_sigma {sigma}")
    if cfg.get("colorall"):
        parts.append("--colorall")
    return " ".join(parts)


def share_string_to_config(text: str) -> tuple[dict, str]:
    result = dict(DEFAULTS)
    profile_name = ""
    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = text.split()
    i = 0
    while i < len(tokens):
        token = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if token == "--profilename":
            profile_name = nxt or ""
            i += 2
        elif token in ("--mog2_history_s", "--mog2_threshold", "--min_contour_area",
                       "--max_contour_area", "--trail_s", "--mog2_learning_rate",
                       "--heatmap_sigma"):
            try:
                result[token[2:]] = float(nxt)
            except (TypeError, ValueError):
                pass
            i += 2
        elif token in ("--morph_open_k", "--morph_close_k", "--debug_frames",
                       "--max_interp_gap"):
            try:
                result[token[2:]] = int(float(nxt))
            except (TypeError, ValueError):
                pass
            i += 2
        elif token.startswith("--") and token[2:] in POINT_KEYS:
            result[token[2:]] = nxt or ""
            i += 2
        elif token == "--paraplatform":
            try:
                result["paraplatform_scale"] = int(float(nxt))
            except (TypeError, ValueError):
                result["paraplatform_scale"] = 4
            result["paraplatform_enabled"] = True
            i += 2
        elif token == "--tracemapcolor":
            result["tracemapcolor_enabled"] = True
            result["tracemapcolor"] = rgb_string_to_hex(nxt or "")
            i += 2
        elif token == "--ratcolor":
            result["ratcolor_enabled"] = True
            result["ratcolor"] = rgb_string_to_hex(nxt or "")
            i += 2
        elif token == "--mog2_detect_shadow":
            result["mog2_detect_shadow"] = True
            i += 1
        elif token == "--quadrantcross":
            result["quadrantcross"] = True
            i += 1
        elif token == "--platformcross":
            result["platformcross"] = True
            i += 1
        elif token == "--proximity":
            result["proximity"] = True
            i += 1
        elif token == "--latency":
            result["latency"] = True
            i += 1
        elif token == "--colorall":
            result["colorall"] = True
            i += 1
        elif token == "--autoconfig":
            result["autoconfig"] = True
            i += 1
        else:
            i += 1
    return result, profile_name


class ConfigStore:
    """Profiles persisted as JSON in the platform config directory."""

    def __init__(self, path: Path | None = None):
        self.path = path or (config_dir() / "profiles.json")
        self.profiles: dict[str, dict] = {}
        self.active = DEFAULT_PROFILE_NAME
        self.load()

    def load(self) -> None:
        data = {}
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        if isinstance(data, dict) and "profiles" in data:
            profiles = data.get("profiles")
            active = data.get("active", DEFAULT_PROFILE_NAME)
        else:
            profiles = data
            active = DEFAULT_PROFILE_NAME
        if not isinstance(profiles, dict):
            profiles = {}
        cleaned = {}
        for name, values in profiles.items():
            if isinstance(values, dict):
                cleaned[str(name)] = {**DEFAULTS, **values}
        if DEFAULT_PROFILE_NAME not in cleaned:
            cleaned[DEFAULT_PROFILE_NAME] = dict(DEFAULTS)
        self.profiles = cleaned
        self.active = active if active in cleaned else DEFAULT_PROFILE_NAME

    def save(self) -> None:
        payload = {"active": self.active, "profiles": self.profiles}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def config(self) -> dict:
        return {**DEFAULTS, **self.profiles.get(self.active, {})}

    def set_config(self, cfg: dict) -> None:
        self.profiles[self.active] = {**DEFAULTS, **cfg}
        self.save()

    def switch(self, name: str) -> dict:
        if name in self.profiles:
            self.active = name
            self.save()
        return self.config()

    def create(self, name: str, cfg: dict | None = None) -> bool:
        name = name.strip()
        if not name or name in self.profiles:
            return False
        self.profiles[name] = {**DEFAULTS, **(cfg or self.config())}
        self.active = name
        self.save()
        return True

    def rename(self, new_name: str) -> bool:
        new_name = new_name.strip()
        if not new_name or new_name == self.active or self.active == DEFAULT_PROFILE_NAME:
            return False
        if new_name in self.profiles:
            return False
        self.profiles[new_name] = self.profiles.pop(self.active)
        self.active = new_name
        self.save()
        return True

    def delete(self) -> bool:
        if self.active == DEFAULT_PROFILE_NAME:
            return False
        self.profiles.pop(self.active, None)
        self.active = DEFAULT_PROFILE_NAME
        self.save()
        return True

    def import_config(self, text: str) -> str:
        imported, profile_name = share_string_to_config(text)
        base = profile_name or "Imported Profile"
        name = base
        counter = 2
        while name in self.profiles:
            name = f"{base} ({counter})"
            counter += 1
        self.profiles[name] = {**self.config(), **imported}
        self.active = name
        self.save()
        return name
