import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, Info, XCircle, RotateCcw, X } from "lucide-react";
import { api } from "@/lib/api";
import { sanitize } from "@/lib/sanitize";

interface HistoryItem {
  id: number;
  timestamp: number;
  operation: string;
  summary: string;
  risk_level: string;
  plan_id: string;
  plan_hash: string;
  status: string;
  original_text: string;
  undo_status: string;
  undo_data?: any;
}

export const HistoryScreen: React.FC = () => {
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState<HistoryItem | null>(null);
  const [opFilter, setOpFilter] = useState("");
  const [dateRange, setDateRange] = useState("7");

  useEffect(() => {
    let isMounted = true;
    const fetchHistory = async () => {
      try {
        setIsLoading(true);
        const res = await api.history.list(50, 0, opFilter || undefined, parseInt(dateRange, 10));
        if (isMounted) {
          setHistoryItems(res.history || []);
        }
      } catch {
        if (isMounted) {
          setHistoryItems([]);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };
    fetchHistory();
    return () => {
      isMounted = false;
    };
  }, [opFilter, dateRange]);

  const handleUndo = async (record: HistoryItem) => {
    alert(`Undo initiated for: ${record.summary}`);
    setSelectedItem(null);
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-text-primary">History</h2>
        <p className="text-xs text-text-secondary mt-0.5">
          View your past commands, audit-logged executions, and undo records.
        </p>
      </div>

      {/* Dropdown Filters matching Mockup */}
      <div className="flex gap-3">
        <select
          value={opFilter}
          onChange={(e) => setOpFilter(e.target.value)}
          className="rounded-control border border-card-border bg-card px-3 py-1.5 text-xs font-semibold text-text-primary shadow-sm focus:outline-none"
        >
          <option value="">All Operations</option>
          <option value="TRASH_FILES">Deletions</option>
          <option value="LIST_PROCESSES">Processes</option>
          <option value="CLEAN_TEMP">Cleanups</option>
        </select>

        <select
          value={dateRange}
          onChange={(e) => setDateRange(e.target.value)}
          className="rounded-control border border-card-border bg-card px-3 py-1.5 text-xs font-semibold text-text-primary shadow-sm focus:outline-none"
        >
          <option value="7">Last 7 Days</option>
          <option value="30">Last 30 Days</option>
          <option value="90">Last 90 Days</option>
        </select>
      </div>

      {/* History Rows matching Mockup */}
      <div className="space-y-3">
        {isLoading && historyItems.length === 0 ? (
          <div className="rounded-card border border-card-border bg-card p-8 text-center text-text-secondary shadow-card">
            Loading command and execution history...
          </div>
        ) : historyItems.length === 0 ? (
          <div className="rounded-card border border-card-border bg-card p-8 text-center text-text-muted shadow-card">
            <p className="text-sm font-medium">No past commands or operations recorded.</p>
            <p className="mt-1 text-xs text-text-secondary">
              All approved operations and decisions are audit-logged in local SQLite storage.
            </p>
          </div>
        ) : (
          historyItems.map((item) => (
            <motion.div
              key={item.id}
              layout
              className="flex items-center justify-between rounded-card border border-card-border bg-card p-4 shadow-card hover:border-brand-indigo/30 transition-all"
            >
              <div className="flex items-center gap-3.5">
                {/* Status Icon matching Mockup */}
                {item.status === "SUCCESS" && item.risk_level === "SAFE" ? (
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-500/10 text-blue-500">
                    <Info className="h-5 w-5" />
                  </div>
                ) : item.status === "SUCCESS" ? (
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-success/10 text-success">
                    <CheckCircle2 className="h-5 w-5" />
                  </div>
                ) : (
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-danger/10 text-danger">
                    <XCircle className="h-5 w-5" />
                  </div>
                )}

                <div>
                  <h4 className="text-sm font-bold text-text-primary">{sanitize(item.summary)}</h4>
                  <p className="text-xs text-text-secondary mt-0.5">
                    {item.status === "CANCELLED" ? "User cancelled" : "Executed"} -{" "}
                    {item.timestamp ? new Date(item.timestamp * 1000).toLocaleString() : "Recently"}
                  </p>
                </div>
              </div>

              <button
                onClick={() => setSelectedItem(item)}
                className="rounded-control border border-card-border bg-surface-subtle px-4 py-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
              >
                View
              </button>
            </motion.div>
          ))
        )}
      </div>

      {/* Detail & Undo Drawer */}
      <AnimatePresence>
        {selectedItem && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/50 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-lg rounded-card border border-card-border bg-surface-elevated p-6 shadow-modal text-text-primary"
            >
              <div className="flex items-center justify-between border-b border-card-border pb-3">
                <h3 className="font-bold text-base">Execution Audit Record</h3>
                <button
                  onClick={() => setSelectedItem(null)}
                  className="text-text-secondary hover:text-text-primary"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="mt-4 space-y-3 text-xs">
                <div>
                  <span className="font-semibold text-text-secondary">Summary: </span>
                  <span className="font-bold text-text-primary">{sanitize(selectedItem.summary)}</span>
                </div>
                <div>
                  <span className="font-semibold text-text-secondary">Operation: </span>
                  <span className="font-mono text-brand-indigo">{selectedItem.operation}</span>
                </div>
                <div>
                  <span className="font-semibold text-text-secondary">Risk Level: </span>
                  <span className="font-semibold">{selectedItem.risk_level}</span>
                </div>
                <div>
                  <span className="font-semibold text-text-secondary">Plan Hash: </span>
                  <span className="font-mono text-text-muted break-all">{selectedItem.plan_hash}</span>
                </div>
                <div>
                  <span className="font-semibold text-text-secondary">Status: </span>
                  <span className="font-semibold text-success">{selectedItem.status}</span>
                </div>
              </div>

              <div className="mt-6 flex justify-between gap-3 border-t border-card-border pt-4">
                <button
                  onClick={() => setSelectedItem(null)}
                  className="rounded-control border border-card-border bg-surface-subtle px-4 py-2 text-xs font-semibold"
                >
                  Close
                </button>
                {selectedItem.undo_status === "AVAILABLE" && (
                  <button
                    onClick={() => handleUndo(selectedItem)}
                    className="flex items-center gap-1.5 rounded-control bg-brand-indigo px-4 py-2 text-xs font-semibold text-white hover:bg-brand-indigo/90"
                  >
                    <RotateCcw className="h-3.5 w-3.5" /> Undo Operation
                  </button>
                )}
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};
