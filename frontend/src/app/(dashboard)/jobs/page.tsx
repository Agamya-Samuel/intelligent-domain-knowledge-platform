"use client";

import { useSession } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
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
import { fetchWithAuth } from "@/lib/api";
import { XCircle, Trash2 } from "lucide-react";

interface JobInfo {
  id: string;
  user_id: string;
  model_id: string;
  dataset_id: string;
  dataset_version: number;
  status: string;
  queue_position: number | null;
  training_metrics: Record<string, unknown> | null;
  eval_report: Record<string, unknown> | null;
  cost: number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

interface BudgetSummary {
  total_spend: number;
  remaining: number;
  budget_limit: number;
  runs_this_month: number;
  estimated_runs_left: number;
}

interface ModelInfo {
  id: string;
  name: string;
  est_cost: number;
  est_time_min: number;
}

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  queued: { bg: "bg-yellow-100", text: "text-yellow-800" },
  training: { bg: "bg-blue-100", text: "text-blue-800" },
  evaluating: { bg: "bg-purple-100", text: "text-purple-800" },
  completed: { bg: "bg-green-100", text: "text-green-800" },
  failed: { bg: "bg-red-100", text: "text-red-800" },
  cancelled: { bg: "bg-gray-100", text: "text-gray-800" },
};

