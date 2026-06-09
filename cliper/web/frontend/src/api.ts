// Thin fetch client + a job-polling helper shared across views.
import type { Clip, Job, Niche, ScheduleRow } from "./types";

async function req<T>(path: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(path, opts);
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail || `HTTP ${r.status}`);
  }
  return r.json() as Promise<T>;
}

function postJSON<T>(path: string, body: unknown): Promise<T> {
  return req<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const api = {
  niches: () => req<{ niches: Niche[] }>("/api/niches"),

  job: (id: string) => req<Job>(`/api/jobs/${id}`),

  createSourceFromUrl: (url: string) =>
    postJSON<{ job_id: string }>("/api/sources", { url }),

  uploadSource: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return req<{ job_id: string }>("/api/sources/upload", { method: "POST", body: fd });
  },

  suggest: (sid: string, niche: string) =>
    postJSON<{ job_id: string }>(`/api/sources/${sid}/suggest`, { niche }),

  makeClips: (sid: string, niche: string, segments: { start: number; end: number }[]) =>
    postJSON<{ job_id: string }>(`/api/sources/${sid}/clips`, { niche, segments }),

  clips: (niche: string) => req<{ clips: Clip[] }>(`/api/clips/${niche}`),

  saveMeta: (niche: string, clipId: string, body: object) =>
    postJSON<{ ok: boolean }>(`/api/clips/${niche}/${clipId}/meta`, body),

  rerender: (niche: string, clipId: string, body: object) =>
    postJSON<{ ok: boolean; state: Clip }>(`/api/clips/${niche}/${clipId}/rerender`, body),

  schedule: (niche: string) =>
    postJSON<{ rows: ScheduleRow[] }>(`/api/schedule/${niche}`, {}),
};

/**
 * Poll a job to completion, invoking `onTick` with each snapshot. Resolves with the
 * job's `result`, rejects on error. (SSE exists server-side; polling is simpler and the
 * jobs are coarse-grained.)
 */
export function pollJob(
  jobId: string,
  onTick: (j: Job) => void,
  intervalMs = 700,
): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const tick = async () => {
      try {
        const job = await api.job(jobId);
        onTick(job);
        if (job.status === "done") return resolve(job.result);
        if (job.status === "error") return reject(new Error(job.error || "job failed"));
        setTimeout(tick, intervalMs);
      } catch (e) {
        reject(e as Error);
      }
    };
    tick();
  });
}

// --- formatting helpers ---
export const fmtTime = (s: number): string => {
  if (!isFinite(s) || s < 0) s = 0;
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
};

export const scoreColor = (s = 0): string =>
  s >= 0.6 ? "text-good" : s >= 0.4 ? "text-warn" : "text-ink-400";
