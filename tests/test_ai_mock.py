"""Mock/offline tests for the OpenAI reasoning path (no API key, no network).

Exercises the data flow that only runs live with a key, and pins the type-coercion hardening
against adversarial-but-valid model JSON (null score, string "false").
"""
from __future__ import annotations

from pathlib import Path

import cliper.utils.llm as llm
from cliper.pipeline import Context, Source
from cliper.stages import select as select_stage
from cliper.stages.aiqa import _keep
from cliper.utils import social


def test_select_survives_null_score(monkeypatch):
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: {"clips": [
        {"start": 5, "end": 25, "score": None, "reason": "x"},
    ]})
    segs = [{"start": float(i * 5), "end": float(i * 5 + 5), "text": f"s{i}"} for i in range(10)]
    ctx = Context(niche={"clip": {"min_sec": 20, "max_sec": 35, "max_per_video": 5}, "select": {}},
                  work_dir=Path("work"), out_dir=Path("out"))
    ctx.sources = [Source(id="vid", path=Path("x"), transcript=segs)]
    select_stage.run(ctx)
    assert len(ctx.clips) == 1
    assert ctx.clips[0].score == 0.0                    # null coerced safely, no crash
    assert 20.0 <= ctx.clips[0].duration <= 35.0        # snapped within bounds on boundaries


def test_aiqa_keep_coerces_adversarial_types():
    assert _keep({"postable": True, "score": 0.8}, 0.5) is True
    assert _keep({"postable": "false", "score": 0.9}, 0.5) is False   # string 'false' is truthy
    assert _keep({"postable": True, "score": None}, 0.5) is False     # null score would crash
    assert _keep({"postable": "true", "score": 0.6}, 0.5) is True


def test_social_offline_variants_differ_per_account(monkeypatch):
    monkeypatch.setattr(social.llm, "available", lambda: False)
    text = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen"
    out = social.caption_variants(text, ["#a", "#b", "#c"], ["acc1", "acc2", "acc3"])
    assert set(out) == {"acc1", "acc2", "acc3"}
    captions = {out[a][0] for a in out}
    hashtags = {tuple(out[a][1]) for a in out}
    assert len(captions) > 1 or len(hashtags) > 1   # accounts must not be identical
