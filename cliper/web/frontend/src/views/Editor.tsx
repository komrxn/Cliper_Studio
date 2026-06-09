import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "../api";
import type { Clip } from "../types";
import { useApp } from "../store";
import { ScoreBadge, Spinner } from "../components/ui";

interface Props {
  niche: string;
  clip: Clip;
  onClose: () => void;
  onSaved: () => void;
  onDelete: () => void;
}

const STYLES = ["classic", "hormozi", "minimal"];
const POSITIONS = [
  { v: "", label: "default" },
  { v: "top", label: "top" },
  { v: "center", label: "center" },
  { v: "bottom", label: "bottom" },
];

export default function Editor({ niche, clip, onClose, onSaved, onDelete }: Props) {
  const { notify } = useApp();
  const accounts = clip.accounts ?? [];
  const [account, setAccount] = useState(accounts[0] ?? "");
  const [caption, setCaption] = useState("");
  const [hashtags, setHashtags] = useState("");

  const [text, setText] = useState(clip.text ?? "");
  const [style, setStyle] = useState(clip.style ?? "classic");
  const [position, setPosition] = useState(clip.position ?? "");
  const [mirror, setMirror] = useState(!!clip.mirror);
  const [bust, setBust] = useState(0);
  const [savingMeta, setSavingMeta] = useState(false);
  const [rendering, setRendering] = useState(false);

  useEffect(() => {
    const meta = clip.accounts_meta?.[account] ?? {};
    setCaption(meta.caption ?? "");
    setHashtags((meta.hashtags ?? []).join(" "));
  }, [account, clip]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const saveMeta = async () => {
    setSavingMeta(true);
    try {
      await api.saveMeta(niche, clip.clip_id, {
        account,
        caption,
        hashtags: hashtags.split(/\s+/).filter(Boolean),
      });
      notify("ok", "Caption saved");
      onSaved();
    } catch (e) {
      notify("err", (e as Error).message);
    } finally {
      setSavingMeta(false);
    }
  };

  const rerender = async () => {
    setRendering(true);
    try {
      await api.rerender(niche, clip.clip_id, {
        text,
        style,
        position: position || null,
        mirror,
      });
      setBust(Date.now());
      notify("ok", "Re-rendered all accounts");
      onSaved();
    } catch (e) {
      notify("err", (e as Error).message);
    } finally {
      setRendering(false);
    }
  };

  const videoSrc = `/out/${niche}/${account}/${clip.clip_id}.mp4?t=${bust}`;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
      />
      <motion.div
        initial={{ x: 40, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ type: "spring", stiffness: 260, damping: 30 }}
        className="relative flex h-full w-full max-w-3xl flex-col border-l border-ink-800 bg-ink-900 shadow-panel"
      >
        {/* header */}
        <div className="flex items-center gap-3 border-b border-ink-800 px-5 py-3">
          <h3 className="font-semibold">{clip.clip_id}</h3>
          <ScoreBadge score={clip.score} />
          {clip.qa?.reason && <span className="truncate text-xs text-ink-500">QA: {clip.qa.reason}</span>}
          <div className="ml-auto flex items-center gap-1">
            <a
              href={account ? `/out/${niche}/${account}/${clip.clip_id}.mp4` : "#"}
              download
              className="rounded-lg px-2 py-1 text-ink-400 hover:bg-ink-800 hover:text-ink-100"
              title="Download this account's clip"
            >
              ↓
            </a>
            <button
              onClick={onDelete}
              className="rounded-lg px-2 py-1 text-ink-400 hover:bg-bad/15 hover:text-bad"
              title="Delete clip"
            >
              🗑
            </button>
            <button onClick={onClose} className="rounded-lg px-2 py-1 text-ink-400 hover:bg-ink-800 hover:text-ink-100">
              ✕
            </button>
          </div>
        </div>

        <div className="grid flex-1 grid-cols-1 gap-5 overflow-y-auto p-5 md:grid-cols-[280px_1fr]">
          {/* video */}
          <div>
            <div className="overflow-hidden rounded-xl border border-ink-800 bg-black">
              <video key={videoSrc} src={videoSrc} controls className="aspect-[9/16] w-full" />
            </div>
            <div className="mt-2">
              <span className="label">Account</span>
              <select className="input mt-1" value={account} onChange={(e) => setAccount(e.target.value)}>
                {accounts.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* controls */}
          <div className="space-y-5">
            {/* caption per account */}
            <section className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="label">Caption · {account}</span>
                <button className="text-xs text-accent-soft hover:text-accent" onClick={saveMeta} disabled={savingMeta}>
                  {savingMeta ? "saving…" : "save caption"}
                </button>
              </div>
              <textarea className="input min-h-[70px] resize-y" value={caption} onChange={(e) => setCaption(e.target.value)} />
              <input className="input" placeholder="#hashtags #here" value={hashtags} onChange={(e) => setHashtags(e.target.value)} />
            </section>

            <div className="h-px bg-ink-800" />

            {/* subtitle re-render */}
            <section className="space-y-3">
              <span className="label">Burned subtitles (re-renders all accounts)</span>
              <textarea
                className="input min-h-[90px] resize-y font-mono text-xs"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="subtitle words (timings are preserved)"
              />
              <div className="grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="label">Style</span>
                  <select className="input mt-1" value={style} onChange={(e) => setStyle(e.target.value)}>
                    {STYLES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="label">Position</span>
                  <select className="input mt-1" value={position} onChange={(e) => setPosition(e.target.value)}>
                    {POSITIONS.map((p) => (
                      <option key={p.v} value={p.v}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="flex items-center gap-2 text-sm text-ink-300">
                <input type="checkbox" checked={mirror} onChange={(e) => setMirror(e.target.checked)} className="accent-accent" />
                Mirror video (subtitles stay readable)
              </label>
              <button className="btn-primary w-full" onClick={rerender} disabled={rendering}>
                {rendering ? (
                  <>
                    <Spinner /> Re-rendering…
                  </>
                ) : (
                  "Re-render clip"
                )}
              </button>
            </section>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
