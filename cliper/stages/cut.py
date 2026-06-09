"""cut — extract each chosen window from its source with ffmpeg."""
from __future__ import annotations

from ..pipeline import Context
from ..utils import ffmpeg


def run(ctx: Context) -> Context:
    cut_dir = ctx.work_dir / "cuts"
    by_id = {s.id: s for s in ctx.sources}
    for clip in ctx.clips:
        src = by_id[clip.source_id]
        clip.cut_path = ffmpeg.cut(src.path, cut_dir / f"{clip.id}.mp4", clip.start, clip.end)
    print(f"  cut {len(ctx.clips)} clips")
    return ctx
