"""detect — generate candidate clip windows (always-on, Mac, no GPU).

Heuristic: per-second audio loudness (RMS) scores a sliding window of ~target length; the
strongest, non-overlapping windows are kept and their edges snapped to nearby scene cuts
(PySceneDetect) so clips don't start mid-shot. Populates ctx.clips.
"""
from __future__ import annotations

import numpy as np

from ..pipeline import Clip, Context
from ..utils import ffmpeg


def run(ctx: Context) -> Context:
    clip_cfg = ctx.niche.get("clip", {})
    min_sec = float(clip_cfg.get("min_sec", 25))
    max_sec = float(clip_cfg.get("max_sec", 60))
    target = (min_sec + max_sec) / 2
    max_per = int(ctx.max_clips or clip_cfg.get("max_per_video", 5))

    for src in ctx.sources:
        audio, sr = ffmpeg.decode_audio_mono(src.path)
        energy = _energy_per_second(audio, sr)
        if energy.size < min_sec:
            print(f"  {src.id}: too short / no audio, skipping")
            continue
        cuts = _scene_cuts(src.path)
        windows = _nms(_rank_windows(energy, target, min_sec, max_sec), max_per)
        for i, (start, end, score) in enumerate(windows):
            s, e = _snap(start, end, cuts, min_sec, max_sec)
            ctx.clips.append(Clip(id=f"{src.id}_{i:02d}", source_id=src.id,
                                  start=s, end=e, score=score))
        print(f"  {src.id}: {len(windows)} candidate windows")
    return ctx


def _energy_per_second(audio: np.ndarray, sr: int) -> np.ndarray:
    n = len(audio) // sr
    if n == 0:
        return np.array([])
    frames = audio[: n * sr].reshape(n, sr)
    return np.sqrt((frames ** 2).mean(axis=1) + 1e-9)


def _rank_windows(energy, target, min_sec, max_sec, step=3):
    length = int(max(min_sec, min(round(target), max_sec, len(energy))))
    out = []
    for start in range(0, max(1, len(energy) - length + 1), step):
        seg = energy[start:start + length]
        out.append((float(start), float(start + length), float(seg.mean() + 0.5 * seg.std())))
    out.sort(key=lambda w: w[2], reverse=True)
    return out


def _overlap(a, b) -> float:
    inter = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    union = (a[1] - a[0]) + (b[1] - b[0]) - inter
    return inter / union if union > 0 else 0.0


def _nms(windows, k, thresh=0.3):
    picked = []
    for w in windows:
        if all(_overlap(w, p) < thresh for p in picked):
            picked.append(w)
        if len(picked) >= k:
            break
    return picked


def _scene_cuts(path) -> list[float]:
    """Full-accuracy scene cuts, run in an isolated subprocess (see `utils/scenes`) so OpenCV
    doesn't clash with PyAV (`av`) in the same interpreter."""
    from ..utils import scenes
    return scenes.scene_cuts(path, fast=False)


def _nearest(cuts, t, tol):
    if not cuts:
        return t
    best = min(cuts, key=lambda c: abs(c - t))
    return best if abs(best - t) <= tol else t


def _snap(start, end, cuts, min_sec, max_sec, tol=2.0):
    start = _nearest(cuts, start, tol)
    end = _nearest(cuts, end, tol)
    if end - start < min_sec:
        end = start + min_sec
    if end - start > max_sec:
        end = start + max_sec
    return round(start, 3), round(end, 3)
