"""caption — dynamic word-level subtitles (CORE feature).

Transcribes the short vertical clip (faster-whisper, word timestamps), writes a karaoke ASS
with the active word highlighted, and burns it on with libass. Runs after reframe so text is
laid out in 9:16 space.
"""
from __future__ import annotations

from ..pipeline import Context
from ..utils import captions, ffmpeg


def run(ctx: Context) -> Context:
    conf = ctx.niche.get("caption", {})
    model = captions.load_model(conf.get("model", "small"), device=ctx.device)
    style = conf.get("style", "classic")
    position = conf.get("position")        # optional override of the style's placement
    lang = ctx.niche.get("language")       # optional: pin whisper language for accuracy
    cdir = ctx.work_dir / "captioned"

    for clip in ctx.clips:
        words = captions.transcribe_words(model, clip.vertical_path, language=lang)
        clip.words = words
        clip.text = " ".join(w["word"] for w in words).strip()
        if not words:
            print(f"  {clip.id}: no speech detected, skipping captions")
            clip.captioned_path = clip.vertical_path
            continue
        ass = captions.write_ass(words, cdir / f"{clip.id}.ass", style=style, position=position)
        clip.captioned_path = ffmpeg.burn_subtitles(clip.vertical_path, cdir / f"{clip.id}.mp4", ass)
        print(f"  {clip.id}: {len(words)} words")
    return ctx
