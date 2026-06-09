"""Re-render a single clip after UI edits (subtitle text, style, position, mirror).

Always re-derives from the clean 9:16 `vertical` (no burned subs), so mirror can be toggled
on/off losslessly. Mirror is applied in the same pass as the subtitle burn (pre_vf=hflip), so
the video is mirrored but the captions stay readable.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..config import ROOT
from ..stages.uniquify import _seed
from ..utils import captions, ffmpeg


def _state_path(niche: str, clip_id: str) -> Path:
    return ROOT / "work" / niche / "state" / f"{clip_id}.json"


def load_state(niche: str, clip_id: str) -> dict:
    p = _state_path(niche, clip_id)
    if not p.exists():
        raise FileNotFoundError(f"no editable state for {niche}/{clip_id} (re-run the pipeline)")
    return json.loads(p.read_text(encoding="utf-8"))


def _words_from_text(text: str, original: list[dict]) -> list[dict]:
    """Re-attach edited text tokens to the original word timings (keeps sub timing intact)."""
    out: list[dict] = []
    for i, tok in enumerate(text.split()):
        if i < len(original):
            out.append({"start": original[i]["start"], "end": original[i]["end"], "word": tok})
        else:
            last = out[-1]["end"] if out else 0.0
            out.append({"start": last, "end": last + 0.3, "word": tok})
    return out


def rerender_clip(niche: str, clip_id: str, *, words=None, text=None, style="classic",
                  position=None, mirror=False, uniquify_conf=None) -> dict:
    state = load_state(niche, clip_id)
    vertical = Path(state["vertical"])
    if not vertical.exists():
        raise FileNotFoundError(f"vertical source missing for {clip_id}")

    if words is None:
        words = _words_from_text(text, state.get("words", [])) if text is not None \
            else state.get("words", [])

    edit_dir = ROOT / "work" / niche / "edit"
    ass = captions.write_ass(words, edit_dir / f"{clip_id}.ass", style=style, position=position)
    captioned = ffmpeg.burn_subtitles(
        vertical, edit_dir / f"{clip_id}.mp4", ass, pre_vf="hflip" if mirror else None
    )

    conf = dict(uniquify_conf or {})
    conf["mirror"] = False  # mirror already baked into `captioned`
    out_dir = ROOT / "out" / niche
    for account in state.get("accounts", []):
        ffmpeg.uniquify(captioned, out_dir / account / f"{clip_id}.mp4",
                        _seed(clip_id, account), conf)

    state.update({"words": words, "text": " ".join(w["word"] for w in words),
                  "style": style, "position": position, "mirror": mirror})
    _state_path(niche, clip_id).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def update_meta(niche: str, clip_id: str, *, account=None, caption=None, hashtags=None) -> None:
    out_dir = ROOT / "out" / niche
    accounts = [account] if account else [p.name for p in out_dir.iterdir() if p.is_dir()]
    for acc in accounts:
        mf = out_dir / acc / f"{clip_id}.json"
        if not mf.exists():
            continue
        data = json.loads(mf.read_text(encoding="utf-8"))
        if caption is not None:
            data["caption"] = caption
        if hashtags is not None:
            data["hashtags"] = hashtags
        mf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
