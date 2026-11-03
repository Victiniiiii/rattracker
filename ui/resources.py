"""Locate bundled resources in development and in a Nuitka build."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        return True
    name = Path(sys.executable).name.lower()
    return not (name.startswith("python") or name in ("py", "py.exe"))


def resource_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def asset_path(name: str) -> Path:
    return resource_root() / "ui" / "assets" / name


def app_icon_path() -> Path:
    return resource_root() / "appicon.png"
