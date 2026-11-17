import React, { useState, useEffect } from "react";
import {
  ShieldCheck,
  Cpu,
  Palette,
  Info,
  Sliders,
  Lock,
  AlertTriangle,
} from "lucide-react";
import { api } from "@/lib/api";

export const SettingsScreen: React.FC<{
  currentTheme: "light" | "dark";
  onToggleTheme: () => void;
  onReopenConsent: () => void;
}> = ({ currentTheme, onToggleTheme, onReopenConsent }) => {
  const [activeTab, setActiveTab] = useState<
    "general" | "safety" | "execution" | "appearance" | "about"
  >("general");

  const [nlSuggestions, setNlSuggestions] = useState(true);
  const [saveHistory, setSaveHistory] = useState(true);
  const [notifications, setNotifications] = useState(true);
  const [language, setLanguage] = useState("English");
  const [reducedMotion, setReducedMotion] = useState(false);

  const [grantInfo, setGrantInfo] = useState<any>({
    is_locked: false,
    capabilities: [
      "SYSTEM_INFO_READ",
      "FILES_READ",
      "FILES_MODIFY",
      "FILES_TRASH",
      "PROCESS_TERMINATE",
      "TASKS_BACKGROUND",
    ],
    folder_roots: ["~/Downloads", "~/Documents", "~/Desktop"],
  });

  useEffect(() => {
    const fetchPerms = async () => {
      try {
        const res = await api.permissions.get();
        setGrantInfo(res);
      } catch {
        // fallback
      }
    };
    fetchPerms();
  }, []);

  const handleRevoke = async () => {
    if (confirm("Are you sure you want to revoke all capabilities? ShellSense will become locked.")) {
      try {
        await api.permissions.revoke();
        onReopenConsent();
      } catch (err: any) {
        alert(err.message);
      }
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-text-primary">Settings</h2>
        <p className="text-xs text-text-secondary mt-0.5">
          Customize ShellSense for your workflow and review capability boundaries.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {/* Settings Navigation Tabs matching Mockup */}
        <div className="space-y-1">
          {[
            { id: "general", label: "General", icon: Sliders },
            { id: "safety", label: "Safety & Permissions", icon: ShieldCheck },
            { id: "execution", label: "Execution", icon: Cpu },
            { id: "appearance", label: "Appearance", icon: Palette },
            { id: "about", label: "About", icon: Info },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex w-full items-center gap-3 rounded-control px-3.5 py-2.5 text-xs font-semibold transition-colors ${
                  isActive
                    ? "bg-brand-indigo/10 text-brand-indigo border border-brand-indigo/20 font-bold"
                    : "text-text-secondary hover:text-text-primary hover:bg-black/5 dark:hover:bg-white/5"
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Tab Content Panel */}
        <div className="md:col-span-3 rounded-card border border-card-border bg-card p-6 shadow-card space-y-6">
          {activeTab === "general" && (
            <div className="space-y-5">
              <h3 className="text-base font-bold text-text-primary">General Settings</h3>

              {/* Read-only OS mode matching Mockup and Invariant 15 */}
              <div className="flex items-center justify-between py-2 border-b border-card-border/50 text-xs">
                <div>
                  <div className="font-semibold text-text-primary">Default Operating System Mode</div>
                  <div className="text-text-secondary mt-0.5">Host operating system automatically detected.</div>
                </div>
                <div className="font-mono bg-surface-subtle border border-card-border px-3 py-1 rounded-control text-text-secondary font-medium">
                  Auto (This System)
                </div>
              </div>

              {/* Natural Language Suggestions Toggle */}
              <div className="flex items-center justify-between py-2 border-b border-card-border/50 text-xs">
                <div>
                  <div className="font-semibold text-text-primary">Enable natural language suggestions</div>
                  <div className="text-text-secondary mt-0.5">Show helpful prompt chips on the chat home screen.</div>
                </div>
                <input
                  type="checkbox"
                  checked={nlSuggestions}
                  onChange={(e) => setNlSuggestions(e.target.checked)}
                  className="h-4 w-4 rounded text-brand-indigo focus:ring-brand-indigo"
                />
              </div>

              {/* Save command history */}
              <div className="flex items-center justify-between py-2 border-b border-card-border/50 text-xs">
                <div>
                  <div className="font-semibold text-text-primary">Save command history</div>
                  <div className="text-text-secondary mt-0.5">Maintain audit-logged executions in local SQLite database.</div>
                </div>
                <input
                  type="checkbox"
                  checked={saveHistory}
                  onChange={(e) => setSaveHistory(e.target.checked)}
                  className="h-4 w-4 rounded text-brand-indigo focus:ring-brand-indigo"
                />
              </div>

              {/* Locked Always-On Confirmation on Sensitive Actions (Invariant 15) */}
              <div className="flex items-center justify-between py-2 border-b border-card-border/50 text-xs bg-brand-indigo/5 p-3 rounded-control border border-brand-indigo/20">
                <div>
                  <div className="font-semibold text-text-primary flex items-center gap-1.5">
                    <Lock className="h-3.5 w-3.5 text-brand-indigo" />
                    Ask for confirmation on sensitive actions
                  </div>
                  <div className="text-text-secondary mt-0.5">
                    Permanently enabled (Invariant 15). Sensitive operations (delete, modify, kill) always require explicit approval.
                  </div>
                </div>
                <span className="font-bold text-brand-indigo text-xs">ALWAYS ON</span>
              </div>

              {/* Notifications */}
              <div className="flex items-center justify-between py-2 border-b border-card-border/50 text-xs">
                <div>
                  <div className="font-semibold text-text-primary">Enable desktop notifications</div>
                  <div className="text-text-secondary mt-0.5">Notify when background scans and archives complete.</div>
                </div>
                <input
                  type="checkbox"
                  checked={notifications}
                  onChange={(e) => setNotifications(e.target.checked)}
                  className="h-4 w-4 rounded text-brand-indigo focus:ring-brand-indigo"
                />
              </div>

              {/* Language */}
              <div className="flex items-center justify-between py-2 text-xs">
                <div>
                  <div className="font-semibold text-text-primary">Language</div>
                  <div className="text-text-secondary mt-0.5">Assistant language interface.</div>
                </div>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="rounded-control border border-card-border bg-surface-subtle px-3 py-1 text-xs"
                >
                  <option value="English">English</option>
                </select>
              </div>
            </div>
          )}

          {activeTab === "safety" && (
            <div className="space-y-5">
              <h3 className="text-base font-bold text-text-primary">Safety & Capability Grants</h3>
              <p className="text-xs text-text-secondary">
                ShellSense enforces a locked-by-default architecture outside this git repository.
              </p>

              <div className="space-y-3 text-xs">
                <div className="font-semibold text-text-primary">Active Capabilities:</div>
                <div className="flex flex-wrap gap-1.5">
                  {grantInfo.capabilities?.map((cap: string) => (
                    <span
                      key={cap}
                      className="rounded-pill bg-brand-indigo/10 border border-brand-indigo/20 px-2.5 py-1 font-mono text-[11px] text-brand-indigo"
                    >
                      {cap}
                    </span>
                  ))}
                </div>
              </div>

              <div className="space-y-3 text-xs">
                <div className="font-semibold text-text-primary">Granted Folder Roots:</div>
                <div className="space-y-1">
                  {grantInfo.folder_roots?.map((root: string) => (
                    <div
                      key={root}
                      className="font-mono text-text-secondary bg-surface-subtle p-2 rounded-control border border-card-border"
                    >
                      {root}
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-4 flex gap-3 border-t border-card-border">
                <button
                  onClick={onReopenConsent}
                  className="rounded-control border border-card-border bg-surface-subtle px-4 py-2 text-xs font-semibold hover:bg-black/5 dark:hover:bg-white/5"
                >
                  Re-run Setup Wizard
                </button>
                <button
                  onClick={handleRevoke}
                  className="rounded-control border border-danger/30 bg-danger/10 px-4 py-2 text-xs font-semibold text-danger hover:bg-danger/20"
                >
                  Revoke All Access
                </button>
              </div>
            </div>
          )}

          {activeTab === "execution" && (
            <div className="space-y-5 text-xs">
              <h3 className="text-base font-bold text-text-primary">Execution Policies</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between py-2 border-b border-card-border/50">
                  <div>
                    <div className="font-semibold text-text-primary">Plan Expiry Timeout</div>
                    <div className="text-text-secondary mt-0.5">Generated plans automatically expire after this duration.</div>
                  </div>
                  <span className="font-mono text-text-primary font-bold">120 seconds</span>
                </div>
                <div className="flex items-center justify-between py-2 border-b border-card-border/50">
                  <div>
                    <div className="font-semibold text-text-primary">Max Bulk Item Limit</div>
                    <div className="text-text-secondary mt-0.5">Maximum number of items permitted in a single plan.</div>
                  </div>
                  <span className="font-mono text-text-primary font-bold">100 items</span>
                </div>
                <div className="flex items-center justify-between py-2">
                  <div>
                    <div className="font-semibold text-text-primary">Background Task Concurrency</div>
                    <div className="text-text-secondary mt-0.5">Maximum simultaneous background worker threads.</div>
                  </div>
                  <span className="font-mono text-text-primary font-bold">2 workers</span>
                </div>
              </div>
            </div>
          )}

          {activeTab === "appearance" && (
            <div className="space-y-5 text-xs">
              <h3 className="text-base font-bold text-text-primary">Appearance & Motion</h3>
              <div className="flex items-center justify-between py-2 border-b border-card-border/50">
                <div>
                  <div className="font-semibold text-text-primary">Color Theme</div>
                  <div className="text-text-secondary mt-0.5">Switch between Light and Dark interface.</div>
                </div>
                <button
                  onClick={onToggleTheme}
                  className="rounded-control border border-card-border bg-surface-subtle px-4 py-1.5 font-semibold text-text-primary capitalize"
                >
                  {currentTheme} Mode
                </button>
              </div>

              <div className="flex items-center justify-between py-2">
                <div>
                  <div className="font-semibold text-text-primary">Reduced Motion Mode</div>
                  <div className="text-text-secondary mt-0.5">
                    Section 17: Replace movement with opacity-only transitions and stop continuous loops.
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={reducedMotion}
                  onChange={(e) => setReducedMotion(e.target.checked)}
                  className="h-4 w-4 rounded text-brand-indigo focus:ring-brand-indigo"
                />
              </div>
            </div>
          )}

          {activeTab === "about" && (
            <div className="space-y-4 text-xs">
              <h3 className="text-base font-bold text-text-primary">About ShellSense</h3>
              <div className="flex items-center gap-2">
                <span className="font-bold text-text-primary">Version:</span>
                <span className="font-mono text-brand-indigo">0.1.0-master-prompt-v2</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-text-primary">License:</span>
                <span>MIT License (Open Source)</span>
              </div>

              {/* Mandatory Honest Limit Statement (Section 9 & 21) */}
              <div className="rounded-control border border-amber-500/30 bg-amber-500/10 p-4 text-text-primary space-y-2 mt-4">
                <div className="font-bold flex items-center gap-1.5 text-amber-600 dark:text-amber-400">
                  <AlertTriangle className="h-4 w-4" />
                  Honest Security Boundary Statement
                </div>
                <p className="text-[11px] leading-relaxed text-text-secondary">
                  ShellSense is open-source software. Anyone who inspects or modifies the source code
                  can alter or bypass internal safety checks. Therefore, consent and capability gates
                  are guardrails for honest use, accidents, and prompt injection defense—not an OS security sandbox.
                  ShellSense operates strictly with the user's local privileges and refuses elevation. For untrusted
                  automation, run inside bubblewrap/firejail on Linux or Windows Sandbox.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
