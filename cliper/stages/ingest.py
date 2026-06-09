"""ingest — resolve a niche's sources into local files.

A source that already exists on disk is used as-is (great for testing); otherwise it is
downloaded via yt-dlp (any site) into work/<niche>/sources/. Respects ctx.limit.
"""
from __future__ import annotations

from pathlib import Path

from ..pipeline import Context, Source
from ..utils import download as dl


def run(ctx: Context) -> Context:
    sdir = ctx.work_dir / "sources"
    sdir.mkdir(parents=True, exist_ok=True)

    sources = ctx.niche.get("sources", [])
    if ctx.limit:
        sources = sources[: ctx.limit]

    for raw in sources:
        local = Path(raw)
        if local.exists():
            ctx.sources.append(Source(id=local.stem, path=local.resolve(), title=local.stem))
            print(f"  using local source: {local}")
            continue
        path = dl.download(raw, sdir)
        print(f"  downloaded: {path.stem} <- {raw}")
        ctx.sources.append(Source(id=path.stem, path=path, url=raw, title=path.stem))
    return ctx
