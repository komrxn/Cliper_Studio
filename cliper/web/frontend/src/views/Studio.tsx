import { useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api, fmtTime, pollJob } from "../api";
import type { Job, Segment, SourceResult, Suggestion } from "../types";
import type { Notify } from "../App";
import { EmptyState, ProgressBar, Spinner } from "../components/ui";
import Timeline from "./Timeline";

interface Props {
  niche: string;
  accounts: string[];
  notify: Notify;
  onDone: () => void;
}

let segCounter = 0;
const newSeg = (s: number, e: number, src: "ai" | "manual", extra?: Partial<Segment>): Segment => ({
  id: `seg-${++segCounter}`,
  start: s,
  end: e,
  source: src,
  ...extra,
});

export default function Studio({ niche, accounts, notify, onDone }: Props) {
  const [url, setUrl] = useState("");
  const [source, setSource] = useState<SourceResult | null>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [current, setCurrent] = useState(0);

  const [intake, setIntake] = useState<{ stage: string; progress: number } | null>(null);
  const [busy, setBusy] = useState<"" | "suggest" | "render">("");
  const videoRef = useRef<HTMLVideoElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const runIntake = async (start: () => Promise<{ job_id: string }>) => {
    setSource(null);
    setSegments([]);
    setIntake({ stage: "starting", progress: 0 });
    try {
      const { job_id } = await start();
      const result = (await pollJob(job_id, (j: Job) =>
        setIntake({ stage: j.stage || "working", progress: j.progress }),
      )) as SourceResult;
      setSource(result);
      setIntake(null);
      notify("ok", `Loaded "${result.title}" · ${result.scenes.length} scene cuts`);
    } catch (e) {
      setIntake(null);
      notify("err", (e as Error).message);
    }
  };

  const loadUrl = () => {
    if (!url.trim()) return;
    runIntake(() => api.createSourceFromUrl(url.trim()));
  };
  const loadFile = (f: File) => runIntake(() => api.uploadSource(f));

  const suggest = async () => {
    if (!source) return;
    setBusy("suggest");
    try {
      const { job_id } = await api.suggest(source.source_id, niche);
      const res = (await pollJob(job_id, () => {})) as { suggestions: Suggestion[] };
      setSegments(res.suggestions.map((s) => newSeg(s.start, s.end, "ai", { score: s.score, reason: s.reason })));
      notify("ok", `${res.suggestions.length} AI moments — drag the edges to fine-tune`);
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
      const { job_id } = await api.makeClips(source.source_id, niche, segs);
      const res = (await pollJob(job_id, () => {})) as { clips: string[] };
      notify("ok", `Rendered ${res.clips.length} clip(s) → Gallery`);
      onDone();
    } catch (e) {
      notify("err", (e as Error).message);
    } finally {
      setBusy("");
    }
  };

  const updateSeg = (id: string, start: number, end: number) =>
    setSegments((prev) => prev.map((s) => (s.id === id ? { ...s, start, end } : s)));
  const addSeg = () => {
    if (!source) return;
    const s = current;
    const e = Math.min(source.duration, current + 30);
    const seg = newSeg(s, e, "manual");
    setSegments((prev) => [...prev, seg]);
    setSelected(seg.id);
  };
  const removeSeg = (id: string) => setSegments((prev) => prev.filter((s) => s.id !== id));

  const seek = (t: number) => {
    if (videoRef.current) videoRef.current.currentTime = t;
    setCurrent(t);
  };

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
          </div>
        ) : (
          <>
            <div className="panel overflow-hidden">
              <div className="flex items-center justify-between border-b border-ink-800 px-4 py-2.5">
                <div className="truncate text-sm font-medium text-ink-200">{source.title}</div>
                <div className="flex items-center gap-2 text-xs text-ink-400">
                  <span className="tabular-nums">{fmtTime(source.duration)}</span>
                  <span className="rounded bg-ink-800 px-1.5 py-0.5">{source.scenes.length} cuts</span>
                  <button
                    className="text-ink-400 hover:text-ink-200"
                    onClick={() => {
                      setSource(null);
                      setSegments([]);
                    }}
                  >
                    change
                  </button>
                </div>
              </div>
              <video
                ref={videoRef}
                src={source.video_url}
                controls
                onTimeUpdate={(e) => setCurrent((e.target as HTMLVideoElement).currentTime)}
                className="aspect-video w-full bg-black"
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
                onSelect={setSelected}
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
                  Drag a region to move · drag its edges to trim (edges snap to scene cuts)
                </span>
              </div>
            </div>
          </>
        )}
      </div>

      {/* RIGHT: clip list + render */}
      <div className="space-y-4">
        <div className="panel flex flex-col">
          <div className="flex items-center justify-between border-b border-ink-800 px-4 py-3">
            <h3 className="text-sm font-semibold">Clips to render</h3>
            <span className="rounded-md bg-ink-800 px-2 py-0.5 text-xs tabular-nums text-ink-300">
              {segments.length}
            </span>
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
                      setSelected(seg.id);
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
                        <span className="rounded bg-ink-800 px-1 text-[10px] text-ink-400">
                          {fmtTime(seg.end - seg.start)}
                        </span>
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
