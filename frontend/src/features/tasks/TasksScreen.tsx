import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  ArrowLeft,
  Plus,
} from "lucide-react";
import { api } from "@/lib/api";
import { sanitize } from "@/lib/sanitize";

interface TaskItem {
  task_id: string;
  name: string;
  target_summary: string;
  status: "queued" | "running" | "paused" | "completed" | "failed" | "cancelled";
  progress_percent: number;
  elapsed_seconds: number;
  files_scanned?: number;
  items_found?: number;
}

export const TasksScreen: React.FC = () => {
  const [selectedTask, setSelectedTask] = useState<TaskItem | null>(null);
  const [taskLogs, setTaskLogs] = useState<string[]>([]);
  const [filterTab, setFilterTab] = useState<"all" | "running" | "queued" | "completed">("all");
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Fetch real task list from backend
  useEffect(() => {
    let isMounted = true;
    const fetchTasks = async () => {
      try {
        const res = await api.tasks.list();
        if (isMounted) {
          setTasks(res.tasks || []);
        }
      } catch {
        if (isMounted) {
          setTasks([]);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };
    fetchTasks();
    const interval = setInterval(fetchTasks, 2000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // Poll live logs when a task is open
  useEffect(() => {
    if (!selectedTask) return;
    let isMounted = true;
    const fetchLogs = async () => {
      try {
        const res = await api.tasks.get(selectedTask.task_id);
        if (isMounted && res.logs) {
          setTaskLogs(res.logs);
        }
      } catch {
        if (isMounted) {
          setTaskLogs([`Waiting for task log output...`]);
        }
      }
    };
    fetchLogs();
    const interval = setInterval(fetchLogs, 1500);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [selectedTask]);

  const handleCancel = async (taskId: string) => {
    try {
      await api.tasks.cancel(taskId);
      setTasks((prev) =>
        prev.map((t) => (t.task_id === taskId ? { ...t, status: "cancelled" } : t))
      );
      if (selectedTask?.task_id === taskId) {
        setSelectedTask((prev) => (prev ? { ...prev, status: "cancelled" } : null));
      }
    } catch {
      // ignore
    }
  };

  const filteredTasks = tasks.filter((t) => {
    if (filterTab === "running") return t.status === "running";
    if (filterTab === "queued") return t.status === "queued";
    if (filterTab === "completed") return t.status === "completed";
    return true;
  });

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* View 2: Task Running Detail Screen (matching Mockup) */}
      {selectedTask ? (
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          className="space-y-6"
        >
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSelectedTask(null)}
                className="flex h-9 w-9 items-center justify-center rounded-control border border-card-border bg-card text-text-secondary hover:text-text-primary transition-colors"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
              <div>
                <h2 className="text-xl font-bold tracking-tight text-text-primary">
                  {sanitize(selectedTask.name)}
                </h2>
                <p className="text-xs text-text-secondary font-mono">{sanitize(selectedTask.target_summary)}</p>
              </div>
            </div>

            <div className="flex items-center gap-2 rounded-pill bg-brand-indigo/10 border border-brand-indigo/20 px-3 py-1 text-xs font-semibold text-brand-indigo">
              <span className="capitalize">{selectedTask.status}</span> - {selectedTask.progress_percent}%
            </div>
          </div>

          {/* Large Progress Bar matching Mockup */}
          <div className="rounded-card border border-card-border bg-card p-6 shadow-card space-y-3">
            <div className="flex justify-between text-xs font-semibold text-text-secondary">
              <span>Overall Progress</span>
              <span className="text-text-primary font-bold">{selectedTask.progress_percent}%</span>
            </div>
            <div className="h-3 w-full rounded-full bg-surface-subtle overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-brand-indigo to-brand-violet"
                animate={{ width: `${selectedTask.progress_percent}%` }}
                transition={{ duration: 0.5 }}
              />
            </div>
          </div>

          {/* 4 Stat Tiles matching Mockup */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="rounded-card border border-card-border bg-card p-4 shadow-card">
              <div className="text-xs text-text-secondary font-medium">Elapsed Time</div>
              <div className="text-xl font-bold text-text-primary mt-1">
                {Math.floor(selectedTask.elapsed_seconds / 60)}m {selectedTask.elapsed_seconds % 60}s
              </div>
            </div>
            <div className="rounded-card border border-card-border bg-card p-4 shadow-card">
              <div className="text-xs text-text-secondary font-medium">Files Scanned</div>
              <div className="text-xl font-bold text-text-primary mt-1">
                {selectedTask.files_scanned !== undefined
                  ? selectedTask.files_scanned.toLocaleString()
                  : "—"}
              </div>
            </div>
            <div className="rounded-card border border-card-border bg-card p-4 shadow-card">
              <div className="text-xs text-text-secondary font-medium">Items Found</div>
              <div className="text-xl font-bold text-text-primary mt-1">
                {selectedTask.items_found !== undefined ? selectedTask.items_found : "—"}
              </div>
            </div>
            <div className="rounded-card border border-card-border bg-card p-4 shadow-card">
              <div className="text-xs text-text-secondary font-medium">Status</div>
              <div className="text-xl font-bold text-text-primary mt-1 capitalize">
                {selectedTask.status}
              </div>
            </div>
          </div>

          {/* Live Logs Terminal Panel matching Mockup */}
          <div className="rounded-card border border-card-border bg-[#0B0A1A] p-5 shadow-card text-xs">
            <div className="font-semibold text-white/80 mb-3 flex items-center justify-between">
              <span>Live Logs</span>
              <span className="text-[11px] font-mono text-white/40">Auto-scrolling</span>
            </div>
            <div className="font-mono space-y-1.5 h-44 overflow-y-auto text-emerald-400">
              {taskLogs.map((log, i) => (
                <div key={i} className="leading-relaxed">
                  {sanitize(log)}
                </div>
              ))}
            </div>
          </div>

          {/* Cancel Button */}
          <div className="flex justify-end">
            <button
              onClick={() => handleCancel(selectedTask.task_id)}
              disabled={selectedTask.status === "completed" || selectedTask.status === "cancelled"}
              className="rounded-control border border-danger/30 bg-danger/10 px-5 py-2 text-xs font-semibold text-danger hover:bg-danger/20 transition-colors disabled:opacity-40"
            >
              Cancel Task
            </button>
          </div>
        </motion.div>
      ) : (
        /* View 1: Tasks List Screen (matching Mockup) */
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-text-primary">Tasks</h2>
              <p className="text-xs text-text-secondary mt-0.5">
                Run and track long operations in the background.
              </p>
            </div>
            <button
              onClick={() => {}}
              className="flex items-center gap-1.5 rounded-control bg-brand-indigo px-3.5 py-2 text-xs font-semibold text-white hover:bg-brand-indigo/90 shadow-sm"
            >
              <Plus className="h-4 w-4" /> New Task
            </button>
          </div>

          {/* Filter Tabs matching Mockup */}
          <div className="flex gap-2">
            {[
              { id: "all", label: `All (${tasks.length})` },
              { id: "running", label: `Running (${tasks.filter((t) => t.status === "running").length})` },
              { id: "queued", label: `Queued (${tasks.filter((t) => t.status === "queued").length})` },
              { id: "completed", label: `Completed (${tasks.filter((t) => t.status === "completed").length})` },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setFilterTab(tab.id as any)}
                className={`rounded-control px-3.5 py-1.5 text-xs font-semibold transition-colors ${
                  filterTab === tab.id
                    ? "bg-brand-indigo text-white shadow-sm"
                    : "bg-card border border-card-border text-text-secondary hover:text-text-primary"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Task Rows matching Mockup */}
          <div className="space-y-3">
            {isLoading && tasks.length === 0 ? (
              <div className="rounded-card border border-card-border bg-card p-8 text-center text-text-secondary shadow-card">
                Loading background tasks...
              </div>
            ) : filteredTasks.length === 0 ? (
              <div className="rounded-card border border-card-border bg-card p-8 text-center text-text-muted shadow-card">
                <p className="text-sm font-medium">No background tasks found.</p>
                <p className="mt-1 text-xs text-text-secondary">
                  Long-running operations such as large file scans or archives run here with live logs.
                </p>
              </div>
            ) : (
              filteredTasks.map((task) => (
                <motion.div
                  key={task.task_id}
                  layout
                  onClick={() => setSelectedTask(task)}
                  className="flex items-center justify-between rounded-card border border-card-border bg-card p-4 shadow-card hover:border-brand-indigo/30 cursor-pointer transition-all"
                >
                  <div className="flex items-center gap-4">
                    {/* Progress Ring or Checkmark */}
                    {task.status === "completed" ? (
                      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-success/10 text-success">
                        <CheckCircle2 className="h-5 w-5" />
                      </div>
                    ) : (
                      <div className="relative flex h-10 w-10 items-center justify-center">
                        <svg className="h-10 w-10 -rotate-90">
                          <circle cx="20" cy="20" r="16" stroke="currentColor" strokeWidth="3" className="text-surface-subtle" fill="none" />
                          <circle
                            cx="20"
                            cy="20"
                            r="16"
                            stroke="currentColor"
                            strokeWidth="3"
                            className="text-brand-indigo"
                            strokeDasharray="100.5"
                            strokeDashoffset={100.5 - (100.5 * task.progress_percent) / 100}
                            fill="none"
                          />
                        </svg>
                        <span className="absolute text-[10px] font-bold text-text-primary">
                          {task.progress_percent}%
                        </span>
                      </div>
                    )}

                    <div>
                      <h4 className="text-sm font-bold text-text-primary">{sanitize(task.name)}</h4>
                      <p className="text-xs text-text-secondary font-mono">{sanitize(task.target_summary)}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span
                      className={`rounded-pill px-3 py-1 text-xs font-medium capitalize ${
                        task.status === "running"
                          ? "bg-brand-indigo/10 text-brand-indigo border border-brand-indigo/20"
                          : task.status === "completed"
                          ? "bg-success/10 text-success border border-success/20"
                          : "bg-surface-subtle text-text-secondary"
                      }`}
                    >
                      {task.status} {task.status === "running" ? `- ${Math.floor(task.elapsed_seconds / 60)}m ${task.elapsed_seconds % 60}s` : ""}
                    </span>
                  </div>
                </motion.div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};
