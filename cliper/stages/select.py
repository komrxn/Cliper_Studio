"""select — three-level moment selection: TEXT → AUDIO → SCENE.

The proper way to find a coherent short clip (not "pure loudness"):
  1. TEXT  — the whisper transcript gives sentence/segment boundaries, so a clip starts and
             ends on a complete thought (a coherent scene), never mid-word.
  2. AUDIO — per-second loudness ranks which spans are engaging and skips dead air.
  3. SCENE — boundaries snap to the nearest shot change so each clip is one visual scene.

`suggest()` runs all three for EVERY niche. When OpenAI is available it ranks the text spans
(best hooks, skip ads); otherwise a local audio+length heuristic ranks them. If a source has
little/no speech, it degrades to audio-energy windows that are still snapped to scene cuts.
"""
from __future__ import annotations

import numpy as np

from ..pipeline import Clip, Context
from ..utils import ffmpeg, llm
from . import detect
from .detect import _scene_cuts

SYSTEM = (
    "You are an expert short-form video editor who finds viral moments in long videos. "
    "You pick self-contained clips that start at a natural sentence boundary, contain a "
    "complete thought or a strong hook, and end cleanly. You never cut off a punchline, "
    "and you skip ads/sponsor reads and filler."
)


def run(ctx: Context) -> Context:
    """Pipeline entry point — same three-level selection used by the Studio Suggest."""
    return suggest(ctx)


def suggest(ctx: Context, on_progress=None) -> Context:
    """Three-level selection (TEXT → AUDIO → SCENE) for every source in ctx."""
    cfg = ctx.niche.get("select", {})
    clip_cfg = ctx.niche.get("clip", {})
    min_sec = float(clip_cfg.get("min_sec", 25))
    max_sec = float(clip_cfg.get("max_sec", 60))
    want = int(ctx.max_clips or clip_cfg.get("max_per_video", 5))
    model = cfg.get("model")

    for src in ctx.sources:
        if on_progress:
            on_progress("finding scene cuts", 0.55)
        scene_cuts = _scene_cuts(src.path)            # SCENE: visual shot boundaries
        energy = _energy(src.path)                    # AUDIO: per-second loudness
        clips: list[Clip] = []

        if src.transcript:                            # TEXT: sentence-bounded coherent scenes
            if on_progress:
                on_progress("ranking moments", 0.8)
            if llm.available():
                try:
                    clips = _llm_pick(src, want, min_sec, max_sec, scene_cuts, model)
                except Exception as exc:  # quota/outage/network → degrade to local, never fail
                    print(f"  (OpenAI ranking failed: {str(exc)[:120]}; using local text+audio)")
                    clips = _local_pick(src, want, min_sec, max_sec, scene_cuts, energy)
            else:
                clips = _local_pick(src, want, min_sec, max_sec, scene_cuts, energy)

        if len(clips) < want:                         # supplement / fallback with audio windows
            clips += _audio_windows(src, want - len(clips), min_sec, max_sec, scene_cuts,
                                    energy, exclude=clips)

        ctx.clips.extend(clips[:want])
        print(f"  {src.id}: {len(clips[:want])} moments "
              f"({'text' if src.transcript else 'audio'} → audio → {len(scene_cuts)} scene cuts)")
    return ctx


def _energy(path) -> np.ndarray:
    """Per-second audio loudness; empty array if the source has no decodable audio."""
    try:
        audio, sr = ffmpeg.decode_audio_mono(path)
        return detect._energy_per_second(audio, sr)
    except Exception as exc:  # audio scoring is a refinement, never fatal
        print(f"  (audio energy skipped: {exc})")
        return np.array([])


def _mean_energy(energy: np.ndarray, start: float, end: float) -> float:
    if energy.size == 0:
        return 0.0
    a, b = int(max(0, start)), int(min(len(energy), end))
    seg = energy[a:b]
    return float(seg.mean()) if seg.size else 0.0


def _llm_pick(src, want, min_sec, max_sec, scene_cuts, model) -> list[Clip]:
    transcript = "\n".join(
        f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}" for s in src.transcript
    )
    user = (
        f"Pick the {want} best short-form moments from this transcript. Each must be a "
        f"SELF-CONTAINED moment {min_sec:.0f}-{max_sec:.0f}s long that BEGINS at the start of a "
        "sentence and ENDS at the end of a sentence — never cut off mid-thought; prefer a strong "
        'hook at the start. Respond with JSON: {"clips": [{"start": <sec>, "end": <sec>, '
        '"reason": <str>, "score": <0..1>}]} ordered best first.\n\nTRANSCRIPT:\n' + transcript
    )
    data = llm.chat_json(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}], model=model,
    )
    return _to_clips(src.id, data.get("clips", []), src.transcript, scene_cuts, min_sec, max_sec, want)


