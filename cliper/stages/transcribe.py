"""transcribe — whole-video transcript with timestamps (smart niches only).

Local faster-whisper (base/small). Slow on long videos but free; the heavy part offloaded to
OpenAI is the *reasoning* LLM, not transcription. Populates source.transcript = [{start,end,text}].
"""
from __future__ import annotations

from ..pipeline import Context
from ..utils import captions


def run(ctx: Context) -> Context:
    model_name = ctx.niche.get("select", {}).get("transcribe_model", "base")
    model = captions.load_model(model_name, device=ctx.device)
    lang = ctx.niche.get("language")
    for src in ctx.sources:
        src.transcript = captions.transcribe_segments(model, src.path, language=lang)
        print(f"  {src.id}: {len(src.transcript)} transcript segments")
    return ctx
