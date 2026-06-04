"use client";

import { useSession } from "next-auth/react";
import { useCallback, useEffect, useRef, useState } from "react";
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
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { fetchWithAuth, getApiUrl, getSessionToken } from "@/lib/api";

/* ── Types ─────────────────────────────────────────────────────────── */

interface StepData {
  step: number;
  loss: number;
  learning_rate?: number;
  epoch?: number;
}

interface EpochData {
  epoch: number;
  avg_loss: number;
  eval_loss?: number;
}

interface EvalData {
  faithfulness?: number;
  context_relevance?: number;
  answer_relevance?: number;
  context_recall?: number;
}

interface CompleteData {
  final_loss?: number;
  adapter_path?: string;
  cost?: number;
  duration_seconds?: number;
  total_steps?: number;
}

interface JobState {
  status: string;
  model_id: string;
  dataset_id: string;
  queue_position?: number | null;
  training_metrics?: Record<string, unknown> | null;
  eval_report?: Record<string, unknown> | null;
}

/* ── Constants ──────────────────────────────────────────────────────── */

const STATUS_COLORS: Record<string, string> = {
  queued: "text-yellow-600",
  training: "text-blue-600",
  evaluating: "text-purple-600",
  completed: "text-green-600",
  failed: "text-red-600",
};

/* ── Component ─────────────────────────────────────────────────────── */

