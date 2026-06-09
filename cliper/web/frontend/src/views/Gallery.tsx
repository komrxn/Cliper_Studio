import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Clip } from "../types";
import { useApp } from "../store";
import { EmptyState, ScoreBadge } from "../components/ui";
import Confirm, { type ConfirmReq } from "../components/Confirm";
import Editor from "./Editor";

type Sort = "score" | "duration" | "recent";

export default function Gallery() {
  const { niche, notify } = useApp();
  const [clips, setClips] = useState<Clip[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState<Clip | null>(null);
  const [bust, setBust] = useState(0);
  const [sort, setSort] = useState<Sort>("score");
  const [accFilter, setAccFilter] = useState("");
  const [search, setSearch] = useState("");
  const [confirm, setConfirm] = useState<ConfirmReq | null>(null);

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

  const allAccounts = useMemo(
    () => [...new Set(clips.flatMap((c) => c.accounts ?? []))].sort(),
    [clips],
  );

  const view = useMemo(() => {
    const q = search.trim().toLowerCase();
    let list = clips;
    if (accFilter) list = list.filter((c) => (c.accounts ?? []).includes(accFilter));
    if (q)
      list = list.filter((c) => {
        const acc = c.accounts?.[0] ?? "";
        const cap = c.accounts_meta?.[acc]?.caption ?? "";
        return (cap + " " + (c.text ?? "")).toLowerCase().includes(q);
      });
    return [...list].sort((a, b) => {
      if (sort === "duration") return (b.duration ?? 0) - (a.duration ?? 0);
      if (sort === "recent") return (b.created_at ?? 0) - (a.created_at ?? 0);
      return (b.score ?? 0) - (a.score ?? 0);
    });
  }, [clips, accFilter, search, sort]);

  const askDelete = (c: Clip) =>
    setConfirm({
      title: `Delete ${c.clip_id}?`,
      body: "Removes the rendered mp4s for all accounts and its editable state. This can't be undone.",
      danger: true,
      confirmLabel: "Delete",
      onConfirm: async () => {
        try {
          await api.deleteClip(niche, c.clip_id);
          notify("ok", "Clip deleted");
          if (open?.clip_id === c.clip_id) setOpen(null);
          load();
        } catch (e) {
          notify("err", (e as Error).message);
        }
      },
    });

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="mr-auto">
          <h2 className="text-lg font-semibold tracking-tight">Gallery</h2>
          <p className="text-sm text-ink-400">
            {loading ? "Loading…" : `${view.length} of ${clips.length} clip${clips.length === 1 ? "" : "s"} in “${niche}”`}
          </p>
        </div>
        <input
          className="input w-44"
          placeholder="Search captions…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select className="input w-auto py-1.5 pr-7" value={accFilter} onChange={(e) => setAccFilter(e.target.value)}>
          <option value="">All accounts</option>
          {allAccounts.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <select className="input w-auto py-1.5 pr-7" value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
          <option value="score">Top score</option>
          <option value="duration">Longest</option>
          <option value="recent">Newest</option>
        </select>
        <button className="btn-ghost" onClick={load}>
          ↻
        </button>
      </div>

      {loading ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="skeleton aspect-[9/16]" />
          ))}
        </div>
      ) : view.length === 0 ? (
        <div className="panel">
          <EmptyState
            icon={<span className="text-xl">🎬</span>}
            title={clips.length ? "No clips match" : "No clips yet"}
            hint={
              clips.length
                ? "Try clearing the search or account filter."
                : "Head to Studio, load a source, mark moments, and render — they’ll show up here."
            }
          />
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {view.map((c) => {
            const acc = c.accounts?.[0] ?? "";
            const meta = c.accounts_meta?.[acc] ?? {};
            return (
              <div
                key={c.clip_id}
                onClick={() => setOpen(c)}
                className="group panel relative cursor-pointer overflow-hidden p-0 text-left transition-transform hover:-translate-y-0.5 hover:shadow-glow"
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
                  {/* hover actions */}
                  <div className="absolute right-1.5 top-1.5 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <a
                      href={acc ? `/out/${niche}/${acc}/${c.clip_id}.mp4` : "#"}
                      download
                      onClick={(e) => e.stopPropagation()}
                      className="grid h-6 w-6 place-items-center rounded-md bg-black/70 text-ink-100 hover:bg-accent"
                      title="Download"
                    >
                      ↓
                    </a>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        askDelete(c);
                      }}
                      className="grid h-6 w-6 place-items-center rounded-md bg-black/70 text-ink-100 hover:bg-bad"
                      title="Delete"
                    >
                      ✕
                    </button>
                  </div>
                  {c.mirror && (
                    <span className="absolute bottom-1.5 right-1.5 rounded-md bg-black/70 px-1.5 py-0.5 text-[10px] text-accent-soft">
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
              </div>
            );
          })}
        </div>
      )}

      {open && (
        <Editor
          niche={niche}
          clip={open}
          onClose={() => setOpen(null)}
          onDelete={() => askDelete(open)}
          onSaved={() => {
            setBust(Date.now());
            load();
          }}
        />
      )}

      <Confirm req={confirm} onClose={() => setConfirm(null)} />
    </div>
  );
}
