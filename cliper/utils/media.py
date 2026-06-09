"""Small filesystem/media helpers shared across stages."""
from __future__ import annotations

import re
from pathlib import Path

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def slugify(text: str, max_len: int = 60) -> str:
    """Filesystem-safe slug for clip/account names."""
    s = _SAFE.sub("_", text.strip()).strip("_")
    return (s[:max_len] or "clip").lower()


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
