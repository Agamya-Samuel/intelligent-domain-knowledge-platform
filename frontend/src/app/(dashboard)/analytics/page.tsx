"use client";

import { useSession } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { fetchWithAuth } from "@/lib/api";

/* ── Types ─────────────────────────────────────────────────────────── */

interface MetricsPoint {
  date: string;
  run_type: string;
  faithfulness: number | null;
  context_relevance: number | null;
  answer_relevance: number | null;
  context_recall: number | null;
}

interface MetricsTrend {
  points: MetricsPoint[];
  latest: {
    faithfulness: number | null;
    context_relevance: number | null;
    answer_relevance: number | null;
    context_recall: number | null;
    run_type: string;
    date: string | null;
  } | null;
}

interface JobStats {
  total_jobs: number;
  completed: number;
  failed: number;
  queued: number;
  total_cost: number;
  avg_cost_per_job: number | null;
  avg_duration_minutes: number | null;
}

interface ChatStats {
  total_sessions: number;
  total_messages: number;
  user_messages: number;
  assistant_messages: number;
  avg_latency_ms: number | null;
}

interface BudgetTrendPoint {
  month: string;
  total_spend: number;
  job_count: number;
}

interface BudgetTrend {
  points: BudgetTrendPoint[];
  current_spend: number;
  budget_limit: number;
}

interface AnalyticsOverview {
  metrics_trend: MetricsTrend;
  job_stats: JobStats;
  chat_stats: ChatStats;
  budget_trend: BudgetTrend;
}

/* ── Metric Card Component ─────────────────────────────────────────── */

function MetricCard({
  title,
  value,
  subtitle,
  color,
}: {
  title: string;
  value: string;
  subtitle?: string;
  color?: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardDescription className="text-xs">{title}</CardDescription>
      </CardHeader>
      <CardContent>
        <p className={`text-2xl font-bold ${color || ""}`}>{value}</p>
        {subtitle && (
          <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
        )}
      </CardContent>
    </Card>
  );
}

/* ── Analytics Page Component ──────────────────────────────────────── */

