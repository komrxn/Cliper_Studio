# CLAUDE.md — Cliper

Guide for Claude Code sessions working in this repo. Keep it current; it is loaded as context.

## What is Cliper

Cliper is a **self-hosted CLI pipeline for a personal multi-niche short-form content farm**.
It turns long videos (YouTube etc.) into short vertical clips (~30–60s), packages them
(9:16, captions, thumbnails), produces a **distinct render per target account**, and lays
everything out ready to post to TikTok / YouTube Shorts / Instagram Reels.

One **niche** = one config = one pool of accounts (e.g. `youtubers`, `anime`, `series`).

**Status:** greenfield, Phase 0 (scaffold + docs). Nothing is built yet beyond this.

## Non-negotiable principles (read before designing)

- **Self-hosted media pipeline; OpenAI only for the AI reasoning layer.** Download, cut, reframe,
  caption, uniquify and clip-level transcription all run locally on the user's machines. The one
  exception (decided 2026-06-07): a strong LLM won't fit the local 8 GB GPU, so **moment selection
  and the pre-upload clip-QA gate call the OpenAI API** (default `gpt-4o-mini`, configurable; needs
  `OPENAI_API_KEY`). All OpenAI use is isolated in `utils/llm.py`, lazy-imported and config-gated,
  so the heuristic path still runs fully offline.
- **"Flies" on the Mac.** The MVP path is pure ffmpeg + Python, no GPU, fast. Use the
  **VideoToolbox** hardware encoder (`h264_videotoolbox`), never software x264 by default.
- **GPU only for heavy/optional stages.** faster-whisper + local LLM run on the user's
  Windows box (8 GB VRAM, CUDA). The Mac path must degrade gracefully when GPU stages are off.
- **Accounts are disposable.** Source is third-party content → expect strikes/bans. Architecture
  assumes account rotation; never hardcode a single account identity.
- **`uniquify` is mandatory, not optional.** Posting the same render to N accounts = shadowban.
  Each account gets a varied render (crop/zoom/mirror/micro-speed/color/metadata/caption).
- **No hardcoded platform limits.** Daily-quota / rate-limit numbers were not verified; treat
  any such number as "verify before relying" and keep it in config, not code constants.

## Architecture — pipeline of stages

```
ingest → detect → [transcribe → select] → cut → reframe → caption → uniquify → export → (publish)
 yt-dlp  scene+    faster-whisper  LLM      ffmpeg  blur-pad  burn    per-acc    folders   Phase 4
         audio     (GPU, opt.)    (opt.)                      (opt.)  variants   +manifest
```

- **ingest** — yt-dlp download; resolve a niche's sources (url / playlist / channel).
- **detect** (always, Mac) — candidate windows via PySceneDetect (content-aware scenes)
  + audio loudness peaks (ffmpeg `ebur128`/RMS) + optional existing-subtitle parse.
- **transcribe + select** (optional, GPU) — faster-whisper transcript → local LLM (Qwen2.5-7B)
  ranks candidates by hook/standalone-ness and **snaps cut points to sentence boundaries**
  (fixes the "clipped punchline" failure of competitors). Only for `strategy: smart` niches.
- **cut** — ffmpeg extract the chosen window.
- **reframe** — 16:9 → 9:16 **blur-pad** (background = blurred stretched copy; sharp center).
- **caption** (CORE, not optional) — **dynamic word-level subtitles** (karaoke highlight). Runs
  faster-whisper on the *short clip* to get word timestamps (Mac CPU, `small`/`base`; GPU optional),
  builds a styled ASS, burns it via libass. ~95% of farm clips use these. Runs after reframe so
  text is placed in 9:16 space.
- **uniquify** — per-account variation pass (anti-dup + reduces Content ID matching).
- **export** — `out/<niche>/<account>/<clip>.mp4` + `manifest.json` (caption, hashtags,
  thumbnail, schedule slot).
- **publish** (Phase 4) — semi-automatic first; see Roadmap.

## Tech stack

| Stage | Tool | License | Machine |
|---|---|---|---|
| download | yt-dlp | Unlicense | Mac/any |
| scene detect | PySceneDetect | BSD-3 | Mac |
| audio/cut/reframe/caption/uniquify | ffmpeg (subprocess) | LGPL/GPL | Mac (VideoToolbox) |
| caption transcript (core) | faster-whisper (`small`/`base`, word ts) on the clip | MIT | Mac CPU |
| captions render (core) | custom styled ASS + ffmpeg/libass | MIT | Mac |
| whole-video transcribe (smart) | faster-whisper (`base`/`small`) | MIT | Mac CPU (slow on long vids) |
| moment-select + clip QA | OpenAI API (`gpt-4o-mini`, configurable, multimodal) | paid | OpenAI cloud |
| smart-crop (Phase 3+) | Autocrop-vertical / Light-ASD | MIT | Windows |

Avoid **Postiz (AGPL-3.0)** for any linked/distributed code. Prefer official SDKs/HTTP or
Mixpost (MIT) when posting work begins. MVP deps are all MIT/BSD/Apache/Unlicense.

## Compute topology

- **MVP = 100% Mac, no GPU.** ingest + heuristic detect + cut + blur-pad + uniquify + export.
- **GPU box (Windows, 8 GB)** = transcribe + LLM only (Phase 2). 8 GB fits faster-whisper
  `large-v3` int8 (or `medium`) and a 7–8B LLM in Q4 (~5–6 GB).
- Cross-machine: not needed for MVP. Phase 2 uses a simple shared-folder job queue
  (Mac drops job → Windows worker runs GPU stages → returns result). No network broker yet.

## Project structure

