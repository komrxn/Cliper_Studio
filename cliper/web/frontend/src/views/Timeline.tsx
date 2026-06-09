import { useCallback, useEffect, useRef, useState } from "react";
import { fmtTime } from "../api";
import type { Filmstrip, Segment } from "../types";

interface Props {
  duration: number;
  scenes: number[];
  filmstrip: Filmstrip;
  segments: Segment[];
  current: number;
  onSeek: (t: number) => void;
  onChange: (id: string, start: number, end: number) => void;
  onSelect: (id: string | null) => void;
  selected: string | null;
}

type DragMode = "move" | "start" | "end";
interface DragState {
  id: string;
  mode: DragMode;
  startX: number;
  origStart: number;
  origEnd: number;
}

const SNAP_PX = 7; // snap a dragged edge to a scene cut within this many pixels

export default function Timeline({
  duration,
  scenes,
  filmstrip,
  segments,
  current,
  onSeek,
  onChange,
  onSelect,
  selected,
}: Props) {
  const trackRef = useRef<HTMLDivElement>(null);
  const drag = useRef<DragState | null>(null);
  const [hoverT, setHoverT] = useState<number | null>(null);

  const pct = (t: number) => `${(t / duration) * 100}%`;
  const widthPx = () => trackRef.current?.getBoundingClientRect().width ?? 1;
  const pxToTime = (px: number) => (px / widthPx()) * duration;

  const snapToScene = useCallback(
    (t: number) => {
      const tol = pxToTime(SNAP_PX);
      let best = t;
      let bestD = tol;
      for (const c of scenes) {
        const d = Math.abs(c - t);
        if (d < bestD) {
          bestD = d;
          best = c;
        }
      }
      return best;
    },
    [scenes, duration],
  );

  // --- dragging segments ---
  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const d = drag.current;
      if (!d) return;
      const dt = pxToTime(e.clientX - d.startX);
      let s = d.origStart;
      let en = d.origEnd;
      if (d.mode === "move") {
        const len = d.origEnd - d.origStart;
        s = Math.max(0, Math.min(duration - len, d.origStart + dt));
        en = s + len;
      } else if (d.mode === "start") {
        s = snapToScene(Math.max(0, Math.min(en - 0.5, d.origStart + dt)));
      } else {
        en = snapToScene(Math.min(duration, Math.max(s + 0.5, d.origEnd + dt)));
      }
      onChange(d.id, s, en);
    };
    const onUp = () => {
      drag.current = null;
      document.body.style.cursor = "";
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [duration, onChange, snapToScene]);

  const startDrag = (e: React.PointerEvent, seg: Segment, mode: DragMode) => {
    e.stopPropagation();
    onSelect(seg.id);
    drag.current = { id: seg.id, mode, startX: e.clientX, origStart: seg.start, origEnd: seg.end };
    document.body.style.cursor = mode === "move" ? "grabbing" : "ew-resize";
  };

  const trackClick = (e: React.PointerEvent) => {
    if (drag.current) return;
    const rect = trackRef.current!.getBoundingClientRect();
    onSeek(((e.clientX - rect.left) / rect.width) * duration);
  };

  const trackMove = (e: React.PointerEvent) => {
    const rect = trackRef.current!.getBoundingClientRect();
    setHoverT(((e.clientX - rect.left) / rect.width) * duration);
  };

  // filmstrip background tiles
  const tiles = Math.max(1, Math.min(filmstrip.cols * filmstrip.rows, Math.ceil(duration / filmstrip.interval)));

  return (
    <div className="select-none">
      {/* time ruler */}
      <div className="relative mb-1 h-4 text-[10px] text-ink-500">
        {Array.from({ length: 11 }).map((_, i) => (
          <span key={i} className="absolute -translate-x-1/2 tabular-nums" style={{ left: `${i * 10}%` }}>
            {fmtTime((duration * i) / 10)}
          </span>
        ))}
      </div>

      <div
        ref={trackRef}
        onPointerDown={trackClick}
        onPointerMove={trackMove}
        onPointerLeave={() => setHoverT(null)}
        className="relative h-20 w-full cursor-text overflow-hidden rounded-xl border border-ink-700 bg-ink-950"
      >
        {/* filmstrip */}
        <div className="pointer-events-none absolute inset-0 flex opacity-50">
          {Array.from({ length: tiles }).map((_, i) => {
            const r = Math.floor(i / filmstrip.cols);
            const c = i % filmstrip.cols;
            return (
              <div
                key={i}
                className="h-full flex-1 border-r border-ink-950/40"
                style={{
                  backgroundImage: `url(${filmstrip.url})`,
                  backgroundSize: `${filmstrip.cols * 100}% ${filmstrip.rows * 100}%`,
                  backgroundPosition: `${(c / Math.max(1, filmstrip.cols - 1)) * 100}% ${
                    (r / Math.max(1, filmstrip.rows - 1)) * 100
                  }%`,
                }}
              />
            );
          })}
        </div>

        {/* scene-cut ticks */}
        <div className="pointer-events-none absolute inset-0">
          {scenes.map((s, i) => (
            <span key={i} className="absolute top-0 h-2 w-px bg-accent-soft/60" style={{ left: pct(s) }} />
          ))}
        </div>

        {/* segments */}
        {segments.map((seg) => {
          const isSel = seg.id === selected;
          return (
            <div
              key={seg.id}
              onPointerDown={(e) => startDrag(e, seg, "move")}
              className={`group absolute top-0 bottom-0 cursor-grab active:cursor-grabbing rounded-md border transition-shadow ${
                isSel
                  ? "border-accent bg-accent/25 shadow-glow z-20"
                  : "border-accent/50 bg-accent/15 hover:bg-accent/20 z-10"
              }`}
              style={{ left: pct(seg.start), width: pct(seg.end - seg.start) }}
            >
              {/* left handle */}
              <span
                onPointerDown={(e) => startDrag(e, seg, "start")}
                className="absolute left-0 top-0 z-10 h-full w-2 cursor-ew-resize rounded-l-md bg-accent/70 opacity-0 transition-opacity group-hover:opacity-100"
                style={{ opacity: isSel ? 1 : undefined }}
              />
              {/* right handle */}
              <span
                onPointerDown={(e) => startDrag(e, seg, "end")}
                className="absolute right-0 top-0 z-10 h-full w-2 cursor-ew-resize rounded-r-md bg-accent/70 opacity-0 transition-opacity group-hover:opacity-100"
                style={{ opacity: isSel ? 1 : undefined }}
              />
              <div className="pointer-events-none flex h-full flex-col justify-between p-1.5">
                <div className="flex items-center gap-1">
                  {seg.source === "ai" ? (
                    <span className="rounded bg-black/40 px-1 text-[9px] font-semibold text-accent-soft">AI</span>
                  ) : (
                    <span className="rounded bg-black/40 px-1 text-[9px] font-semibold text-ink-300">✎</span>
                  )}
                  {typeof seg.score === "number" && (
                    <span className="rounded bg-black/40 px-1 text-[9px] tabular-nums text-ink-200">
                      {seg.score.toFixed(2)}
                    </span>
                  )}
                </div>
                <span className="rounded bg-black/50 px-1 text-[9px] tabular-nums text-ink-100">
                  {fmtTime(seg.end - seg.start)}
                </span>
              </div>
            </div>
          );
        })}

        {/* hover guide */}
        {hoverT !== null && !drag.current && (
          <span className="pointer-events-none absolute top-0 bottom-0 w-px bg-ink-400/40" style={{ left: pct(hoverT) }} />
        )}

        {/* playhead */}
        <span className="pointer-events-none absolute top-0 bottom-0 z-30 w-0.5 bg-white" style={{ left: pct(current) }}>
          <span className="absolute -top-0 -left-[5px] h-3 w-3 -translate-y-0 rotate-45 rounded-sm bg-white" />
        </span>
      </div>
    </div>
  );
}
