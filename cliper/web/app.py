"""FastAPI backend for the Cliper editor UI.

Auto pipeline + manual "Studio" (load source → scenes + filmstrip → AI suggestions → render
clips from segments). Long work runs in a thread pool; progress streams over SSE. Serves the
built React app from frontend/dist (falls back to the legacy static UI until the build exists).
"""
from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ..config import NICHES_DIR, ROOT, load_env, load_niche
from ..pipeline import Context, Source, run_pipeline
from ..utils import download as dl
from ..utils import ffmpeg
from . import manual, render

load_env()

OUT = ROOT / "out"
WORK = ROOT / "work"
STATIC = Path(__file__).resolve().parent / "static"
DIST = Path(__file__).resolve().parent / "frontend" / "dist"
OUT.mkdir(exist_ok=True)
WORK.mkdir(exist_ok=True)

app = FastAPI(title="Cliper")
JOBS: dict[str, dict] = {}
SOURCES: dict[str, dict] = {}
_EXEC = ThreadPoolExecutor(max_workers=2)

# Registry of loaded sources, persisted so a downloaded/uploaded video survives a server
# restart and can be reopened in Studio without re-downloading.
SRC_REGISTRY = WORK / "sources" / "registry.json"

_SRC_PUBLIC = ("source_id", "video_url", "duration", "title", "scenes", "filmstrip", "poster")


def _source_public(s: dict) -> dict:
    """The subset of a source record the frontend consumes (no local path / transcript)."""
    return {k: s[k] for k in _SRC_PUBLIC if k in s}


def _save_sources() -> None:
    SRC_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    SRC_REGISTRY.write_text(json.dumps(SOURCES, ensure_ascii=False), encoding="utf-8")


