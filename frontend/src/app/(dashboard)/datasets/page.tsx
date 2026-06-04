"use client";

import { useSession } from "next-auth/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { fetchWithAuth } from "@/lib/api";
import {
  Plus,
  Search,
  FolderOpen,
  Archive,
  Trash2,
  ExternalLink,
  FileText,
  Link as LinkIcon,
  ChevronRight,
  AlertCircle,
  CheckCircle2,
  Loader2,
} from "lucide-react";

/* ── Types ─────────────────────────────────────────────────────────── */

interface DatasetInfo {
  id: string;
  name: string;
  description: string | null;
  version: number;
  status: string;
  source_count: number;
  created_at: string;
  updated_at: string;
}

interface DatasetDetail extends DatasetInfo {
  domain_tags: string[] | null;
  sources: DatasetSource[];
  version_history: DatasetVersion[];
}

interface DatasetSource {
  id: string;
  dataset_id: string;
  dataset_version: number;
  source_type: string;
  source_path: string;
  file_name: string | null;
  file_size: number | null;
  mime_type: string | null;
  content_hash: string | null;
  processed: boolean;
  processing_error: string | null;
  created_at: string;
}

interface DatasetVersion {
  id: string;
  dataset_id: string;
  version: number;
  change_description: string | null;
  source_count: number | null;
  sources_added: number | null;
  created_at: string;
}

/* ── Toast Notification ───────────────────────────────────────────── */

function Toast({
  message,
  type,
  onDismiss,
}: {
  message: string;
  type: "success" | "error";
  onDismiss: () => void;
}) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 4000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  return (
    <div
      className={`fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-lg px-4 py-3 text-sm shadow-lg transition-all animate-in slide-in-from-bottom-2 ${
        type === "success"
          ? "bg-green-600 text-white"
          : "bg-destructive text-white"
      }`}
    >
      {type === "success" ? (
        <CheckCircle2 className="size-4" />
      ) : (
        <AlertCircle className="size-4" />
      )}
      {message}
      <button
        onClick={onDismiss}
        className="ml-2 text-xs opacity-70 hover:opacity-100"
      >
        Dismiss
      </button>
    </div>
  );
}

/* ── Loading Skeleton ─────────────────────────────────────────────── */

function DatasetCardSkeleton() {
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="mb-3 h-4 w-3/4 animate-pulse rounded bg-muted" />
      <div className="mb-2 h-3 w-1/2 animate-pulse rounded bg-muted" />
      <div className="flex items-center justify-between">
        <div className="h-5 w-14 animate-pulse rounded bg-muted" />
        <div className="h-3 w-20 animate-pulse rounded bg-muted" />
      </div>
    </div>
  );
}

/* ── Format Helpers ───────────────────────────────────────────────── */

