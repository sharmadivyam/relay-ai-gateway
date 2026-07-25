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
import { api, OverviewData, GuardrailDay, GuardrailEvent } from "../api/client";
import { Badge } from "../components/Badge";
import { MetricCard } from "../components/MetricCard";
import { TableSkeleton, Skeleton } from "../components/Skeleton";

const TOOLTIP_STYLE = {
  backgroundColor: "#FFFFFF",
  border: "1px solid #E3E7E2",
  borderRadius: "8px",
  fontSize: "12px",
  color: "#14181A",
};

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

function ActionBadge({ action }: { action: string }) {
  if (action === "blocked") return <Badge label="blocked" variant="red" />;
  if (action === "redacted") return <Badge label="redacted" variant="amber" />;
  return <Badge label={action} variant="gray" />;
}

export function Guardrails() {
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [timeseries, setTimeseries] = useState<GuardrailDay[] | null>(null);
  const [events, setEvents] = useState<GuardrailEvent[] | null>(null);
  const [days, setDays] = useState(7);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.overview(),
      api.guardrailsTimeseries(days),
      api.guardrailEvents(50),
    ])
      .then(([ov, ts, ev]) => {
        setOverview(ov);
        setTimeseries(ts);
        setEvents(ev);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [days]);

  const total = overview?.total_requests ?? 0;
  const blocked = overview?.blocked_requests ?? 0;
  const redacted = overview?.redacted_requests ?? 0;
  const triggerRate =
    total > 0 ? `${(((blocked + redacted) / total) * 100).toFixed(1)}%` : "0%";

  const hasChart = timeseries && timeseries.some(
    (d) => d.blocked + d.redacted + d.passed > 0
  );

  return (
    <div className="space-y-8">
      <div>
        <p className="section-label mb-2">Safety</p>
        <h2 className="text-3xl font-bold tracking-tight text-ink">Guardrails</h2>
        <p className="mt-1 text-sm text-muted">
          Input safety, PII redaction, and output filtering
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-danger/20 bg-danger/5 px-6 py-5">
          <p className="section-label text-danger/80">Blocked</p>
          {loading ? (
            <div className="mt-2 h-8 w-16 animate-pulse rounded bg-subtle" />
          ) : (
            <p className="mt-2 text-3xl font-bold tracking-tight text-danger metric-update">{blocked}</p>
          )}
          <p className="mt-1 text-xs text-muted">Input guardrail fired — request rejected</p>
        </div>

        <div className="rounded-xl border border-warn/20 bg-warn/5 px-6 py-5">
          <p className="section-label text-warn/80">Redacted</p>
          {loading ? (
            <div className="mt-2 h-8 w-16 animate-pulse rounded bg-subtle" />
          ) : (
            <p className="mt-2 text-3xl font-bold tracking-tight text-warn metric-update">{redacted}</p>
          )}
          <p className="mt-1 text-xs text-muted">Output guardrail fired — PII scrubbed</p>
        </div>

        <MetricCard
          label="Trigger rate"
          value={triggerRate}
          sub="% of all requests that hit a guardrail"
          loading={loading}
        />
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

      {/* Stacked bar chart */}
      <div className="rounded-xl border border-line bg-surface p-6">
        {loading ? (
          <div className="space-y-3">
            <Skeleton className="h-4 w-48" />
            <div className="h-64 w-full animate-pulse rounded bg-subtle" />
          </div>
        ) : !hasChart ? (
          <div className="flex h-64 flex-col items-center justify-center text-center">
            <p className="text-sm text-muted">No guardrail events in this range</p>
            <p className="mt-1 text-xs text-muted/70">
              Try sending a prompt containing "ignore all instructions" to trigger one
            </p>
          </div>
        ) : (
          <>
            <h3 className="mb-4 text-sm font-semibold text-ink">Daily guardrail activity</h3>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={timeseries!} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EEF1EE" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: "#6B726C" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: "#6B726C" }}
                  axisLine={false}
                  tickLine={false}
                  allowDecimals={false}
                />
                <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "#F1F4F1" }} />
                <Legend wrapperStyle={{ fontSize: "12px", color: "#6B726C" }} />
                <Bar dataKey="passed" stackId="g" fill="#C7E3D3" radius={[0, 0, 0, 0]} name="Passed" />
                <Bar dataKey="redacted" stackId="g" fill="#E6C878" radius={[0, 0, 0, 0]} name="Redacted" />
                <Bar dataKey="blocked" stackId="g" fill="#C0402B" radius={[4, 4, 0, 0]} name="Blocked" />
              </BarChart>
            </ResponsiveContainer>
          </>
        )}
      </div>

      {/* Guardrail events table */}
      <div>
        <h3 className="mb-4 text-sm font-semibold text-ink">Recent guardrail events</h3>
        <div className="overflow-hidden rounded-xl border border-line bg-surface">
          {loading ? (
            <div className="p-6">
              <TableSkeleton rows={4} />
            </div>
          ) : !events || events.length === 0 ? (
            <p className="px-6 py-12 text-center text-sm text-muted">
              No guardrail events yet — all requests passed
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left">
                  {["Time", "Action", "Reason", "Model"].map((h) => (
                    <th key={h} className="section-label px-5 py-3.5 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.id} className="border-b border-line/60 last:border-0 hover:bg-subtle/60">
                    <td className="px-5 py-3.5 font-mono text-xs text-muted">
                      {formatDate(e.created_at)}
                    </td>
                    <td className="px-5 py-3.5">
                      <ActionBadge action={e.action} />
                    </td>
                    <td className="max-w-xs px-5 py-3.5 text-xs text-ink">
                      {e.reason ?? "—"}
                    </td>
                    <td className="px-5 py-3.5 font-mono text-xs text-muted">
                      {e.model_used ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
