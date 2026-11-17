import React, { useState, useEffect } from "react";
import {
  Folder,
  FileText,
  Archive,
  Search,
  Plus,
  Move,
  Copy,
  Edit2,
  Trash2,
  FolderOpen,
} from "lucide-react";
import { api } from "@/lib/api";
import { sanitize } from "@/lib/sanitize";
import { ConfirmationModal } from "@/components/ConfirmationModal";

interface FileEntry {
  name: string;
  path: string;
  is_dir: boolean;
  size_bytes: number;
  mtime: number;
}

export const FilesScreen: React.FC = () => {
  const [currentPath, setCurrentPath] = useState<string>("");
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [modalPlan, setModalPlan] = useState<any | null>(null);

  // Fetch real filesystem contents within granted roots
  useEffect(() => {
    let isMounted = true;
    const fetchDir = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const res = await api.files.list(currentPath);
        if (isMounted) {
          setEntries(res.entries || []);
          if (res.current_path) {
            setCurrentPath(res.current_path);
          }
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || "Unable to list files");
          setEntries([]);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };
    fetchDir();
    return () => {
      isMounted = false;
    };
  }, [currentPath]);

  const toggleSelect = (path: string) => {
    setSelectedPaths((prev) =>
      prev.includes(path) ? prev.filter((p) => p !== path) : [...prev, path]
    );
  };

  const selectAll = () => {
    if (selectedPaths.length === entries.length) {
      setSelectedPaths([]);
    } else {
      setSelectedPaths(entries.map((e) => e.path));
    }
  };

  const handleAction = async (action: string) => {
    if (selectedPaths.length === 0 && action !== "new_folder") return;

    try {
      const planRes = await api.files.createPlan(action, selectedPaths);
      // Open Confirmation Modal with the plan
      setModalPlan(planRes);
    } catch (err: any) {
      alert(`Action error: ${err.message}`);
    }
  };

  const handleConfirmPlan = async () => {
    if (!modalPlan) return;
    try {
      await api.plans.approve(
        modalPlan.plan_id,
        modalPlan.plan_hash,
        modalPlan.confirmation_token
      );
      // Remove deleted paths locally
      setEntries((prev) => prev.filter((e) => !selectedPaths.includes(e.path)));
      setSelectedPaths([]);
      setModalPlan(null);
    } catch (err: any) {
      alert(`Execution error: ${err.message}`);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes === 0) return "--";
    if (bytes > 1024 * 1024 * 1024) return `${(bytes / (1024**3)).toFixed(1)} GB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const filteredEntries = entries.filter((e) =>
    e.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-text-primary">File Operations</h2>
        <p className="text-xs text-text-secondary mt-0.5">
          Manage files and directories with simple commands.
        </p>
      </div>

      {/* Toolbar matching Mockup */}
      <div className="flex flex-wrap items-center gap-2 border-b border-card-border pb-4">
        <button
          onClick={() => handleAction("new_folder")}
          className="flex items-center gap-1.5 rounded-control border border-card-border bg-card px-3 py-1.5 text-xs font-semibold text-text-primary shadow-sm hover:bg-surface-subtle"
        >
          <Plus className="h-3.5 w-3.5 text-brand-indigo" /> New Folder
        </button>
        <button
          disabled={selectedPaths.length === 0}
          onClick={() => handleAction("move")}
          className="flex items-center gap-1.5 rounded-control border border-card-border bg-card px-3 py-1.5 text-xs font-semibold text-text-primary shadow-sm hover:bg-surface-subtle disabled:opacity-40"
        >
          <Move className="h-3.5 w-3.5 text-brand-indigo" /> Move
        </button>
        <button
          disabled={selectedPaths.length === 0}
          onClick={() => handleAction("copy")}
          className="flex items-center gap-1.5 rounded-control border border-card-border bg-card px-3 py-1.5 text-xs font-semibold text-text-primary shadow-sm hover:bg-surface-subtle disabled:opacity-40"
        >
          <Copy className="h-3.5 w-3.5 text-brand-indigo" /> Copy
        </button>
        <button
          disabled={selectedPaths.length !== 1}
          onClick={() => handleAction("rename")}
          className="flex items-center gap-1.5 rounded-control border border-card-border bg-card px-3 py-1.5 text-xs font-semibold text-text-primary shadow-sm hover:bg-surface-subtle disabled:opacity-40"
        >
          <Edit2 className="h-3.5 w-3.5 text-brand-indigo" /> Rename
        </button>
        <button
          disabled={selectedPaths.length === 0}
          onClick={() => handleAction("delete")}
          className="flex items-center gap-1.5 rounded-control border border-danger/30 bg-danger/10 px-3 py-1.5 text-xs font-semibold text-danger shadow-sm hover:bg-danger/20 disabled:opacity-40"
        >
          <Trash2 className="h-3.5 w-3.5" /> Delete
        </button>
      </div>

      {/* Breadcrumb & Search Bar matching Mockup */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-1 text-xs font-mono text-text-secondary bg-surface-subtle px-3 py-1.5 rounded-control border border-card-border">
          <FolderOpen className="h-3.5 w-3.5 text-brand-indigo mr-1" />
          <span>{currentPath ? sanitize(currentPath) : "No folder selected"}</span>
        </div>

        <div className="relative">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-text-muted" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search files..."
            className="w-48 sm:w-64 rounded-control border border-card-border bg-card pl-8 pr-3 py-1.5 text-xs text-text-primary placeholder:text-text-muted focus:outline-none"
          />
        </div>
      </div>

      {/* File Table matching Mockup */}
      <div className="rounded-card border border-card-border bg-card shadow-card overflow-hidden">
        <table className="w-full text-left text-xs">
          <thead className="bg-surface-subtle/70 text-text-secondary uppercase tracking-wider text-[10px] border-b border-card-border font-semibold">
            <tr>
              <th className="py-3 px-4 w-10">
                <input
                  type="checkbox"
                  checked={selectedPaths.length === entries.length && entries.length > 0}
                  onChange={selectAll}
                  className="rounded text-brand-indigo"
                />
              </th>
              <th className="py-3 px-4">Name</th>
              <th className="py-3 px-4">Size</th>
              <th className="py-3 px-4">Type</th>
              <th className="py-3 px-4">Modified</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-card-border">
            {isLoading && entries.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-text-secondary">
                  Loading files...
                </td>
              </tr>
            ) : error && entries.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-danger">
                  <p>{sanitize(error)}</p>
                  <p className="mt-1 text-[11px] text-text-secondary">
                    Please ensure folder permissions are granted in Settings or the setup wizard.
                  </p>
                </td>
              </tr>
            ) : filteredEntries.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-text-muted">
                  No files found in this directory.
                </td>
              </tr>
            ) : (
              filteredEntries.map((file) => {
                const isSelected = selectedPaths.includes(file.path);
                return (
                  <tr
                    key={file.path}
                    onClick={() => toggleSelect(file.path)}
                    className={`hover:bg-surface-subtle/50 cursor-pointer transition-colors ${
                      isSelected ? "bg-brand-indigo/5" : ""
                    }`}
                  >
                    <td className="py-3 px-4" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelect(file.path)}
                        className="rounded text-brand-indigo"
                      />
                    </td>
                    <td className="py-3 px-4 font-medium text-text-primary flex items-center gap-2">
                      {file.is_dir ? (
                        <Folder className="h-4 w-4 text-amber-500 flex-shrink-0" />
                      ) : file.name.endsWith(".zip") ? (
                        <Archive className="h-4 w-4 text-brand-violet flex-shrink-0" />
                      ) : (
                        <FileText className="h-4 w-4 text-blue-500 flex-shrink-0" />
                      )}
                      <span className="truncate max-w-[200px]">{sanitize(file.name)}</span>
                    </td>
                    <td className="py-3 px-4 text-text-secondary">
                      {file.is_dir ? "—" : formatSize(file.size_bytes)}
                    </td>
                    <td className="py-3 px-4 text-text-secondary">
                      {file.is_dir ? "Folder" : file.name.split(".").pop()?.toUpperCase() + " File"}
                    </td>
                    <td className="py-3 px-4 text-text-muted">
                      {file.mtime ? new Date(file.mtime * 1000).toLocaleDateString() : "—"}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Confirmation Modal when Delete or Sensitive action is requested */}
      {modalPlan && (
        <ConfirmationModal
          isOpen={true}
          title="Confirm Deletion"
          subtitle={`You are about to delete ${modalPlan.target_count || selectedPaths.length} items.`}
          consequences={modalPlan.consequences}
          items={selectedPaths.map((p) => ({ name: p.split("/").pop() || p }))}
          riskLevel="DESTRUCTIVE"
          expectedToken={modalPlan.confirmation_token}
          confirmButtonLabel={`Delete (${modalPlan.target_count || selectedPaths.length})`}
          onConfirm={handleConfirmPlan}
          onCancel={() => setModalPlan(null)}
        />
      )}
    </div>
  );
};
