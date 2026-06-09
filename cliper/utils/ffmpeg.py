"""Thin ffmpeg/ffprobe wrappers. ALL ffmpeg use in Cliper goes through here.

On macOS we default to the VideoToolbox hardware encoder (`h264_videotoolbox`) to keep the
pipeline fast ("flies on Mac"); pass `encoder=` to override (e.g. libx264 for reproducible
CPU encodes in tests).
"""
from __future__ import annotations

import json
import platform
import random
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np


class FFmpegError(RuntimeError):
    """Raised when an ffmpeg/ffprobe invocation fails or a binary is missing."""


def _bin(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise FFmpegError(f"`{name}` not found on PATH; install ffmpeg")
    return path


def default_encoder() -> str:
    """Hardware H.264 on macOS, software x264 elsewhere."""
    return "h264_videotoolbox" if platform.system() == "Darwin" else "libx264"


def _quality_args(encoder: str, crf: int, bitrate: str = "6M") -> list[str]:
    return ["-b:v", bitrate] if encoder.endswith("videotoolbox") else ["-crf", str(crf)]


def _run(cmd: list[str], what: str, cwd: str | None = None) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if res.returncode != 0:
        raise FFmpegError(f"{what} failed: {res.stderr.strip()[-800:]}")


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    duration: float


def probe(src: str | Path) -> VideoInfo:
    """Return width/height/duration of the first video stream of `src`."""
    res = subprocess.run(
        [
            _bin("ffprobe"), "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height:format=duration",
            "-of", "json", str(src),
        ],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        raise FFmpegError(f"ffprobe failed for {src}: {res.stderr.strip()}")
    data = json.loads(res.stdout)
    stream = data["streams"][0]
    duration = float(data.get("format", {}).get("duration", 0.0))
    return VideoInfo(int(stream["width"]), int(stream["height"]), duration)


def decode_audio_mono(src: str | Path, sr: int = 16000) -> tuple[np.ndarray, int]:
    """Decode `src` audio to a mono float32 array in [-1, 1]."""
    res = subprocess.run(
        [_bin("ffmpeg"), "-v", "error", "-i", str(src),
         "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
        capture_output=True,
    )
    if res.returncode != 0:
        raise FFmpegError(f"audio decode failed for {src}: {res.stderr.decode()[-400:]}")
    audio = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    return audio, sr


def extract_frame(src, t: float, dst, *, width: int | None = None) -> Path:
    """Save a single JPEG frame at time `t` seconds from `src` (used by the AI QA gate)."""
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    scale = ["-vf", f"scale={width}:-1"] if width else []
    cmd = [_bin("ffmpeg"), "-y", "-ss", f"{t:.3f}", "-i", str(src),
           "-frames:v", "1", "-update", "1", *scale, str(dst)]
    _run(cmd, f"extract_frame {src.name}")
    return dst


def sprite(src, dst, *, interval: float = 5.0, cols: int = 10, rows: int = 10,
           w: int = 160, h: int = 90) -> Path:
    """Generate one tiled thumbnail sprite (cols x rows) for a timeline filmstrip.

    Samples a frame every `interval` seconds; pick `interval ≈ duration/(cols*rows)` to span the
    whole video. Front-end maps a time to a tile via CSS background-position.
    """
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    vf = f"fps=1/{interval:.4f},scale={w}:{h},tile={cols}x{rows}"
    cmd = [_bin("ffmpeg"), "-y", "-i", str(src), "-vf", vf, "-frames:v", "1", "-update", "1", str(dst)]
    _run(cmd, f"sprite {src.name}")
    return dst


# ---- rendering ---------------------------------------------------------------

def cut(src, dst, start: float, end: float, *, encoder: str | None = None, crf: int = 20) -> Path:
    """Trim [start, end] from `src` into `dst` (re-encoded for frame accuracy)."""
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    enc = encoder or default_encoder()
    cmd = [
        _bin("ffmpeg"), "-y", "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{end - start:.3f}",
        "-c:v", enc, *_quality_args(enc, crf), "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", str(dst),
    ]
    _run(cmd, f"cut {src.name}")
    return dst


def blur_pad_filter(width: int = 1080, height: int = 1920, sigma: int = 20) -> str:
    """Filtergraph: any aspect -> width x height with blurred padding."""
    return (
        "[0:v]split=2[bg][fg];"
        f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},gblur=sigma={sigma}[bgb];"
        f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[fgs];"
        "[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1[outv]"
    )


def blur_pad(src, dst, *, width=1080, height=1920, sigma=20, encoder=None, crf=20) -> Path:
    """Render `src` into a width x height vertical clip with blurred padding."""
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    enc = encoder or default_encoder()
    cmd = [
        _bin("ffmpeg"), "-y", "-i", str(src),
        "-filter_complex", blur_pad_filter(width, height, sigma),
        "-map", "[outv]", "-map", "0:a?",
        "-c:v", enc, *_quality_args(enc, crf, "5M"), "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", str(dst),
    ]
    _run(cmd, f"blur_pad {src.name}")
    return dst


def burn_subtitles(src, dst, ass_path, *, encoder=None, crf=20, pre_vf=None) -> Path:
    """Burn an .ass subtitle file onto `src` via libass.

    The subtitles filter resolves its filename relative to cwd, so we run from the .ass
    directory and pass the bare filename — this avoids brittle filtergraph path escaping.
    `pre_vf` (e.g. "hflip") is applied BEFORE the subtitles filter, so a mirrored video keeps
    readable (non-mirrored) subtitles in a single pass.
    """
    src, dst, ass_path = Path(src).resolve(), Path(dst).resolve(), Path(ass_path).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    enc = encoder or default_encoder()
    vf = f"subtitles={ass_path.name}"
    if pre_vf:
        vf = f"{pre_vf},{vf}"
    cmd = [
        _bin("ffmpeg"), "-y", "-i", str(src),
        "-vf", vf,
        "-c:v", enc, *_quality_args(enc, crf), "-c:a", "copy",
        "-movflags", "+faststart", str(dst),
    ]
    _run(cmd, f"burn_subtitles {src.name}", cwd=str(ass_path.parent))
    return dst


def uniquify(src, dst, seed: int, conf: dict, *, encoder=None, crf=20,
             width=1080, height=1920) -> Path:
    """Render a per-account variant: seeded mirror / zoom / color / speed jitter + metadata strip.

    Seeded by (clip, account) so variants are distinct across accounts but reproducible.
    """
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(seed)
    enc = encoder or default_encoder()

    vf: list[str] = []
    zj = float(conf.get("zoom_jitter", 0.0) or 0.0)
    if zj > 0:
        z = 1.0 + rnd.uniform(0.0, zj)
        vf.append(f"scale=iw*{z:.4f}:ih*{z:.4f}")
        vf.append(f"crop={width}:{height}")
    if conf.get("mirror") and rnd.random() < 0.5:
        vf.append("hflip")
    vf.append(f"eq=brightness={rnd.uniform(-0.03, 0.03):.3f}:saturation={1 + rnd.uniform(-0.05, 0.05):.3f}")

    af: list[str] = []
    sj = float(conf.get("speed_jitter", 0.0) or 0.0)
    if sj > 0:
        sp = 1.0 + rnd.uniform(-sj, sj)
        vf.append(f"setpts={1 / sp:.4f}*PTS")
        af.append(f"atempo={sp:.4f}")

    cmd = [_bin("ffmpeg"), "-y", "-i", str(src), "-map_metadata", "-1",
           "-vf", ",".join(vf) if vf else "null"]
    if af:
        cmd += ["-af", ",".join(af)]
    cmd += ["-c:v", enc, *_quality_args(enc, crf), "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", str(dst)]
    _run(cmd, f"uniquify {src.name}")
    return dst