def _load_sources() -> None:
    """Load the persisted registry on startup, dropping any whose video file is gone."""
    if not SRC_REGISTRY.exists():
        return
    try:
        data = json.loads(SRC_REGISTRY.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    for sid, rec in data.items():
        if rec.get("path") and Path(rec["path"]).exists():
            SOURCES[sid] = rec


_load_sources()


# ---- jobs (thread pool + SSE) ------------------------------------------------

def _new_job() -> str:
    jid = uuid.uuid4().hex[:8]
    JOBS[jid] = {"id": jid, "status": "running", "stage": "", "progress": 0.0,
                 "result": None, "error": None, "log": []}
    return jid


def _run(jid: str, fn):
    """Run fn(update) in a worker thread; fn calls update(**fields) to report progress."""
    job = JOBS[jid]

    def update(**kw):
        job.update(kw)
        if kw.get("stage"):
            job["log"].append(kw["stage"])

    def task():
        try:
            job["result"] = fn(update)
            job.update(status="done", progress=1.0)
        except Exception as exc:  # noqa: BLE001 — surface to the UI
            job.update(status="error", error=str(exc))
            job["log"].append(f"ERROR: {exc}")

    _EXEC.submit(task)


@app.get("/api/jobs/{jid}")
def job_status(jid: str):
    job = JOBS.get(jid)
    if not job:
        raise HTTPException(404, "no such job")
    return job


@app.get("/api/jobs/{jid}/events")
async def job_events(jid: str):
    async def gen():
        last = None
        while True:
            job = JOBS.get(jid)
            if not job:
                yield f"data: {json.dumps({'status': 'error', 'error': 'no job'})}\n\n"
                return
            snap = {k: job[k] for k in ("status", "stage", "progress", "error")}
            if snap != last:
                yield f"data: {json.dumps(snap)}\n\n"
                last = dict(snap)
            if job["status"] in ("done", "error"):
                yield f"event: result\ndata: {json.dumps(job.get('result'))}\n\n"
                return
            await asyncio.sleep(0.4)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


# ---- niches ------------------------------------------------------------------

@app.get("/api/niches")
def list_niches():
    out = []
    for p in sorted(NICHES_DIR.glob("*.yaml")):
        try:
            n = load_niche(p.stem)
            out.append({"name": n["name"], "category": n.get("category"),
                        "accounts": n.get("accounts", []), "sources": len(n.get("sources", []))})
        except Exception:
            out.append({"name": p.stem, "category": None, "accounts": [], "sources": 0})
    return {"niches": out}


def _safe_source(source: str) -> str:
    """A job source must be a valid http(s) URL or a file already under work/ (uploads)."""
    if dl.is_allowed_url(source):
        return source
    p = Path(source).resolve()
    if str(p).startswith(str(WORK.resolve())) and p.exists():
        return str(p)
    raise HTTPException(400, "source must be a valid http(s) URL or an uploaded file")


# ---- auto pipeline -----------------------------------------------------------

@app.post("/api/jobs")
def create_job(payload: dict = Body(...)):
    name = payload.get("niche")
    if not name:
        raise HTTPException(400, "niche is required")
    niche = load_niche(name)
    if payload.get("source"):
        niche["sources"] = [_safe_source(payload["source"])]
    if payload.get("max_clips"):
        niche["clip"] = {**niche.get("clip", {}), "max_per_video": int(payload["max_clips"])}

    jid = _new_job()

    def work(update):
        ctx = Context(niche=niche, work_dir=ROOT / "work" / niche["name"],
                      out_dir=ROOT / "out" / niche["name"])
        run_pipeline(ctx, log=lambda m: update(stage=m.lstrip("→ ").strip()))
        return {"niche": niche["name"], "clips": [c.id for c in ctx.clips]}

    _run(jid, work)
    return {"job_id": jid}


# ---- sources (manual Studio) -------------------------------------------------

def _register_source(path: Path, title: str, update) -> dict:
    import time

    info = ffmpeg.probe(path)
    update(stage="detecting scenes", progress=0.6)
    scenes = manual.fast_scene_cuts(path)
    update(stage="building filmstrip", progress=0.85)
    cols, rows = 10, 10
    interval = max(2.0, (info.duration or 60) / (cols * rows))
    strip = WORK / "sources" / f"{path.stem}_strip.jpg"
    ffmpeg.sprite(path, strip, interval=interval, cols=cols, rows=rows)
    update(stage="thumbnail", progress=0.95)
    poster = WORK / "sources" / f"{path.stem}_poster.jpg"
    try:
        ffmpeg.extract_frame(path, (info.duration or 10) * 0.1, poster, width=480)
        poster_url = f"/work/sources/{poster.name}"
    except Exception:  # poster is cosmetic — never fail the load over it
        poster_url = None
    record = {
        "source_id": path.stem, "id": path.stem, "path": str(path),
        "video_url": f"/work/sources/{path.name}", "duration": info.duration, "title": title,
        "scenes": scenes,
        "filmstrip": {"url": f"/work/sources/{strip.name}", "cols": cols, "rows": rows,
                      "interval": interval},
        "poster": poster_url, "created_at": time.time(),
    }
    prev = SOURCES.get(path.stem)
    if prev and prev.get("transcript"):
        record["transcript"] = prev["transcript"]  # don't re-transcribe an already-known source
    SOURCES[path.stem] = record
    _save_sources()
    return _source_public(record)


@app.post("/api/sources")
def create_source(payload: dict = Body(...)):
    url = payload.get("url", "")
    if not dl.is_allowed_url(url):
        raise HTTPException(400, "a valid http(s) video URL is required")
    jid = _new_job()

    def work(update):
        update(stage="probing")
        meta = dl.probe(url)
        if meta["duration"] and meta["duration"] > 4 * 3600:
            raise RuntimeError("video too long (>4h)")
        update(stage="downloading")
        path = dl.download(url, WORK / "sources",
                           on_progress=lambda p: update(progress=round(p * 0.6, 3)))
        return _register_source(path, meta.get("title", path.stem), update)

    _run(jid, work)
    return {"job_id": jid}


@app.post("/api/sources/upload")
async def create_source_upload(file: UploadFile = File(...)):
    dst = WORK / "sources" / Path(file.filename).name
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    jid = _new_job()
    _run(jid, lambda update: _register_source(dst, dst.stem, update))
    return {"job_id": jid}


@app.get("/api/sources")
def list_sources():
    """Recently loaded sources (newest first) for the Studio 'Recent' strip / reopen."""
    items = sorted(SOURCES.values(), key=lambda s: s.get("created_at", 0), reverse=True)
    return {"sources": [_source_public(s) for s in items]}


@app.get("/api/sources/{sid}")
def get_source(sid: str):
    """Reopen a previously loaded source without re-downloading."""
    src = SOURCES.get(sid)
    if not src:
        raise HTTPException(404, "unknown source")
    if not Path(src["path"]).exists():
        SOURCES.pop(sid, None)
        _save_sources()
        raise HTTPException(410, "source file no longer on disk")
    return _source_public(src)


@app.post("/api/sources/{sid}/suggest")
def suggest_clips(sid: str, payload: dict = Body(...)):
    src = SOURCES.get(sid)
    if not src:
        raise HTTPException(404, "unknown source")
    niche = load_niche(payload.get("niche", "cartoons"))
    jid = _new_job()

    def work(update):
        from ..stages import select
        from ..utils import captions

        # TEXT level, for EVERY niche: transcribe so moments are sentence-bounded coherent scenes
        # (not "pure loudness"). Cached in the registry → re-suggest is instant.
        transcript = src.get("transcript", [])
        if not transcript:
            update(stage="transcribing (long videos take a while)", progress=0.1)
            model = captions.load_model(niche.get("select", {}).get("transcribe_model", "base"))
            transcript = captions.transcribe_segments(model, Path(src["path"]),
                                                      language=niche.get("language"))
            SOURCES[sid]["transcript"] = transcript
            _save_sources()  # persist so reopen + re-suggest works after a restart
        source = Source(id=sid, path=Path(src["path"]), title=src.get("title", ""),
                        transcript=transcript)
        ctx = Context(niche=niche, work_dir=WORK / niche["name"], out_dir=OUT / niche["name"])
        ctx.sources = [source]
        # AUDIO + SCENE levels happen inside select.suggest (energy ranking + scene-cut snap).
        select.suggest(ctx, on_progress=lambda s, p: update(stage=s, progress=p))
        return {"suggestions": [{"start": c.start, "end": c.end, "score": c.score,
                                 "reason": c.reason} for c in ctx.clips]}

    _run(jid, work)
    return {"job_id": jid}


@app.post("/api/sources/{sid}/clips")
def make_clips(sid: str, payload: dict = Body(...)):
    src = SOURCES.get(sid)
    if not src:
        raise HTTPException(404, "unknown source")
    niche = load_niche(payload.get("niche", "cartoons"))
    segments = payload.get("segments", [])
    if not segments:
        raise HTTPException(400, "no segments")
    jid = _new_job()

    caption = payload.get("caption")  # {enabled, style} — subtitles toggle from the UI

    def work(update):
        source = Source(id=sid, path=Path(src["path"]), title=src.get("title", ""),
                        transcript=src.get("transcript", []))
        update(stage="starting render", progress=0.05)
        clips = manual.clips_from_segments(
            niche, source, segments, src.get("scenes", []), caption=caption,
            on_progress=lambda s, p: update(stage=s, progress=p),
        )
        return {"niche": niche["name"], "clips": [c.id for c in clips]}

    _run(jid, work)
    return {"job_id": jid}


# ---- clips (gallery + editor) ------------------------------------------------

@app.get("/api/clips/{niche}")
def list_clips(niche: str):
    state_dir = WORK / niche / "state"
    out_dir = OUT / niche
    clips = []
    if state_dir.exists():
        for sf in sorted(state_dir.glob("*.json")):
            st = json.loads(sf.read_text(encoding="utf-8"))
            meta = {}
            for acc in st.get("accounts", []):
                mf = out_dir / acc / f"{st['clip_id']}.json"
                if mf.exists():
                    meta[acc] = json.loads(mf.read_text(encoding="utf-8"))
            clips.append({**st, "accounts_meta": meta, "created_at": sf.stat().st_mtime})
    clips.sort(key=lambda c: c.get("score", 0), reverse=True)
    return {"clips": clips}


@app.get("/api/thumb/{niche}/{clip_id}")
def thumb(niche: str, clip_id: str):
    out_dir = OUT / niche
    if not out_dir.exists():
        raise HTTPException(404, "no output")
    src = next((acc / f"{clip_id}.mp4" for acc in sorted(out_dir.iterdir())
                if acc.is_dir() and (acc / f"{clip_id}.mp4").exists()), None)
    if not src:
        raise HTTPException(404, "no clip")
    dst = WORK / niche / "thumbs" / f"{clip_id}.jpg"
    if not dst.exists():
        ffmpeg.extract_frame(src, 1.0, dst, width=270)
    return FileResponse(dst)


@app.post("/api/clips/{niche}/{clip_id}/meta")
def edit_meta(niche: str, clip_id: str, payload: dict = Body(...)):
    render.update_meta(niche, clip_id, account=payload.get("account"),
                       caption=payload.get("caption"), hashtags=payload.get("hashtags"))
    return {"ok": True}


@app.post("/api/clips/{niche}/{clip_id}/rerender")
def rerender(niche: str, clip_id: str, payload: dict = Body(...)):
    niche_cfg = load_niche(niche)
    try:
        state = render.rerender_clip(
            niche, clip_id, words=payload.get("words"), text=payload.get("text"),
            style=payload.get("style", "classic"), position=payload.get("position"),
            mirror=bool(payload.get("mirror")), uniquify_conf=niche_cfg.get("uniquify", {}),
        )
    except FileNotFoundError as exc:
        raise HTTPException(400, str(exc))
    thumb_path = WORK / niche / "thumbs" / f"{clip_id}.jpg"
    if thumb_path.exists():
        thumb_path.unlink()
    return {"ok": True, "state": state}


@app.delete("/api/clips/{niche}/{clip_id}")
def delete_clip(niche: str, clip_id: str):
    removed = render.delete_clip(niche, clip_id)
    if not removed:
        raise HTTPException(404, "clip not found")
    return {"ok": True, "removed": removed}


@app.post("/api/schedule/{niche}")
def make_schedule(niche: str):
    from datetime import datetime, timedelta

    from .. import schedule as sched
    niche_cfg = load_niche(niche)
    out_dir = OUT / niche
    if not out_dir.exists():
        raise HTTPException(404, "run the niche first")
    start = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = sched.build_schedule(niche_cfg, out_dir, start)
    sched.write_csv(rows, out_dir / "schedule.csv")
    return {"rows": rows}


# ---- media + SPA (mounted last; /api wins) -----------------------------------

app.mount("/out", StaticFiles(directory=str(OUT)), name="out")
app.mount("/work", StaticFiles(directory=str(WORK)), name="work")
if (DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(DIST / "assets")), name="assets")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/{full_path:path}", response_class=HTMLResponse)
def spa(full_path: str):
    """Serve the React build if present, else the legacy static UI."""
    if (DIST / "index.html").exists():
        return (DIST / "index.html").read_text(encoding="utf-8")
    return (STATIC / "index.html").read_text(encoding="utf-8")
