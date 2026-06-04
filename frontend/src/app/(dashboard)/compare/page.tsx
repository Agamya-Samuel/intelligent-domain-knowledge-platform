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

/* ── Types ─────────────────────────────────────────────────────────── */

interface VariantResponse {
  variant: string;
  response: string;
  citations: Array<{ source: string; page?: number; section?: string }>;
  latency_ms: number;
  token_count: number;
}

interface ComparisonMetrics {
  latency_delta_ms: number;
  token_count_delta: number;
  citation_overlap: number;
  response_length_delta: number;
}

interface CompareResult {
  query: string;
  base: VariantResponse;
  finetuned: VariantResponse;
  comparison: ComparisonMetrics;
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
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(`${API_URL}${url}`, { ...options, headers, credentials: "include" });
}

/* ── Component ─────────────────────────────────────────────────────── */

export default function ComparePage() {
  const { data: session, status } = useSession();
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCompare = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetchWithAuth("/api/v1/compare", {
        method: "POST",
        body: JSON.stringify({ query: query.trim() }),
      });
      if (res.ok) {
        setResult(await res.json());
      } else {
        const data = await res.json();
        setError(data.detail || `Comparison failed (HTTP ${res.status})`);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey && !loading) {
      e.preventDefault();
      handleCompare();
    }
  };

  // Auth/loading guards
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
            Please sign in to compare model responses.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Model Comparison</h1>
        <p className="text-sm text-muted-foreground">
          Compare base vs. fine-tuned model responses side by side with metrics.
        </p>
      </div>

      {/* Query Input */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Query</CardTitle>
          <CardDescription>
            Enter a question to compare base and fine-tuned model responses.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <textarea
            className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm min-h-[80px]"
            placeholder="Ask a question about your domain knowledge..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            maxLength={4096}
          />
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              {query.length}/4096 characters
            </span>
            <Button onClick={handleCompare} disabled={loading || !query.trim()}>
              {loading ? "Comparing..." : "Compare Models"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Error */}
      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {error}
          <button className="ml-2 text-xs underline" onClick={() => setError(null)} type="button">
            Dismiss
          </button>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="space-y-2 text-center">
            <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            <p className="text-sm text-muted-foreground">
              Running query through both models...
            </p>
          </div>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <>
          {/* Metrics Delta */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-base">Comparison Metrics</CardTitle>
              <CardDescription>Differences between base and fine-tuned responses.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <MetricBadge
                  title="Latency Delta"
                  value={`${result.comparison.latency_delta_ms > 0 ? "+" : ""}${result.comparison.latency_delta_ms}ms`}
                  positive={result.comparison.latency_delta_ms < 0}
                />
                <MetricBadge
                  title="Token Count Delta"
                  value={`${result.comparison.token_count_delta > 0 ? "+" : ""}${result.comparison.token_count_delta}`}
                  neutral
                />
                <MetricBadge
                  title="Citation Overlap"
                  value={`${(result.comparison.citation_overlap * 100).toFixed(1)}%`}
                  positive={result.comparison.citation_overlap >= 0.7}
                />
                <MetricBadge
                  title="Response Length Delta"
                  value={`${result.comparison.response_length_delta > 0 ? "+" : ""}${result.comparison.response_length_delta} chars`}
                  neutral
                />
              </div>
            </CardContent>
          </Card>

          {/* Side-by-side responses */}
          <div className="grid gap-4 lg:grid-cols-2">
            {/* Base Model */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Base Model</CardTitle>
                  <span className="text-xs text-muted-foreground">
                    {result.base.latency_ms}ms &middot; {result.base.token_count} tokens
                  </span>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="rounded-lg bg-muted p-3">
                  <p className="whitespace-pre-wrap text-sm leading-relaxed">
                    {result.base.response}
                  </p>
                </div>
                {result.base.citations.length > 0 && (
                  <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">Citations</p>
                    <div className="flex flex-wrap gap-1.5">
                      {result.base.citations.map((c, i) => (
                        <span
                          key={i}
                          className="rounded border bg-background px-2 py-0.5 text-[11px] text-muted-foreground"
                          title={`Source: ${c.source}`}
                        >
                          {c.source}{c.page ? `:${c.page}` : ""}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Fine-tuned Model */}
            <Card className="border-primary/30">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">
                    Fine-tuned Model
                    <span className="ml-2 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                      FT
                    </span>
                  </CardTitle>
                  <span className="text-xs text-muted-foreground">
                    {result.finetuned.latency_ms}ms &middot; {result.finetuned.token_count} tokens
                  </span>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="rounded-lg bg-muted p-3">
                  <p className="whitespace-pre-wrap text-sm leading-relaxed">
                    {result.finetuned.response}
                  </p>
                </div>
                {result.finetuned.citations.length > 0 && (
                  <div>
                    <p className="mb-1 text-xs font-medium text-muted-foreground">Citations</p>
                    <div className="flex flex-wrap gap-1.5">
                      {result.finetuned.citations.map((c, i) => (
                        <span
                          key={i}
                          className="rounded border bg-background px-2 py-0.5 text-[11px] text-muted-foreground"
                          title={`Source: ${c.source}`}
                        >
                          {c.source}{c.page ? `:${c.page}` : ""}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

/* ── Metric Badge ──────────────────────────────────────────────────── */

function MetricBadge({
  title,
  value,
  positive,
  neutral,
}: {
  title: string;
  value: string;
  positive?: boolean;
  neutral?: boolean;
}) {
  return (
    <div className="rounded-lg border p-3 text-center">
      <p className="text-xs text-muted-foreground">{title}</p>
      <p
        className={`mt-1 text-lg font-semibold ${
          neutral
            ? "text-foreground"
            : positive
              ? "text-green-600"
              : "text-red-600"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
