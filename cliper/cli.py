"""Cliper CLI entrypoint."""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from . import __version__
from .config import load_env, load_niche
from .pipeline import Context, run_pipeline, stages_for

ROOT = Path(__file__).resolve().parent.parent


def cmd_run(args: argparse.Namespace) -> int:
    niche = load_niche(args.niche)
    ctx = Context(
        niche=niche,
        work_dir=ROOT / "work" / niche["name"],
        out_dir=ROOT / "out" / niche["name"],
        limit=args.limit,
        max_clips=args.max_clips,
        smart=args.smart,
        device=args.device,
    )
    effective = "smart" if (ctx.smart or niche.get("strategy") == "smart") else "heuristic"
    print(f"cliper {__version__} — niche '{niche['name']}' "
          f"[{effective}, device={ctx.device}]")
    print(f"  stages: {' -> '.join(stages_for(ctx))}\n")

    started = time.monotonic()
    run_pipeline(ctx)
    elapsed = time.monotonic() - started

    print(f"\n✓ done in {elapsed:.0f}s — {len(ctx.clips)} clips x "
          f"{len(niche['accounts'])} accounts -> {ctx.out_dir}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    niche = load_niche(args.niche)
    ctx = Context(niche=niche, work_dir=ROOT / "work" / niche["name"],
                  out_dir=ROOT / "out" / niche["name"], smart=args.smart)
    print(f"niche '{niche['name']}' stages: {' -> '.join(stages_for(ctx))}")
    return 0


def cmd_schedule(args: argparse.Namespace) -> int:
    from datetime import datetime, timedelta

    from . import schedule as sched

    niche = load_niche(args.niche)
    out_dir = ROOT / "out" / niche["name"]
    if not out_dir.exists():
        print(f"no output for niche '{niche['name']}' — run it first")
        return 1
    start = (datetime.fromisoformat(args.start) if args.start
             else (datetime.now() + timedelta(days=1)).replace(
                 hour=0, minute=0, second=0, microsecond=0))
    rows = sched.build_schedule(niche, out_dir, start)
    csv_path = sched.write_csv(rows, out_dir / "schedule.csv")
    print(f"scheduled {len(rows)} posts -> {csv_path}")
    for r in rows[:8]:
        print(f"  {r['post_at']}  {r['account']:12}  {r['clip_id']}")
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    import uvicorn
    print(f"Cliper editor UI → http://{args.host}:{args.port}")
    uvicorn.run("cliper.web.app:app", host=args.host, port=args.port, log_level="warning")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cliper", description="Multi-niche short-form clip factory")
    p.add_argument("--version", action="version", version=f"cliper {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run the pipeline for a niche")
    run.add_argument("--niche", required=True, help="niche name or path to a YAML config")
    run.add_argument("--limit", type=int, default=None, help="max source videos to process")
    run.add_argument("--max-clips", type=int, default=None, dest="max_clips",
                     help="max clips per source video")
    run.add_argument("--smart", action="store_true", help="force smart (whisper+LLM) selection")
    run.add_argument("--device", default="cpu", choices=["cpu", "cuda"], help="compute device")
    run.set_defaults(func=cmd_run)

    plan = sub.add_parser("plan", help="print the resolved stage plan without running")
    plan.add_argument("--niche", required=True, help="niche name or path to a YAML config")
    plan.add_argument("--smart", action="store_true")
    plan.set_defaults(func=cmd_plan)

    sch = sub.add_parser("schedule", help="build a posting schedule from exported clips")
    sch.add_argument("--niche", required=True, help="niche name or path to a YAML config")
    sch.add_argument("--start", default=None, help="ISO start datetime (default: tomorrow 00:00)")
    sch.set_defaults(func=cmd_schedule)

    ui = sub.add_parser("ui", help="launch the editor web UI")
    ui.add_argument("--host", default="127.0.0.1")
    ui.add_argument("--port", type=int, default=8000)
    ui.set_defaults(func=cmd_ui)
    return p


def main(argv: list[str] | None = None) -> int:
    load_env()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
