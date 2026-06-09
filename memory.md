# memory.md — Cliper process log

Living log of **decisions**, **progress**, and **open questions**. Update at the end of every
phase (or whenever a decision is made/changed). Newest entries on top within each section.
`CLAUDE.md` = how the project works; this file = how we got here and what's left.

---

## Decisions log

Format: `YYYY-MM-DD · decision · rationale`

- **2026-06-07 · OpenAI API allowed for the AI REASONING layer (decision REVERSAL).** Earlier
  "no paid APIs" is relaxed: local 8 GB GPU can't run a strong LLM, so moment-selection AND a new
  pre-upload clip-QA gate call OpenAI (default gpt-4o-mini, configurable; needs OPENAI_API_KEY).
  Media pipeline (download/cut/reframe/caption/uniquify) and clip-level transcription stay
  local/self-hosted. *How to apply:* OpenAI calls live in `utils/llm.py`, lazy-imported, behind
  config flags, so the heuristic path still runs fully offline.
- **2026-06-07 · New requirement: AI QA gate before upload** — validate BOTH the transcript and
  the fragment (sampled frames) with a multimodal model; drop clips below a postability threshold.
  New `aiqa` stage runs after caption, before uniquify (don't render variants of rejected clips).
- **2026-06-07 · Build-then-test directive:** finish the software fully, then do a proper
  AI-validated test pass before any uploads. [[user wants full software before testing]]
- **2026-06-07 · Dynamic word-level subtitles = MANDATORY core feature, pulled into Phase 1**
  (was Phase 3). *Why:* user says ~95% of farm clips use burned karaoke captions for watchability.
  *How:* faster-whisper word timestamps on the SHORT cut clip (runs on Mac CPU, model `small`/`base`;
  GPU optional) → styled ASS with current-word highlight → burn via ffmpeg/libass (fast). Distinct
  from whole-video transcription used for smart selection (heavy, GPU). So caption ⇒ clip-level
  transcription on Mac; `transcribe` stage stays for whole-video smart-select only.
- **2026-06-07 · Phase 0 first deliverable = `CLAUDE.md` + `memory.md`** before any pipeline code.
  *Why:* user requirement; gives future sessions durable context and a decision trail.
- **2026-06-07 · Verification metric = clip quality hit-rate, not "pipeline ran".**
  *Why:* for a clipper, moment-selection quality is the whole product; technical checks alone
  could greenlight a folder of unwatchable clips. ~10 clips/video, count keepers.
- **2026-06-07 · Vertical 9:16 = blur-pad (user pick).** *Why:* trivial in ffmpeg, universal,
  loses nothing in frame → MVP needs no YOLO/ASD and runs entirely on Mac. smart_crop deferred.
- **2026-06-07 · Moment selection = hybrid, heuristic-default (Claude decided, user delegated).**
  *Why:* heuristics (scene+audio) fit anime/series/action and fly on Mac; LLM-on-transcript only
  helps dialogue niches and fixes clipped-punchline boundaries. Stage B is opt-in per niche.
- **2026-06-07 · Build = fully OSS, self-hosted, NO paid APIs (user correction).**
  *Why:* user wants to run it himself on Mac, offload heavy to Windows 8 GB VRAM box. Heavy =
  faster-whisper + local Ollama LLM on GPU; light = ffmpeg path on Mac.
- **2026-06-07 · Use VideoToolbox hardware encoder on Mac** (`h264_videotoolbox`). *Why:* the
  "flies on Mac" requirement; blur + N-per-account re-encodes are the throughput driver.
- **2026-06-07 · Languages = RU + EN.** *Why:* user's content. faster-whisper handles both;
  Qwen2.5 strong multilingual. (Uzbek would need extra transcript checks — not primary.)
- **2026-06-07 · Source = third-party content (creator clips / anime / series), niche-per-account.**
  *Why:* user's farm model. ⇒ **accounts are disposable**; design for rotation + `uniquify`.
  Honest caveat recorded: anime/series = studio copyright, high strike/ban risk.
- **2026-06-07 · Product = personal multi-niche farm, NOT SaaS.** *Why:* user pick → CLI pipeline,
  no OAuth multitenant / billing / web app.
- **2026-06-07 · Posting deferred to Phase 4 (semi-auto first).** *Why:* all ban/legal/audit
  complexity lives there; prove the clip factory first. Official TikTok API is closed for
  posting to one's own accounts, so no official one-click path exists.

### Numbers to re-verify before use (do NOT hardcode)
- YouTube Data API upload quota cost per `videos.insert` (research gave conflicting 1600 vs 100).
- Instagram content-publish posts/24h cap (research gave 25 vs 100). Both surface only in Phase 4.

---

## Progress tracker

- [x] **Phase 0** — scaffold + docs ✅
  - [x] `CLAUDE.md`
  - [x] `memory.md`
  - [x] project scaffold (git, `cliper/` package, stages, utils, niches, configs, requirements)
  - [x] deps installed (venv); ffmpeg blur-pad smoke test green (libx264 + VideoToolbox → 1080×1920)
- [x] **Phase 1** — MVP clip factory ✅ end-to-end on the test slice (EN)
  - [x] ingest (yt-dlp + local-file passthrough) · [x] detect (audio-energy windows + scene snap)
  - [x] cut · [x] reframe (blur_pad) · [x] caption (faster-whisper word ts → karaoke ASS → libass burn)
  - [x] uniquify (per-account; mirror auto-off when captioned) · [x] export + manifest · [x] runner
  - [~] hit-rate eval: 3/3 EN sample inspected, clip0 = coherent postable moment; full eval pending
  - [x] RU/Cyrillic subtitle validation ✅ (Arial+libass renders Cyrillic cleanly; вДудь slice)
  - [ ] caption social-text hook polish (Phase 3)
- [~] **AI layer** (was "Phase 2") — OpenAI smart selection + multimodal pre-upload QA gate.
  Code complete & offline-verified (imports, stage plans, `_to_clips` clamp, `llm.available()`=False
  without key). **Live test pending OPENAI_API_KEY** (use `niches/test_smart.yaml`).
- [~] **Phase 3** — styled captions: 3 presets ✅ (classic [default] / hormozi / minimal).
  AI social caption + hashtags, **distinct per account** ✅ (`utils/social.py`, offline-graceful).
  Remaining (CORE, not polish): **per-account variation of the BURNED-IN subtitles** (currently
  identical words/render across accounts — a dup signal); full uniquify set; smart-crop reframe.
- [~] **Phase 4 (semi-auto)** — `cliper schedule` builds a staggered posting plan -> schedule.csv
  from manifests ✅. Remaining (deferred, risky): actual platform posting automation + account
  isolation. No platform API calls yet by design.
- [x] **AI path live-tested** ✅ — EN (MrBeast 3-min + 10-min) + RU (вДудь); select + QA curate;
  per-account AI captions with retention hooks. Needs OPENAI_API_KEY (in .env).
- [x] **Editor web UI** ✅ — `cliper ui`: generate (URL/upload/niche) w/ live progress, gallery
  (thumbs+score), per-account caption/hashtag edit, subtitle edit + style/position/mirror +
  re-render. Self-tested via preview browser (re-render mirror+hormozi → mirrored video, readable subs).

Legend: `[ ]` todo · `[~]` in progress · `[x]` done

---

## Test inputs (user-provided 2026-06-07)

- `6Zy5VLcEbZc` — mixed action+voice (https://youtu.be/6Zy5VLcEbZc) — primary wiring test.
- `wDkztLMNK9k` — interview/podcast (https://youtu.be/wDkztLMNK9k) — smart-select / dialogue.
- `id5oYbrp49I` — informative (https://youtu.be/id5oYbrp49I).
- User note: AMV-style not interesting to clip.

## Open questions

- ⚠️ **SOURCE TYPE matters for cartoons (found in v2.1 R&M re-test).** The mechanical fixes work
  (subs in-frame, 60–82s, ends snap to scene cuts), BUT the source was a gag COMPILATION (10–30s
  unrelated bits). Forcing 60s makes a clip span MULTIPLE unrelated gags (clip01: squirrels→
  afterlife; clip03: afterlife→garage) — ends cleanly but content jumps. You can't get "60s" AND
  "one coherent scene" from a gag compilation. Fork for the user: (a) source full episodes / long
  continuous scenes → coherent 60s clips (researcher should target these); (b) accept montage-style
  cross-gag 60s clips (a common farm format); (c) shorter one-gag clips (<60s) for compilations.
- ⚠️ **anime / series / cartoons (the real target niches) are UNVERIFIED.** Only dialogue content
  tested (EN MrBeast, RU вДудь). `anime.yaml` / `youtubers.yaml` sources are `REPLACE_ME`. Need real
  anime + series URLs to validate: selection quality, caption language/timing on animation, QA on
  animated frames. Engine likely transfers (anime/series are dialogue-driven too) but expect
  per-niche tuning (caption language, keep existing subs?, scene-cut sensitivity, heuristic vs smart).
- Exact `uniquify` transform set + intensity — tune empirically by account survival.
- Mac↔Windows job queue format (shared folder vs lightweight broker) — decide in Phase 2.
- Heuristic detect quality on real niches — measure via hit-rate; may force earlier `--smart`.
- Concrete Phase-4 posting path (native schedulers vs device automation) — after factory proven.

---

## Changelog

- **2026-06-09** — **Bug-fix pass: seek, render progress, captions, 3-level selection, URL ingest.**
  (1) **Seek** "jumps to start": the mechanism was fine — the real bug was UX, the track only seeked
  on a single click, so press-drag-to-scrub seeked once to the press point (near left = start). Added
  **drag-to-scrub** + guarded the `startAt` restore so it can't override a user seek. Permanent e2e
  test `tests/e2e/test_seek.py` (real click+drag) so it can't silently regress. (2) **3-level
  selection** (`select.suggest`): TEXT (whisper transcript → sentence spans) → AUDIO (energy rank) →
  SCENE (cut snap), for **every** niche (the suggest endpoint always transcribes now). OpenAI ranks
  when available, **falls back to local text+audio on quota/outage** (verified: 429 → local pick).
  Transcript cached in the registry (re-suggest instant); `_register_source` preserves it on
  re-upload. (3) **Captions ON by default** + style toggle in Studio; clips endpoint takes a caption
  override so subtitles burn regardless of niche (verified 54 words on the action niche). (4) **Global
  render job** (`store.track` + `JobBar`): granular backend progress (cut→reframe→burn subs→uniquify→
  export), visible across tabs, **navigation never blocks**. (5) **URL ingest** hardened: looser format
  fallback, `CLIPER_COOKIES_FROM_BROWSER`/`_FILE` for auth-gated sites, error surfaced in the load
  panel (not a silent stall). Verified end-to-end (API + headless Chrome), pytest 18/18. NOTE: the
  OpenAI key in `.env` is **over quota** (429) — selection runs on the local path until it's topped up.
- **2026-06-09** — **Prod hardening: state persistence, scene-detect isolation, Gallery, polish.**
  Fixed the "switching tabs resets Studio" bug — root cause was conditional render unmounting the
  view. Introduced a React Context **session store** (`web/frontend/src/store.tsx`): niche + tab
  persisted to localStorage, Studio session (source/segments/selected/playhead) + Gallery cache +
  recent sources live above the views, so navigation no longer loses state; player re-seeks via a
  new `startAt` prop. Fixed the intermittent **"0 cuts"** — `cv2`/`av` `libavdevice` clash crashed
  scene detection after a smart Suggest loaded PyAV; new `cliper/utils/scenes.py` runs detection in
  a **spawned subprocess** (import-light, never loads `av`); `manual.fast_scene_cuts` and
  `detect._scene_cuts` delegate to it. Backend: **sources persisted** to `work/sources/registry.json`
  (survive restart + reopen without re-download) via `GET /api/sources[/{sid}]` + posters;
  `DELETE /api/clips/{niche}/{id}` + `render.delete_clip` (removes mp4s/json/state/thumb/edit).
  Gallery: sort/filter/search, delete (confirm dialog), download. Global: `ErrorBoundary`,
  `Confirm` dialog, keyboard (Space/←→/Del), Plan CSV download. **Verified** (headless Chrome +
  live API): Studio survives Gallery→Studio round-trip (segments 3→3); niche+tab remembered after
  reload; with `av` loaded a fresh source still detects 109/407/46 scenes; registry survives restart;
  reopen + delete work; 0 console errors; pytest 17/17 (added `tests/test_prod.py`).
- **2026-06-09** — **Studio player + filmstrip fix.** User: the timeline looked like noise and the
  raw `<video>` was poor. Root cause: the filmstrip squished up to 100 sprite frames into ~11px tiles
  (vertical smears) — the **sprite itself is fine** (verified: clean 10×10 frame grid). Fixes:
  (1) **Player → Vidstack** (`@vidstack/react` 1.15.5 — note its npm `latest` tag is stale 0.6.15, so
  pin 1.x; modern `DefaultVideoLayout`); `web/frontend/src/views/Player.tsx` exposes a
  `MediaPlayerInstance` ref so the timeline seeks via `player.currentTime`. (2) **Filmstrip rebuilt**
  to render readable frames that tile the track (count = round(width/128) via ResizeObserver), real
  px↔time math, nicer scene ticks + drag handles + hover tooltip. Verified in headless Chrome on the
  22-min R&M source: filmstrip shows recognizable frames, **407 scene cuts** render, 8 AI segments
  overlay + drag, Vidstack controls present, 0 console errors. Note: the earlier "0 cuts" the user
  saw was a **transient** cv2/av `libavdevice` duplicate-class crash (caught → returns []); detection
  is reliable (407 in 10s) and the timeline handles 0 scenes gracefully.
- **2026-06-09** — **Prod Studio UI rebuilt (React/Vite) + manual clip-marking timeline.** Resumed
  the interrupted "4 edits" session. Found 3/4 already done on the backend (yt-dlp `utils/download.py`;
  smart niche `CATEGORIES` taxonomy in `config.py`; manual-marking endpoints in `web/manual.py` +
  `web/app.py` `/api/sources[/suggest|/clips]`) — the gap was the **frontend** (app.py served a
  `frontend/dist` that never existed; `static/app.js` was stale/broken). Built a full **dark-studio
  React+TS+Tailwind+framer-motion** SPA in `cliper/web/frontend/` (Vite → `dist`, served by the
  existing SPA route; `base:"/"` so `/assets/*` matches FastAPI's mount). Three views: **Studio**
  (URL/upload → scene-cut + filmstrip **timeline** with draggable AI-suggested in/out regions that
  snap to scene cuts → render), **Gallery** (clip grid + per-account **Editor** drawer: caption/
  hashtags, subtitle text/style/position/mirror, re-render), **Plan** (schedule table). Backend edit:
  `/api/sources/{sid}/suggest` now **branches on strategy** — smart→transcribe+select (OpenAI),
  heuristic→`detect.run` (no pointless OpenAI on action niches). Added `niches/series.yaml`
  (American series/films fold into the `dialogue` category — taxonomy by content TYPE, not per-show).
  Housekeeping: removed stale `static/app.js`, replaced `static/index.html` with a build-notice
  fallback, gitignored `frontend/{node_modules,dist}`, documented `npm build` in CLAUDE.md.
  **Verified end-to-end** (fresh uvicorn + headless Chrome/Playwright): backend chain
  upload→suggest→clips→gallery green; UI loads with **0 console errors**; timeline renders 3 AI
  segments + drag mutates a segment's bounds (clip list updates live); URL-download path renders the
  download progress bar and registers the source; gallery shows the real 9:16 clip with Russian
  karaoke subs; editor
  re-render (hormozi+mirror+center) regenerates the file; `pytest` 15/15. Build once:
  `cd cliper/web/frontend && npm install && npm run build`, then `python -m cliper.cli ui`.
- **2026-06-07** — **Full-episode re-test (coherence confirmed).** User chose "full episodes/scenes"
  over compilations. Re-ran R&M on a 12-min continuous episode slice (`rm_ep.mp4`, Russian, `ru`):
  5 clips, 62–89s, all passed QA, 231 scene cuts. **Coherent** now — frames show clip00 (75s) is ONE
  continuous classroom scene start→end (vs the compilation's squirrels→afterlife jump); clip01 (89s)
  is continuous narrative ending cleanly on "Плохой пёс. Плохой." Subtitles in-frame (Russian).
  Takeaway: **cartoon sources must be full episodes / long continuous scenes** — the researcher
  (next) should target these, not gag compilations. Awaiting user quality verdict → then researcher
  + posting.
- **2026-06-07** — **v2.1 (R&M feedback fixes).** (1) Cartoons min length → 60s (was 30):
  `rick_and_morty`/`simpsons` now 60–90s. (2) **Scene-aware boundaries** — `select` runs
  PySceneDetect on the source and ends each clip on the **visual scene cut right after a finished
  sentence** (fixes "concы супер обрезаны"); `_snap_to_segments` takes `scene_cuts`, `_to_clips`
  threads them; reuses `detect._scene_cuts`. (3) Subtitle overflow was NOT a code bug — the user
  tested via the **stale UI server** (started pre-fix, no auto-reload); fresh code renders Russian
  subs in-frame (verified «вперед. Если» / «оформляется»). Restarted the UI server. R&M re-tested on
  a **Russian-dubbed** source (`language: ru`, `work/test/rm_ru.mp4`, 10:30). pytest 8/8. **Lesson:
  always re-launch the UI server after code edits** (uvicorn reload is off). HARD STOP again after
  re-test for the user's quality call.
- **2026-06-07** — **R&M gate result (cartoons validated).** Ran `rick_and_morty` on a 13-min
  "Funniest Moments" compilation: 140 segments → 6 coherent moments (31–35s, snapped to sentence
  boundaries — no abrupt cuts) → all 6 passed QA (0.7) → 12 variants. Our karaoke subtitles render
  clean and IN-FRAME on cartoons. **Finding:** this source has its OWN burned-in subtitles → our
  captions stack on top = double-subs (looks cluttered). Per-niche fix needed: source clean
  (sub-less) videos, OR set `caption.enabled: false` when the source is already subtitled (later:
  auto-detect burned-in subs and skip our layer). Awaiting user's quality verdict — HARD STOP here.
- **2026-06-07** — **v2: coherent clips + clean subtitles + niche cleanup.** (1) Subtitle overflow
  fixed — caption lines break on a CHARACTER budget (`max_chars` per style) + bigger margins +
  smaller active-word scale → text stays in-frame (verified classic + hormozi). (2) Selection
  rewritten for coherence — `select._snap_to_segments` snaps LLM picks to transcript sentence
  boundaries; `min_sec` is a FILTER (drop a moment that can't reach it on a clean boundary), NEVER a
  stretch target; over-max trims whole trailing segments → kills "тупо обрубается". `youtubers`
  → 60–90s. (3) Niches cleaned — deleted `anime` + all `test_*`; kept `youtubers`; added
  `rick_and_morty` + `simpsons`. (4) Per-niche `language` pins whisper for accuracy. pytest 8/8.
  Plan: `~/.claude/plans/twinkling-coalescing-koala.md`. Researcher + posting are SKETCHES (not
  built) — HARD STOP after R&M for the user's quality review.
- **2026-06-07** — **AI path live + editor UI built & self-tested.** OpenAI key wired via gitignored
  `.env` (loaded in `config.load_env`). Live runs validated the AI layer: `test_smart` (3-min) and
  `test_full` (10-min) — select picks moments, **QA gate curates** (kept 3/6 hooky clips, dropped
  3 weak), AI captions distinct per account with retention hooks. Calibrated QA (fairer prompt,
  threshold 0.45, `keep_min`). RU validated via UI on a вДудь slice (Russian select + captions).
  Built the **editor web UI** (FastAPI `web/app.py` + `web/render.py` + Tailwind/vanilla SPA):
  generate (URL/upload/niche) with live progress, clip gallery w/ thumbnails+score, per-account
  caption/hashtag edit, subtitle edit + style/position/**mirror** + **re-render**. Self-tested with
  the preview browser: gallery renders, editor populates, re-render with mirror+hormozi produced a
  mirrored video with READABLE restyled subtitles (mirror applied pre-burn in one pass). `cliper ui`
  + `cliper schedule` CLI. Clip state persisted (`work/<niche>/state/`) for editing. Engine: more
  clips/video + part-style retention hooks. Boundaries set: no mass account-creation / stealth
  posting; real posting stays semi-auto (schedule) or via a future legal aggregator seam.
- **2026-06-07** — **Pre-handoff hardening (advisor pass).** The OpenAI surface had never executed
  (only stage plans were verified). Added `utils/llm.as_float`/`as_bool` and used them in `select`
  (`score: null` no longer crashes) and `aiqa` (`postable: "false"` string no longer kept as
  truthy). Made social captions + hashtags **distinct per account** (`social.caption_variants`) —
  identical text across accounts was a shadowban signal. Added `tests/test_ai_mock.py` (mocks
  `llm.chat_json`, runs select/aiqa/social on adversarial JSON). pytest 8 passed. Flagged: burned-in
  subtitle text is still identical across accounts (next core item, not polish).
- **2026-06-07** — **Semi-auto posting + AI social captions.** `utils/social.py` generates a
  caption + hashtags per clip (OpenAI when available, transcript-hook fallback) — wired into
  export manifests. `schedule.py` + `cliper schedule` CLI build a staggered posting plan from
  manifests → `out/<niche>/schedule.csv` (verified: 6 posts laid out for the test niche). Real
  platform posting automation stays deferred (risky). Software is now feature-complete for the
  generate→QA→export→schedule loop; next is a live AI test pass once OPENAI_API_KEY is set.
- **2026-06-07** — **AI layer + caption styles built.** Added OpenAI reasoning layer (`utils/llm.py`,
  lazy/offline-safe): `transcribe` (local faster-whisper whole-video) → `select` (GPT picks moments)
  for smart niches, and a new `aiqa` multimodal QA gate (transcript + sampled frames → postable
  score, drops weak clips before uniquify). Wired into pipeline + `stages_for`; offline heuristic
  path unchanged (verified). Added 3 caption presets (classic/hormozi/minimal) — all render
  correctly incl. uppercase/center for hormozi. New niches: `youtubers` (smart+qa), `test_smart`
  (local AI-path test). `openai` added to deps. pytest 5 passed. Pending: OPENAI_API_KEY for live
  AI test; then posting (Phase 4) + AI social captions.
- **2026-06-07** — **Phase 1 clip factory works end-to-end** on the 3-min MrBeast slice:
  3 clips × 2 accounts in 256s (CPU `small` transcription dominates; encodes are fast via
  VideoToolbox). QA frames confirm blur-pad + **dynamic karaoke subtitles** look professional
  (current word highlighted yellow + scaled, white outline, lower third). Bug found & fixed:
  uniquify `hflip` flipped burned-in subtitles into mirror text → mirror now auto-disabled when
  captions are on. Heuristic picked a coherent emotional moment (clip0). Known benign noise: objc
  duplicate libavdevice warning (cv2 vs av). Caption *social-text* hook is naive (mid-sentence) —
  Phase 3/4. RU/Cyrillic validated: a вДудь slice rendered Cyrillic karaoke subs cleanly in
  34s (model cached). Note: heuristic picked a sponsor/ad-read segment (high audio energy) —
  a good argument for Phase 2 LLM selection to skip ads.
- **2026-06-07** — **Phase 0 complete.** Scaffolded `cliper/` package (cli/config/pipeline +
  9 stage stubs + `utils/ffmpeg.py`), `niches/{anime,youtubers}.yaml`, `config.example.yaml`,
  tests. venv created; installed yt-dlp 2026.3.17, scenedetect 0.7, opencv 4.13, PyYAML, pytest 9.
  CLI resolves niches and prints correct stage plans (heuristic vs smart). `pytest` green
  (blur-pad → 1080×1920). VideoToolbox hardware encode verified. Next: Phase 1 wiring.
- **2026-06-07** — Research (competitors / OSS stack / posting feasibility) done; plan approved;
  `CLAUDE.md` + `memory.md` created. Toolchain verified: Python 3.11.9, ffmpeg 8.0 with
  VideoToolbox, git, brew present.
