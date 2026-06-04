"use client";

import { useSession } from "next-auth/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
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
  const router = useRouter();
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
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
              onClick={() => router.push(`/datasets/${ds.id}`)}
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
