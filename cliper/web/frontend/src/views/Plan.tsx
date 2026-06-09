import { useState } from "react";
import { api } from "../api";
import type { ScheduleRow } from "../types";
import type { Notify } from "../App";
import { EmptyState, Spinner } from "../components/ui";

interface Props {
  niche: string;
  notify: Notify;
}

export default function Plan({ niche, notify }: Props) {
  const [rows, setRows] = useState<ScheduleRow[] | null>(null);
  const [loading, setLoading] = useState(false);

  const build = async () => {
    setLoading(true);
    try {
      const { rows } = await api.schedule(niche);
      setRows(rows);
      notify("ok", `Scheduled ${rows.length} post${rows.length === 1 ? "" : "s"}`);
    } catch (e) {
      notify("err", (e as Error).message);
      setRows([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Posting plan</h2>
          <p className="text-sm text-ink-400">
            A staggered schedule across the niche’s accounts, built from the exported clips.
          </p>
        </div>
        <button className="btn-primary" onClick={build} disabled={loading}>
          {loading ? <Spinner /> : "Build schedule"}
        </button>
      </div>

      <div className="panel overflow-hidden">
        {rows === null ? (
          <EmptyState
            icon={<span className="text-xl">🗓</span>}
            title="No schedule yet"
            hint="Build a staggered posting plan for the rendered clips in this niche."
          />
        ) : rows.length === 0 ? (
          <EmptyState icon={<span className="text-xl">∅</span>} title="No clips to schedule" hint="Render some clips in Studio first." />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ink-800 text-left text-xs uppercase tracking-wide text-ink-500">
                <th className="px-4 py-2.5 font-medium">Post at</th>
                <th className="px-4 py-2.5 font-medium">Account</th>
                <th className="px-4 py-2.5 font-medium">Clip</th>
                <th className="px-4 py-2.5 font-medium">Caption</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-b border-ink-850 last:border-0 hover:bg-ink-850">
                  <td className="whitespace-nowrap px-4 py-2.5 tabular-nums text-ink-200">{r.post_at}</td>
                  <td className="px-4 py-2.5">
                    <span className="rounded-md bg-ink-800 px-1.5 py-0.5 text-xs text-ink-300">{r.account}</span>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-ink-400">{r.clip_id}</td>
                  <td className="max-w-[320px] truncate px-4 py-2.5 text-ink-400">{r.caption}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
