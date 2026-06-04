"use client";

import { useSession } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
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

interface BudgetSummary {
  total_spend: number;
  remaining: number;
  budget_limit: number;
  runs_this_month: number;
  estimated_runs_left: number;
}

interface FineTuneResult {
  job_id: string;
  status: string;
  queue_position: number | null;
  estimated_cost: number | null;
}

/* ── Constants ──────────────────────────────────────────────────────── */

const TIER_LABELS: Record<number, string> = {
  0: "Tier 0 — Compact",
  1: "Tier 1 — Standard (Recommended)",
  2: "Tier 2 — Enhanced",
  3: "Tier 3 — Maximum",
};

const TIER_DESCRIPTIONS: Record<number, string> = {
  0: "Fastest training/inference; good baseline for RAG",
  1: "Best quality/cost ratio; strong reasoning across all domains",
  2: "Near-70B quality at half the VRAM; requires L40S",
  3: "Maximum quality; limited runs per month on $30 budget",
};

/* ── Models Page Component ─────────────────────────────────────────── */

export default function ModelsPage() {
  const { data: session, status } = useSession();
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [budget, setBudget] = useState<BudgetSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [fineTuneResult, setFineTuneResult] = useState<FineTuneResult | null>(null);
  const [fineTuneError, setFineTuneError] = useState<string | null>(null);
  const [triggeringModel, setTriggeringModel] = useState<string | null>(null);

  // Fetch models + budget on mount
  const fetchData = useCallback(async () => {
    try {
      const [modelsRes, budgetRes] = await Promise.all([
        fetchWithAuth("/api/v1/models"),
        fetchWithAuth("/api/v1/budget"),
      ]);

      if (modelsRes.ok) {
        const data = await modelsRes.json();
        setModels(data.models);
      }

      if (budgetRes.ok) {
        setBudget(await budgetRes.json());
      }
    } catch (err) {
      console.error("Failed to fetch models/budget:", err);
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
  }, [status, fetchData]);

  // Trigger fine-tune job
  const triggerFineTune = async (modelId: string) => {
    if (!selectedDatasetId) return;

    setTriggeringModel(modelId);
    setFineTuneError(null);
    setFineTuneResult(null);

    try {
      const res = await fetchWithAuth("/api/v1/fine-tune", {
        method: "POST",
        body: JSON.stringify({
          model_id: modelId,
          dataset_id: selectedDatasetId,
        }),
      });

      const data = await res.json();

      if (res.ok) {
        setFineTuneResult(data);
        // Refresh budget
        const budgetRes = await fetchWithAuth("/api/v1/budget");
        if (budgetRes.ok) setBudget(await budgetRes.json());
      } else {
        setFineTuneError(data.detail || data.message || `HTTP ${res.status}`);
      }
    } catch (err) {
      setFineTuneError((err as Error).message || "Failed to trigger fine-tune");
    } finally {
      setTriggeringModel(null);
    }
  };

  // Group models by tier
  const groupedByTier = models.reduce<Record<number, ModelInfo[]>>((acc, m) => {
    if (!acc[m.tier]) acc[m.tier] = [];
    acc[m.tier].push(m);
    return acc;
  }, {});

  // Auth states
  if (status === "loading") {
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
            Please sign in to browse the model catalog.
          </CardContent>
        </Card>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading model catalog...</p>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Model Catalog</h1>
        <p className="text-sm text-muted-foreground">
          Browse available models across 4 tiers. Select a model to trigger
          fine-tuning within your $30/month budget.
        </p>
      </div>

      {/* Budget Summary */}
      {budget && (
        <div className="mb-6 rounded-lg border bg-muted/30 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Monthly Budget</p>
              <p className="text-2xl font-bold">
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
              <p className="text-xs text-muted-foreground">
                {budget.runs_this_month} runs this month
              </p>
            </div>
          </div>
          {/* Progress bar */}
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{
                width: `${Math.min((budget.total_spend / budget.budget_limit) * 100, 100)}%`,
              }}
            />
          </div>
        </div>
      )}

      {/* Dataset ID input */}
      <div className="mb-6 flex items-end gap-3">
        <div className="flex-1">
          <label
            htmlFor="dataset-id"
            className="mb-1.5 block text-sm font-medium"
          >
            Active Dataset ID
          </label>
          <input
            id="dataset-id"
            type="text"
            value={selectedDatasetId}
            onChange={(e) => setSelectedDatasetId(e.target.value)}
            placeholder="Enter dataset UUID to fine-tune on..."
            className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
          />
        </div>
      </div>

      {/* Fine-tune result / error */}
      {fineTuneResult && (
        <div className="mb-4 rounded-lg border border-green-200 bg-green-50 p-3 text-sm dark:border-green-800 dark:bg-green-950">
          <p className="font-medium text-green-800 dark:text-green-200">
            Fine-tune job submitted
          </p>
          <p className="mt-1 text-green-700 dark:text-green-300">
            Job ID: {fineTuneResult.job_id} | Status: {fineTuneResult.status}
            {fineTuneResult.queue_position != null &&
              ` | Queue position: ${fineTuneResult.queue_position}`}
            {fineTuneResult.estimated_cost != null &&
              ` | Est. cost: $${fineTuneResult.estimated_cost.toFixed(2)}`}
          </p>
          <button
            className="mt-1 text-xs underline"
            onClick={() => setFineTuneResult(null)}
            type="button"
          >
            Dismiss
          </button>
        </div>
      )}
      {fineTuneError && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {fineTuneError}
          <button
            className="ml-2 text-xs underline"
            onClick={() => setFineTuneError(null)}
            type="button"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Model Tiers */}
      <div className="space-y-8">
        {[0, 1, 2, 3].map((tier) => {
          const tierModels = groupedByTier[tier];
          if (!tierModels?.length) return null;

          return (
            <section key={tier}>
              <div className="mb-3">
                <h2 className="text-base font-semibold">
                  {TIER_LABELS[tier]}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {TIER_DESCRIPTIONS[tier]}
                </p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {tierModels.map((model) => {
                  const canAfford = budget
                    ? budget.remaining >= model.est_cost
                    : true;
                  const canTrigger =
                    model.available && canAfford && !!selectedDatasetId;

                  return (
                    <Card key={model.id}>
                      <CardHeader>
                        <CardTitle className="text-sm font-medium">
                          {model.name}
                        </CardTitle>
                        <CardDescription>
                          {model.size} parameters
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-1 text-xs text-muted-foreground">
                        <p>GPU: {model.gpu}</p>
                        <p>VRAM: {model.vram_gb} GB</p>
                        <p>Est. cost: ${model.est_cost.toFixed(2)}/run</p>
                        <p>Est. time: ~{model.est_time_min} min</p>
                        <p>License: {model.license}</p>
                        {model.quality_rating != null && (
                          <p>
                            Quality: {(model.quality_rating * 100).toFixed(0)}%
                          </p>
                        )}
                      </CardContent>
                      <CardFooter>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={!canTrigger}
                          onClick={() => triggerFineTune(model.id)}
                        >
                          {triggeringModel === model.id
                            ? "Submitting..."
                            : !model.available
                              ? "Unavailable"
                              : !canAfford
                                ? "Over Budget"
                                : !selectedDatasetId
                                  ? "Select Dataset"
                                  : "Fine-tune"}
                        </Button>
                      </CardFooter>
                    </Card>
                  );
                })}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
