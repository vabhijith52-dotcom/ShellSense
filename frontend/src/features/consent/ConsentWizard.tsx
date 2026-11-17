import React, { useState } from "react";
import { motion } from "framer-motion";
import { ShieldAlert, FolderPlus, ArrowRight, Check } from "lucide-react";
import { api } from "@/lib/api";

const CAPABILITIES = [
  {
    id: "SYSTEM_INFO_READ",
    name: "System Hardware & Resource Monitoring",
    description: "Read CPU usage, RAM stats, disk capacity, and operating system info.",
  },
  {
    id: "FILES_READ",
    name: "File Inspection & Search",
    description: "List directory contents, scan for duplicates, and search files inside chosen folders.",
  },
  {
    id: "FILES_MODIFY",
    name: "File Creation & Organization",
    description: "Create folders, move, rename, copy, and create backup zip archives.",
  },
  {
    id: "FILES_TRASH",
    name: "Move Files to Trash",
    description: "Move files to desktop Trash / Recycle Bin with undo records. No permanent deletion.",
  },
  {
    id: "PROCESS_TERMINATE",
    name: "Process Control",
    description: "Terminate user-owned applications and unresponsive tasks with explicit confirmation.",
  },
  {
    id: "TASKS_BACKGROUND",
    name: "Background Automation",
    description: "Execute approved scans, duplicate checks, and cleanup tasks in the background.",
  },
] as const;

