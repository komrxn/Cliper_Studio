"""publish — post exported clips to platforms (Phase 4, separate from the core pipeline).

Starts semi-automatic (native platform schedulers consume the export manifest); later,
optional automation with per-account isolation. NOT wired into the default STAGE_ORDER.
Re-verify per-platform rate/quota limits before relying on any numbers.
"""
from __future__ import annotations

from ..pipeline import Context


def run(ctx: Context) -> Context:
    raise NotImplementedError("publish: implement in Phase 4 (semi-auto first)")
