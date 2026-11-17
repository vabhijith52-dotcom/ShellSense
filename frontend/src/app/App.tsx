import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquare,
  Layers,
  BarChart2,
  Folder,
  Cpu,
  Clock,
  Settings as SettingsIcon,
  Sun,
  Moon,
  Terminal,
  Monitor,
  Search,
} from "lucide-react";
import { MOTION_SPRINGS, pageTransitionVariants } from "@/lib/motion";
import { api, initApiClient } from "@/lib/api";
import { ToastContainer, ToastMessage } from "@/components/Toast";
import { CommandPalette } from "@/components/CommandPalette";
import { ConsentWizard } from "@/features/consent/ConsentWizard";
import { ChatScreen } from "@/features/chat/ChatScreen";
import { TasksScreen } from "@/features/tasks/TasksScreen";
import { MonitorScreen } from "@/features/monitor/MonitorScreen";
import { FilesScreen } from "@/features/files/FilesScreen";
import { ProcessScreen } from "@/features/processes/ProcessScreen";
import { HistoryScreen } from "@/features/history/HistoryScreen";
import { SettingsScreen } from "@/features/settings/SettingsScreen";

type NavTab =
  | "chat"
  | "tasks"
  | "monitor"
  | "files"
  | "processes"
  | "history"
  | "settings";

