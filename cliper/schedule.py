"""Phase 4 (semi-auto): turn exported clips into a posting schedule.

Reads the per-account manifests under out/<niche>/ and assigns each clip a staggered post time
based on the niche's `schedule` config (per_day, stagger_min). Writes a schedule.csv the user
(or a future automation / native platform scheduler) can act on. No platform API calls here —
the risky automation is intentionally deferred.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

FIELDS = ["post_at", "account", "clip_id", "video", "caption", "hashtags"]
BASE_HOUR = 9  # first post of each day


def build_schedule(niche: dict, out_dir: Path, start: datetime) -> list[dict]:
    sched = niche.get("schedule", {})
    per_day = max(1, int(sched.get("per_day", 3)))
    stagger = int(sched.get("stagger_min", 90))

    rows: list[dict] = []
    for acc_dir in sorted(p for p in out_dir.iterdir() if p.is_dir()):
        for idx, mf in enumerate(sorted(acc_dir.glob("*.json"))):
            data = json.loads(mf.read_text(encoding="utf-8"))
            day, slot = divmod(idx, per_day)
            when = (start + timedelta(days=day)).replace(
                hour=BASE_HOUR, minute=0, second=0, microsecond=0
            ) + timedelta(minutes=slot * stagger)
            rows.append({
                "post_at": when.isoformat(timespec="minutes"),
                "account": acc_dir.name,
                "clip_id": data.get("clip_id", mf.stem),
                "video": data.get("video", ""),
                "caption": data.get("caption", ""),
                "hashtags": " ".join(data.get("hashtags", [])),
            })
    rows.sort(key=lambda r: (r["post_at"], r["account"]))
    return rows


def write_csv(rows: list[dict], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path
