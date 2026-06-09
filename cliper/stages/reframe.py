"""reframe — 16:9 (any aspect) -> 9:16 vertical via blur-pad (utils.ffmpeg.blur_pad).

Phase 3+ may add smart_crop with subject/motion tracking.
"""
from __future__ import annotations

from ..pipeline import Context
from ..utils import ffmpeg


def run(ctx: Context) -> Context:
    mode = ctx.niche.get("reframe", "blur_pad")
    if mode != "blur_pad":
        raise NotImplementedError(f"reframe mode {mode!r} not implemented (Phase 1 = blur_pad)")
    vdir = ctx.work_dir / "vertical"
    for clip in ctx.clips:
        clip.vertical_path = ffmpeg.blur_pad(clip.cut_path, vdir / f"{clip.id}.mp4")
    print(f"  reframed {len(ctx.clips)} clips -> 9:16")
    return ctx
