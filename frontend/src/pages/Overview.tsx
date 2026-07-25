import { useEffect, useRef, useState } from "react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { api, OverviewData, RequestEntry } from "../api/client";
import { MetricCard } from "../components/MetricCard";
import { Badge } from "../components/Badge";
import { TableSkeleton, Skeleton } from "../components/Skeleton";

const POLL_MS = 3000;

// Token palette for charts
const GREEN = "#1C7C55";
const GREEN_BRIGHT = "#35C67C";
const DONUT_ROUTING_COLORS = [GREEN, GREEN_BRIGHT];
const DONUT_MODEL_COLORS = [GREEN, GREEN_BRIGHT, "#8FBFA6", "#B7791F", "#C0402B"];

const TOOLTIP_STYLE = {
  backgroundColor: "#FFFFFF",
  border: "1px solid #E3E7E2",
  borderRadius: "8px",
  fontSize: "12px",
  color: "#14181A",
};

function formatLatency(ms: number | null): string {
  if (ms == null) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${Math.round(ms)}ms`;
}

function formatCost(usd: number | null): string {
  if (usd == null) return "—";
  return `$${usd.toFixed(5)}`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

function RoutingBadge({ tier, cached }: { tier: string | null; cached: boolean }) {
  if (cached) return <Badge label="cached" variant="green" />;
  if (!tier || tier === "n/a") return null;
  if (tier === "simple") return <Badge label="simple" variant="green" />;
  if (tier === "complex") return <Badge label="complex" variant="amber" />;
  return <Badge label={tier} variant="gray" />;
}

function GuardrailBadge({ action }: { action: string | null }) {
  if (!action || action === "passed") return null;
  if (action === "blocked") return <Badge label="blocked" variant="red" />;
  if (action === "redacted") return <Badge label="redacted" variant="amber" />;
  return <Badge label={action} variant="gray" />;
}

export function Overview() {
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [requests, setRequests] = useState<RequestEntry[]>([]);
  const [loadingInit, setLoadingInit] = useState(true);
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const prevIdsRef = useRef<Set<string>>(new Set());

  async function refresh() {
    try {
      const [ov, reqs] = await Promise.all([
        api.overview(),
        api.requests(20),
      ]);
      setOverview(ov);

      const incoming = new Set(reqs.map((r) => r.id));
      const fresh = new Set<string>();
      for (const id of incoming) {
        if (!prevIdsRef.current.has(id)) fresh.add(id);
      }
      if (fresh.size > 0) {
        setNewIds(fresh);
        setTimeout(() => setNewIds(new Set()), 2000);
      }
      prevIdsRef.current = incoming;
      setRequests(reqs);
    } catch {
      // silently ignore poll errors
    } finally {
      setLoadingInit(false);
    }
  }

  useEffect(() => {
    void refresh();
    const id = setInterval(() => void refresh(), POLL_MS);
    return () => clearInterval(id);
  }, []);

  const cacheHitPct = overview
    ? `${(overview.cache_hit_rate * 100).toFixed(1)}%`
    : "—";

  const routingDonut =
    overview && (overview.simple_requests + overview.complex_requests) > 0
      ? [
          { name: "Complex", value: overview.complex_requests },
          { name: "Simple", value: overview.simple_requests },
        ]
      : null;

  const modelCounts: Record<string, number> = {};
  for (const r of requests) {
    if (r.model_used && !["BLOCKED", "cache", "error"].includes(r.model_used)) {
      modelCounts[r.model_used] = (modelCounts[r.model_used] ?? 0) + 1;
    }
  }
  const modelDonut = Object.entries(modelCounts).map(([name, value]) => ({ name, value }));

  return (
    <div className="space-y-10">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <p className="section-label mb-2">Dashboard</p>
          <h2 className="text-3xl font-bold tracking-tight text-ink">Overview</h2>
          <p className="mt-1 text-sm text-muted">
            Live gateway metrics · refreshes every 3 s
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-xs font-medium text-muted">
          <span className="h-1.5 w-1.5 rounded-full bg-green-bright" />
          Live
        </span>
      </div>

      {/* Hero row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-line bg-surface px-6 py-6">
          <p className="section-label">Total requests</p>
          {loadingInit ? (
            <div className="mt-3 h-10 w-28 animate-pulse rounded bg-subtle" />
          ) : (
            <p className="mt-3 text-4xl font-bold tracking-tight text-ink metric-update">
              {overview?.total_requests ?? "—"}
            </p>
          )}
          {!loadingInit && overview && (
            <p className="mt-2 text-xs text-muted">
              {overview.simple_requests}s · {overview.complex_requests}c routed
            </p>
          )}
        </div>

        <div className="rounded-xl border border-green/20 bg-green-soft px-6 py-6 shadow-sm">
          <p className="section-label text-green/80">Total saved</p>
          {loadingInit ? (
            <div className="mt-3 h-10 w-28 animate-pulse rounded bg-green/10" />
          ) : (
            <p className="mt-3 text-4xl font-bold tracking-tight text-green metric-update">
              ${overview?.total_savings_usd.toFixed(4) ?? "—"}
            </p>
          )}
          {!loadingInit && overview && (
            <p className="mt-2 text-xs text-muted">
              vs ${overview.total_cost_usd.toFixed(4)} spent
            </p>
          )}
        </div>

        <div className="rounded-xl border border-line bg-surface px-6 py-6">
          <p className="section-label">Avg latency</p>
          {loadingInit ? (
            <div className="mt-3 h-10 w-28 animate-pulse rounded bg-subtle" />
          ) : (
            <p className="mt-3 text-4xl font-bold tracking-tight text-ink metric-update">
              {overview ? formatLatency(overview.avg_latency_ms) : "—"}
            </p>
          )}
          {!loadingInit && overview && (
            <p className="mt-2 text-xs text-muted">
              {overview.total_tokens.toLocaleString()} tokens total
            </p>
          )}
        </div>
      </div>

      {/* Secondary health row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <MetricCard label="Cache hits" value={cacheHitPct} loading={loadingInit} />
        <div className="rounded-lg border border-danger/20 bg-danger/5 px-5 py-4">
          <p className="section-label text-danger/80">Blocked</p>
          {loadingInit ? (
            <div className="mt-2 h-6 w-10 animate-pulse rounded bg-subtle" />
          ) : (
            <p className="mt-2 text-2xl font-semibold text-danger metric-update">
              {overview?.blocked_requests ?? 0}
            </p>
          )}
        </div>
        <div className="rounded-lg border border-warn/20 bg-warn/5 px-5 py-4">
          <p className="section-label text-warn/80">Redacted</p>
          {loadingInit ? (
            <div className="mt-2 h-6 w-10 animate-pulse rounded bg-subtle" />
          ) : (
            <p className="mt-2 text-2xl font-semibold text-warn metric-update">
              {overview?.redacted_requests ?? 0}
            </p>
          )}
        </div>
        <MetricCard label="Fallbacks" value={overview?.fallback_requests ?? "—"} loading={loadingInit} />
        <MetricCard label="Errors" value={overview?.error_requests ?? "—"} loading={loadingInit} />
      </div>

      {/* Donut charts */}
      {!loadingInit && (routingDonut || modelDonut.length > 0) && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-line bg-surface p-6">
            <h3 className="text-sm font-semibold text-ink">Routing tier split</h3>
            <p className="mt-0.5 text-xs text-muted">Complex → premium · Simple → cheap</p>
            {routingDonut ? (
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie
                    data={routingDonut}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={72}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {routingDonut.map((_, i) => (
                      <Cell key={i} fill={DONUT_ROUTING_COLORS[i % DONUT_ROUTING_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => [`${v} req`, ""]} contentStyle={TOOLTIP_STYLE} />
                  <Legend wrapperStyle={{ fontSize: "12px", color: "#6B726C" }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-44 items-center justify-center text-xs text-muted">
                No routing data yet
              </div>
            )}
          </div>

          <div className="rounded-xl border border-line bg-surface p-6">
            <h3 className="text-sm font-semibold text-ink">Model usage</h3>
            <p className="mt-0.5 text-xs text-muted">
              Request distribution across models (last 20)
            </p>
            {modelDonut.length > 0 ? (
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie
                    data={modelDonut}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={72}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {modelDonut.map((_, i) => (
                      <Cell key={i} fill={DONUT_MODEL_COLORS[i % DONUT_MODEL_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number, name: string) => [`${v} req`, name]} contentStyle={TOOLTIP_STYLE} />
                  <Legend
                    wrapperStyle={{ fontSize: "11px", color: "#6B726C" }}
                    formatter={(v: string) => (v.length > 16 ? `…${v.slice(-14)}` : v)}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-44 items-center justify-center text-xs text-muted">
                No model data yet
              </div>
            )}
          </div>
        </div>
      )}
      {loadingInit && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {[1, 2].map((n) => (
            <div key={n} className="rounded-xl border border-line bg-surface p-6">
              <Skeleton className="mb-2 h-4 w-36" />
              <div className="h-44 animate-pulse rounded bg-subtle" />
            </div>
          ))}
        </div>
      )}

      {/* Live request feed */}
      <div>
        <h3 className="mb-4 text-sm font-semibold text-ink">Recent requests</h3>

        <div className="overflow-hidden rounded-xl border border-line bg-surface">
          {loadingInit ? (
            <div className="p-6">
              <TableSkeleton rows={5} />
            </div>
          ) : requests.length === 0 ? (
            <p className="px-6 py-12 text-center text-sm text-muted">
              No requests yet — fire one at{" "}
              <code className="rounded border border-line bg-subtle px-1.5 py-0.5 font-mono text-xs text-ink/70">
                POST /v1/chat/completions
              </code>
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[700px] text-sm">
                <thead>
                  <tr className="border-b border-line text-left">
                    {["Time", "Model", "Routing", "Tokens", "Latency", "Cost", "Saved", "Guardrails"].map((h) => (
                      <th key={h} className="section-label px-5 py-3.5 font-medium">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {requests.map((r) => (
                    <tr
                      key={r.id}
                      className={`border-b border-line/60 last:border-0 transition-colors duration-700 ${
                        newIds.has(r.id) ? "bg-green-soft/50" : "hover:bg-subtle/60"
                      }`}
                    >
                      <td className="px-5 py-3.5 font-mono text-xs text-muted">
                        {formatDate(r.created_at)}
                      </td>
                      <td className="px-5 py-3.5 font-mono text-xs text-ink">
                        {r.model_used ?? "—"}
                        {r.was_fallback && (
                          <span className="ml-1.5 rounded border border-warn/20 bg-warn/10 px-1 py-0.5 text-xs text-warn">
                            fallback
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-3.5">
                        <RoutingBadge tier={r.routing_tier} cached={r.was_cached} />
                      </td>
                      <td className="px-5 py-3.5 tabular-nums font-mono text-xs text-muted">
                        {r.prompt_tokens > 0
                          ? `${r.prompt_tokens}p / ${r.completion_tokens}c`
                          : "—"}
                      </td>
                      <td className="px-5 py-3.5 tabular-nums font-mono text-xs text-ink">
                        {formatLatency(r.total_latency_ms)}
                      </td>
                      <td className="px-5 py-3.5 tabular-nums font-mono text-xs text-ink">
                        {formatCost(r.estimated_cost_usd)}
                      </td>
                      <td className="px-5 py-3.5 tabular-nums font-mono text-xs text-green">
                        {r.total_savings_usd != null && r.total_savings_usd > 0
                          ? `+${formatCost(r.total_savings_usd)}`
                          : "—"}
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex gap-1">
                          <GuardrailBadge action={r.input_guardrail_action} />
                          <GuardrailBadge action={r.output_guardrail_action} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
