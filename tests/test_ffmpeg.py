"""Smoke tests for the ffmpeg blur-pad reframe recipe (the Phase 0 core)."""
from __future__ import annotations

import shutil
import subprocess

import pytest

from cliper.utils import ffmpeg

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="ffmpeg/ffprobe not on PATH",
)


def _make_test_source(path, width=640, height=360, seconds=2):
    """Generate a synthetic 16:9 clip with a tone so it has video+audio."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=size={width}x{height}:rate=24:duration={seconds}",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
            "-c:v", "libx264", "-c:a", "aac", "-shortest", str(path),
        ],
        check=True, capture_output=True,
    )


def test_blur_pad_outputs_vertical_1080x1920(tmp_path):
    src = tmp_path / "src.mp4"
    dst = tmp_path / "out.mp4"
    _make_test_source(src)

    # Force libx264 for a deterministic, hardware-independent encode in CI.
    ffmpeg.blur_pad(src, dst, encoder="libx264")

    info = ffmpeg.probe(dst)
    assert (info.width, info.height) == (1080, 1920)
    assert info.duration > 1.0


def test_probe_reads_dimensions(tmp_path):
    src = tmp_path / "src.mp4"
    _make_test_source(src, width=1280, height=720)
    info = ffmpeg.probe(src)
    assert (info.width, info.height) == (1280, 720)
