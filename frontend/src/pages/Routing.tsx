import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { api, OverviewData, SavingsDay, ModelStat } from "../api/client";
import { Skeleton } from "../components/Skeleton";

const GREEN = "#1C7C55";
const GREEN_BRIGHT = "#35C67C";

const TOOLTIP_STYLE = {
  backgroundColor: "#FFFFFF",
  border: "1px solid #E3E7E2",
  borderRadius: "8px",
  fontSize: "12px",
  color: "#14181A",
};

function formatUSD(v: number) {
  return `$${v.toFixed(4)}`;
}

export function Routing() {
  const [timeseries, setTimeseries] = useState<SavingsDay[] | null>(null);
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [models, setModels] = useState<ModelStat[] | null>(null);
  const [days, setDays] = useState(7);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([api.savingsTimeseries(days), api.overview(), api.models()])
      .then(([ts, ov, ms]) => {
        setTimeseries(ts);
        setOverview(ov);
        setModels(ms);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [days]);

  const totalCompression =
    timeseries?.reduce((s, d) => s + d.compression_savings_usd, 0) ?? 0;
  const totalRouting =
    timeseries?.reduce((s, d) => s + d.routing_savings_usd, 0) ?? 0;
  const totalSaved = totalCompression + totalRouting;
  const hasData = timeseries && timeseries.length > 0;

  const totalRouted =
    (overview?.simple_requests ?? 0) + (overview?.complex_requests ?? 0);
  const complexPct =
    totalRouted > 0
      ? Math.round(((overview?.complex_requests ?? 0) / totalRouted) * 100)
      : 0;

  const maxRequests = Math.max(...(models?.map((m) => m.requests) ?? [1]), 1);

  return (
    <div className="space-y-8">
      <div>
        <p className="section-label mb-2">Analytics</p>
        <h2 className="text-3xl font-bold tracking-tight text-ink">Intelligence</h2>
        <p className="mt-1 text-sm text-muted">
          Smart routing, cost savings, and model distribution
        </p>
      </div>

      {/* Summary panel */}
      <div className="rounded-xl border border-line bg-surface px-6 py-4">
        {loading ? (
          <Skeleton className="h-5 w-72" />
        ) : (
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-ink">
            <span>
              Total saved:{" "}
              <span className="font-semibold text-green">{formatUSD(totalSaved)}</span>{" "}
              across{" "}
              <span className="font-semibold">{overview?.total_requests ?? 0}</span>{" "}
              requests
            </span>
            {totalCompression > 0 && (
              <span className="text-xs text-muted">
                ({formatUSD(totalCompression)} compression · {formatUSD(totalRouting)} routing)
              </span>
            )}
            {totalRouted > 0 && (
              <span className="border-l border-line pl-6 text-muted">
                <span className="font-semibold text-ink">{overview?.simple_requests ?? 0}</span>{" "}
                simple ·{" "}
                <span className="font-semibold text-ink">{overview?.complex_requests ?? 0}</span>{" "}
                complex —{" "}
                <span className="font-semibold text-green">{complexPct}%</span>{" "}
                routed to premium
              </span>
            )}
          </div>
        )}
      </div>

      {/* Day-range chip track */}
      <div className="flex items-center gap-3">
        <span className="section-label">Range</span>
        <div className="inline-flex gap-1 rounded-lg border border-line bg-subtle p-1">
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                days === d
                  ? "bg-green text-white"
                  : "text-muted hover:text-ink"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {/* Daily savings chart */}
      <div className="rounded-xl border border-line bg-surface p-6">
        {loading ? (
          <div className="space-y-3">
            <Skeleton className="h-4 w-40" />
            <div className="h-64 w-full animate-pulse rounded bg-subtle" />
          </div>
        ) : !hasData ? (
          <div className="flex h-64 flex-col items-center justify-center text-center">
            <p className="text-sm text-muted">No savings data for this range</p>
            <p className="mt-1 text-xs text-muted/70">
              Enable{" "}
              <code className="rounded border border-line bg-subtle px-1 font-mono text-xs text-ink/70">
                ENABLE_SMART_ROUTING=true
              </code>{" "}
              or{" "}
              <code className="rounded border border-line bg-subtle px-1 font-mono text-xs text-ink/70">
                ENABLE_PROMPT_COMPRESSION=true
              </code>
            </p>
          </div>
        ) : (
          <>
            <h3 className="mb-4 text-sm font-semibold text-ink">Daily savings (USD)</h3>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={timeseries} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EEF1EE" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: "#6B726C" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tickFormatter={(v: number) => `$${v.toFixed(3)}`}
                  tick={{ fontSize: 11, fill: "#6B726C" }}
                  axisLine={false}
                  tickLine={false}
                  width={60}
                />
                <Tooltip
                  formatter={(value: number, name: string) => [
                    formatUSD(value),
                    name === "compression_savings_usd" ? "Compression" : "Routing",
                  ]}
                  contentStyle={TOOLTIP_STYLE}
                  cursor={{ fill: "#F1F4F1" }}
                />
                <Legend
                  formatter={(value) =>
                    value === "compression_savings_usd"
                      ? "Compression savings"
                      : "Routing savings"
                  }
                  wrapperStyle={{ fontSize: "12px", color: "#6B726C" }}
                />
                <Bar dataKey="compression_savings_usd" stackId="savings" fill={GREEN_BRIGHT} radius={[0, 0, 0, 0]} />
                <Bar dataKey="routing_savings_usd" stackId="savings" fill={GREEN} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </>
        )}
      </div>

      {/* Model distribution */}
      <div className="rounded-xl border border-line bg-surface p-6">
        <h3 className="text-sm font-semibold text-ink">Model distribution</h3>
        <p className="mb-5 mt-0.5 text-xs text-muted">Requests and cost breakdown per model</p>
        {loading ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-3 w-28" />
                <div className="h-6 flex-1 animate-pulse rounded bg-subtle" />
                <Skeleton className="h-3 w-16" />
              </div>
            ))}
          </div>
        ) : !models || models.length === 0 ? (
          <p className="text-sm text-muted">No model data yet</p>
        ) : (
          <div className="space-y-3">
            {models.map((m) => (
              <div key={m.model} className="flex items-center gap-3">
                <span className="w-36 shrink-0 truncate font-mono text-xs text-muted">
                  {m.model}
                </span>
                <div className="relative flex-1 overflow-hidden rounded-md bg-subtle">
                  <div
                    className="h-5 rounded-md transition-all duration-500"
                    style={{
                      width: `${Math.max(4, (m.requests / maxRequests) * 100)}%`,
                      background: `linear-gradient(90deg, ${GREEN}, ${GREEN_BRIGHT})`,
                    }}
                  />
                </div>
                <span className="w-24 shrink-0 text-right tabular-nums font-mono text-xs text-muted">
                  {m.requests} req · {formatUSD(m.cost_usd)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
