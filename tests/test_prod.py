"""Tests for the prod-hardening pass: isolated scene detection + clip deletion."""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not on PATH")


def _make_clip(path, seconds=3):
    # two visually distinct halves so a scene cut exists
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"testsrc=size=320x180:rate=12:duration={seconds}",
         "-c:v", "libx264", str(path)],
        check=True, capture_output=True,
    )


def test_scene_cuts_runs_with_av_loaded(tmp_path):
    """Detection must survive PyAV being imported in the parent (the cv2/av clash repro)."""
    pytest.importorskip("av")
    import av  # noqa: F401  — load PyAV in the parent first

    from cliper.utils import scenes
    clip = tmp_path / "c.mp4"
    _make_clip(clip)
    cuts = scenes.scene_cuts(clip, fast=True)
    assert isinstance(cuts, list)
    assert all(isinstance(c, float) for c in cuts)


def test_delete_clip_removes_all_artifacts(tmp_path, monkeypatch):
    from cliper.web import render
    monkeypatch.setattr(render, "ROOT", tmp_path)

    niche, clip_id, acc = "n", "src_00", "acc_a"
    (tmp_path / "out" / niche / acc).mkdir(parents=True)
    (tmp_path / "work" / niche / "state").mkdir(parents=True)
    mp4 = tmp_path / "out" / niche / acc / f"{clip_id}.mp4"
    meta = tmp_path / "out" / niche / acc / f"{clip_id}.json"
    state = tmp_path / "work" / niche / "state" / f"{clip_id}.json"
    mp4.write_bytes(b"x")
    meta.write_text("{}")
    state.write_text(json.dumps({"clip_id": clip_id, "accounts": [acc]}))

    removed = render.delete_clip(niche, clip_id)

    assert not mp4.exists() and not meta.exists() and not state.exists()
    assert len(removed) == 3
    assert render.delete_clip(niche, clip_id) == []  # idempotent
