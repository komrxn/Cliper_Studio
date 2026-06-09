import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { MediaPlayerInstance } from "@vidstack/react";
import { api, fmtTime, pollJob } from "../api";
import type { Job, Segment, SourceResult, Suggestion } from "../types";
import { useApp } from "../store";
import { EmptyState, ProgressBar, Spinner } from "../components/ui";
import Timeline from "./Timeline";
import Player from "./Player";

let segCounter = 0;
const newSeg = (s: number, e: number, src: "ai" | "manual", extra?: Partial<Segment>): Segment => ({
  id: `seg-${++segCounter}`,
  start: s,
  end: e,
  source: src,
  ...extra,
});

const CAPTION_STYLES = ["classic", "hormozi", "minimal"];

export default function Studio() {
  const { niche, accounts, notify, session, patchSession, resetSession, recent, refreshRecent, setTab, track } = useApp();
  const { source, segments, selected, current } = session;

  const [url, setUrl] = useState("");
  const [intake, setIntake] = useState<{ stage: string; progress: number } | null>(null);
  const [intakeError, setIntakeError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"" | "suggest" | "render">("");
  const [subsOn, setSubsOn] = useState(true);
  const [subStyle, setSubStyle] = useState("classic");
  const playerRef = useRef<MediaPlayerInstance>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const runIntake = async (start: () => Promise<{ job_id: string }>) => {
    resetSession();
    setIntakeError(null);
    setIntake({ stage: "starting", progress: 0 });
    try {
      const { job_id } = await start();
      const result = (await pollJob(job_id, (j: Job) =>
        setIntake({ stage: j.stage || "working", progress: j.progress }),
      )) as SourceResult;
      patchSession({ source: result, segments: [], selected: null, current: 0 });
      setIntake(null);
      refreshRecent();
      notify("ok", `Loaded "${result.title}" · ${result.scenes.length} scene cuts`);
    } catch (e) {
      setIntake(null);
      setIntakeError((e as Error).message); // keep it on screen, not a fleeting toast
      notify("err", "Couldn’t load that source");
    }
  };

  const loadUrl = () => url.trim() && runIntake(() => api.createSourceFromUrl(url.trim()));
  const loadFile = (f: File) => runIntake(() => api.uploadSource(f));

  const openRecent = async (sid: string) => {
    try {
      const result = await api.getSource(sid);
      patchSession({ source: result, segments: [], selected: null, current: 0 });
      notify("ok", `Reopened "${result.title}"`);
    } catch (e) {
      notify("err", (e as Error).message);
      refreshRecent();
    }
  };

  const suggest = async () => {
    if (!source) return;
    setBusy("suggest");
    try {
      const { job_id } = await api.suggest(source.source_id, niche);
      const res = (await track(job_id, "Finding moments")) as { suggestions: Suggestion[] };
      patchSession({
        segments: res.suggestions.map((s) => newSeg(s.start, s.end, "ai", { score: s.score, reason: s.reason })),
        selected: null,
      });
      notify("ok", `${res.suggestions.length} moments — drag the edges to fine-tune`);
    } catch (e) {
      notify("err", (e as Error).message);
    } finally {
      setBusy("");
    }
  };

  const render = async () => {
    if (!source || !segments.length) return;
    setBusy("render");
    try {
      const segs = segments.map((s) => ({ start: s.start, end: s.end }));
      const caption = { enabled: subsOn, style: subStyle };
      const { job_id } = await api.makeClips(source.source_id, niche, segs, caption);
      // tracked globally → progress shows in the JobBar and navigation isn't blocked
      const res = (await track(job_id, "Rendering clips")) as { clips: string[] };
      notify("ok", `Rendered ${res.clips.length} clip(s) → Gallery`);
      setTab("gallery");
    } catch (e) {
      notify("err", (e as Error).message);
    } finally {
      setBusy("");
    }
  };

  const updateSeg = (id: string, start: number, end: number) =>
    patchSession({ segments: segments.map((s) => (s.id === id ? { ...s, start, end } : s)) });
  const addSeg = () => {
    if (!source) return;
    const seg = newSeg(current, Math.min(source.duration, current + 30), "manual");
    patchSession({ segments: [...segments, seg], selected: seg.id });
  };
  const removeSeg = (id: string) => patchSession({ segments: segments.filter((s) => s.id !== id) });

  const seek = (t: number) => {
    const clamped = Math.max(0, Math.min(source?.duration ?? t, t));
    if (playerRef.current) playerRef.current.currentTime = clamped;
    patchSession({ current: clamped });
  };

  // Keyboard shortcuts (ignored while typing). Space play/pause · ←/→ seek ±5s · Del removes selected.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (!source || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable) return;
      const p = playerRef.current;
      if (e.code === "Space" && p) {
        e.preventDefault();
        p.paused ? p.play() : p.pause();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        seek(current - 5);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        seek(current + 5);
      } else if ((e.key === "Delete" || e.key === "Backspace") && selected) {
        e.preventDefault();
        removeSeg(selected);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source, current, selected, segments]);

  const otherRecent = recent.filter((r) => r.source_id !== source?.source_id).slice(0, 8);

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.55fr_1fr]">
      {/* LEFT: player + timeline */}
      <div className="space-y-4">
        {!source ? (
          <div className="panel p-6">
            <h2 className="mb-1 text-lg font-semibold tracking-tight">Load a source</h2>
            <p className="mb-5 text-sm text-ink-400">
              Paste any video link (YouTube, etc.) or upload a file. Cliper downloads it, detects scene cuts,
              and builds a scrubbable filmstrip.
            </p>
            <div className="flex gap-2">
              <input
                className="input"
                placeholder="https://youtube.com/watch?v=…"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && loadUrl()}
                disabled={!!intake}
              />
              <button className="btn-primary whitespace-nowrap" onClick={loadUrl} disabled={!!intake || !url.trim()}>
                {intake ? <Spinner /> : "Load"}
              </button>
            </div>
            <div className="my-4 flex items-center gap-3 text-xs text-ink-500">
              <div className="h-px flex-1 bg-ink-800" /> or <div className="h-px flex-1 bg-ink-800" />
            </div>
            <button className="btn-ghost w-full" onClick={() => fileRef.current?.click()} disabled={!!intake}>
              Upload a video file
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="video/*"
              hidden
              onChange={(e) => e.target.files?.[0] && loadFile(e.target.files[0])}
            />

            <AnimatePresence>
              {intake && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mt-5"
                >
                  <ProgressBar value={intake.progress} label={intake.stage} />
                </motion.div>
              )}
            </AnimatePresence>

            {intakeError && (
              <div className="mt-4 rounded-xl border border-bad/30 bg-bad/10 p-3 text-xs text-bad">
                <div className="mb-1 font-medium">Couldn’t download that link</div>
                <div className="break-words text-bad/80">{intakeError}</div>
                <div className="mt-2 text-ink-400">
                  If the site needs a login (e.g. YouTube bot-check), set{" "}
                  <code className="rounded bg-ink-800 px-1">CLIPER_COOKIES_FROM_BROWSER=chrome</code> and restart.
                </div>
              </div>
            )}

            {recent.length > 0 && !intake && (
              <div className="mt-6">
                <div className="label mb-2">Recent sources</div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {recent.slice(0, 6).map((r) => (
                    <button
                      key={r.source_id}
                      onClick={() => openRecent(r.source_id)}
                      className="group overflow-hidden rounded-lg border border-ink-800 bg-ink-950 text-left transition hover:border-accent/50"
                    >
                      <div className="aspect-video bg-ink-900">
                        {r.poster && (
                          <img src={r.poster} className="h-full w-full object-cover transition group-hover:opacity-90" alt="" />
                        )}
                      </div>
                      <div className="p-1.5">
                        <div className="truncate text-xs text-ink-200">{r.title}</div>
                        <div className="text-[10px] tabular-nums text-ink-500">{fmtTime(r.duration)}</div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="panel overflow-hidden">
              <div className="flex items-center justify-between border-b border-ink-800 px-4 py-2.5">
                <div className="truncate text-sm font-medium text-ink-200">{source.title}</div>
                <div className="flex items-center gap-2 text-xs text-ink-400">
                  <span className="tabular-nums">{fmtTime(source.duration)}</span>
                  <span className="rounded bg-ink-800 px-1.5 py-0.5">{source.scenes.length} cuts</span>
                  <button className="text-ink-400 hover:text-ink-200" onClick={() => resetSession()}>
                    change
                  </button>
                </div>
              </div>
              <Player
                src={source.video_url}
                title={source.title}
                startAt={current}
                playerRef={playerRef}
                onTime={(t) => patchSession({ current: t })}
              />
            </div>

            <div className="panel p-4">
              <Timeline
                duration={source.duration}
                scenes={source.scenes}
                filmstrip={source.filmstrip}
                segments={segments}
                current={current}
                onSeek={seek}
                onChange={updateSeg}
                onSelect={(id) => patchSession({ selected: id })}
                selected={selected}
              />
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button className="btn-primary" onClick={suggest} disabled={busy !== ""}>
                  {busy === "suggest" ? <Spinner /> : "✦"} Suggest with AI
                </button>
                <button className="btn-ghost" onClick={addSeg} disabled={busy !== ""}>
                  + Add clip at playhead
                </button>
                <span className="ml-auto text-xs text-ink-500">
                  Drag to move · drag edges to trim (snap to cuts) ·{" "}
                  <kbd className="rounded bg-ink-800 px-1">Space</kbd> play ·{" "}
                  <kbd className="rounded bg-ink-800 px-1">←/→</kbd> ±5s ·{" "}
                  <kbd className="rounded bg-ink-800 px-1">Del</kbd> remove
                </span>
              </div>
            </div>

            {otherRecent.length > 0 && (
              <div className="panel p-4">
                <div className="label mb-2">Switch source</div>
                <div className="flex gap-2 overflow-x-auto pb-1">
                  {otherRecent.map((r) => (
                    <button
                      key={r.source_id}
                      onClick={() => openRecent(r.source_id)}
                      title={r.title}
                      className="w-28 shrink-0 overflow-hidden rounded-lg border border-ink-800 bg-ink-950 text-left transition hover:border-accent/50"
                    >
                      <div className="aspect-video bg-ink-900">
                        {r.poster && <img src={r.poster} className="h-full w-full object-cover" alt="" />}
                      </div>
                      <div className="truncate p-1 text-[10px] text-ink-300">{r.title}</div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* RIGHT: clip list + render */}
      <div className="space-y-4">
        <div className="panel flex flex-col">
          <div className="flex items-center justify-between border-b border-ink-800 px-4 py-3">
            <h3 className="text-sm font-semibold">Clips to render</h3>
            <span className="rounded-md bg-ink-800 px-2 py-0.5 text-xs tabular-nums text-ink-300">{segments.length}</span>
          </div>

          {segments.length === 0 ? (
            <EmptyState
              icon={<span className="text-xl">✂</span>}
              title="No clips yet"
              hint={source ? "Run “Suggest with AI” or add one at the playhead." : "Load a source first."}
            />
          ) : (
            <ul className="divide-y divide-ink-800">
              {segments
                .slice()
                .sort((a, b) => a.start - b.start)
                .map((seg, i) => (
                  <li
                    key={seg.id}
                    onClick={() => {
                      patchSession({ selected: seg.id });
                      seek(seg.start);
                    }}
                    className={`flex cursor-pointer items-center gap-3 px-4 py-3 transition-colors ${
                      selected === seg.id ? "bg-ink-800/60" : "hover:bg-ink-850"
                    }`}
                  >
                    <span className="grid h-6 w-6 place-items-center rounded-md bg-ink-800 text-xs font-semibold text-ink-300">
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 text-sm tabular-nums">
                        {fmtTime(seg.start)} → {fmtTime(seg.end)}
                        <span className="rounded bg-ink-800 px-1 text-[10px] text-ink-400">{fmtTime(seg.end - seg.start)}</span>
                      </div>
                      {seg.reason && <div className="truncate text-xs text-ink-500">{seg.reason}</div>}
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeSeg(seg.id);
                      }}
                      className="text-ink-500 hover:text-bad"
                      aria-label="remove clip"
                    >
                      ✕
                    </button>
                  </li>
                ))}
            </ul>
          )}

          <div className="border-t border-ink-800 p-4">
            <div className="mb-3 flex items-center gap-3">
              <label className="flex items-center gap-2 text-sm text-ink-200">
                <input type="checkbox" checked={subsOn} onChange={(e) => setSubsOn(e.target.checked)} className="accent-accent" />
                Subtitles
              </label>
              <select
                className="input ml-auto w-auto py-1 pr-7 text-xs disabled:opacity-40"
                value={subStyle}
                onChange={(e) => setSubStyle(e.target.value)}
                disabled={!subsOn}
              >
                {CAPTION_STYLES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <div className="mb-3 flex items-center gap-2 text-xs text-ink-400">
              <span className="label">Accounts</span>
              {accounts.length ? (
                accounts.map((a) => (
                  <span key={a} className="rounded-md bg-ink-800 px-1.5 py-0.5 text-[11px] text-ink-300">
                    {a}
                  </span>
                ))
              ) : (
                <span className="text-ink-500">none</span>
              )}
            </div>
            <button className="btn-primary w-full" onClick={render} disabled={busy !== "" || !segments.length}>
              {busy === "render" ? (
                <>
                  <Spinner /> Rendering…
                </>
              ) : (
                `Render ${segments.length || ""} clip${segments.length === 1 ? "" : "s"} → ${accounts.length} account${
                  accounts.length === 1 ? "" : "s"
                }`
              )}
            </button>
            <p className="mt-2 text-center text-[11px] text-ink-500">
              Each clip is cut, reframed to 9:16, captioned, and uniquified per account.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
