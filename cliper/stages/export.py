"""export — lay out finished variants per account + write a manifest per clip.

out/<niche>/<account>/<clip>.mp4 and a sibling <clip>.json the schedule/publish steps consume.
A social caption + hashtags are generated per clip (OpenAI if available, else a transcript hook).
"""
from __future__ import annotations

import json
import shutil

from ..pipeline import Context
from ..utils import social
from ..utils.media import ensure_dir


def run(ctx: Context) -> Context:
    niche = ctx.niche["name"]
    base_tags = ctx.niche.get("hashtags", [])
    schedule = ctx.niche.get("schedule", {})
    model = ctx.niche.get("select", {}).get("model")
    count = 0

    for clip in ctx.clips:
        meta = social.caption_variants(
            clip.text, base_tags, clip.variants.keys(), model=model, niche_name=niche
        )
        for account, variant in clip.variants.items():
            caption, hashtags = meta[account]
            outdir = ensure_dir(ctx.out_dir / account)
            final = outdir / f"{clip.id}.mp4"
            shutil.copy2(variant, final)
            manifest = {
                "clip_id": clip.id,
                "niche": niche,
                "account": account,
                "source_id": clip.source_id,
                "start": clip.start,
                "end": clip.end,
                "duration": clip.duration,
                "score": round(clip.score, 4),
                "reason": clip.reason,
                "qa": clip.qa,
                "caption": caption,
                "hashtags": hashtags,
                "transcript": clip.text,
                "schedule": schedule,
                "video": str(final),
            }
            (outdir / f"{clip.id}.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            count += 1
        _write_state(ctx, clip, niche)
    print(f"  exported {count} files to {ctx.out_dir}")
    return ctx


def _write_state(ctx: Context, clip, niche: str) -> None:
    """Persist per-clip state (words, intermediate paths) so the UI can edit & re-render."""
    state_dir = ensure_dir(ctx.work_dir / "state")
    (state_dir / f"{clip.id}.json").write_text(json.dumps({
        "clip_id": clip.id, "niche": niche, "source_id": clip.source_id,
        "start": clip.start, "end": clip.end, "duration": clip.duration,
        "score": round(clip.score, 4), "reason": clip.reason, "qa": clip.qa,
        "text": clip.text, "words": clip.words,
        "vertical": str(clip.vertical_path) if clip.vertical_path else None,
        "captioned": str(clip.captioned_path) if clip.captioned_path else None,
        "accounts": list(clip.variants.keys()),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