export default function JobsPage() {
  const { data: session, status } = useSession();
  const [jobs, setJobs] = useState<JobInfo[]>([]);
  const [budget, setBudget] = useState<BudgetSummary | null>(null);
  const [models, setModels] = useState<Record<string, ModelInfo>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Cancel/Delete dialog state
  const [cancelJobId, setCancelJobId] = useState<string | null>(null);
  const [deleteJobId, setDeleteJobId] = useState<string | null>(null);

  // Toast notification
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [jobsRes, budgetRes, modelsRes] = await Promise.all([
        fetchWithAuth("/api/v1/fine-tune/history"),
        fetchWithAuth("/api/v1/budget"),
        fetchWithAuth("/api/v1/models"),
      ]);

      if (jobsRes.ok) {
        const jobsData = await jobsRes.json();
        setJobs(jobsData.jobs || []);
      }

      if (budgetRes.ok) {
        setBudget(await budgetRes.json());
      }

      if (modelsRes.ok) {
        const modelsData = await modelsRes.json();
        const modelsMap: Record<string, ModelInfo> = {};
        for (const m of modelsData.models || []) {
          modelsMap[m.id] = m;
        }
        setModels(modelsMap);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (status === "authenticated") {
      fetchData();
    } else if (status === "unauthenticated") {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    const hasActiveJobs = jobs.some(
      (j) => j.status === "queued" || j.status === "training" || j.status === "evaluating"
    );
    if (!hasActiveJobs || status !== "authenticated") return;

    const interval = setInterval(() => {
      fetchData();
    }, 10000);
    return () => clearInterval(interval);
  }, [jobs, status]);

  const formatDuration = (startedAt: string | null, completedAt: string | null): string => {
    if (!startedAt) return "-";
    const start = new Date(startedAt);
    const end = completedAt ? new Date(completedAt) : new Date();
    const diff = Math.floor((end.getTime() - start.getTime()) / 1000 / 60);
    return `${diff} min`;
  };

  const formatETA = (job: JobInfo): string => {
    if (job.status === "completed" || job.status === "failed" || job.status === "cancelled") return "-";
    if (job.status === "queued" && job.queue_position != null) {
      return `Position ${job.queue_position}`;
    }
    if (job.status === "training" || job.status === "evaluating") {
      const model = models[job.model_id];
      if (!model || !job.started_at) return "Calculating...";
      const start = new Date(job.started_at);
      const elapsedMin = (new Date().getTime() - start.getTime()) / 1000 / 60;
      const remaining = Math.max(0, model.est_time_min - elapsedMin);
      return `${Math.ceil(remaining)} min`;
    }
    return "-";
  };

  // Cancel job handler
  const handleCancelJob = async () => {
    if (!cancelJobId) return;
    setActionLoading(true);
    try {
      const res = await fetchWithAuth(`/api/v1/fine-tune/${cancelJobId}/cancel`, {
        method: "POST",
      });
      if (res.ok) {
        setToast({ message: "Job cancelled successfully", type: "success" });
        await fetchData();
      } else {
        const data = await res.json();
        setToast({ message: data.detail || "Failed to cancel job", type: "error" });
      }
    } catch (err) {
      setToast({ message: (err as Error).message, type: "error" });
    } finally {
      setActionLoading(false);
      setCancelJobId(null);
    }
  };

  // Delete job handler
  const handleDeleteJob = async () => {
    if (!deleteJobId) return;
    setActionLoading(true);
    try {
      const res = await fetchWithAuth(`/api/v1/fine-tune/${deleteJobId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setToast({ message: "Job deleted successfully", type: "success" });
        await fetchData();
      } else {
        const data = await res.json();
        setToast({ message: data.detail || "Failed to delete job", type: "error" });
      }
    } catch (err) {
      setToast({ message: (err as Error).message, type: "error" });
    } finally {
      setActionLoading(false);
      setDeleteJobId(null);
    }
  };

  // Auto-dismiss toast after 3 seconds
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(timer);
  }, [toast]);

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
            Please sign in to view your fine-tuning jobs.
          </CardContent>
        </Card>
      </div>
    );
  }

  const stats = {
    total: jobs.length,
    queued: jobs.filter((j) => j.status === "queued").length,
    training: jobs.filter((j) => j.status === "training").length,
    completed: jobs.filter((j) => j.status === "completed").length,
    failed: jobs.filter((j) => j.status === "failed").length,
    totalCost: jobs.reduce((sum, j) => sum + (j.cost || 0), 0),
  };

  const hasActiveJobs = jobs.some(
    (j) => j.status === "queued" || j.status === "training" || j.status === "evaluating"
  );

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Fine-tuning Jobs</h1>
          <p className="text-sm text-muted-foreground">
            View all your fine-tuning jobs and their status.
            {hasActiveJobs && " Auto-refreshing every 10s."}
          </p>
        </div>
        <Button variant="outline" onClick={fetchData}>
          Refresh
        </Button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {error}
          <button
            className="ml-2 text-xs underline"
            onClick={() => setError(null)}
            type="button"
          >
            Dismiss
          </button>
        </div>
      )}

      {budget && (
        <Card className="mb-6">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Budget Overview</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-sm font-medium">
                  ${budget.total_spend.toFixed(2)}
                  <span className="ml-1 text-sm font-normal text-muted-foreground">
                    / ${budget.budget_limit.toFixed(2)}
                  </span>
                </p>
              </div>
              <div className="text-right">
                <p className="text-sm text-muted-foreground">
                  {budget.estimated_runs_left} estimated runs remaining
                </p>
              </div>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{
                  width: `${Math.min((budget.total_spend / budget.budget_limit) * 100, 100)}%`,
                }}
              />
            </div>
          </CardContent>
        </Card>
      )}

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Total Jobs</CardDescription>
            <CardTitle className="text-2xl">{stats.total}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Queued</CardDescription>
            <CardTitle className="text-2xl">{stats.queued}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Training</CardDescription>
            <CardTitle className="text-2xl">{stats.training}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Completed</CardDescription>
            <CardTitle className="text-2xl">{stats.completed}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="text-xs">Failed</CardDescription>
            <CardTitle className="text-2xl">{stats.failed}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Job History</CardTitle>
        </CardHeader>
        <CardContent>
          {jobs.length === 0 ? (
            <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
              No fine-tuning jobs yet. Start your first job from the Models or Fine-tune page.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="pb-2 text-left font-medium">Model</th>
                    <th className="pb-2 text-left font-medium">Dataset</th>
                    <th className="pb-2 text-left font-medium">Status</th>
                    <th className="pb-2 text-left font-medium">Queue</th>
                    <th className="pb-2 text-left font-medium">ETA</th>
                    <th className="pb-2 text-left font-medium">Duration</th>
                    <th className="pb-2 text-left font-medium">Cost</th>
                    <th className="pb-2 text-left font-medium">Created</th>
                    <th className="pb-2 text-left font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr key={job.id} className="border-b last:border-0">
                      <td className="py-3">
                        <p className="font-medium">{models[job.model_id]?.name || job.model_id}</p>
                      </td>
                      <td className="py-3">
                        <p className="font-mono text-xs">{job.dataset_id.slice(0, 8)}...</p>
                      </td>
                      <td className="py-3">
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                            STATUS_COLORS[job.status]?.bg || "bg-gray-100"
                          } ${STATUS_COLORS[job.status]?.text || "text-gray-800"}`}
                        >
                          {job.status}
                        </span>
                        {job.error_message && (
                          <p className="mt-1 text-xs text-red-600 max-w-[200px] truncate">
                            {job.error_message}
                          </p>
                        )}
                      </td>
                      <td className="py-3">
                        {job.queue_position != null ? job.queue_position : "-"}
                      </td>
                      <td className="py-3">
                        {formatETA(job)}
                      </td>
                      <td className="py-3">
                        {formatDuration(job.started_at, job.completed_at)}
                      </td>
                      <td className="py-3">
                        {job.cost != null ? `$${job.cost.toFixed(2)}` : "-"}
                      </td>
                      <td className="py-3 text-muted-foreground">
                        {new Date(job.created_at).toLocaleString()}
                      </td>
                      <td className="py-3">
                        <div className="flex items-center gap-2">
                          <Link href={`/fine-tune/${job.id}`}>
                            <Button variant="outline" size="sm">
                              View
                            </Button>
                          </Link>
                          {/* Cancel button for active jobs */}
                          {(job.status === "queued" ||
                            job.status === "training" ||
                            job.status === "evaluating") && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="text-destructive hover:bg-destructive/10"
                              onClick={() => setCancelJobId(job.id)}
                              disabled={actionLoading}
                            >
                              <XCircle className="mr-1 size-3" />
                              Cancel
                            </Button>
                          )}
                          {/* Delete button for terminal jobs */}
                          {(job.status === "completed" ||
                            job.status === "failed" ||
                            job.status === "cancelled") && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                              onClick={() => setDeleteJobId(job.id)}
                              disabled={actionLoading}
                            >
                              <Trash2 className="mr-1 size-3" />
                              Delete
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Cancel Confirmation Dialog */}
      <Dialog open={cancelJobId !== null} onOpenChange={(open) => !open && setCancelJobId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel Job</DialogTitle>
            <DialogDescription>
              Are you sure you want to cancel this fine-tuning job? This action cannot be undone.
              {cancelJobId && jobs.find((j) => j.id === cancelJobId)?.status === "training" && (
                <span className="mt-2 block text-yellow-600 dark:text-yellow-400">
                  This job is currently training. Cancelling will stop the GPU computation.
                </span>
              )}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCancelJobId(null)}
              disabled={actionLoading}
            >
              Keep Job
            </Button>
            <Button
              variant="destructive"
              onClick={handleCancelJob}
              disabled={actionLoading}
            >
              {actionLoading ? "Cancelling..." : "Cancel Job"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteJobId !== null} onOpenChange={(open) => !open && setDeleteJobId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Job</DialogTitle>
            <DialogDescription>
              Are you sure you want to permanently delete this job from your history? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteJobId(null)}
              disabled={actionLoading}
            >
              Keep Job
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteJob}
              disabled={actionLoading}
            >
              {actionLoading ? "Deleting..." : "Delete Job"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Toast Notification */}
      {toast && (
        <div
          className={`fixed bottom-4 right-4 z-50 rounded-lg p-4 text-sm shadow-lg transition-all ${
            toast.type === "success"
              ? "bg-green-600 text-white"
              : "bg-red-600 text-white"
          }`}
        >
          {toast.message}
        </div>
      )}
    </div>
  );
}