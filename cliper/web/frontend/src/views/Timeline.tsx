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
const TRACK_H = 76; // filmstrip height (px)
const TILE_W = 128; // target thumbnail width → 16:9 against TRACK_H

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
  const [width, setWidth] = useState(1000);

  // keep the real pixel width so px↔time math (and tile count) is correct + responsive
  useEffect(() => {
    const el = trackRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width));
    ro.observe(el);
    setWidth(el.getBoundingClientRect().width);
    return () => ro.disconnect();
  }, []);

  const pct = (t: number) => `${(t / duration) * 100}%`;
  const pxToTime = useCallback((px: number) => (px / width) * duration, [width, duration]);

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
    [scenes, pxToTime],
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
  }, [duration, onChange, snapToScene, pxToTime]);

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

  // --- filmstrip: render frames at a readable width that tile the full track ---
  const framesAvail = Math.max(1, Math.min(filmstrip.cols * filmstrip.rows, Math.ceil(duration / filmstrip.interval)));
  const tileCount = Math.max(4, Math.min(framesAvail, Math.round(width / TILE_W)));

  return (
    <div className="select-none">
      {/* time ruler */}
      <div className="relative mb-1.5 h-4 text-[10px] text-ink-500">
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
        className="relative w-full cursor-text overflow-hidden rounded-xl border border-ink-700 bg-ink-950"
        style={{ height: TRACK_H }}
      >
        {/* filmstrip (real frames) */}
        <div className="pointer-events-none absolute inset-0 flex">
          {Array.from({ length: tileCount }).map((_, i) => {
            const frame = Math.min(framesAvail - 1, Math.round(((i + 0.5) / tileCount) * framesAvail));
            const r = Math.floor(frame / filmstrip.cols);
            const c = frame % filmstrip.cols;
            return (
              <div
                key={i}
                className="h-full bg-cover"
                style={{
                  width: `${100 / tileCount}%`,
                  backgroundImage: `url(${filmstrip.url})`,
                  backgroundSize: `${filmstrip.cols * 100}% ${filmstrip.rows * 100}%`,
                  backgroundPosition: `${(c / Math.max(1, filmstrip.cols - 1)) * 100}% ${
                    (r / Math.max(1, filmstrip.rows - 1)) * 100
                  }%`,
                  boxShadow: "inset -1px 0 0 rgba(0,0,0,0.35)",
                }}
              />
            );
          })}
        </div>
        {/* darken filmstrip slightly so overlays read clearly */}
        <div className="pointer-events-none absolute inset-0 bg-ink-950/25" />

        {/* scene-cut ticks */}
        <div className="pointer-events-none absolute inset-x-0 top-0">
          {scenes.map((s, i) => (
            <span key={i} className="absolute top-0 h-2.5 w-px bg-white/40" style={{ left: pct(s) }} />
          ))}
        </div>

        {/* segments */}
        {segments.map((seg) => {
          const isSel = seg.id === selected;
          return (
            <div
              key={seg.id}
              onPointerDown={(e) => startDrag(e, seg, "move")}
              className={`group absolute top-0 bottom-0 cursor-grab rounded-md border-2 transition-shadow active:cursor-grabbing ${
                isSel
                  ? "z-20 border-accent bg-accent/25 shadow-glow"
                  : "z-10 border-accent/60 bg-accent/15 hover:bg-accent/25"
              }`}
              style={{ left: pct(seg.start), width: pct(seg.end - seg.start) }}
            >
              <span
                onPointerDown={(e) => startDrag(e, seg, "start")}
                className="absolute left-0 top-0 z-10 flex h-full w-2.5 cursor-ew-resize items-center justify-center rounded-l bg-accent/80"
              >
                <span className="h-5 w-0.5 rounded bg-white/80" />
              </span>
              <span
                onPointerDown={(e) => startDrag(e, seg, "end")}
                className="absolute right-0 top-0 z-10 flex h-full w-2.5 cursor-ew-resize items-center justify-center rounded-r bg-accent/80"
              >
                <span className="h-5 w-0.5 rounded bg-white/80" />
              </span>
              <div className="pointer-events-none flex h-full flex-col justify-between p-1.5">
                <div className="flex items-center gap-1">
                  <span className="rounded bg-black/55 px-1 text-[9px] font-semibold text-accent-soft">
                    {seg.source === "ai" ? "AI" : "✎"}
                  </span>
                  {typeof seg.score === "number" && (
                    <span className="rounded bg-black/55 px-1 text-[9px] tabular-nums text-ink-100">
                      {seg.score.toFixed(2)}
                    </span>
                  )}
                </div>
                <span className="self-start rounded bg-black/60 px-1 text-[9px] tabular-nums text-ink-100">
                  {fmtTime(seg.end - seg.start)}
                </span>
              </div>
            </div>
          );
        })}

        {/* hover guide + tooltip */}
        {hoverT !== null && !drag.current && (
          <span className="pointer-events-none absolute top-0 bottom-0 z-30 w-px bg-white/50" style={{ left: pct(hoverT) }}>
            <span className="absolute -top-5 left-1/2 -translate-x-1/2 rounded bg-ink-800 px-1 text-[9px] tabular-nums text-ink-200">
              {fmtTime(hoverT)}
            </span>
          </span>
        )}

        {/* playhead */}
        <span className="pointer-events-none absolute top-0 bottom-0 z-40 w-0.5 bg-white shadow-[0_0_6px_rgba(255,255,255,0.5)]" style={{ left: pct(current) }}>
          <span className="absolute -left-[5px] -top-[3px] h-3 w-3 rotate-45 rounded-sm bg-white" />
        </span>
      </div>
    </div>
  );
}