export const ConsentWizard: React.FC<{ onGranted: () => void }> = ({ onGranted }) => {
  const [selectedCaps, setSelectedCaps] = useState<string[]>([
    "SYSTEM_INFO_READ",
    "FILES_READ",
    "FILES_MODIFY",
    "FILES_TRASH",
    "PROCESS_TERMINATE",
    "TASKS_BACKGROUND",
  ]);
  const [folderRoots, setFolderRoots] = useState<string[]>([
    "~/Downloads",
    "~/Documents",
    "~/Desktop",
  ]);
  const [newRootInput, setNewRootInput] = useState("");
  const [typedPhrase, setTypedPhrase] = useState("");
  const [step, setStep] = useState<1 | 2>(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleCap = (id: string) => {
    setSelectedCaps((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
    );
  };

  const addFolderRoot = () => {
    if (newRootInput.trim() && !folderRoots.includes(newRootInput.trim())) {
      setFolderRoots([...folderRoots, newRootInput.trim()]);
      setNewRootInput("");
    }
  };

  const removeFolderRoot = (root: string) => {
    setFolderRoots(folderRoots.filter((r) => r !== root));
  };

  const handleSubmit = async () => {
    if (typedPhrase.trim() !== "I GRANT ACCESS") {
      setError("Please type exactly 'I GRANT ACCESS' to confirm.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      await api.permissions.grant({
        capabilities: selectedCaps,
        folder_roots: folderRoots,
        confirmation_phrase: typedPhrase.trim(),
        nonce: Date.now().toString(),
      });
      onGranted();
    } catch (err: any) {
      setError(err.message || "Failed to save capability grant.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-slate-950/70 backdrop-blur-md">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="w-full max-w-2xl rounded-card border border-card-border bg-surface-elevated p-8 shadow-modal text-text-primary"
      >
        {/* Header */}
        <div className="flex items-center gap-3 border-b border-card-border pb-5">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-indigo/10 text-brand-indigo">
            <ShieldAlert className="h-6 w-6" />
          </div>
          <div>
            <h2 className="text-xl font-bold tracking-tight">ShellSense Initial Setup & Capability Grant</h2>
            <p className="text-xs text-text-secondary">
              Locked by default. ShellSense requires your explicit permission before accessing the system.
            </p>
          </div>
        </div>

        {step === 1 ? (
          /* Step 1: Capabilities and Folder Selection */
          <div className="mt-6 space-y-6">
            <div>
              <h3 className="text-sm font-semibold text-text-primary mb-3">1. Select Capabilities to Grant</h3>
              <div className="grid grid-cols-1 gap-2.5 max-h-52 overflow-y-auto pr-1">
                {CAPABILITIES.map((cap) => {
                  const isChecked = selectedCaps.includes(cap.id);
                  return (
                    <div
                      key={cap.id}
                      onClick={() => toggleCap(cap.id)}
                      className={`flex items-start gap-3 p-3 rounded-control border cursor-pointer transition-colors ${
                        isChecked
                          ? "border-brand-indigo/30 bg-brand-indigo/5"
                          : "border-card-border bg-surface-subtle/50"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleCap(cap.id)}
                        className="mt-1 h-4 w-4 rounded text-brand-indigo focus:ring-brand-indigo"
                      />
                      <div>
                        <div className="text-xs font-semibold text-text-primary">{cap.name}</div>
                        <div className="text-[11px] text-text-secondary mt-0.5">{cap.description}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-text-primary mb-2">2. Scoped Folder Roots (Allowed Directories)</h3>
              <p className="text-xs text-text-secondary mb-2">
                ShellSense cannot touch files outside these explicitly granted folders.
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newRootInput}
                  onChange={(e) => setNewRootInput(e.target.value)}
                  placeholder="e.g. ~/Projects"
                  className="flex-1 rounded-control border border-card-border bg-surface-subtle px-3 py-1.5 text-xs font-mono"
                />
                <button
                  onClick={addFolderRoot}
                  className="flex items-center gap-1 rounded-control bg-surface-subtle px-3 py-1.5 text-xs font-semibold hover:bg-black/5 dark:hover:bg-white/5 border border-card-border"
                >
                  <FolderPlus className="h-3.5 w-3.5" /> Add
                </button>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {folderRoots.map((root) => (
                  <span
                    key={root}
                    className="inline-flex items-center gap-1 rounded-pill bg-brand-indigo/10 px-2.5 py-1 text-xs font-mono text-brand-indigo border border-brand-indigo/20"
                  >
                    {root}
                    <button
                      onClick={() => removeFolderRoot(root)}
                      className="hover:text-danger ml-1"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            </div>

            <div className="flex justify-end pt-4 border-t border-card-border">
              <button
                disabled={selectedCaps.length === 0}
                onClick={() => setStep(2)}
                className="flex items-center gap-2 rounded-control bg-brand-indigo px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-brand-indigo/90 transition-colors disabled:opacity-50"
              >
                Review & Confirm <ArrowRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        ) : (
          /* Step 2: Typed Human Confirmation */
          <div className="mt-6 space-y-6">
            <div className="rounded-control border border-card-border bg-surface-subtle p-4 text-xs space-y-2">
              <div className="font-semibold text-text-primary">Summary of Human Access Grant:</div>
              <div>Capabilities: <span className="font-mono text-brand-indigo">{selectedCaps.join(", ")}</span></div>
              <div>Permitted Roots: <span className="font-mono text-brand-indigo">{folderRoots.join(", ")}</span></div>
              <div className="text-text-muted mt-2">
                This grant will be written with owner-only permissions (0o600) on your local user profile.
                Sensitive actions will always still require explicit approval.
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-medium text-text-secondary">
                To confirm this grant, type <span className="font-mono font-bold text-brand-indigo">I GRANT ACCESS</span> below:
              </label>
              <input
                type="text"
                value={typedPhrase}
                onChange={(e) => setTypedPhrase(e.target.value)}
                placeholder="I GRANT ACCESS"
                className="w-full rounded-control border border-card-border bg-surface-subtle px-3 py-2 text-sm font-mono focus:border-brand-indigo focus:outline-none focus:ring-1 focus:ring-brand-indigo"
              />
            </div>

            {error && <div className="text-xs text-danger font-medium">{error}</div>}

            <div className="flex justify-between items-center pt-4 border-t border-card-border">
              <button
                onClick={() => setStep(1)}
                className="rounded-control border border-card-border px-4 py-2 text-xs font-semibold text-text-secondary hover:text-text-primary"
              >
                Back
              </button>
              <button
                disabled={typedPhrase.trim() !== "I GRANT ACCESS" || isSubmitting}
                onClick={handleSubmit}
                className="flex items-center gap-2 rounded-control bg-success px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-success/90 transition-colors disabled:opacity-50"
              >
                <Check className="h-4 w-4" />
                {isSubmitting ? "Activating..." : "Confirm & Launch ShellSense"}
              </button>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
};