function formatFileSize(bytes: number | null): string {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/* ── Datasets Page Component ──────────────────────────────────────── */

export default function DatasetsPage() {
  const { data: session, status } = useSession();
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<DatasetDetail | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Toast state
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);

  // Create dataset dialog state
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);

  // Archive confirm dialog
  const [showArchiveConfirm, setShowArchiveConfirm] = useState(false);

  // Add source dialog
  const [showAddSourceDialog, setShowAddSourceDialog] = useState(false);
  const [sourceTab, setSourceTab] = useState<"text" | "url">("text");
  const [sourceText, setSourceText] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");

  // Fetch datasets
  const fetchDatasets = useCallback(async () => {
    try {
      const res = await fetchWithAuth("/api/v1/datasets");
      if (res.ok) {
        setDatasets(await res.json());
      } else if (res.status === 401) {
        setError("Authentication failed. Please sign in again.");
      }
    } catch (err) {
      console.error("Failed to fetch datasets:", err);
      setError("Failed to load datasets. Please try again.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (status === "authenticated") fetchDatasets();
    else if (status === "unauthenticated") setLoading(false);
  }, [status, fetchDatasets]);

  // Fetch dataset detail
  const fetchDetail = useCallback(async (datasetId: string) => {
    setActionLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth(`/api/v1/datasets/${datasetId}`);
      if (res.ok) {
        setSelectedDataset(await res.json());
      } else {
        setError("Failed to load dataset details");
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setActionLoading(false);
    }
  }, []);

  // Create dataset
  const handleCreate = async () => {
    // Validate
    const trimmedName = newName.trim();
    if (!trimmedName) {
      setNameError("Dataset name is required");
      return;
    }
    if (trimmedName.length < 2) {
      setNameError("Name must be at least 2 characters");
      return;
    }
    if (trimmedName.length > 100) {
      setNameError("Name must be under 100 characters");
      return;
    }

    setActionLoading(true);
    setError(null);
    setNameError(null);

    try {
      const res = await fetchWithAuth("/api/v1/datasets", {
        method: "POST",
        body: JSON.stringify({
          name: trimmedName,
          description: newDescription.trim() || undefined,
        }),
      });
      if (res.ok) {
        setShowCreateDialog(false);
        setNewName("");
        setNewDescription("");
        setToast({ message: "Dataset created successfully", type: "success" });
        await fetchDatasets();
      } else if (res.status === 401) {
        setToast({
          message: "Authentication expired. Please sign in again.",
          type: "error",
        });
      } else {
        const data = await res.json();
        setToast({
          message: data.detail || "Failed to create dataset",
          type: "error",
        });
      }
    } catch (err) {
      setToast({ message: (err as Error).message, type: "error" });
    } finally {
      setActionLoading(false);
    }
  };

  // Archive dataset
  const handleArchive = async () => {
    if (!selectedDataset) return;
    setActionLoading(true);
    try {
      const res = await fetchWithAuth(
        `/api/v1/datasets/${selectedDataset.id}/archive`,
        { method: "POST" }
      );
      if (res.ok) {
        setShowArchiveConfirm(false);
        setSelectedDataset(null);
        setToast({ message: "Dataset archived", type: "success" });
        await fetchDatasets();
      }
    } catch (err) {
      setToast({ message: (err as Error).message, type: "error" });
    } finally {
      setActionLoading(false);
    }
  };

  // Add text source
  const handleAddTextSource = async () => {
    if (!selectedDataset || !sourceText.trim()) return;
    setActionLoading(true);
    try {
      const res = await fetchWithAuth(
        `/api/v1/datasets/${selectedDataset.id}/sources?source_type=text&text_content=${encodeURIComponent(sourceText)}`,
        { method: "POST" }
      );
      if (res.ok) {
        setShowAddSourceDialog(false);
        setSourceText("");
        setToast({ message: "Source added", type: "success" });
        await fetchDetail(selectedDataset.id);
        await fetchDatasets();
      } else {
        const data = await res.json();
        setToast({
          message: data.detail || "Failed to add source",
          type: "error",
        });
      }
    } catch (err) {
      setToast({ message: (err as Error).message, type: "error" });
    } finally {
      setActionLoading(false);
    }
  };

  // Add URL source
  const handleAddUrlSource = async () => {
    if (!selectedDataset || !sourceUrl.trim()) return;
    setActionLoading(true);
    try {
      const res = await fetchWithAuth(
        `/api/v1/datasets/${selectedDataset.id}/sources?source_type=url&source_path=${encodeURIComponent(sourceUrl)}`,
        { method: "POST" }
      );
      if (res.ok) {
        const data = await res.json();
        setShowAddSourceDialog(false);
        setSourceUrl("");
        if (data.status === "failed") {
          setToast({
            message: "URL was added but content could not be fetched",
            type: "error",
          });
        } else {
          setToast({ message: "URL source added", type: "success" });
        }
        await fetchDetail(selectedDataset.id);
        await fetchDatasets();
      } else {
        const data = await res.json();
        setToast({
          message: data.detail || "Failed to add source",
          type: "error",
        });
      }
    } catch (err) {
      setToast({ message: (err as Error).message, type: "error" });
    } finally {
      setActionLoading(false);
    }
  };

  // Remove source
  const handleRemoveSource = async (sourceId: string) => {
    if (!selectedDataset) return;
    setActionLoading(true);
    try {
      const res = await fetchWithAuth(
        `/api/v1/datasets/${selectedDataset.id}/sources/${sourceId}`,
        { method: "DELETE" }
      );
      if (res.ok) {
        setToast({ message: "Source removed", type: "success" });
        await fetchDetail(selectedDataset.id);
        await fetchDatasets();
      }
    } catch (err) {
      setToast({ message: (err as Error).message, type: "error" });
    } finally {
      setActionLoading(false);
    }
  };

  // Reset create dialog on open/close
  const openCreateDialog = () => {
    setNewName("");
    setNewDescription("");
    setNameError(null);
    setShowCreateDialog(true);
  };

  // Filtered datasets
  const filteredDatasets = useMemo(() => {
    if (!searchQuery.trim()) return datasets;
    const q = searchQuery.toLowerCase();
    return datasets.filter(
      (ds) =>
        ds.name.toLowerCase().includes(q) ||
        ds.description?.toLowerCase().includes(q)
    );
  }, [datasets, searchQuery]);

  // Auth/loading guards
  if (status === "loading" || loading) {
    return (
      <div className="p-6">
        <div className="mb-6">
          <div className="mb-1 h-8 w-40 animate-pulse rounded bg-muted" />
          <div className="h-4 w-64 animate-pulse rounded bg-muted" />
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <DatasetCardSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-center">Sign in required</CardTitle>
            <CardDescription className="text-center">
              Please sign in to manage datasets.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  /* ── Detail View ────────────────────────────────────────────────── */
  if (selectedDataset) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        {/* Toast */}
        {toast && (
          <Toast
            message={toast.message}
            type={toast.type}
            onDismiss={() => setToast(null)}
          />
        )}

        {/* Header */}
        <div className="mb-6 flex items-start justify-between">
          <div>
            <button
              onClick={() => setSelectedDataset(null)}
              className="mb-2 flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              <ChevronRight className="size-3 rotate-180" />
              Back to datasets
            </button>
            <h1 className="text-2xl font-semibold tracking-tight">
              {selectedDataset.name}
            </h1>
            <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
              <span className="rounded-md bg-muted px-1.5 py-0.5 text-xs font-medium">
                v{selectedDataset.version}
              </span>
              <span
                className={`rounded-md px-1.5 py-0.5 text-xs font-medium ${
                  selectedDataset.status === "active"
                    ? "bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300"
                    : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
                }`}
              >
                {selectedDataset.status}
              </span>
              <span>·</span>
              <span>
                {selectedDataset.sources.length} source
                {selectedDataset.sources.length !== 1 ? "s" : ""}
              </span>
              <span>·</span>
              <span>Created {formatDate(selectedDataset.created_at)}</span>
            </div>
          </div>
          <div className="flex gap-2">
            {selectedDataset.status === "active" && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setSourceTab("text");
                    setSourceText("");
                    setSourceUrl("");
                    setShowAddSourceDialog(true);
                  }}
                >
                  <Plus className="size-3.5" />
                  Add Source
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setShowArchiveConfirm(true)}
                  disabled={actionLoading}
                >
                  <Archive className="size-3.5" />
                  Archive
                </Button>
              </>
            )}
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            <AlertCircle className="size-4 shrink-0" />
            {error}
            <button
              className="ml-auto text-xs underline"
              onClick={() => setError(null)}
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Description */}
        {selectedDataset.description && (
          <Card className="mb-4" size="sm">
            <CardContent className="text-sm text-muted-foreground">
              {selectedDataset.description}
            </CardContent>
          </Card>
        )}

        {/* Sources */}
        <Card className="mb-4">
          <CardHeader>
            <CardTitle>Sources</CardTitle>
            <CardDescription>
              Documents and data in this dataset
            </CardDescription>
          </CardHeader>
          <CardContent>
            {selectedDataset.sources.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <FileText className="mb-3 size-10 text-muted-foreground/50" />
                <p className="text-sm font-medium">No sources yet</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Add text content or URLs to build your dataset.
                </p>
                {selectedDataset.status === "active" && (
                  <Button
                    className="mt-4"
                    size="sm"
                    onClick={() => {
                      setSourceTab("text");
                      setSourceText("");
                      setSourceUrl("");
                      setShowAddSourceDialog(true);
                    }}
                  >
                    <Plus className="size-3.5" />
                    Add First Source
                  </Button>
                )}
              </div>
            ) : (
              <div className="overflow-hidden rounded-lg border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">
                        Name
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">
                        Type
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">
                        Size
                      </th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">
                        Status
                      </th>
                      {selectedDataset.status === "active" && (
                        <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">
                          Actions
                        </th>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {selectedDataset.sources.map((source) => (
                      <tr
                        key={source.id}
                        className="border-t transition-colors hover:bg-muted/30"
                      >
                        <td className="px-3 py-2.5 text-xs">
                          <div className="flex items-center gap-2">
                            {source.source_type === "url" ? (
                              <LinkIcon className="size-3.5 text-muted-foreground" />
                            ) : (
                              <FileText className="size-3.5 text-muted-foreground" />
                            )}
                            <span className="truncate max-w-[200px]">
                              {source.file_name || source.source_path.slice(-40)}
                            </span>
                          </div>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider">
                            {source.source_type}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-xs text-muted-foreground">
                          {formatFileSize(source.file_size)}
                        </td>
                        <td className="px-3 py-2.5 text-xs">
                          {source.processing_error ? (
                            <span className="inline-flex items-center gap-1 text-destructive">
                              <AlertCircle className="size-3" />
                              Failed
                            </span>
                          ) : source.processed ? (
                            <span className="inline-flex items-center gap-1 text-green-600 dark:text-green-400">
                              <CheckCircle2 className="size-3" />
                              Processed
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-yellow-600 dark:text-yellow-400">
                              <Loader2 className="size-3 animate-spin" />
                              Pending
                            </span>
                          )}
                        </td>
                        {selectedDataset.status === "active" && (
                          <td className="px-3 py-2.5 text-right">
                            <button
                              className="inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-destructive"
                              onClick={() => handleRemoveSource(source.id)}
                              disabled={actionLoading}
                            >
                              <Trash2 className="size-3" />
                              Remove
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Version History */}
        <Card>
          <CardHeader>
            <CardTitle>Version History</CardTitle>
            <CardDescription>Track changes over time</CardDescription>
          </CardHeader>
          <CardContent>
            {selectedDataset.version_history.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted-foreground">
                No version history.
              </p>
            ) : (
              <div className="space-y-0">
                {selectedDataset.version_history
                  .slice()
                  .reverse()
                  .map((vh, i) => (
                    <div
                      key={vh.id}
                      className={`flex items-center gap-4 px-1 py-2.5 text-sm ${
                        i > 0 ? "border-t" : ""
                      }`}
                    >
                      <span className="shrink-0 rounded-md bg-muted px-1.5 py-0.5 text-xs font-medium">
                        v{vh.version}
                      </span>
                      <span className="flex-1 text-xs text-muted-foreground">
                        {vh.change_description || "Initial version"}
                      </span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {vh.source_count ?? "—"} sources
                      </span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {formatDate(vh.created_at)}
                      </span>
                    </div>
                  ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Archive Confirmation Dialog */}
        <Dialog open={showArchiveConfirm} onOpenChange={setShowArchiveConfirm}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Archive Dataset</DialogTitle>
              <DialogDescription>
                Are you sure you want to archive &ldquo;{selectedDataset.name}
                &rdquo;? Archived datasets cannot be used for fine-tuning.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setShowArchiveConfirm(false)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleArchive}
                disabled={actionLoading}
              >
                {actionLoading ? (
                  <>
                    <Loader2 className="size-3.5 animate-spin" />
                    Archiving...
                  </>
                ) : (
                  "Archive"
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Add Source Dialog */}
        <Dialog open={showAddSourceDialog} onOpenChange={setShowAddSourceDialog}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Add Source</DialogTitle>
              <DialogDescription>
                Add text content or a URL reference to this dataset.
              </DialogDescription>
            </DialogHeader>

            {/* Tab switcher */}
            <div className="flex gap-1 rounded-lg bg-muted p-1">
              <button
                className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  sourceTab === "text"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                onClick={() => setSourceTab("text")}
              >
                <FileText className="mr-1 inline size-3" />
                Text Content
              </button>
              <button
                className={`flex-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  sourceTab === "url"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                onClick={() => setSourceTab("url")}
              >
                <LinkIcon className="mr-1 inline size-3" />
                URL
              </button>
            </div>

            {sourceTab === "text" ? (
              <div className="space-y-2">
                <Label htmlFor="source-text" className="text-xs">
                  Text Content
                </Label>
                <textarea
                  id="source-text"
                  className="min-h-[120px] w-full rounded-lg border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/50"
                  placeholder="Paste your training text content here..."
                  value={sourceText}
                  onChange={(e) => setSourceText(e.target.value)}
                />
                <p className="text-[10px] text-muted-foreground">
                  {sourceText.length} characters
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                <Label htmlFor="source-url" className="text-xs">
                  URL
                </Label>
                <Input
                  id="source-url"
                  placeholder="https://example.com/training-data"
                  value={sourceUrl}
                  onChange={(e) => setSourceUrl(e.target.value)}
                />
                <p className="text-[10px] text-muted-foreground">
                  The URL will be fetched and its content extracted.
                </p>
              </div>
            )}

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setShowAddSourceDialog(false)}
              >
                Cancel
              </Button>
              <Button
                onClick={
                  sourceTab === "text" ? handleAddTextSource : handleAddUrlSource
                }
                disabled={
                  actionLoading ||
                  (sourceTab === "text"
                    ? !sourceText.trim()
                    : !sourceUrl.trim())
                }
              >
                {actionLoading ? (
                  <>
                    <Loader2 className="size-3.5 animate-spin" />
                    Adding...
                  </>
                ) : (
                  <>
                    <Plus className="size-3.5" />
                    Add Source
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    );
  }

  /* ── List View ──────────────────────────────────────────────────── */
  return (
    <div className="p-6">
      {/* Toast */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onDismiss={() => setToast(null)}
        />
      )}

      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Datasets</h1>
          <p className="text-sm text-muted-foreground">
            Manage versioned datasets for fine-tuning.
          </p>
        </div>
        <Button onClick={openCreateDialog}>
          <Plus className="size-4" />
          New Dataset
        </Button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="size-4 shrink-0" />
          {error}
          <button
            className="ml-auto text-xs underline"
            onClick={() => setError(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Search bar (only show when datasets exist) */}
      {datasets.length > 0 && (
        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search datasets..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
      )}

      {/* Create Dataset Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Dataset</DialogTitle>
            <DialogDescription>
              Create a new dataset to hold documents for fine-tuning.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="ds-name">
                Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="ds-name"
                placeholder="e.g., Medical Research Papers"
                value={newName}
                onChange={(e) => {
                  setNewName(e.target.value);
                  if (nameError) setNameError(null);
                }}
                autoFocus
                className={nameError ? "border-destructive" : ""}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && newName.trim()) handleCreate();
                }}
              />
              {nameError && (
                <p className="flex items-center gap-1 text-xs text-destructive">
                  <AlertCircle className="size-3" />
                  {nameError}
                </p>
              )}
              <p className="text-[10px] text-muted-foreground">
                {newName.length}/100 characters
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="ds-desc">Description (optional)</Label>
              <textarea
                id="ds-desc"
                className="min-h-[80px] w-full rounded-lg border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/50"
                placeholder="Describe the dataset contents, domain, or purpose..."
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && e.metaKey && newName.trim())
                    handleCreate();
                }}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={actionLoading || !newName.trim()}
            >
              {actionLoading ? (
                <>
                  <Loader2 className="size-3.5 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Plus className="size-3.5" />
                  Create Dataset
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dataset cards */}
      {datasets.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-16 text-center">
          <div className="mb-4 flex size-14 items-center justify-center rounded-full bg-muted">
            <FolderOpen className="size-7 text-muted-foreground" />
          </div>
          <h3 className="mb-1 text-base font-medium">No datasets yet</h3>
          <p className="mb-6 max-w-sm text-sm text-muted-foreground">
            Create your first dataset to begin fine-tuning. Each dataset can
            contain documents, text content, and URL references.
          </p>
          <Button onClick={openCreateDialog}>
            <Plus className="size-4" />
            Create Your First Dataset
          </Button>
        </div>
      ) : filteredDatasets.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed py-12 text-center">
          <Search className="mb-3 size-8 text-muted-foreground/50" />
          <p className="text-sm font-medium">No matching datasets</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Try a different search term.
          </p>
          <Button
            variant="ghost"
            size="sm"
            className="mt-3"
            onClick={() => setSearchQuery("")}
          >
            Clear search
          </Button>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filteredDatasets.map((ds) => (
            <Card
              key={ds.id}
              className="cursor-pointer transition-all hover:ring-2 hover:ring-primary/30"
              onClick={() => fetchDetail(ds.id)}
            >
              <CardHeader>
                <CardTitle className="text-sm">{ds.name}</CardTitle>
                <CardDescription className="line-clamp-2 text-xs">
                  {ds.description || "No description"}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span
                      className={`rounded-md px-1.5 py-0.5 text-[10px] font-medium ${
                        ds.status === "active"
                          ? "bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300"
                          : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
                      }`}
                    >
                      {ds.status}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      v{ds.version} · {ds.source_count} source
                      {ds.source_count !== 1 ? "s" : ""}
                    </span>
                  </div>
                  <span className="text-[10px] text-muted-foreground">
                    {formatDate(ds.updated_at)}
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
