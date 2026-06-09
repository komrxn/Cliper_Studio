"""Scene-cut detection, isolated in a spawned subprocess.

Why a subprocess: PySceneDetect uses OpenCV (`cv2`) and faster-whisper uses PyAV (`av`). Both
ship a bundled `libavdevice`; loading both in one interpreter registers duplicate Obj-C classes
and can crash cv2 frame reads ("0 cuts" after a transcribe ran earlier in the same process).
Running detection in a `spawn`-ed child that imports only `scenedetect` keeps `cv2` and `av`
in separate interpreters, so neither conflicts. This module is kept import-light (no `av`, no
`cv2` at module scope) so the spawned child never triggers the clash.
"""
from __future__ import annotations

import atexit
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

_EXECUTOR: ProcessPoolExecutor | None = None


def _detect(path_str: str, fast: bool) -> list[float]:
    """Run in the spawned child. Imports only scenedetect (cv2) — never `av`."""
    from scenedetect import ContentDetector, SceneManager, open_video

    video = open_video(path_str)
    sm = SceneManager()
    sm.add_detector(ContentDetector())
    if fast:  # timeline filmstrip: downscale + frame-skip ≈ 14s on a 12-min clip
        sm.auto_downscale = False
        sm.downscale = 3
        sm.detect_scenes(video, frame_skip=1, show_progress=False)
    else:  # pipeline: full accuracy
        sm.detect_scenes(video, show_progress=False)
    scenes = sm.get_scene_list()
    cuts = [s[0].get_seconds() for s in scenes]
    if scenes:
        cuts.append(scenes[-1][1].get_seconds())
    return sorted(cuts)


def _get_executor() -> ProcessPoolExecutor:
    global _EXECUTOR
    if _EXECUTOR is None:
        # one long-lived spawn worker, reused across calls (spawn startup ~0.5s)
        _EXECUTOR = ProcessPoolExecutor(max_workers=1, mp_context=get_context("spawn"))
        atexit.register(lambda: _EXECUTOR and _EXECUTOR.shutdown(wait=False, cancel_futures=True))
    return _EXECUTOR


def scene_cuts(path: str | Path, fast: bool = True, timeout: float = 600.0) -> list[float]:
    """Scene-cut timestamps (seconds). Detection runs in an isolated subprocess; on any failure
    it falls back to in-process detection, and finally to `[]` (detection is a refinement, never
    fatal — callers degrade to no edge-snapping)."""
    p = str(path)
    try:
        return _get_executor().submit(_detect, p, fast).result(timeout=timeout)
    except Exception as exc:  # broken pool / timeout / extractor error
        print(f"  (scene_cuts subprocess failed: {exc}; trying in-process)")
        global _EXECUTOR
        _EXECUTOR = None  # drop a possibly-broken pool; next call respawns
        try:
            return _detect(p, fast)
        except Exception as exc2:
            print(f"  (scene detect skipped: {exc2})")
            return []
