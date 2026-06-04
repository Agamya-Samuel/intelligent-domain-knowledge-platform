"use client";

import { useSession } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fetchWithAuth } from "@/lib/api";
import {
  Plus,
  Archive,
  Trash2,
  FileText,
  Link as LinkIcon,
  ChevronRight,
  AlertCircle,
  CheckCircle2,
  Loader2,
} from "lucide-react";

/* ── Types ─────────────────────────────────────────────────────────── */

interface DatasetDetail {
  id: string;
  name: string;
  description: string | null;
  version: number;
  status: string;
  source_count: number;
  created_at: string;
  updated_at: string;
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

/* ── Dataset Detail Page Component ─────────────────────────────────── */

export default function DatasetDetailPage() {
  const { data: session, status } = useSession();
  const params = useParams();
  const router = useRouter();
  const datasetId = params.datasetId as string;

  const [dataset, setDataset] = useState<DatasetDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Toast state
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error";
  } | null>(null);

  // Archive confirm dialog
  const [showArchiveConfirm, setShowArchiveConfirm] = useState(false);

  // Add source dialog
  const [showAddSourceDialog, setShowAddSourceDialog] = useState(false);
  const [sourceTab, setSourceTab] = useState<"text" | "url">("text");
  const [sourceText, setSourceText] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");

  // Fetch dataset detail
  const fetchDetail = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth(`/api/v1/datasets/${datasetId}`);
      if (res.ok) {
        setDataset(await res.json());
      } else {
        setError("Failed to load dataset details");
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [datasetId]);

  useEffect(() => {
    if (status === "authenticated") fetchDetail();
    else if (status === "unauthenticated") setLoading(false);
  }, [status, fetchDetail]);

  // Archive dataset
  const handleArchive = async () => {
    if (!dataset) return;
    setActionLoading(true);
    try {
      const res = await fetchWithAuth(
        `/api/v1/datasets/${dataset.id}/archive`,
        { method: "POST" }
      );
      if (res.ok) {
        setShowArchiveConfirm(false);
        setToast({ message: "Dataset archived", type: "success" });
        router.push("/datasets");
      }
    } catch (err) {
      setToast({ message: (err as Error).message, type: "error" });
    } finally {
      setActionLoading(false);
    }
  };

  // Add text source
  const handleAddTextSource = async () => {
    if (!dataset || !sourceText.trim()) return;
    setActionLoading(true);
    try {
      const res = await fetchWithAuth(
        `/api/v1/datasets/${dataset.id}/sources?source_type=text&text_content=${encodeURIComponent(sourceText)}`,
        { method: "POST" }
      );
      if (res.ok) {
        setShowAddSourceDialog(false);
        setSourceText("");
        setToast({ message: "Source added", type: "success" });
        await fetchDetail();
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
    if (!dataset || !sourceUrl.trim()) return;
    setActionLoading(true);
    try {
      const res = await fetchWithAuth(
        `/api/v1/datasets/${dataset.id}/sources?source_type=url&source_path=${encodeURIComponent(sourceUrl)}`,
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
        await fetchDetail();
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
    if (!dataset) return;
    setActionLoading(true);
    try {
      const res = await fetchWithAuth(
        `/api/v1/datasets/${dataset.id}/sources/${sourceId}`,
        { method: "DELETE" }
      );
      if (res.ok) {
        setToast({ message: "Source removed", type: "success" });
        await fetchDetail();
      }
    } catch (err) {
      setToast({ message: (err as Error).message, type: "error" });
    } finally {
      setActionLoading(false);
    }
  };

  // Auth/loading guards
  if (status === "loading" || loading) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <div className="mb-6">
          <div className="mb-2 h-8 w-40 animate-pulse rounded bg-muted" />
          <div className="h-4 w-64 animate-pulse rounded bg-muted" />
        </div>
      </div>
    );
  }

  if (!session || !dataset) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-center">
              {!session ? "Sign in required" : "Dataset not found"}
            </CardTitle>
            <CardDescription className="text-center">
              {!session
                ? "Please sign in to view dataset details."
                : "The dataset you're looking for doesn't exist or you don't have access."}
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

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
            onClick={() => router.push("/datasets")}
            className="mb-2 flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            <ChevronRight className="size-3 rotate-180" />
            Back to datasets
          </button>
          <h1 className="text-2xl font-semibold tracking-tight">
            {dataset.name}
          </h1>
          <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
            <span className="rounded-md bg-muted px-1.5 py-0.5 text-xs font-medium">
              v{dataset.version}
            </span>
            <span
              className={`rounded-md px-1.5 py-0.5 text-xs font-medium ${
                dataset.status === "active"
                  ? "bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-300"
                  : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
              }`}
            >
              {dataset.status}
            </span>
            <span>·</span>
            <span>
              {dataset.sources.length} source
              {dataset.sources.length !== 1 ? "s" : ""}
            </span>
            <span>·</span>
            <span>Created {formatDate(dataset.created_at)}</span>
          </div>
        </div>
        <div className="flex gap-2">
          {dataset.status === "active" && (
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
      {dataset.description && (
        <Card className="mb-4" size="sm">
          <CardContent className="text-sm text-muted-foreground">
            {dataset.description}
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
          {dataset.sources.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <FileText className="mb-3 size-10 text-muted-foreground/50" />
              <p className="text-sm font-medium">No sources yet</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Add text content or URLs to build your dataset.
              </p>
              {dataset.status === "active" && (
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
                    {dataset.status === "active" && (
                      <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">
                        Actions
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {dataset.sources.map((source) => (
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
                      {dataset.status === "active" && (
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
          {dataset.version_history.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">
              No version history.
            </p>
          ) : (
            <div className="space-y-0">
              {dataset.version_history
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
              Are you sure you want to archive &ldquo;{dataset.name}
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