export default function AnalyticsPage() {
  const { data: session, status } = useSession();
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetchWithAuth("/api/v1/analytics/overview");
      if (res.ok) {
        setOverview(await res.json());
      }
    } catch (err) {
      console.error("Failed to fetch analytics:", err);
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

  if (status === "loading" || loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading analytics...</p>
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
            Please sign in to view analytics.
          </CardContent>
        </Card>
      </div>
    );
  }

  const latest = overview?.metrics_trend.latest;
  const jobStats = overview?.job_stats;
  const chatStats = overview?.chat_stats;
  const budgetTrend = overview?.budget_trend;

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
        <p className="text-sm text-muted-foreground">
          RAGAS metrics, job statistics, and usage overview.
        </p>
      </div>

      {/* RAGAS Metrics */}
      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold">RAGAS Metrics</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            title="Faithfulness"
            value={latest?.faithfulness?.toFixed(2) ?? "—"}
            subtitle={latest?.run_type ? `Last: ${latest.run_type}` : undefined}
            color="text-blue-600"
          />
          <MetricCard
            title="Context Relevance"
            value={latest?.context_relevance?.toFixed(2) ?? "—"}
            color="text-green-600"
          />
          <MetricCard
            title="Answer Relevance"
            value={latest?.answer_relevance?.toFixed(2) ?? "—"}
            color="text-purple-600"
          />
          <MetricCard
            title="Context Recall"
            value={latest?.context_recall?.toFixed(2) ?? "—"}
            color="text-orange-600"
          />
        </div>

        {/* Metrics history table */}
        {overview?.metrics_trend.points.length ? (
          <div className="mt-4 overflow-x-auto rounded-lg border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Date</th>
                  <th className="px-3 py-2 text-left font-medium">Type</th>
                  <th className="px-3 py-2 text-right font-medium">Faithfulness</th>
                  <th className="px-3 py-2 text-right font-medium">Ctx Relevance</th>
                  <th className="px-3 py-2 text-right font-medium">Ans Relevance</th>
                  <th className="px-3 py-2 text-right font-medium">Ctx Recall</th>
                </tr>
              </thead>
              <tbody>
                {overview.metrics_trend.points.slice(-10).reverse().map((p, i) => (
                  <tr key={i} className="border-t">
                    <td className="px-3 py-2 text-xs">
                      {new Date(p.date).toLocaleDateString()}
                    </td>
                    <td className="px-3 py-2 text-xs">{p.run_type}</td>
                    <td className="px-3 py-2 text-right text-xs">
                      {p.faithfulness?.toFixed(3) ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-right text-xs">
                      {p.context_relevance?.toFixed(3) ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-right text-xs">
                      {p.answer_relevance?.toFixed(3) ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-right text-xs">
                      {p.context_recall?.toFixed(3) ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-4 text-sm text-muted-foreground">
            No evaluation runs yet. Run an evaluation to see metrics.
          </p>
        )}
      </section>

      {/* Job Statistics */}
      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold">Fine-tuning Jobs</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            title="Total Jobs"
            value={String(jobStats?.total_jobs ?? 0)}
          />
          <MetricCard
            title="Completed"
            value={String(jobStats?.completed ?? 0)}
            color="text-green-600"
          />
          <MetricCard
            title="Failed"
            value={String(jobStats?.failed ?? 0)}
            color="text-red-600"
          />
          <MetricCard
            title="Total Cost"
            value={`$${jobStats?.total_cost.toFixed(2) ?? "0.00"}`}
            subtitle={
              jobStats?.avg_cost_per_job
                ? `Avg: $${jobStats.avg_cost_per_job.toFixed(2)}/job`
                : undefined
            }
          />
        </div>
        {jobStats?.avg_duration_minutes && (
          <p className="mt-2 text-xs text-muted-foreground">
            Average job duration: {jobStats.avg_duration_minutes.toFixed(0)} minutes
          </p>
        )}
      </section>

      {/* Chat Usage */}
      <section className="mb-8">
        <h2 className="mb-3 text-lg font-semibold">Chat Usage</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            title="Sessions"
            value={String(chatStats?.total_sessions ?? 0)}
          />
          <MetricCard
            title="Total Messages"
            value={String(chatStats?.total_messages ?? 0)}
          />
          <MetricCard
            title="User Messages"
            value={String(chatStats?.user_messages ?? 0)}
          />
          <MetricCard
            title="Avg Response Time"
            value={
              chatStats?.avg_latency_ms
                ? `${(chatStats.avg_latency_ms / 1000).toFixed(1)}s`
                : "—"
            }
          />
        </div>
      </section>

      {/* Budget Trend */}
      <section>
        <h2 className="mb-3 text-lg font-semibold">Budget Trend</h2>
        {budgetTrend && (
          <>
            <div className="mb-3 flex items-center gap-4">
              <span className="text-sm">
                Current month:{" "}
                <span className="font-semibold">
                  ${budgetTrend.current_spend.toFixed(2)}
                </span>{" "}
                / ${budgetTrend.budget_limit.toFixed(2)}
              </span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-all"
                  style={{
                    width: `${Math.min(
                      (budgetTrend.current_spend / budgetTrend.budget_limit) * 100,
                      100
                    )}%`,
                  }}
                />
              </div>
            </div>
            {budgetTrend.points.length > 0 && (
              <div className="overflow-x-auto rounded-lg border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="px-3 py-2 text-left font-medium">Month</th>
                      <th className="px-3 py-2 text-right font-medium">Spend</th>
                      <th className="px-3 py-2 text-right font-medium">Jobs</th>
                    </tr>
                  </thead>
                  <tbody>
                    {budgetTrend.points.map((p, i) => (
                      <tr key={i} className="border-t">
                        <td className="px-3 py-2 text-xs">{p.month}</td>
                        <td className="px-3 py-2 text-right text-xs">
                          ${p.total_spend.toFixed(2)}
                        </td>
                        <td className="px-3 py-2 text-right text-xs">
                          {p.job_count}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