def _local_pick(src, want, min_sec, max_sec, scene_cuts, energy) -> list[Clip]:
    """No-OpenAI ranking: each transcript sentence is a candidate start; score the resulting
    coherent (sentence+scene snapped) span by its mean audio energy. Text picks the boundaries,
    audio picks which are engaging."""
    segs = src.transcript
    cand = []
    for i, s in enumerate(segs):
        snapped = _snap_to_segments(segs, s["start"], s["start"] + (min_sec + max_sec) / 2,
                                    scene_cuts, min_sec, max_sec)
        if snapped is None:
            continue
        a, b = snapped
        cand.append((a, b, _mean_energy(energy, a, b)))
    cand.sort(key=lambda c: c[2], reverse=True)
    picked, clips = [], []
    for a, b, sc in cand:
        if any(min(b, pb) - max(a, pa) > 0 for pa, pb in picked):  # no overlap
            continue
        picked.append((a, b))
        clips.append(Clip(id=f"{src.id}_{len(clips):02d}", source_id=src.id, start=a, end=b,
                          score=round(min(1.0, sc * 3), 2), reason="text+audio"))
        if len(clips) >= want:
            break
    return clips


def _audio_windows(src, want, min_sec, max_sec, scene_cuts, energy, exclude) -> list[Clip]:
    """AUDIO fallback/supplement: loudest non-overlapping windows, snapped to scene cuts. Used
    when there's no/sparse speech, or to top up a short text pick."""
    if energy.size < min_sec or want <= 0:
        return []
    target = (min_sec + max_sec) / 2
    taken = [(c.start, c.end) for c in exclude]
    windows = detect._nms(detect._rank_windows(energy, target, min_sec, max_sec), want + len(taken))
    clips = []
    for start, end, score in windows:
        s, e = detect._snap(start, end, scene_cuts, min_sec, max_sec)
        if any(min(e, pe) - max(s, ps) > 0 for ps, pe in taken):  # skip overlaps
            continue
        taken.append((s, e))
        clips.append(Clip(id=f"{src.id}_a{len(clips):02d}", source_id=src.id, start=s, end=e,
                          score=round(float(score), 2), reason="audio+scene"))
        if len(clips) >= want:
            break
    return clips


def _nearest_cut(cuts, t):
    return min(cuts, key=lambda x: abs(x - t)) if cuts else None


def _snap_to_segments(segments, start, end, scene_cuts, min_sec, max_sec, tol=2.0):
    """Snap [start,end] to clean boundaries — a completed sentence that ALSO lands on a visual
    scene change, so clips never end abruptly.

    Coherence wins, length is a target. `start` snaps to the nearest segment start (and to a
    nearby scene cut if one is close). Among segment-boundary ends with duration in [min,max],
    prefer the sentence end that has a scene cut right after it (the thought finishes AND the shot
    changes) and end exactly on that cut; tie-break by closeness to the LLM's pick. Reach `min`
    only via whole following segments; if unreachable on a clean boundary → drop.
    """
    if not segments:
        return None
    si = min(range(len(segments)), key=lambda k: abs(segments[k]["start"] - start))
    actual_start = segments[si]["start"]
    c = _nearest_cut(scene_cuts, actual_start)
    if c is not None and abs(c - actual_start) <= tol:
        actual_start = c

    best = None            # (fwd_cut_dist, llm_dist, end_time)
    fallback_end = None
    for ej in range(si, len(segments)):
        e = segments[ej]["end"]
        dur = e - actual_start
        if dur > max_sec:
            break
        fallback_end = e
        if dur >= min_sec:
            after = [x for x in scene_cuts if e <= x <= e + tol and x - actual_start <= max_sec]
            end_time = min(after) if after else e        # end on the scene cut after the sentence
            cand = ((end_time - e) if after else 99.0, abs(e - end), end_time)
            if best is None or (cand[0], cand[1]) < (best[0], best[1]):
                best = cand
    if best is not None:
        return round(actual_start, 3), round(best[2], 3)
    if fallback_end is None:                       # one segment alone is longer than max — keep it
        return round(actual_start, 3), round(segments[si]["end"], 3)
    return None                                    # longest coherent clip < min_sec → drop


def _to_clips(source_id, raw, segments, scene_cuts, min_sec, max_sec, want):
    clips = []
    for c in raw:
        if len(clips) >= want:
            break
        try:
            start, end = float(c["start"]), float(c["end"])
        except (KeyError, TypeError, ValueError):
            continue
        snapped = _snap_to_segments(segments, start, end, scene_cuts, min_sec, max_sec)
        if snapped is None:                        # no coherent clip of >= min_sec here
            continue
        s, e = snapped
        clips.append(Clip(
            id=f"{source_id}_{len(clips):02d}", source_id=source_id,
            start=s, end=e,
            score=llm.as_float(c.get("score"), 0.0), reason=str(c.get("reason", "")),
        ))
    return clips
