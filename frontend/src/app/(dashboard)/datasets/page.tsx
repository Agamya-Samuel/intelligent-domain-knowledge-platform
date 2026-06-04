"use client";

import { useSession } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";
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

/* ── API Helper ────────────────────────────────────────────────────── */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getSessionToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith("next-auth.session-token="));
  return match ? match.split("=")[1] : undefined;
}

async function fetchWithAuth(
  url: string,
  options: RequestInit = {},
): Promise<Response> {
  const token = getSessionToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  return fetch(`${API_URL}${url}`, { ...options, headers, credentials: "include" });
}

/* ── Datasets Page Component ──────────────────────────────────────── */

export default function DatasetsPage() {
  const { data: session, status } = useSession();
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<DatasetDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Create dataset form state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");

  // Add source form state
  const [showAddSource, setShowAddSource] = useState(false);
  const [sourceText, setSourceText] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");

  // Fetch datasets
  const fetchDatasets = useCallback(async () => {
    try {
      const res = await fetchWithAuth("/api/v1/datasets");
      if (res.ok) {
        setDatasets(await res.json());
      }
    } catch (err) {
      console.error("Failed to fetch datasets:", err);
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
    if (!newName.trim()) return;
    setActionLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth("/api/v1/datasets", {
        method: "POST",
        body: JSON.stringify({ name: newName.trim(), description: newDescription.trim() || undefined }),
      });
      if (res.ok) {
        setShowCreateForm(false);
        setNewName("");
        setNewDescription("");
        await fetchDatasets();
      } else {
        const data = await res.json();
        setError(data.detail || "Failed to create dataset");
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setActionLoading(false);
    }
  };

  // Archive dataset
  const handleArchive = async (datasetId: string) => {
    if (!confirm("Archive this dataset? It will no longer be available for fine-tuning.")) return;
    setActionLoading(true);
    try {
      const res = await fetchWithAuth(`/api/v1/datasets/${datasetId}/archive`, {
        method: "POST",
      });
      if (res.ok) {
        setSelectedDataset(null);
        await fetchDatasets();
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setActionLoading(false);
    }
  };

  // Add text source
  const handleAddTextSource = async () => {
    if (!selectedDataset || !sourceText.trim()) return;
    setActionLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth(
        `/api/v1/datasets/${selectedDataset.id}/sources?source_type=text&text_content=${encodeURIComponent(sourceText)}`,
        { method: "POST" },
      );
      if (res.ok) {
        setShowAddSource(false);
        setSourceText("");
        await fetchDetail(selectedDataset.id);
        await fetchDatasets();
      } else {
        const data = await res.json();
        setError(data.detail || "Failed to add source");
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setActionLoading(false);
    }
  };

  // Add URL source
  const handleAddUrlSource = async () => {
    if (!selectedDataset || !sourceUrl.trim()) return;
    setActionLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth(
        `/api/v1/datasets/${selectedDataset.id}/sources?source_type=url&source_path=${encodeURIComponent(sourceUrl)}`,
        { method: "POST" },
      );
      if (res.ok) {
        setShowAddSource(false);
        setSourceUrl("");
        await fetchDetail(selectedDataset.id);
        await fetchDatasets();
      } else {
        const data = await res.json();
        setError(data.detail || "Failed to add source");
      }
    } catch (err) {
      setError((err as Error).message);
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
        { method: "DELETE" },
      );
      if (res.ok) {
        await fetchDetail(selectedDataset.id);
        await fetchDatasets();
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setActionLoading(false);
    }
  };

  // Auth/loading guards
  if (status === "loading" || loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="text-center">Sign in required</CardTitle>
          </CardHeader>
          <CardContent className="text-center text-sm text-muted-foreground">
            Please sign in to manage datasets.
          </CardContent>
        </Card>
      </div>
    );
  }

  /* ── Detail View ────────────────────────────────────────────────── */
  if (selectedDataset) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{selectedDataset.name}</h1>
            <p className="text-sm text-muted-foreground">
              v{selectedDataset.version} &middot; {selectedDataset.status} &middot; {selectedDataset.sources.length} sources
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => setSelectedDataset(null)}>
              Back
            </Button>
            {selectedDataset.status === "active" && (
              <Button
                variant="destructive"
                size="sm"
                onClick={() => handleArchive(selectedDataset.id)}
                disabled={actionLoading}
              >
                Archive
              </Button>
            )}
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
            {error}
            <button className="ml-2 text-xs underline" onClick={() => setError(null)} type="button">
              Dismiss
            </button>
          </div>
        )}

        {/* Description */}
        {selectedDataset.description && (
          <Card className="mb-4">
            <CardContent className="pt-4">
              <p className="text-sm text-muted-foreground">{selectedDataset.description}</p>
            </CardContent>
          </Card>
        )}

        {/* Sources */}
        <Card className="mb-4">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-base">Sources</CardTitle>
              <CardDescription>Documents and data in this dataset</CardDescription>
            </div>
            {selectedDataset.status === "active" && (
              <Button size="sm" onClick={() => setShowAddSource(!showAddSource)}>
                {showAddSource ? "Cancel" : "Add Source"}
              </Button>
            )}
          </CardHeader>
          <CardContent>
            {showAddSource && (
              <div className="mb-4 space-y-3 rounded-lg border p-3">
                <div className="space-y-1">
                  <Label htmlFor="source-text" className="text-xs">Text Content</Label>
                  <textarea
                    id="source-text"
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm min-h-[80px]"
                    placeholder="Paste text content..."
                    value={sourceText}
                    onChange={(e) => setSourceText(e.target.value)}
                  />
                  <Button size="sm" onClick={handleAddTextSource} disabled={actionLoading || !sourceText.trim()}>
                    Add Text
                  </Button>
                </div>
                <div className="border-t pt-3 space-y-1">
                  <Label htmlFor="source-url" className="text-xs">URL</Label>
                  <div className="flex gap-2">
                    <Input
                      id="source-url"
                      placeholder="https://example.com/doc"
                      value={sourceUrl}
                      onChange={(e) => setSourceUrl(e.target.value)}
                    />
                    <Button size="sm" onClick={handleAddUrlSource} disabled={actionLoading || !sourceUrl.trim()}>
                      Add URL
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {selectedDataset.sources.length === 0 ? (
              <p className="text-sm text-muted-foreground">No sources added yet.</p>
            ) : (
              <div className="overflow-x-auto rounded-lg border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium text-xs">Name</th>
                      <th className="px-3 py-2 text-left font-medium text-xs">Type</th>
                      <th className="px-3 py-2 text-left font-medium text-xs">Version</th>
                      <th className="px-3 py-2 text-left font-medium text-xs">Status</th>
                      <th className="px-3 py-2 text-right font-medium text-xs">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedDataset.sources.map((source) => (
                      <tr key={source.id} className="border-t">
                        <td className="px-3 py-2 text-xs">
                          {source.file_name || source.source_path.slice(-40)}
                        </td>
                        <td className="px-3 py-2">
                          <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium">
                            {source.source_type}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-xs">v{source.dataset_version}</td>
                        <td className="px-3 py-2 text-xs">
                          <span className={source.processed ? "text-green-600" : "text-yellow-600"}>
                            {source.processing_error ? "Failed" : source.processed ? "Processed" : "Pending"}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right">
                          {selectedDataset.status === "active" && (
                            <button
                              className="text-xs text-red-600 hover:underline"
                              onClick={() => handleRemoveSource(source.id)}
                              disabled={actionLoading}
                            >
                              Remove
                            </button>
                          )}
                        </td>
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
            <CardTitle className="text-base">Version History</CardTitle>
            <CardDescription>Track changes over time</CardDescription>
          </CardHeader>
          <CardContent>
            {selectedDataset.version_history.length === 0 ? (
              <p className="text-sm text-muted-foreground">No version history.</p>
            ) : (
              <div className="overflow-x-auto rounded-lg border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium text-xs">Version</th>
                      <th className="px-3 py-2 text-left font-medium text-xs">Description</th>
                      <th className="px-3 py-2 text-right font-medium text-xs">Sources</th>
                      <th className="px-3 py-2 text-left font-medium text-xs">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedDataset.version_history.slice().reverse().map((vh) => (
                      <tr key={vh.id} className="border-t">
                        <td className="px-3 py-2 text-xs font-medium">v{vh.version}</td>
                        <td className="px-3 py-2 text-xs text-muted-foreground">
                          {vh.change_description || "—"}
                        </td>
                        <td className="px-3 py-2 text-right text-xs">
                          {vh.source_count ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-xs">
                          {new Date(vh.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  /* ── List View ──────────────────────────────────────────────────── */
  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Datasets</h1>
          <p className="text-sm text-muted-foreground">
            Manage versioned datasets for fine-tuning.
          </p>
        </div>
        <Button onClick={() => setShowCreateForm(!showCreateForm)}>
          {showCreateForm ? "Cancel" : "Create Dataset"}
        </Button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {error}
          <button className="ml-2 text-xs underline" onClick={() => setError(null)} type="button">
            Dismiss
          </button>
        </div>
      )}

      {/* Create form */}
      {showCreateForm && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base">New Dataset</CardTitle>
            <CardDescription>Create a dataset to hold documents for fine-tuning.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="ds-name">Name</Label>
              <Input
                id="ds-name"
                placeholder="e.g., Medical Research Papers"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="ds-desc">Description (optional)</Label>
              <textarea
                id="ds-desc"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm min-h-[60px]"
                placeholder="Describe the dataset contents..."
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
              />
            </div>
            <div className="flex gap-2">
              <Button
                onClick={handleCreate}
                disabled={actionLoading || !newName.trim()}
              >
                {actionLoading ? "Creating..." : "Create"}
              </Button>
              <Button variant="outline" onClick={() => setShowCreateForm(false)}>
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Dataset cards */}
      {datasets.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">No datasets yet</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Create your first dataset to begin fine-tuning. Each dataset can
              contain documents from multiple domains and supports file uploads,
              text content, and URL references.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {datasets.map((ds) => (
            <Card
              key={ds.id}
              className="cursor-pointer hover:ring-2 hover:ring-primary transition-all"
              onClick={() => fetchDetail(ds.id)}
            >
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">{ds.name}</CardTitle>
                <CardDescription>
                  v{ds.version} &middot; {ds.source_count} source{ds.source_count !== 1 ? "s" : ""}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-1 text-xs text-muted-foreground">
                <div className="flex items-center justify-between">
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                      ds.status === "active"
                        ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                        : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
                    }`}
                  >
                    {ds.status}
                  </span>
                  <span>{new Date(ds.updated_at).toLocaleDateString()}</span>
                </div>
                {ds.description && (
                  <p className="truncate">{ds.description}</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
