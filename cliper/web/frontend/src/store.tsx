import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, pollJob } from "./api";
import type { Job, Niche, Segment, SourceResult } from "./types";

export type Tab = "studio" | "gallery" | "plan";
export interface ToastT {
  kind: "ok" | "err";
  text: string;
}
/** A long-running backend job tracked globally so its progress shows across all tabs and
 *  navigation is never blocked. */
export interface JobState {
  id: string;
  label: string;
  stage: string;
  progress: number;
  status: "running" | "done" | "error";
  error?: string;
}
/** Studio working state that must survive tab switches (the bug: it used to reset). */
export interface Session {
  source: SourceResult | null;
  segments: Segment[];
  selected: string | null;
  current: number;
}

const EMPTY_SESSION: Session = { source: null, segments: [], selected: null, current: 0 };

interface AppCtx {
  niches: Niche[];
  niche: string;
  setNiche: (n: string) => void;
  accounts: string[];
  online: boolean | null;
  tab: Tab;
  setTab: (t: Tab) => void;
  toast: ToastT | null;
  notify: (kind: "ok" | "err", text: string) => void;
  session: Session;
  patchSession: (p: Partial<Session>) => void;
  resetSession: () => void;
  recent: SourceResult[];
  refreshRecent: () => void;
  activeJob: JobState | null;
  track: (jobId: string, label: string) => Promise<unknown>;
}

const Ctx = createContext<AppCtx | null>(null);

export const useApp = (): AppCtx => {
  const c = useContext(Ctx);
  if (!c) throw new Error("useApp must be used within <AppProvider>");
  return c;
};

const lsGet = (k: string, fallback: string) => {
  try {
    return localStorage.getItem(k) ?? fallback;
  } catch {
    return fallback;
  }
};
const lsSet = (k: string, v: string) => {
  try {
    localStorage.setItem(k, v);
  } catch {
    /* ignore */
  }
};

export function AppProvider({ children }: { children: ReactNode }) {
  const [niches, setNiches] = useState<Niche[]>([]);
  const [niche, setNicheState] = useState<string>(() => lsGet("cliper.niche", ""));
  const [online, setOnline] = useState<boolean | null>(null);
  const [tab, setTabState] = useState<Tab>(() => lsGet("cliper.tab", "studio") as Tab);
  const [toast, setToast] = useState<ToastT | null>(null);
  const [session, setSession] = useState<Session>(EMPTY_SESSION);
  const [recent, setRecent] = useState<SourceResult[]>([]);
  const [activeJob, setActiveJob] = useState<JobState | null>(null);
  const toastTimer = useRef<number>();

  const setNiche = useCallback((n: string) => {
    setNicheState(n);
    lsSet("cliper.niche", n);
  }, []);
  const setTab = useCallback((t: Tab) => {
    setTabState(t);
    lsSet("cliper.tab", t);
  }, []);

  const notify = useCallback((kind: "ok" | "err", text: string) => {
    setToast({ kind, text });
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 3400);
  }, []);

  const patchSession = useCallback((p: Partial<Session>) => setSession((s) => ({ ...s, ...p })), []);
  const resetSession = useCallback(() => setSession(EMPTY_SESSION), []);

  const refreshRecent = useCallback(() => {
    api
      .sources()
      .then(({ sources }) => setRecent(sources))
      .catch(() => setRecent([]));
  }, []);

  // Track a backend job globally: progress shows in the JobBar across tabs; the promise resolves
  // with the result. Callers can `await track(...)` without blocking navigation.
  const track = useCallback((jobId: string, label: string) => {
    setActiveJob({ id: jobId, label, stage: "starting", progress: 0, status: "running" });
    const upd = (p: Partial<JobState>) =>
      setActiveJob((a) => (a && a.id === jobId ? { ...a, ...p } : a));
    return pollJob(jobId, (j: Job) => upd({ stage: j.stage, progress: j.progress }))
      .then((result) => {
        upd({ status: "done", progress: 1, stage: "done" });
        window.setTimeout(() => setActiveJob((a) => (a?.id === jobId ? null : a)), 1400);
        return result;
      })
      .catch((e) => {
        upd({ status: "error", error: (e as Error).message });
        window.setTimeout(() => setActiveJob((a) => (a?.id === jobId ? null : a)), 5000);
        throw e;
      });
  }, []);

  useEffect(() => {
    api
      .niches()
      .then(({ niches }) => {
        setNiches(niches);
        setOnline(true);
        setNicheState((cur) => (cur && niches.some((n) => n.name === cur) ? cur : niches[0]?.name ?? ""));
      })
      .catch(() => setOnline(false));
    refreshRecent();
  }, [refreshRecent]);

  const accounts = niches.find((n) => n.name === niche)?.accounts ?? [];

  return (
    <Ctx.Provider
      value={{
        niches, niche, setNiche, accounts, online,
        tab, setTab, toast, notify,
        session, patchSession, resetSession,
        recent, refreshRecent,
        activeJob, track,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}