interface NavItem {
  id: NavTab;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const NAV_ITEMS: readonly NavItem[] = [
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "tasks", label: "Tasks", icon: Layers },
  { id: "monitor", label: "System Monitor", icon: BarChart2 },
  { id: "files", label: "File Operations", icon: Folder },
  { id: "processes", label: "Process Manager", icon: Cpu },
  { id: "history", label: "History", icon: Clock },
  { id: "settings", label: "Settings", icon: SettingsIcon },
] as const;

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<NavTab>("chat");
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [, setIsLocked] = useState(false);
  const [showWizard, setShowWizard] = useState(false);
  const [isPaletteOpen, setIsPaletteOpen] = useState(false);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [detectedOS, setDetectedOS] = useState("Auto (This System)");
  const [username, setUsername] = useState<string>("");

  useEffect(() => {
    // Check lock status and load system info
    const checkLock = async () => {
      try {
        await initApiClient();
        const perms = await api.permissions.get();
        if (perms.is_locked) {
          setIsLocked(true);
          setShowWizard(true);
        }
        const sys = await api.system.getInfo();
        if (sys.os?.display_name) {
          setDetectedOS(sys.os.display_name);
        }
        if (sys.user) {
          setUsername(sys.user);
        }
      } catch {
        // keep defaults in dev
      }
    };
    checkLock();

    // Global Ctrl+K listener
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setIsPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
      root.setAttribute("data-theme", "dark");
    } else {
      root.classList.remove("dark");
      root.setAttribute("data-theme", "light");
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  };

  const addToast = (msg: Omit<ToastMessage, "id">) => {
    const newToast: ToastMessage = { ...msg, id: Date.now().toString() };
    setToasts((prev) => [...prev, newToast]);
  };

  const dismissToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-page text-text-primary">
      {/* Sidebar matching Mockup */}
      <aside className="w-64 flex-shrink-0 flex flex-col justify-between p-4 border-r border-card-border bg-card/60 backdrop-blur-xl">
        <div className="space-y-6">
          {/* Logo Header */}
          <div className="flex items-center gap-3 px-2 py-1">
            <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-brand-indigo to-brand-violet text-white shadow-md">
              <Terminal className="h-5 w-5" />
              <div className="absolute -inset-0.5 rounded-xl border border-white/20 pointer-events-none" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-text-primary">
                ShellSense
              </h1>
              <p className="text-xs text-text-secondary">
                Natural Language OS Assistant
              </p>
            </div>
          </div>

          {/* Navigation Links with animated shared-layout pill */}
          <nav className="space-y-1">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`relative flex w-full items-center gap-3 rounded-control px-3.5 py-2.5 text-sm font-medium transition-colors ${
                    isActive
                      ? "text-brand-indigo font-semibold dark:text-white"
                      : "text-text-secondary hover:text-text-primary hover:bg-black/5 dark:hover:bg-white/5"
                  }`}
                >
                  {isActive && (
                    <motion.div
                      layoutId="active-nav-pill"
                      className="absolute inset-0 rounded-control bg-brand-indigo/10 border border-brand-indigo/20 dark:bg-brand-violet/20"
                      transition={MOTION_SPRINGS.layout}
                    />
                  )}
                  <Icon className="relative z-10 h-4 w-4" />
                  <span className="relative z-10">{item.label}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Bottom OS Status Card (Display-only per Invariant 15) */}
        <div className="rounded-control border border-card-border bg-surface-subtle/50 p-3 text-xs">
          <div className="flex items-center gap-2 font-medium">
            <span className="h-2 w-2 rounded-full bg-success animate-pulse" />
            <span className="text-text-primary truncate">{detectedOS}</span>
          </div>
          <p className="mt-1 text-[11px] text-text-secondary">
            Cross-platform (Linux & Windows)
          </p>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top Header Bar */}
        <header className="flex h-16 items-center justify-between border-b border-card-border px-8 bg-card/40 backdrop-blur-md">
          {/* Quick Search Shortcut */}
          <button
            onClick={() => setIsPaletteOpen(true)}
            className="flex items-center gap-2 rounded-pill border border-card-border bg-card px-3 py-1.5 text-xs text-text-muted hover:border-brand-indigo/40 hover:text-text-primary transition-all"
          >
            <Search className="h-3.5 w-3.5 text-brand-indigo" />
            <span>Search or ask anything...</span>
            <kbd className="ml-2 rounded bg-surface-subtle px-1.5 py-0.5 text-[10px] font-mono">
              Ctrl+K
            </kbd>
          </button>

          <div className="flex items-center gap-4">
            {/* Display-only detected OS badge */}
            <div className="flex items-center gap-1.5 rounded-pill border border-card-border bg-card px-3 py-1 text-xs font-medium text-text-secondary">
              <Monitor className="h-3.5 w-3.5 text-brand-indigo" />
              <span>{detectedOS}</span>
            </div>

            {/* Light / Dark Mode Toggle */}
            <button
              onClick={toggleTheme}
              aria-label="Toggle theme"
              className="flex h-9 w-9 items-center justify-center rounded-pill border border-card-border bg-card text-text-secondary transition-colors hover:text-text-primary"
            >
              {theme === "light" ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
            </button>

            {/* User Avatar */}
            <div className="flex h-9 w-9 items-center justify-center rounded-pill bg-gradient-to-tr from-brand-indigo to-brand-violet text-sm font-semibold text-white shadow-sm">
              {username ? username.charAt(0).toUpperCase() : "U"}
            </div>
          </div>
        </header>

        {/* Screen Viewport with smooth transitions */}
        <main className="flex-1 overflow-y-auto p-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              variants={pageTransitionVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              className="h-full"
            >
              {activeTab === "chat" && <ChatScreen username={username} />}
              {activeTab === "tasks" && <TasksScreen />}
              {activeTab === "monitor" && <MonitorScreen />}
              {activeTab === "files" && <FilesScreen />}
              {activeTab === "processes" && <ProcessScreen />}
              {activeTab === "history" && <HistoryScreen />}
              {activeTab === "settings" && (
                <SettingsScreen
                  currentTheme={theme}
                  onToggleTheme={toggleTheme}
                  onReopenConsent={() => setShowWizard(true)}
                />
              )}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>

      {/* Global Command Palette */}
      <CommandPalette
        isOpen={isPaletteOpen}
        onClose={() => setIsPaletteOpen(false)}
        onSelectCommand={() => {
          setActiveTab("chat");
        }}
      />

      {/* Global Toast Notifications */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      {/* First-Run Setup Wizard */}
      {showWizard && (
        <ConsentWizard
          onGranted={() => {
            setIsLocked(false);
            setShowWizard(false);
            addToast({
              type: "success",
              message: "ShellSense capabilities successfully granted! Ready to use.",
            });
          }}
        />
      )}
    </div>
  );
};
