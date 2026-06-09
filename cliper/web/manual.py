"""Manual-marking support: fast scene cuts, snapping a user's range, and rendering clips from
explicit segments — reusing the existing pipeline stages.
"""
from __future__ import annotations

from pathlib import Path

from ..config import ROOT
from ..pipeline import Clip, Context, Source
from ..stages import caption as caption_stage
from ..stages import cut as cut_stage
from ..stages import export as export_stage
from ..stages import reframe as reframe_stage
from ..stages import uniquify as uniquify_stage


def fast_scene_cuts(path) -> list[float]:
    """Quick scene-cut timestamps for the timeline. Runs in an isolated subprocess (see
    `utils/scenes`) so OpenCV doesn't clash with PyAV after a transcribe has loaded `av`."""
    from ..utils import scenes
    return scenes.scene_cuts(path, fast=True)


def snap_manual(scene_cuts, start: float, end: float, tol: float = 2.0) -> tuple[float, float]:
    """Snap an approximate [start,end] to the nearest scene cuts (clean visual edges)."""
    def nearest(t):
        if not scene_cuts:
            return t
        c = min(scene_cuts, key=lambda x: abs(x - t))
        return c if abs(c - t) <= tol else t

    s, e = nearest(start), nearest(end)
    if e <= s:
        e = end
    return round(max(0.0, s), 3), round(e, 3)


def clips_from_segments(niche: dict, source: Source, segments, scene_cuts) -> list[Clip]:
    """Snap each segment to scenes, then run cut→reframe→caption?→uniquify→export. Returns clips."""
    name = niche["name"]
    ctx = Context(niche=niche, work_dir=ROOT / "work" / name, out_dir=ROOT / "out" / name)
    ctx.sources = [source]
    for i, seg in enumerate(segments):
        s, e = snap_manual(scene_cuts, float(seg["start"]), float(seg["end"]))
        ctx.clips.append(Clip(id=f"{source.id}_m{i:02d}", source_id=source.id,
                              start=s, end=e, score=1.0, reason="manual"))
    cut_stage.run(ctx)
    reframe_stage.run(ctx)
    if niche.get("caption", {}).get("enabled"):
        caption_stage.run(ctx)
    uniquify_stage.run(ctx)
    export_stage.run(ctx)
    return ctx.clips
