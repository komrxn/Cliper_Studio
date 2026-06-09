import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { Clip } from "../types";
import type { Notify } from "../App";
import { EmptyState, ScoreBadge } from "../components/ui";
import Editor from "./Editor";

interface Props {
  niche: string;
  notify: Notify;
}

export default function Gallery({ niche, notify }: Props) {
  const [clips, setClips] = useState<Clip[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState<Clip | null>(null);
  const [bust, setBust] = useState(0); // cache-buster for thumbnails after re-render

  const load = useCallback(async () => {
    if (!niche) return;
    setLoading(true);
    try {
      const { clips } = await api.clips(niche);
      setClips(clips);
    } catch {
      setClips([]);
    } finally {
      setLoading(false);
    }
  }, [niche]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Gallery</h2>
          <p className="text-sm text-ink-400">
            {loading ? "Loading…" : `${clips.length} clip${clips.length === 1 ? "" : "s"} in “${niche}”`}
          </p>
        </div>
        <button className="btn-ghost" onClick={load}>
          ↻ Refresh
        </button>
      </div>

      {loading ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="skeleton aspect-[9/16]" />
          ))}
        </div>
      ) : clips.length === 0 ? (
        <div className="panel">
          <EmptyState
            icon={<span className="text-xl">🎬</span>}
            title="No clips yet"
            hint="Head to Studio, load a source, mark moments, and render — they’ll show up here."
          />
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {clips.map((c) => {
            const acc = c.accounts?.[0] ?? "";
            const meta = c.accounts_meta?.[acc] ?? {};
            return (
              <button
                key={c.clip_id}
                onClick={() => setOpen(c)}
                className="group panel overflow-hidden p-0 text-left transition-transform hover:-translate-y-0.5 hover:shadow-glow"
              >
                <div className="relative aspect-[9/16] bg-black">
                  <img
                    loading="lazy"
                    src={`/api/thumb/${niche}/${c.clip_id}?t=${bust}`}
                    className="h-full w-full object-cover transition-opacity group-hover:opacity-90"
                    alt={c.clip_id}
                  />
                  <div className="absolute left-1.5 top-1.5 flex gap-1">
                    <ScoreBadge score={c.score} />
                    <span className="rounded-md bg-black/70 px-1.5 py-0.5 text-[10px] tabular-nums text-ink-200">
                      {(c.duration ?? 0).toFixed(0)}s
                    </span>
                  </div>
                  {c.mirror && (
                    <span className="absolute right-1.5 top-1.5 rounded-md bg-black/70 px-1.5 py-0.5 text-[10px] text-accent-soft">
                      ⇄
                    </span>
                  )}
                </div>
                <div className="p-2.5">
                  <div className="line-clamp-2 text-xs text-ink-200">
                    {meta.caption || c.text || <span className="text-ink-500">no caption</span>}
                  </div>
                  <div className="mt-1.5 truncate text-[10px] text-ink-500">{(c.accounts ?? []).join(" · ")}</div>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {open && (
        <Editor
          niche={niche}
          clip={open}
          notify={notify}
          onClose={() => setOpen(null)}
          onSaved={() => {
            setBust(Date.now());
            load();
          }}
        />
      )}
    </div>
  );
}
