import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";

export interface ConfirmReq {
  title: string;
  body?: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
}

/** Controlled confirm dialog. Pass `req` to open; `onClose` clears it. */
export default function Confirm({ req, onClose }: { req: ConfirmReq | null; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <AnimatePresence>
      {req && (
        <div className="fixed inset-0 z-[60] grid place-items-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ type: "spring", stiffness: 320, damping: 26 }}
            className="panel relative w-full max-w-sm p-6"
          >
            <h3 className="mb-1 text-base font-semibold">{req.title}</h3>
            {req.body && <p className="mb-5 text-sm text-ink-400">{req.body}</p>}
            <div className="flex justify-end gap-2">
              <button className="btn-ghost" onClick={onClose}>
                Cancel
              </button>
              <button
                className={`btn ${req.danger ? "bg-bad text-white hover:bg-bad/80" : "btn-primary"}`}
                onClick={() => {
                  req.onConfirm();
                  onClose();
                }}
                autoFocus
              >
                {req.confirmLabel ?? "Confirm"}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
