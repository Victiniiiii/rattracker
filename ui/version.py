"""Single source of truth for the app version.

``VERSION`` at the project root is read at runtime and copied into the
standalone build, so the in-app label, the installers, and CI all agree.
Bump the version by editing that file, then rerun the build.
"""

from __future__ import annotations

import re
import sys
from functools import lru_cache
from pathlib import Path

FALLBACK = "0.0.0"
_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def _candidates():
    here = Path(__file__).resolve()
    yield here.parent.parent / "VERSION"  # source checkout / frozen build
    yield Path(sys.executable).resolve().parent / "VERSION"  # frozen build
    yield Path.cwd() / "VERSION"


@lru_cache(maxsize=1)
def read_version() -> str:
    for path in _candidates():
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if not text:
            continue
        if not _PATTERN.match(text):
            raise ValueError(f"Invalid version in {path}: {text!r}")
        return text
    return FALLBACK