export default function JobDetailPage() {
  const { data: session, status: authStatus } = useSession();
  const params = useParams();
  const router = useRouter();
  const jobId = params.jobId as string;

  const [job, setJob] = useState<JobState | null>(null);
  const [steps, setSteps] = useState<StepData[]>([]);
  const [epochs, setEpochs] = useState<EpochData[]>([]);
  const [evalMetrics, setEvalMetrics] = useState<EvalData | null>(null);
  const [completeData, setCompleteData] = useState<CompleteData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // Fetch initial job state via REST
  const fetchJob = useCallback(async () => {
    try {
      const res = await fetchWithAuth(`/api/v1/fine-tune/status/${jobId}`);
      if (res.ok) {
        const data = await res.json();
        setJob({
          status: data.status,
          model_id: data.model_id,
          dataset_id: data.dataset_id,
          queue_position: data.queue_position,
          training_metrics: data.training_metrics,
          eval_report: data.eval_report,
        });
      } else {
        setError("Failed to load job status");
      }
    } catch (err) {
      setError((err as Error).message);
    }
  }, [jobId]);

  // WebSocket connection
  const connectWS = useCallback(() => {
    const token = getSessionToken();
    if (!token || !jobId) return;

    const wsUrl = getApiUrl().replace(/^http/, "ws");
    const ws = new WebSocket(`${wsUrl}/ws/fine-tune/${jobId}?token=${token}`);
    wsRef.current = ws;

    ws.onopen = () => setWsConnected(true);
    ws.onclose = () => setWsConnected(false);
    ws.onerror = () => setWsConnected(false);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        switch (msg.type) {
          case "connected":
            setJob((prev) =>
              prev
                ? { ...prev, ...msg.data }
                : { status: "connected", model_id: "", dataset_id: "", ...msg.data }
            );
            break;
          case "step":
            setSteps((prev) => [...prev, msg.data as StepData]);
            break;
          case "epoch":
            setEpochs((prev) => [...prev, msg.data as EpochData]);
            setJob((prev) => prev ? { ...prev, status: "training" } : prev);
            break;
          case "eval":
            setEvalMetrics(msg.data as EvalData);
            setJob((prev) => prev ? { ...prev, status: "evaluating" } : prev);
            break;
          case "complete":
            setCompleteData(msg.data as CompleteData);
            setJob((prev) => prev ? { ...prev, status: "completed" } : prev);
            break;
          case "error":
            setError(msg.data?.message || "Training error");
            setJob((prev) => prev ? { ...prev, status: "failed" } : prev);
            break;
        }
      } catch {
        // Ignore parse errors
      }
    };

    return () => {
      ws.close();
    };
  }, [jobId]);

  useEffect(() => {
    if (authStatus === "authenticated" && jobId) {
      fetchJob();
      const cleanup = connectWS();
      return cleanup;
    }
  }, [authStatus, jobId, fetchJob, connectWS]);

  /* ── Render guards ──────────────────────────────────────────────── */

  if (authStatus === "loading") {
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
        </Card>
      </div>
    );
  }

  /* ── Render ─────────────────────────────────────────────────────── */

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Fine-tune Job</h1>
          <p className="text-xs text-muted-foreground font-mono">{jobId}</p>
        </div>
        <div className="flex items-center gap-3">
          <div
            className={`h-2 w-2 rounded-full ${
              wsConnected ? "bg-green-500" : "bg-gray-400"
            }`}
            title={wsConnected ? "WebSocket connected" : "WebSocket disconnected"}
          />
          <Button variant="outline" size="sm" onClick={() => router.push("/models")}>
            Back to Models
          </Button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {error}
        </div>
      )}

      {/* Job status card */}
      {job && (
        <Card className="mb-6">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">Job Status</CardTitle>
              <span
                className={`text-sm font-semibold uppercase ${
                  STATUS_COLORS[job.status] || "text-gray-600"
                }`}
              >
                {job.status}
              </span>
            </div>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            <div>
              <p className="text-muted-foreground text-xs">Model</p>
              <p className="font-medium">{job.model_id}</p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs">Dataset</p>
              <p className="font-mono text-xs">{job.dataset_id.slice(0, 8)}...</p>
            </div>
            {job.queue_position != null && (
              <div>
                <p className="text-muted-foreground text-xs">Queue Position</p>
                <p className="font-medium">{job.queue_position}</p>
              </div>
            )}
            <div>
              <p className="text-muted-foreground text-xs">Steps</p>
              <p className="font-medium">{steps.length}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Loss chart */}
      <Card className="mb-6">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Training Loss</CardTitle>
          <CardDescription>
            {steps.length > 0
              ? `${steps.length} steps recorded`
              : "Waiting for training data..."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {steps.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={steps}>
                <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                <XAxis dataKey="step" fontSize={11} />
                <YAxis fontSize={11} domain={["auto", "auto"]} />
                <Tooltip
                  contentStyle={{ fontSize: "12px" }}
                  formatter={(value) => [Number(value).toFixed(4), "Loss"]}
                />
                <Line
                  type="monotone"
                  dataKey="loss"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
              {job?.status === "queued"
                ? "Job is queued — waiting for GPU..."
                : "No training steps yet"}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Epoch progress */}
      {epochs.length > 0 && (
        <Card className="mb-6">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Epoch Progress</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {epochs.map((ep) => (
                <div key={ep.epoch} className="flex items-center justify-between text-sm">
                  <span>Epoch {ep.epoch}</span>
                  <div className="flex gap-4">
                    <span className="text-muted-foreground">
                      Avg loss: {ep.avg_loss.toFixed(4)}
                    </span>
                    {ep.eval_loss != null && (
                      <span className="text-muted-foreground">
                        Eval loss: {ep.eval_loss.toFixed(4)}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Eval metrics */}
      {evalMetrics && (
        <Card className="mb-6">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Evaluation Metrics</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            {Object.entries(evalMetrics).map(([key, value]) => (
              <div key={key}>
                <p className="text-xs text-muted-foreground capitalize">
                  {key.replace("_", " ")}
                </p>
                <p className="text-lg font-semibold">
                  {value != null ? (value * 100).toFixed(1) + "%" : "—"}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Completion card */}
      {completeData && (
        <Card className="mb-6 border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-green-800 dark:text-green-200">
              Training Complete
            </CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            {completeData.final_loss != null && (
              <div>
                <p className="text-xs text-muted-foreground">Final Loss</p>
                <p className="font-medium">{completeData.final_loss.toFixed(4)}</p>
              </div>
            )}
            {completeData.cost != null && (
              <div>
                <p className="text-xs text-muted-foreground">Cost</p>
                <p className="font-medium">${completeData.cost.toFixed(2)}</p>
              </div>
            )}
            {completeData.duration_seconds != null && (
              <div>
                <p className="text-xs text-muted-foreground">Duration</p>
                <p className="font-medium">
                  {Math.round(completeData.duration_seconds / 60)} min
                </p>
              </div>
            )}
            {completeData.total_steps != null && (
              <div>
                <p className="text-xs text-muted-foreground">Total Steps</p>
                <p className="font-medium">{completeData.total_steps}</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
