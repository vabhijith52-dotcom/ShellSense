import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Terminal, ArrowRight } from "lucide-react";
import { modalBackdropVariants, modalPanelVariants } from "@/lib/motion";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectCommand: (cmd: string) => void;
}

const QUICK_COMMANDS = [
  "Show my system usage",
  "Show my RAM usage",
  "Show CPU usage",
  "Show disk usage",
  "Find large files",
  "Delete temporary files",
  "List running processes",
  "Find duplicate files",
];

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onSelectCommand,
}) => {
  const [query, setQuery] = useState("");

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        if (isOpen) onClose();
      }
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const filtered = QUICK_COMMANDS.filter((c) =>
    c.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 p-4">
          <motion.div
            variants={modalBackdropVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            onClick={onClose}
            className="fixed inset-0 bg-slate-950/50 backdrop-blur-sm"
          />

          <motion.div
            variants={modalPanelVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            className="relative z-10 w-full max-w-xl rounded-card border border-card-border bg-surface-elevated shadow-modal overflow-hidden text-text-primary"
          >
            <div className="flex items-center gap-3 border-b border-card-border px-4 py-3">
              <Search className="h-4 w-4 text-text-muted" />
              <input
                autoFocus
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && query.trim()) {
                    onSelectCommand(query.trim());
                    onClose();
                  }
                }}
                placeholder="Type a command or natural language request..."
                className="flex-1 bg-transparent text-sm placeholder:text-text-muted focus:outline-none"
              />
              <span className="rounded bg-surface-subtle px-1.5 py-0.5 text-[10px] font-mono text-text-muted">
                ESC
              </span>
            </div>

            <div className="max-h-72 overflow-y-auto p-2 space-y-1">
              {filtered.map((cmd) => (
                <button
                  key={cmd}
                  onClick={() => {
                    onSelectCommand(cmd);
                    onClose();
                  }}
                  className="flex w-full items-center justify-between rounded-control px-3 py-2 text-xs font-medium text-text-secondary hover:bg-brand-indigo/10 hover:text-brand-indigo transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <Terminal className="h-3.5 w-3.5" />
                    <span>{cmd}</span>
                  </span>
                  <ArrowRight className="h-3.5 w-3.5 opacity-60" />
                </button>
              ))}

              {query && !filtered.includes(query) && (
                <button
                  onClick={() => {
                    onSelectCommand(query);
                    onClose();
                  }}
                  className="flex w-full items-center justify-between rounded-control px-3 py-2 text-xs font-semibold text-brand-indigo bg-brand-indigo/5 hover:bg-brand-indigo/10 transition-colors"
                >
                  <span>Ask ShellSense: "{query}"</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
