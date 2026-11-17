import React, { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Trash2, AlertTriangle, X } from "lucide-react";
import {
  modalBackdropVariants,
  modalPanelVariants,
} from "@/lib/motion";
import { sanitize } from "@/lib/sanitize";

export interface ModalTargetItem {
  name: string;
  size?: string;
  path?: string;
}

export interface ConfirmationModalProps {
  isOpen: boolean;
  title: string;
  subtitle: string;
  consequences: string;
  items: ModalTargetItem[];
  totalSize?: string;
  riskLevel: "MODIFY" | "DESTRUCTIVE";
  expectedToken?: string | null;
  confirmButtonLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmationModal: React.FC<ConfirmationModalProps> = ({
  isOpen,
  title,
  subtitle,
  consequences,
  items,
  totalSize,
  riskLevel,
  expectedToken,
  confirmButtonLabel = "Confirm",
  onConfirm,
  onCancel,
}) => {
  const [typedToken, setTypedToken] = useState("");
  const [isArmed, setIsArmed] = useState(false);
  const cancelButtonRef = useRef<HTMLButtonElement>(null);

  // Focus cancel button on mount (Invariant: Cancel is default focused)
  useEffect(() => {
    if (isOpen) {
      setTypedToken("");
      setIsArmed(false);
      // 1-second arming delay for destructive operations
      const timer = setTimeout(() => setIsArmed(true), 800);
      setTimeout(() => cancelButtonRef.current?.focus(), 50);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  // Handle ESC key to cancel
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onCancel();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onCancel]);

  const isDestructive = riskLevel === "DESTRUCTIVE";
  const tokenMatches = !expectedToken || typedToken.trim() === expectedToken.trim();
  const canConfirm = !isDestructive || (isArmed && tokenMatches);

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop with blur */}
          <motion.div
            variants={modalBackdropVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            onClick={onCancel}
            className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm"
          />

          {/* Modal Card matching mockup */}
          <motion.div
            variants={modalPanelVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            className="relative z-10 w-full max-w-md rounded-card border border-card-border bg-surface-elevated p-6 shadow-modal text-text-primary"
          >
            {/* Close button */}
            <button
              onClick={onCancel}
              className="absolute right-4 top-4 text-text-secondary hover:text-text-primary transition-colors"
              aria-label="Close modal"
            >
              <X className="h-5 w-5" />
            </button>

            {/* Icon Header */}
            <div className="flex flex-col items-center text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-danger/10 text-danger mb-4">
                {isDestructive ? (
                  <Trash2 className="h-7 w-7" />
                ) : (
                  <AlertTriangle className="h-7 w-7 text-warning" />
                )}
              </div>
              <h3 className="text-xl font-bold tracking-tight">{sanitize(title)}</h3>
              <p className="mt-1 text-sm text-text-secondary">{sanitize(subtitle)}</p>
              <p className="mt-2 text-xs text-text-muted bg-surface-subtle p-2 rounded-control w-full">
                {sanitize(consequences)}
              </p>
            </div>

            {/* Target List (Mockup layout) */}
            <div className="mt-5 max-h-48 overflow-y-auto space-y-2 rounded-control border border-card-border bg-surface-subtle/50 p-3 text-xs">
              {items.map((item, idx) => (
                <div key={idx} className="flex items-center justify-between py-1 border-b border-card-border/50 last:border-b-0">
                  <span className="font-mono text-text-primary truncate max-w-[240px]">
                    {sanitize(item.name)}
                  </span>
                  {item.size && (
                    <span className="text-text-secondary font-medium ml-2">{sanitize(item.size)}</span>
                  )}
                </div>
              ))}
            </div>

            {totalSize && (
              <div className="mt-3 text-right text-xs font-semibold text-text-secondary">
                Total Size: <span className="text-text-primary">{sanitize(totalSize)}</span>
              </div>
            )}

            {/* Typed Token Input for DESTRUCTIVE actions */}
            {isDestructive && expectedToken && (
              <div className="mt-4 space-y-1.5">
                <label className="block text-xs font-medium text-text-secondary">
                  Type <span className="font-mono font-bold text-danger">{sanitize(expectedToken)}</span> to confirm:
                </label>
                <input
                  type="text"
                  value={typedToken}
                  onChange={(e) => setTypedToken(e.target.value)}
                  placeholder={expectedToken}
                  className="w-full rounded-control border border-card-border bg-surface-subtle px-3 py-2 text-sm font-mono focus:border-danger focus:outline-none focus:ring-1 focus:ring-danger"
                />
              </div>
            )}

            {/* Action Buttons */}
            <div className="mt-6 flex gap-3">
              <button
                ref={cancelButtonRef}
                onClick={onCancel}
                className="flex-1 rounded-control border border-card-border bg-surface-subtle py-2.5 text-sm font-semibold text-text-primary hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
              >
                Cancel
              </button>
              <button
                disabled={!canConfirm}
                onClick={onConfirm}
                className={`flex-1 rounded-control py-2.5 text-sm font-semibold text-white shadow-sm transition-all ${
                  canConfirm
                    ? isDestructive
                      ? "bg-danger hover:bg-danger/90 active:scale-95"
                      : "bg-brand-indigo hover:bg-brand-indigo/90 active:scale-95"
                    : "bg-slate-400 cursor-not-allowed opacity-50"
                }`}
              >
                {confirmButtonLabel}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
