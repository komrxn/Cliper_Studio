import { AnimatePresence, motion } from "framer-motion";
import { useApp } from "../store";
import { Spinner } from "./ui";

/** Global, docked progress for the active backend job — visible on every tab so rendering /
 *  transcribing never feels frozen and navigation stays free. */
export default function JobBar() {
  const { activeJob } = useApp();
  return (
    <AnimatePresence>
      {activeJob && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          className="panel fixed bottom-5 right-5 z-50 w-80 p-4"
        >
          <div className="mb-2 flex items-center gap-2">
            {activeJob.status === "running" ? (
              <Spinner />
            ) : activeJob.status === "error" ? (
              <span className="text-bad">✕</span>
            ) : (
              <span className="text-good">✓</span>
            )}
            <span className="text-sm font-medium">{activeJob.label}</span>
          </div>
          {activeJob.status === "error" ? (
            <p className="text-xs text-bad">{activeJob.error}</p>
          ) : (
            <>
              <div className="mb-1.5 flex justify-between text-xs text-ink-400">
                <span className="capitalize">{activeJob.stage || "working"}</span>
                <span className="tabular-nums">{Math.round(activeJob.progress * 100)}%</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-ink-800">
                <motion.div
                  className="h-full rounded-full bg-accent"
                  animate={{ width: `${Math.max(4, activeJob.progress * 100)}%` }}
                  transition={{ type: "spring", stiffness: 120, damping: 22 }}
                />
              </div>
            </>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
