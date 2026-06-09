import { AnimatePresence, motion } from "framer-motion";
import { useApp, type Tab } from "./store";
import { Toast } from "./components/ui";
import Studio from "./views/Studio";
import Gallery from "./views/Gallery";
import Plan from "./views/Plan";

const TABS: { id: Tab; label: string }[] = [
  { id: "studio", label: "Studio" },
  { id: "gallery", label: "Gallery" },
  { id: "plan", label: "Plan" },
];

export default function App() {
  const { niches, niche, setNiche, online, tab, setTab, toast } = useApp();

  return (
    <div className="flex min-h-screen flex-col">
      {/* Top bar */}
      <header className="sticky top-0 z-40 border-b border-ink-800 bg-ink-950/80 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center gap-4 px-5">
          <div className="flex items-center gap-2.5">
            <div className="grid h-7 w-7 place-items-center rounded-lg bg-accent text-white shadow-glow">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                <path d="M5 5l14 7-14 7V5z" fill="currentColor" />
              </svg>
            </div>
            <span className="text-[15px] font-semibold tracking-tight">Cliper</span>
            <span className="rounded-md bg-ink-800 px-1.5 py-0.5 text-[10px] font-medium text-ink-400">
              studio
            </span>
          </div>

          <nav className="ml-2 flex items-center gap-1">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`relative rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                  tab === t.id ? "text-ink-100" : "text-ink-400 hover:text-ink-200"
                }`}
              >
                {tab === t.id && (
                  <motion.span
                    layoutId="tab-bg"
                    className="absolute inset-0 rounded-lg bg-ink-800"
                    transition={{ type: "spring", stiffness: 380, damping: 30 }}
                  />
                )}
                <span className="relative">{t.label}</span>
              </button>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            {niches.length > 0 && (
              <label className="flex items-center gap-2 text-sm">
                <span className="text-ink-400">Niche</span>
                <select
                  value={niche}
                  onChange={(e) => setNiche(e.target.value)}
                  className="input w-auto py-1.5 pr-7"
                >
                  {niches.map((n) => (
                    <option key={n.name} value={n.name}>
                      {n.name}
                      {n.category ? ` · ${n.category}` : ""}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <span
              className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium ${
                online === false ? "bg-bad/15 text-bad" : online ? "bg-good/15 text-good" : "bg-ink-800 text-ink-400"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  online === false ? "bg-bad" : online ? "bg-good" : "bg-ink-500"
                }`}
              />
              {online === false ? "offline" : online ? "ready" : "…"}
            </span>
          </div>
        </div>
      </header>

      {/* Body — views are mounted lazily but their session state lives in the store, so
          switching tabs no longer resets Studio. */}
      <main className="mx-auto w-full max-w-[1400px] flex-1 px-5 py-6">
        <AnimatePresence mode="wait">
          <motion.div
            key={tab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.18 }}
          >
            {tab === "studio" && <Studio />}
            {tab === "gallery" && <Gallery />}
            {tab === "plan" && <Plan />}
          </motion.div>
        </AnimatePresence>
      </main>

      <AnimatePresence>{toast && <Toast kind={toast.kind} text={toast.text} />}</AnimatePresence>
    </div>
  );
}