```
cliper/
  cli.py          # entrypoint: run / plan / schedule / ui
  config.py       # load + validate niche YAML; load .env
  pipeline.py     # Context, Clip, stage order + runner
  schedule.py     # posting-plan builder (schedule.csv)
  stages/
    ingest.py  detect.py  transcribe.py  select.py  cut.py
    reframe.py caption.py aiqa.py uniquify.py export.py publish.py
  utils/
    ffmpeg.py     # ffmpeg/ffprobe wrappers (VideoToolbox-aware)
    captions.py   # whisper word ts + styled karaoke ASS (classic/hormozi/minimal)
    llm.py        # OpenAI wrapper (moment selection + clip QA)
    social.py     # AI caption + hashtags, distinct per account
    media.py
  web/            # Studio UI: FastAPI (app.py, manual.py, render.py) + React app (frontend/, Vite→dist/)
niches/           # one YAML per niche
out/              # generated clips + manifests + schedule.csv (gitignored)
work/             # downloads, intermediates, clip state, thumbs (gitignored)
tests/
```

## Niche config format (YAML)

```yaml
name: rick_and_morty
language: en                 # optional: pin whisper language for accuracy; omit = auto-detect
sources:
  - https://www.youtube.com/watch?v=...       # url / playlist / channel / local path
strategy: smart              # heuristic (scene+audio, offline) | smart (whisper + OpenAI select)
clip:
  min_sec: 30                # coherence-snapping DROPS moments that can't reach min on a clean cut
  max_sec: 75
  max_per_video: 6
select: { model: gpt-4o-mini, transcribe_model: base }   # smart only; needs OPENAI_API_KEY
reframe: blur_pad            # blur_pad (default) | smart_crop (later)
caption:                     # dynamic word-level subtitles (core)
  enabled: true
  style: classic             # classic | hormozi | minimal
  model: small               # faster-whisper model for clip transcription (base|small|medium)
qa: { enabled: true, model: gpt-4o-mini, threshold: 0.45, keep_min: 3 }   # AI pre-upload gate
uniquify:
  mirror: false              # auto-off when captions on (would flip burned subs)
  speed_jitter: 0.03
  zoom_jitter: 0.05
accounts: [rm_a, rm_b]       # 1 niche = pool of accounts
schedule: { per_day: 3, stagger_min: 90 }
```

## Commands

> Filled in as the code lands; keep this section truthful.

```bash
# setup (Phase 0)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# put your key in .env (gitignored): OPENAI_API_KEY=sk-...

# run a niche (heuristic = offline; smart = OpenAI selection + QA)
python -m cliper.cli run --niche test_full
python -m cliper.cli run --niche anime --limit 1 --max-clips 8

# Studio web UI — prod React app (Vite). Build once; the FastAPI server serves dist/ automatically.
cd cliper/web/frontend && npm install && npm run build && cd ../../..
python -m cliper.cli ui            # http://127.0.0.1:8000
#   Studio: load any URL/upload → scene-cut + filmstrip timeline → AI suggests clip in/out →
#           drag to fine-tune (edges snap to scene cuts) → render. Gallery + per-account editor + Plan.
#   Frontend dev (hot reload): `cd cliper/web/frontend && npm run dev` (proxies /api to :8000).

# posting schedule from generated clips
python -m cliper.cli schedule --niche test_full

# tests
pytest -q
```

## Conventions

- **Python 3.11**, standard library + the stack above. Type hints on public funcs.
- **Stage pattern:** each `stages/<x>.py` exposes a pure-ish `run(ctx) -> ctx` that takes and
  returns a pipeline context (dataclass), reads inputs from disk/ctx, writes outputs to disk.
  Stages are independently testable and skippable via config.
- **All ffmpeg goes through `utils/ffmpeg.py`** — no scattered subprocess calls. The wrapper
  picks `h264_videotoolbox` on macOS and exposes deterministic args for testable outputs.
- **No silent failures.** A stage that can't proceed raises; the pipeline logs which niche/clip.
- **Config over constants.** Clip lengths, jitter ranges, per-day caps, platform limits → YAML.
- **Determinism for tests:** seed any randomness (uniquify jitter) so test outputs are checkable.

## Roadmap (phases)

- **Phase 0** — scaffold + this doc + `memory.md`. *(in progress)*
- **Phase 1** — MVP clip factory (heuristic, blur-pad, **dynamic subtitles**, basic uniquify,
  export). All on Mac.
- **Phase 2** — smart selection (faster-whisper + Qwen) on the GPU box.
- **Phase 3** — styled captions + full per-account uniquification.
- **Phase 4** — posting: semi-auto (native schedulers) → later automation w/ account isolation.

## Risks / legal reality (design consequences, not legal advice)

- Clipping creators who want reach = low risk. **Anime / series / movies = studio copyright**
  with aggressive Content ID; those accounts churn (strike → ban → new). Build for that.
- `uniquify` reduces—does not defeat—Content ID, and does not make infringing content legal.
  It exists primarily to avoid cross-account duplicate suppression.
- TikTok's official Content Posting API forbids apps that post to the *developer's own*
  accounts → no official one-click path for this use case. Posting is deliberately Phase 4.

## Quality bar (how we judge success)

The metric is **not "the pipeline ran"** — it's **"would I actually post this clip?"**
Validate selection with a manual hit-rate (~10 clips/video, count the keepers) before trusting
any heuristic. If heuristic hit-rate is low on a dialogue niche, enable `--smart` and compare.

## Pointers

- Full plan: `~/.claude/plans/lovely-questing-quiche.md`
- Process log + decisions: `memory.md` (update at the end of every phase)
