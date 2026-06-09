"""Tests for category presets + deep-merge in config.load_niche."""
from __future__ import annotations

import pytest

import cliper.config as cfg


def test_deep_merge_override_wins_and_merges_nested():
    base = {"a": 1, "clip": {"min_sec": 60, "max_sec": 90}}
    override = {"b": 2, "clip": {"min_sec": 30}}
    out = cfg._deep_merge(base, override)
    assert out["a"] == 1 and out["b"] == 2
    assert out["clip"] == {"min_sec": 30, "max_sec": 90}   # nested merge; override wins


def test_categories_have_core_fields():
    for preset in cfg.CATEGORIES.values():
        assert "strategy" in preset and "clip" in preset


def test_load_niche_applies_category_with_overrides(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text("name: x\ncategory: dialogue\nsources: [foo.mp4]\naccounts: [a]\nclip: {min_sec: 45}\n")
    niche = cfg.load_niche(str(p))
    assert niche["strategy"] == "smart"            # from the dialogue preset
    assert niche["caption"]["enabled"] is True     # from the preset
    assert niche["clip"]["min_sec"] == 45          # explicit override wins
    assert niche["clip"]["max_sec"] == 90          # preset default preserved


def test_load_niche_rejects_unknown_category(tmp_path):
    p = tmp_path / "y.yaml"
    p.write_text("name: y\ncategory: nope\nsources: [foo.mp4]\naccounts: [a]\n")
    with pytest.raises(ValueError):
        cfg.load_niche(str(p))
