import { motion } from "framer-motion";
import type { ReactNode } from "react";

export function ScoreBadge({ score = 0 }: { score?: number }) {
  const bg = score >= 0.6 ? "bg-good/15 text-good" : score >= 0.4 ? "bg-warn/15 text-warn" : "bg-ink-700 text-ink-300";
  return (
    <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold tabular-nums ${bg}`}>
      {score.toFixed(2)}
    </span>
  );
}

export function Pill({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-md bg-ink-800 px-1.5 py-0.5 text-[10px] font-medium text-ink-300">
      {children}
    </span>
  );
}

export function ProgressBar({ value, label }: { value: number; label?: string }) {
  return (
    <div className="w-full">
      {label && (
        <div className="mb-1 flex justify-between text-xs text-ink-400">
          <span className="capitalize">{label}</span>
          <span className="tabular-nums">{Math.round(value * 100)}%</span>
        </div>
      )}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-800">
        <motion.div
          className="h-full rounded-full bg-accent"
          initial={false}
          animate={{ width: `${Math.max(2, value * 100)}%` }}
          transition={{ type: "spring", stiffness: 120, damping: 22 }}
        />
      </div>
    </div>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-ink-600 border-t-accent ${className}`}
    />
  );
}

export function EmptyState({ icon, title, hint }: { icon: ReactNode; title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-center">
      <div className="grid h-14 w-14 place-items-center rounded-2xl bg-ink-800 text-ink-400">{icon}</div>
      <div className="text-sm font-medium text-ink-200">{title}</div>
      {hint && <div className="max-w-xs text-xs text-ink-400">{hint}</div>}
    </div>
  );
}

export function Toast({ kind, text }: { kind: "ok" | "err"; text: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 12 }}
      className={`fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-xl border px-4 py-2 text-sm shadow-panel ${
        kind === "ok"
          ? "border-good/30 bg-good/10 text-good"
          : "border-bad/30 bg-bad/10 text-bad"
      }`}
    >
      {text}
    </motion.div>
  );
}
