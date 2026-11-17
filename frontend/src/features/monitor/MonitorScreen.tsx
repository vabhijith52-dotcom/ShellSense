import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Cpu, HardDrive, Database } from "lucide-react";
import { api } from "@/lib/api";

export const MonitorScreen: React.FC = () => {
  const [stats, setStats] = useState<any>(null);
  const [history, setHistory] = useState<number[]>([]);
  const [timeRange, setTimeRange] = useState("10m");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const fetchStats = async () => {
      try {
        const res = await api.system.getInfo();
        if (isMounted && res.sample) {
          setStats(res.sample);
          setHistory((prev) => [...prev.slice(-15), res.sample.cpu_percent]);
          setError(null);
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || "Unable to read hardware metrics");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 1500); // 1.5s refresh
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  if (isLoading && !stats) {
    return (
      <div className="space-y-6 max-w-5xl mx-auto text-center py-24">
        <p className="text-text-secondary text-sm">Connecting to system monitor...</p>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div className="space-y-6 max-w-5xl mx-auto text-center py-24 text-danger">
        <p className="text-sm font-semibold">{error}</p>
        <p className="text-xs text-text-secondary mt-1">Please ensure ShellSense backend is running.</p>
      </div>
    );
  }

  const ramUsedGB = (stats.ram_used_bytes / 1024**3).toFixed(1);
  const ramTotalGB = (stats.ram_total_bytes / 1024**3).toFixed(0);
  const ramFreeGB = ((stats.ram_total_bytes - stats.ram_used_bytes) / 1024**3).toFixed(1);
  const diskUsedGB = (stats.disk_used_bytes / 1024**3).toFixed(0);
  const diskTotalGB = (stats.disk_total_bytes / 1024**3).toFixed(0);

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-text-primary">System Monitor</h2>
          <p className="text-xs text-text-secondary mt-0.5">
            Real-time system performance and resource usage.
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-pill bg-success/10 border border-success/20 px-3 py-1 text-xs font-semibold text-success">
          <span className="h-2 w-2 rounded-full bg-success animate-ping" />
          Live
        </div>
      </div>

      {/* 3 Stat Cards matching Mockup */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* CPU Card */}
        <div className="rounded-card border border-card-border bg-card p-5 shadow-card">
          <div className="flex items-center justify-between text-xs font-semibold text-text-secondary">
            <span className="flex items-center gap-1.5">
              <Cpu className="h-4 w-4 text-brand-indigo" /> CPU
            </span>
            <span className="text-success font-bold">{stats.cpu_percent.toFixed(0)}%</span>
          </div>
          <div className="mt-3 text-3xl font-extrabold text-text-primary">
            {stats.cpu_percent.toFixed(0)}%
          </div>
          <div className="mt-4 h-2 w-full rounded-full bg-surface-subtle overflow-hidden">
            <motion.div
              className="h-full bg-brand-indigo"
              animate={{ width: `${stats.cpu_percent}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>

        {/* RAM Card */}
        <div className="rounded-card border border-card-border bg-card p-5 shadow-card">
          <div className="flex items-center justify-between text-xs font-semibold text-text-secondary">
            <span className="flex items-center gap-1.5">
              <Database className="h-4 w-4 text-brand-violet" /> RAM
            </span>
            <span>{ramUsedGB} / {ramTotalGB} GB</span>
          </div>
          <div className="mt-3 text-3xl font-extrabold text-text-primary">
            {stats.ram_percent.toFixed(0)}%
          </div>
          <div className="mt-4 h-2 w-full rounded-full bg-surface-subtle overflow-hidden">
            <motion.div
              className="h-full bg-brand-violet"
              animate={{ width: `${stats.ram_percent}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>

        {/* Disk Card */}
        <div className="rounded-card border border-card-border bg-card p-5 shadow-card">
          <div className="flex items-center justify-between text-xs font-semibold text-text-secondary">
            <span className="flex items-center gap-1.5">
              <HardDrive className="h-4 w-4 text-brand-indigo" /> Disk (Root)
            </span>
            <span>{diskUsedGB} / {diskTotalGB} GB</span>
          </div>
          <div className="mt-3 text-3xl font-extrabold text-text-primary">
            {stats.disk_percent.toFixed(0)}%
          </div>
          <div className="mt-4 h-2 w-full rounded-full bg-surface-subtle overflow-hidden">
            <motion.div
              className="h-full bg-brand-indigo"
              animate={{ width: `${stats.disk_percent}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>
      </div>

      {/* Main Charts Row matching Mockup */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* CPU Usage Area Chart (2 cols) */}
        <div className="lg:col-span-2 rounded-card border border-card-border bg-card p-6 shadow-card">
          <div className="flex items-center justify-between mb-4">
            <div className="font-bold text-base text-text-primary">CPU Usage</div>
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="rounded-control border border-card-border bg-surface-subtle px-3 py-1 text-xs font-medium text-text-secondary focus:outline-none"
            >
              <option value="10m">Last 10 minutes</option>
              <option value="1h">Last 1 hour</option>
            </select>
          </div>

          {/* SVG Wave Sparkline / Line Chart */}
          <div className="relative h-48 w-full flex items-end pt-4">
            <svg className="w-full h-full overflow-visible" viewBox="0 0 400 120" preserveAspectRatio="none">
              <defs>
                <linearGradient id="cpuGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#4F46E5" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="#7C3AED" stopOpacity="0.0" />
                </linearGradient>
              </defs>
              {/* Grid lines */}
              <line x1="0" y1="30" x2="400" y2="30" stroke="currentColor" strokeOpacity="0.1" />
              <line x1="0" y1="60" x2="400" y2="60" stroke="currentColor" strokeOpacity="0.1" />
              <line x1="0" y1="90" x2="400" y2="90" stroke="currentColor" strokeOpacity="0.1" />

              {/* Area fill and stroke path */}
              <path
                d={`M 0 120 ${history
                  .map((val, i) => `L ${(i / (history.length - 1)) * 400} ${120 - (val / 100) * 100}`)
                  .join(" ")} L 400 120 Z`}
                fill="url(#cpuGradient)"
              />
              <path
                d={`M 0 ${120 - (history[0]! / 100) * 100} ${history
                  .map((val, i) => `L ${(i / (history.length - 1)) * 400} ${120 - (val / 100) * 100}`)
                  .join(" ")}`}
                fill="none"
                stroke="#6366F1"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>

          <div className="flex justify-between text-[11px] text-text-muted mt-2 border-t border-card-border/50 pt-2">
            <span>Now</span>
            <span>-1 min</span>
            <span>-3 min</span>
            <span>-5 min</span>
            <span>-10 min</span>
          </div>
        </div>

        {/* Memory Donut Chart (1 col) matching Mockup */}
        <div className="rounded-card border border-card-border bg-card p-6 shadow-card flex flex-col justify-between">
          <div className="font-bold text-base text-text-primary">Memory Usage</div>

          {/* SVG Donut Ring */}
          <div className="relative flex items-center justify-center my-4">
            <svg className="h-36 w-36 -rotate-90" viewBox="0 0 100 100">
              <circle
                cx="50"
                cy="50"
                r="40"
                className="text-surface-subtle stroke-current"
                strokeWidth="12"
                fill="none"
              />
              <motion.circle
                cx="50"
                cy="50"
                r="40"
                className="text-brand-violet stroke-current"
                strokeWidth="12"
                strokeDasharray="251.2"
                animate={{ strokeDashoffset: 251.2 - (251.2 * stats.ram_percent) / 100 }}
                transition={{ duration: 0.8 }}
                strokeLinecap="round"
                fill="none"
              />
            </svg>
            <div className="absolute text-center">
              <span className="text-2xl font-extrabold text-text-primary">
                {stats.ram_percent.toFixed(0)}%
              </span>
            </div>
          </div>

          {/* Legend matching Mockup */}
          <div className="space-y-1.5 text-xs">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-text-secondary">
                <span className="h-2.5 w-2.5 rounded-full bg-brand-violet" /> Used
              </span>
              <span className="font-semibold text-text-primary">{ramUsedGB} GB</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-text-secondary">
                <span className="h-2.5 w-2.5 rounded-full bg-surface-subtle border border-card-border" /> Free
              </span>
              <span className="font-semibold text-text-primary">{ramFreeGB} GB</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
