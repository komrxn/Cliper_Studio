"""Offline tests for stage resolution and OpenAI-free selection logic."""
from __future__ import annotations

from pathlib import Path

from cliper.pipeline import Context, stages_for
from cliper.stages.select import _to_clips


def _ctx(niche):
    return Context(niche=niche, work_dir=Path("work"), out_dir=Path("out"))


def test_heuristic_skips_ai_stages():
    stages = stages_for(_ctx({"strategy": "heuristic", "caption": {"enabled": True}}))
    assert "detect" in stages and "caption" in stages
    assert "transcribe" not in stages and "select" not in stages and "aiqa" not in stages


def test_smart_with_qa_orders_stages():
    stages = stages_for(_ctx({
        "strategy": "smart", "caption": {"enabled": True}, "qa": {"enabled": True},
    }))
    assert "detect" not in stages
    assert stages.index("transcribe") < stages.index("select") < stages.index("cut")
    assert stages.index("caption") < stages.index("aiqa") < stages.index("uniquify")


def test_to_clips_snaps_to_boundaries_and_drops():
    segs = [{"start": float(i * 5), "end": float(i * 5 + 5), "text": f"s{i}"} for i in range(20)]
    raw = [
        {"start": 10, "end": 28, "score": None},   # snaps to a clean clip in [20,35]
        {"start": 95, "end": 100, "score": 0.5},   # only 5s left -> can't reach min -> dropped
    ]
    clips = _to_clips("vid", raw, segs, [], 20.0, 35.0, 5)
    assert len(clips) == 1                          # second moment dropped (too short for a clean min)
    c = clips[0]
    assert c.score == 0.0                           # null score coerced safely
    assert 20.0 <= c.duration <= 35.0
    assert c.start in {s["start"] for s in segs}    # start lands on a segment boundary
    assert c.end in {s["end"] for s in segs}        # end lands on a segment boundary
    assert c.id == "vid_00"
