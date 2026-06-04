"use client";

import { useSession } from "next-auth/react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { fetchWithAuth } from "@/lib/api";

/* ── Types ─────────────────────────────────────────────────────────── */

interface ModelInfo {
  id: string;
  name: string;
  tier: number;
  size: string;
  gpu: string;
  vram_gb: number;
  est_cost: number;
  est_time_min: number;
  license: string;
  available: boolean;
  quality_rating?: number;
}

interface DatasetInfo {
  id: string;
  name: string;
  version: number;
  status: string;
  source_count: number;
}

interface CostEstimate {
  model_id: string;
  estimated_cost: number;
  estimated_time_min: number;
  dataset_sample_count: number;
  remaining_budget: number;
  within_budget: boolean;
}

interface TrainingPreview {
  dataset_id: string;
  dataset_version: number;
  total_samples: number;
  domain_samples: number;
  general_samples: number;
  by_type: Record<string, number>;
  preview_samples: Array<{
    instruction: string;
    input: string;
    output: string;
    domain: string;
    type: string;
  }>;
}

interface FineTuneResult {
  job_id: string;
  status: string;
  queue_position: number | null;
  estimated_cost: number | null;
}

/* ── Constants ──────────────────────────────────────────────────────── */

type Step = "model" | "dataset" | "preview" | "confirm" | "done";

/* ── Component ─────────────────────────────────────────────────────── */

