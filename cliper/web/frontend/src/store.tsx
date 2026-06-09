import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "./api";
import type { Niche, Segment, SourceResult } from "./types";

export type Tab = "studio" | "gallery" | "plan";
export interface ToastT {
  kind: "ok" | "err";
  text: string;
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
      }}
    >
      {children}
    </Ctx.Provider>
  );
}
