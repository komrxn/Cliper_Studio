"""Pipeline data model, stage ordering, and the runner."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# Full stage order. Optional stages are skipped based on niche config / flags.
STAGE_ORDER = [
    "ingest", "detect", "transcribe", "select",
    "cut", "reframe", "caption", "aiqa", "uniquify", "export",
]


@dataclass
class Source:
    id: str
    path: Path
    url: str = ""
    title: str = ""
    transcript: list[dict] = field(default_factory=list)  # [{start, end, text}]


@dataclass
class Clip:
    id: str
    source_id: str
    start: float
    end: float
    score: float = 0.0
    reason: str = ""
    # filled by later stages:
    cut_path: Path | None = None
    vertical_path: Path | None = None
    captioned_path: Path | None = None
    words: list[dict] = field(default_factory=list)        # [{start, end, word}]
    text: str = ""
    qa: dict = field(default_factory=dict)                 # {postable, score, reason}
    variants: dict[str, Path] = field(default_factory=dict)  # account -> rendered path

    @property
    def duration(self) -> float:
        return round(self.end - self.start, 3)

    def current_path(self) -> Path | None:
        """Latest rendered artifact (captioned > vertical > cut)."""
        return self.captioned_path or self.vertical_path or self.cut_path


@dataclass
class Context:
    niche: dict[str, Any]
    work_dir: Path
    out_dir: Path
    limit: int | None = None          # max source videos
    max_clips: int | None = None      # max clips per source (overrides config)
    smart: bool = False
    device: str = "cpu"
    sources: list[Source] = field(default_factory=list)
    clips: list[Clip] = field(default_factory=list)


def is_smart(ctx: Context) -> bool:
    return ctx.smart or ctx.niche.get("strategy") == "smart"


def stages_for(ctx: Context) -> list[str]:
    """Resolve which stages actually run for this context."""
    skip: set[str] = set()
    if is_smart(ctx):
        skip.add("detect")                       # select drives clip choice instead
    else:
        skip |= {"transcribe", "select"}
    if not ctx.niche.get("caption", {}).get("enabled"):
        skip.add("caption")
    if not ctx.niche.get("qa", {}).get("enabled"):
        skip.add("aiqa")
    return [s for s in STAGE_ORDER if s not in skip]


def run_pipeline(ctx: Context, log: Callable[[str], None] = print) -> Context:
    """Execute the resolved stages in order, threading ctx through each."""
    from .stages import (  # noqa: F401  local import keeps optional deps lazy
        ingest, detect, transcribe, select, cut, reframe, caption, aiqa, uniquify, export,
    )

    registry = {
        "ingest": ingest, "detect": detect, "transcribe": transcribe, "select": select,
        "cut": cut, "reframe": reframe, "caption": caption, "aiqa": aiqa,
        "uniquify": uniquify, "export": export,
    }
    for name in stages_for(ctx):
        log(f"→ {name}")
        ctx = registry[name].run(ctx)
    return ctx
