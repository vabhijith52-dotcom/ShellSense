import React, { useState, useEffect } from "react";
import { Cpu, RefreshCw, Trash2, Info, Search } from "lucide-react";
import { api } from "@/lib/api";
import { sanitize } from "@/lib/sanitize";
import { ConfirmationModal } from "@/components/ConfirmationModal";

interface ProcessItem {
  pid: number;
  name: string;
  user: string;
  cpu_percent: number;
  memory_rss_bytes: number;
  is_protected: boolean;
  is_own: boolean;
  can_terminate: boolean;
}

export const ProcessScreen: React.FC = () => {
  const [processes, setProcesses] = useState<ProcessItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [modalPlan, setModalPlan] = useState<any | null>(null);
  const [targetPid, setTargetPid] = useState<number | null>(null);

  const fetchProcesses = async () => {
    try {
      setError(null);
      const res = await api.processes.list();
      setProcesses(res.processes || []);
    } catch (err: any) {
      setError(err.message || "Failed to load active processes");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProcesses();
    if (!autoRefresh) return;
    const interval = setInterval(fetchProcesses, 3000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const handleTerminateClick = async (proc: ProcessItem) => {
    if (!proc.can_terminate) return;
    setTargetPid(proc.pid);

    try {
      const planRes = await api.processes.createPlan("terminate", [proc.pid]);
      setModalPlan(planRes);
    } catch (err: any) {
      alert(`Process action error: ${err.message}`);
    }
  };

  const handleConfirmTerminate = async () => {
    if (!modalPlan) return;
    try {
      await api.plans.approve(
        modalPlan.plan_id,
        modalPlan.plan_hash,
        modalPlan.confirmation_token
      );
      setProcesses((prev) => prev.filter((p) => p.pid !== targetPid));
      setModalPlan(null);
    } catch (err: any) {
      alert(`Termination error: ${err.message}`);
    }
  };

  const formatMemory = (bytes: number) => {
    if (bytes > 1024 * 1024 * 1024) return `${(bytes / (1024**3)).toFixed(1)} GB`;
    return `${(bytes / (1024 * 1024)).toFixed(0)} MB`;
  };

  const filtered = processes.filter(
    (p) =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.pid.toString().includes(searchQuery)
  );

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-text-primary">Process Manager</h2>
        <p className="text-xs text-text-secondary mt-0.5">
          View and manage running processes with fail-closed safety guardrails.
        </p>
      </div>

      {/* Toolbar & Search matching Mockup */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-text-muted" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search processes..."
            className="w-56 sm:w-72 rounded-control border border-card-border bg-card pl-8 pr-3 py-1.5 text-xs text-text-primary placeholder:text-text-muted focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchProcesses}
            className="flex items-center gap-1.5 rounded-control border border-card-border bg-card px-3 py-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary transition-colors shadow-sm"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </button>
          <label className="flex items-center gap-1.5 text-xs text-text-secondary cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded text-brand-indigo"
            />
            Auto-refresh
          </label>
        </div>
      </div>

      {/* Process Table matching Mockup */}
      <div className="rounded-card border border-card-border bg-card shadow-card overflow-hidden">
        <table className="w-full text-left text-xs">
          <thead className="bg-surface-subtle/70 text-text-secondary uppercase tracking-wider text-[10px] border-b border-card-border font-semibold">
            <tr>
              <th className="py-3 px-4">Process Name</th>
              <th className="py-3 px-4">PID</th>
              <th className="py-3 px-4">CPU</th>
              <th className="py-3 px-4">Memory</th>
              <th className="py-3 px-4 text-center">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-card-border">
            {isLoading && processes.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-text-secondary">
                  <div className="flex items-center justify-center gap-2">
                    <RefreshCw className="h-4 w-4 animate-spin text-brand-indigo" />
                    <span>Loading running processes...</span>
                  </div>
                </td>
              </tr>
            ) : error && processes.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-danger">
                  <p>{sanitize(error)}</p>
                  <button
                    onClick={fetchProcesses}
                    className="mt-2 inline-flex items-center gap-1.5 rounded-control border border-card-border bg-card px-3 py-1 text-xs text-text-primary hover:bg-black/5"
                  >
                    <RefreshCw className="h-3 w-3" /> Retry
                  </button>
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-text-muted">
                  No matching processes found.
                </td>
              </tr>
            ) : (
              filtered.map((proc) => (
                <tr key={proc.pid} className="hover:bg-surface-subtle/50 transition-colors">
                  <td className="py-3 px-4 font-medium text-text-primary flex items-center gap-2">
                    <div className="flex h-6 w-6 items-center justify-center rounded bg-brand-indigo/10 text-brand-indigo">
                      <Cpu className="h-3.5 w-3.5" />
                    </div>
                    <span className="truncate max-w-[220px]">{sanitize(proc.name)}</span>
                  </td>
                  <td className="py-3 px-4 font-mono text-text-secondary">{proc.pid}</td>
                  <td className="py-3 px-4 text-text-secondary">{proc.cpu_percent.toFixed(1)}%</td>
                  <td className="py-3 px-4 text-text-secondary">{formatMemory(proc.memory_rss_bytes)}</td>
                  <td className="py-3 px-4">
                    <div className="flex items-center justify-center gap-2">
                      <button
                        title={`Process: ${proc.name} | User: ${proc.user}`}
                        className="text-text-secondary hover:text-text-primary p-1"
                      >
                        <Info className="h-4 w-4" />
                      </button>
                      {proc.can_terminate ? (
                        <button
                          onClick={() => handleTerminateClick(proc)}
                          className="text-danger hover:text-danger/80 p-1"
                          title="Terminate Process"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      ) : (
                        <span
                          title={
                            proc.is_protected
                              ? "Protected operating system process"
                              : "Process owned by another user"
                          }
                          className="text-text-muted p-1 opacity-40 cursor-not-allowed"
                        >
                          <Trash2 className="h-4 w-4" />
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Confirmation Modal for Terminate Process */}
      {modalPlan && (
        <ConfirmationModal
          isOpen={true}
          title="Confirm Process Termination"
          subtitle={`You are about to terminate PID ${modalPlan.confirmation_token}.`}
          consequences="Unsaved work in the target process may be lost."
          items={[{ name: `PID ${modalPlan.confirmation_token}` }]}
          riskLevel="DESTRUCTIVE"
          expectedToken={modalPlan.confirmation_token}
          confirmButtonLabel={`Terminate (${modalPlan.confirmation_token})`}
          onConfirm={handleConfirmTerminate}
          onCancel={() => setModalPlan(null)}
        />
      )}
    </div>
  );
};
