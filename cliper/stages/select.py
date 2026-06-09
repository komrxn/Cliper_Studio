"""select — pick the best moments from the transcript via OpenAI (smart niches).

Sends the timestamped transcript to OpenAI and asks for the most engaging, self-contained
moments with clean sentence boundaries; turns them into ctx.clips. Fixes the "clipped
punchline" failure of pure-heuristic selection.
"""
from __future__ import annotations

from ..pipeline import Clip, Context
from ..utils import llm
from .detect import _scene_cuts

SYSTEM = (
    "You are an expert short-form video editor who finds viral moments in long videos. "
    "You pick self-contained clips that start at a natural sentence boundary, contain a "
    "complete thought or a strong hook, and end cleanly. You never cut off a punchline, "
    "and you skip ads/sponsor reads and filler."
)


def run(ctx: Context) -> Context:
    cfg = ctx.niche.get("select", {})
    clip_cfg = ctx.niche.get("clip", {})
    min_sec = float(clip_cfg.get("min_sec", 25))
    max_sec = float(clip_cfg.get("max_sec", 60))
    want = int(ctx.max_clips or clip_cfg.get("max_per_video", 5))
    model = cfg.get("model")

    for src in ctx.sources:
        if not src.transcript:
            print(f"  {src.id}: empty transcript, skipping")
            continue
        scene_cuts = _scene_cuts(src.path)     # visual shot boundaries → clean, non-abrupt cuts
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
            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            model=model,
        )
        picked = _to_clips(src.id, data.get("clips", []), src.transcript, scene_cuts,
                           min_sec, max_sec, want)
        ctx.clips.extend(picked)
        print(f"  {src.id}: {len(picked)} moments selected ({len(scene_cuts)} scene cuts)")
    return ctx


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
