"""uniquify — produce a DISTINCT render per target account (mandatory in production).

Seeded per (clip, account): mirror / zoom / colour / speed jitter + metadata strip. Reduces
cross-account duplicate suppression (and incidentally Content ID matching). Runs after caption
so the burned subtitles travel with each variant.
"""
from __future__ import annotations

import hashlib

from ..pipeline import Context
from ..utils import ffmpeg


def _seed(clip_id: str, account: str) -> int:
    return int(hashlib.sha256(f"{clip_id}:{account}".encode()).hexdigest()[:8], 16)


def run(ctx: Context) -> Context:
    conf = dict(ctx.niche.get("uniquify", {}))
    # Mirroring flips burned-in subtitles (and logos) into unreadable text, so it is
    # incompatible with captions — disable it whenever captions are on.
    if ctx.niche.get("caption", {}).get("enabled") and conf.get("mirror"):
        conf["mirror"] = False
        print("  (mirror disabled — would flip burned-in subtitles)")
    accounts = ctx.niche.get("accounts", [])
    udir = ctx.work_dir / "variants"
    for clip in ctx.clips:
        base = clip.current_path()
        for account in accounts:
            dst = udir / account / f"{clip.id}.mp4"
            clip.variants[account] = ffmpeg.uniquify(base, dst, _seed(clip.id, account), conf)
    print(f"  {len(ctx.clips)} clips x {len(accounts)} accounts = "
          f"{len(ctx.clips) * len(accounts)} variants")
    return ctx
