# Cliper

Self-hosted CLI + web pipeline for a personal multi-niche short-form content farm: long video →
AI/heuristic moment selection → ~20–60s vertical clips → dynamic karaoke subtitles → per-account
uniquified renders → AI quality gate → ready-to-post export + posting schedule.

The media pipeline runs locally (ffmpeg, yt-dlp, faster-whisper). Only the **reasoning layer**
(moment selection + clip QA + social captions) calls the **OpenAI API**.

> Internals & decisions: [`CLAUDE.md`](CLAUDE.md) · [`memory.md`](memory.md)

---

## ⚠️ First: your OpenAI key

The key lives in a gitignored `.env` (already created). **Rotate it** in the OpenAI dashboard
when convenient — it was shared in chat, so treat it as exposed.

```
# .env
OPENAI_API_KEY=sk-...
CLIPER_OPENAI_MODEL=gpt-4o-mini   # default; any chat+vision model works
```

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ffmpeg -version          # system dependency (Homebrew: brew install ffmpeg)
```

## Use it — Web UI (recommended)

```bash
python -m cliper.cli ui          # → http://127.0.0.1:8000
```

In the UI you can:
- **Generate** — pick a niche, optionally paste a YouTube URL or upload a file, set max clips.
  Watch live stage progress.
- **Browse** — a gallery of vertical clips with thumbnails, AI score, duration, AI caption.
- **Edit a clip** — click it:
  - edit the **caption + hashtags** per account (Save);
  - fix the **subtitles** (timings kept), switch **style** (classic / hormozi / minimal),
    **position**, or **mirror** the video, then **Re-render** (mirror keeps subtitles readable).
- **Schedule** — build a staggered posting plan (`out/<niche>/schedule.csv`).

## Use it — CLI

```bash
# run a niche end-to-end
python -m cliper.cli run --niche test_full
python -m cliper.cli run --niche anime --limit 1 --max-clips 8

# just show which stages will run
python -m cliper.cli plan --niche youtubers

# build a posting schedule from generated clips
python -m cliper.cli schedule --niche test_full

# tests
pytest -q
```

## Pipeline

```
ingest → detect /[transcribe → select] → cut → reframe → caption → aiqa → uniquify → export
 yt-dlp   scene+    whisper   OpenAI       ffmpeg  blur-pad  subs    OpenAI   per-acc   folders
          audio    (local)   (cloud)                                  QA gate  variants  +manifest
```

- **heuristic** niches (`strategy: heuristic`): scene + audio-energy selection, fully offline.
- **smart** niches (`strategy: smart`): local whisper transcript → OpenAI picks the best moments
  (clean sentence boundaries, skips ads/filler).
- **caption**: faster-whisper word timestamps on the short clip → styled karaoke ASS → libass burn.
- **aiqa** (optional, `qa.enabled`): OpenAI judges transcript + frames, drops weak clips
  (`threshold`, `keep_min`).
- **uniquify**: a distinct render per account (speed/zoom/color) + distinct AI caption + hashtags.

## Niches

One YAML per niche in `niches/`. See [`config.example.yaml`](config.example.yaml) for every
field. Examples included: `youtubers` (smart+QA), `anime` (heuristic), `test_full` (AI demo).

## Cost (OpenAI)

Per clip: ~1 selection call (shared per video) + 1 QA call (3 small frames) + 1 caption call.
With `gpt-4o-mini` this is roughly a cent or two per video. Heuristic niches cost nothing.

## Posting

Posting is **semi-automatic by design** (mass auto-posting to many accounts is what gets them
banned). `schedule` gives you a dated plan + ready files; post via the platforms' native
schedulers, or wire a legal aggregator (upload-post.com / Ayrshare) into `stages/publish.py`
later. Account creation is manual — not automated.

## Testing guide

See the "How to test" section at the bottom of the chat handoff, or:
1. `python -m cliper.cli ui`, open the UI, niche `test_full` → 3 clips appear.
2. Open a clip → change style to **hormozi**, tick **Mirror**, **Re-render** → video mirrors,
   subtitles stay readable.
3. `pytest -q` → all green (offline).
4. Generate from a fresh YouTube URL to exercise the full download→AI→clips flow.

## Legal note

You are responsible for the rights to any content you process. Clipping creators who welcome
reach is low-risk; reusing studio-owned anime/series/films is copyright infringement and gets
accounts terminated. Cliper does not make infringing content legal.
