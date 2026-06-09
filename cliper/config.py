"""Load and lightly validate niche YAML configs; load local .env secrets."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
NICHES_DIR = ROOT / "niches"


def load_env(path: str | Path | None = None) -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ (without overriding existing)."""
    p = Path(path) if path else ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


# Category presets — the "smart" niche taxonomy. A niche picks a `category`; these defaults are
# merged UNDER its explicit fields, so a niche only needs name/category/sources/accounts.
CATEGORIES: dict[str, dict] = {
    "dialogue": {  # talk-driven (youtubers, podcasts, sitcoms, cartoons, series): transcript + LLM
        "strategy": "smart",
        "select": {"model": "gpt-4o-mini", "transcribe_model": "base"},
        "reframe": "blur_pad",
        "caption": {"enabled": True, "style": "classic", "model": "small"},
        "qa": {"enabled": True, "model": "gpt-4o-mini", "threshold": 0.45, "keep_min": 3},
        "clip": {"min_sec": 60, "max_sec": 90, "max_per_video": 6},
        "uniquify": {"mirror": False, "speed_jitter": 0.03, "zoom_jitter": 0.05},
        "schedule": {"per_day": 3, "stagger_min": 90},
    },
    "action": {  # visual-driven (action scenes, sports, fights): scene + audio energy
        "strategy": "heuristic",
        "reframe": "blur_pad",
        "caption": {"enabled": False},
        "qa": {"enabled": False},
        "clip": {"min_sec": 20, "max_sec": 60, "max_per_video": 8},
        "uniquify": {"mirror": False, "speed_jitter": 0.03, "zoom_jitter": 0.06},
        "schedule": {"per_day": 3, "stagger_min": 90},
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge `override` onto `base` (override wins; nested dicts merged recursively)."""
    out = dict(base)
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def load_niche(name_or_path: str) -> dict[str, Any]:
    """Load a niche config by name (niches/<name>.yaml) or by explicit path.

    If the niche declares a `category`, that category's preset is merged in as defaults (the
    niche's own fields win).
    """
    p = Path(name_or_path)
    if not p.exists():
        p = NICHES_DIR / f"{name_or_path}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"niche config not found: {name_or_path}")
    data = yaml.safe_load(p.read_text()) or {}
    data.setdefault("name", p.stem)
    category = data.get("category")
    if category:
        if category not in CATEGORIES:
            raise ValueError(f"{p}: unknown category {category!r}; use one of {list(CATEGORIES)}")
        data = _deep_merge(CATEGORIES[category], data)   # explicit niche fields win
    _validate(data, p)
    return data


def _validate(data: dict[str, Any], path: Path) -> None:
    if not data.get("sources"):
        raise ValueError(f"{path}: 'sources' is required")
    strategy = data.get("strategy", "heuristic")
    if strategy not in ("heuristic", "smart"):
        raise ValueError(f"{path}: strategy must be 'heuristic' or 'smart', got {strategy!r}")
    if not data.get("accounts"):
        raise ValueError(f"{path}: 'accounts' (target account pool) is required")
