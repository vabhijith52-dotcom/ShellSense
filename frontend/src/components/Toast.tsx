import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, AlertCircle, RotateCcw, X } from "lucide-react";
import { sanitize } from "@/lib/sanitize";

export interface ToastMessage {
  id: string;
  type: "success" | "error" | "undo";
  message: string;
  undoAction?: () => void;
  duration?: number;
}

interface ToastContainerProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

export const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, onDismiss }) => {
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      <AnimatePresence>
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onDismiss={() => onDismiss(toast.id)} />
        ))}
      </AnimatePresence>
    </div>
  );
};

const ToastItem: React.FC<{ toast: ToastMessage; onDismiss: () => void }> = ({ toast, onDismiss }) => {
  const [progress, setProgress] = useState(100);

  useEffect(() => {
    if (toast.type === "error") return; // Errors persist until dismissed

    const duration = toast.duration || (toast.type === "undo" ? 8000 : 4000);
    const interval = 50;
    const step = (interval / duration) * 100;

    const timer = setInterval(() => {
      setProgress((prev) => {
        if (prev <= step) {
          clearInterval(timer);
          onDismiss();
          return 0;
        }
        return prev - step;
      });
    }, interval);

    return () => clearInterval(timer);
  }, [toast, onDismiss]);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9, transition: { duration: 0.15 } }}
      className="pointer-events-auto relative overflow-hidden rounded-control border border-card-border bg-surface-elevated p-4 shadow-modal text-text-primary text-sm"
    >
      <div className="flex items-center gap-3">
        {toast.type === "success" && <CheckCircle2 className="h-5 w-5 text-success flex-shrink-0" />}
        {toast.type === "error" && <AlertCircle className="h-5 w-5 text-danger flex-shrink-0" />}
        {toast.type === "undo" && <RotateCcw className="h-5 w-5 text-brand-indigo flex-shrink-0" />}

        <div className="flex-1 font-medium">{sanitize(toast.message)}</div>

        {toast.undoAction && (
          <button
            onClick={() => {
              toast.undoAction?.();
              onDismiss();
            }}
            className="rounded-control bg-brand-indigo px-2.5 py-1 text-xs font-semibold text-white hover:bg-brand-indigo/90 transition-colors"
          >
            Undo
          </button>
        )}

        <button onClick={onDismiss} className="text-text-secondary hover:text-text-primary">
          <X className="h-4 w-4" />
        </button>
      </div>

      {toast.type === "undo" && (
        <div className="absolute bottom-0 left-0 right-0 h-1 bg-surface-subtle">
          <div
            className="h-full bg-brand-indigo transition-all ease-linear"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </motion.div>
  );
};