export default function FineTunePage() {
  const { data: session, status } = useSession();

  const [step, setStep] = useState<Step>("model");
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState<ModelInfo | null>(null);
  const [selectedDataset, setSelectedDataset] = useState<DatasetInfo | null>(null);
  const [costEstimate, setCostEstimate] = useState<CostEstimate | null>(null);
  const [trainingPreview, setTrainingPreview] = useState<TrainingPreview | null>(null);
  const [ftResult, setFtResult] = useState<FineTuneResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pageLoading, setPageLoading] = useState(true);

  // Load models + datasets on mount
  const fetchData = useCallback(async () => {
    try {
      const [modelsRes, datasetsRes] = await Promise.all([
        fetchWithAuth("/api/v1/models"),
        fetchWithAuth("/api/v1/datasets"),
      ]);
      if (modelsRes.ok) {
        const d = await modelsRes.json();
        setModels(d.models.filter((m: ModelInfo) => m.available));
      }
      if (datasetsRes.ok) {
        const d = await datasetsRes.json();
        setDatasets(d.datasets.filter((ds: DatasetInfo) => ds.status === "active"));
      }
    } catch (err) {
      console.error("Failed to load models/datasets:", err);
    } finally {
      setPageLoading(false);
    }
  }, []);

  useEffect(() => {
    if (status === "authenticated") fetchData();
    else if (status === "unauthenticated") setPageLoading(false);
  }, [status, fetchData]);

  // Estimate cost when model + dataset selected
  const fetchEstimate = useCallback(async (modelId: string, datasetId: string) => {
    try {
      const [estRes, previewRes] = await Promise.all([
        fetchWithAuth(`/api/v1/fine-tune/estimate?model_id=${modelId}&dataset_id=${datasetId}`),
        fetchWithAuth(`/api/v1/fine-tune/training-data/preview?dataset_id=${datasetId}`),
      ]);
      if (estRes.ok) setCostEstimate(await estRes.json());
      if (previewRes.ok) setTrainingPreview(await previewRes.json());
    } catch (err) {
      console.error("Cost estimate failed:", err);
    }
  }, []);

  const handleSelectModel = (model: ModelInfo) => {
    setSelectedModel(model);
    setStep("dataset");
    setError(null);
  };

  const handleSelectDataset = async (dataset: DatasetInfo) => {
    if (!selectedModel) return;
    setSelectedDataset(dataset);
    setStep("preview");
    setLoading(true);
    await fetchEstimate(selectedModel.id, dataset.id);
    setLoading(false);
  };

  const handleConfirm = async () => {
    if (!selectedModel || !selectedDataset) return;
    setStep("confirm");
    setLoading(true);
    setError(null);
    try {
      const res = await fetchWithAuth("/api/v1/fine-tune", {
        method: "POST",
        body: JSON.stringify({
          model_id: selectedModel.id,
          dataset_id: selectedDataset.id,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setFtResult(data);
        setStep("done");
      } else {
        setError(data.detail?.message || data.detail || `HTTP ${res.status}`);
        setStep("preview");
      }
    } catch (err) {
      setError((err as Error).message);
      setStep("preview");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setStep("model");
    setSelectedModel(null);
    setSelectedDataset(null);
    setCostEstimate(null);
    setTrainingPreview(null);
    setFtResult(null);
    setError(null);
  };

  /* ── Auth / loading guards ────────────────────────────────────────── */

  if (status === "loading" || pageLoading) {
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
            Please sign in to trigger fine-tuning.
          </CardContent>
        </Card>
      </div>
    );
  }

  /* ── Step indicators ──────────────────────────────────────────────── */

  const steps: { key: Step; label: string }[] = [
    { key: "model", label: "1. Select Model" },
    { key: "dataset", label: "2. Select Dataset" },
    { key: "preview", label: "3. Cost Preview" },
    { key: "confirm", label: "4. Confirm" },
  ];

  /* ── Render ─────────────────────────────────────────────────────── */

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Fine-tune a Model</h1>
        <p className="text-sm text-muted-foreground">
          Follow the steps below to prepare and launch a QLoRA fine-tuning job.
        </p>
      </div>

      {/* Step indicator */}
      <div className="mb-8 flex gap-2">
        {steps.map((s) => (
          <div
            key={s.key}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              step === s.key
                ? "bg-primary text-primary-foreground"
                : steps.findIndex((x) => x.key === step) >
                    steps.findIndex((x) => x.key === s.key)
                  ? "bg-primary/20 text-primary"
                  : "bg-muted text-muted-foreground"
            }`}
          >
            {s.label}
          </div>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {error}
          <button className="ml-2 text-xs underline" onClick={() => setError(null)} type="button">
            Dismiss
          </button>
        </div>
      )}

      {/* ── Step 1: Select Model ──────────────────────────────────────── */}
      {step === "model" && (
        <div className="space-y-4">
          <h2 className="text-lg font-medium">Select a Model</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {models.map((model) => (
              <Card
                key={model.id}
                className="cursor-pointer hover:ring-2 hover:ring-primary transition-all"
                onClick={() => handleSelectModel(model)}
              >
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">{model.name}</CardTitle>
                  <CardDescription>
                    Tier {model.tier} &middot; {model.size}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-1 text-xs text-muted-foreground">
                  <p>GPU: {model.gpu} &middot; VRAM: {model.vram_gb} GB</p>
                  <p>Est. cost: ${model.est_cost.toFixed(2)} &middot; ~{model.est_time_min} min</p>
                  {model.quality_rating != null && (
                    <p>Quality: {(model.quality_rating * 100).toFixed(0)}%</p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
          {models.length === 0 && (
            <p className="text-sm text-muted-foreground">No available models found.</p>
          )}
        </div>
      )}

      {/* ── Step 2: Select Dataset ───────────────────────────────────── */}
      {step === "dataset" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium">Select a Dataset</h2>
            <Button variant="outline" size="sm" onClick={() => setStep("model")}>
              Back
            </Button>
          </div>
          <p className="text-sm text-muted-foreground">
            Selected model: <span className="font-medium">{selectedModel?.name}</span>
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {datasets.map((ds) => (
              <Card
                key={ds.id}
                className="cursor-pointer hover:ring-2 hover:ring-primary transition-all"
                onClick={() => handleSelectDataset(ds)}
              >
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">{ds.name}</CardTitle>
                  <CardDescription>
                    v{ds.version} &middot; {ds.source_count} sources
                  </CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
          {datasets.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No active datasets found. Create a dataset and add sources first.
            </p>
          )}
        </div>
      )}

      {/* ── Step 3: Cost Preview ─────────────────────────────────────── */}
      {step === "preview" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium">Cost &amp; Training Data Preview</h2>
            <Button variant="outline" size="sm" onClick={() => setStep("dataset")}>
              Back
            </Button>
          </div>

          {loading && <p className="text-sm text-muted-foreground">Calculating estimate...</p>}

          {costEstimate && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Cost Estimation</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Estimated cost</span>
                  <span className="font-medium">${costEstimate.estimated_cost.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Estimated time</span>
                  <span className="font-medium">~{costEstimate.estimated_time_min} min</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Remaining budget</span>
                  <span className="font-medium">${costEstimate.remaining_budget.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Training samples</span>
                  <span className="font-medium">{costEstimate.dataset_sample_count}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Within budget</span>
                  <span
                    className={`font-medium ${
                      costEstimate.within_budget ? "text-green-600" : "text-red-600"
                    }`}
                  >
                    {costEstimate.within_budget ? "Yes" : "No — budget exceeded"}
                  </span>
                </div>
              </CardContent>
            </Card>
          )}

          {trainingPreview && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Training Data Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-wrap gap-3 text-xs">
                  <span className="rounded bg-muted px-2 py-1">
                    Total: {trainingPreview.total_samples}
                  </span>
                  <span className="rounded bg-muted px-2 py-1">
                    Domain: {trainingPreview.domain_samples}
                  </span>
                  <span className="rounded bg-muted px-2 py-1">
                    General: {trainingPreview.general_samples}
                  </span>
                  {Object.entries(trainingPreview.by_type).map(([k, v]) => (
                    <span key={k} className="rounded bg-muted px-2 py-1">
                      {k}: {v}
                    </span>
                  ))}
                </div>

                {trainingPreview.preview_samples.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground">Sample preview:</p>
                    {trainingPreview.preview_samples.slice(0, 3).map((s, i) => (
                      <div
                        key={i}
                        className="rounded border p-2 text-xs space-y-1"
                      >
                        <p className="font-medium">[{s.type}] {s.instruction.slice(0, 80)}...</p>
                        <p className="text-muted-foreground truncate">
                          Input: {s.input.slice(0, 120)}...
                        </p>
                        <p className="text-muted-foreground truncate">
                          Output: {s.output.slice(0, 120)}...
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {costEstimate && (
            <div className="flex gap-3">
              <Button
                onClick={handleConfirm}
                disabled={!costEstimate.within_budget || loading}
              >
                {loading ? "Submitting..." : "Confirm & Start Fine-tune"}
              </Button>
              <Button variant="outline" onClick={handleReset}>
                Start Over
              </Button>
            </div>
          )}
        </div>
      )}

      {/* ── Step 4: Confirming ────────────────────────────────────────── */}
      {step === "confirm" && (
        <div className="flex h-48 items-center justify-center">
          <p className="text-sm text-muted-foreground">Submitting fine-tune job...</p>
        </div>
      )}

      {/* ── Step 5: Done ─────────────────────────────────────────────── */}
      {step === "done" && ftResult && (
        <div className="space-y-6">
          <Card className="border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950">
            <CardHeader>
              <CardTitle className="text-green-800 dark:text-green-200">
                Fine-tune Job Submitted
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Job ID</span>
                <span className="font-mono text-xs">{ftResult.job_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Status</span>
                <span className="font-medium">{ftResult.status}</span>
              </div>
              {ftResult.queue_position != null && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Queue position</span>
                  <span className="font-medium">{ftResult.queue_position}</span>
                </div>
              )}
              {ftResult.estimated_cost != null && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Estimated cost</span>
                  <span className="font-medium">${ftResult.estimated_cost.toFixed(2)}</span>
                </div>
              )}
            </CardContent>
          </Card>
          <div className="flex gap-3">
            <Button variant="outline" onClick={handleReset}>
              Start Another Job
            </Button>
            <Link href={`/fine-tune/${ftResult.job_id}`}>
              <Button variant="outline">View Job Details</Button>
            </Link>
            <Button variant="outline" onClick={() => window.location.assign("/models")}>
              Back to Models
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
