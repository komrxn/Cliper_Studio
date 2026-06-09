// Shapes returned by the FastAPI backend (cliper/web/app.py).

export interface Niche {
  name: string;
  category: string | null;
  accounts: string[];
  sources: number;
}

export interface Job {
  id: string;
  status: "running" | "done" | "error";
  stage: string;
  progress: number;
  result: unknown;
  error: string | null;
  log: string[];
}

export interface Filmstrip {
  url: string;
  cols: number;
  rows: number;
  interval: number; // seconds per tile
}

export interface SourceResult {
  source_id: string;
  video_url: string;
  duration: number;
  title: string;
  scenes: number[];
  filmstrip: Filmstrip;
}

export interface Suggestion {
  start: number;
  end: number;
  score: number;
  reason: string;
}

// A draggable clip region on the timeline (UI-side; gets an id for React keys).
export interface Segment {
  id: string;
  start: number;
  end: number;
  score?: number;
  reason?: string;
  source: "ai" | "manual";
}

export interface AccountMeta {
  caption?: string;
  hashtags?: string[];
}

export interface Clip {
  clip_id: string;
  score?: number;
  duration?: number;
  text?: string;
  style?: string;
  position?: string | null;
  mirror?: boolean;
  accounts?: string[];
  accounts_meta?: Record<string, AccountMeta>;
  qa?: { postable?: boolean; score?: number; reason?: string };
  words?: { start: number; end: number; word: string }[];
}

export interface ScheduleRow {
  post_at: string;
  account: string;
  clip_id: string;
  caption?: string;
}
