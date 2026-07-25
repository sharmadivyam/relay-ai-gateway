interface MetricCardProps {
  label: string;
  value: string | number;
  sub?: string;
  loading?: boolean;
  accent?: boolean;
}

export function MetricCard({
  label,
  value,
  sub,
  loading = false,
  accent = false,
}: MetricCardProps) {
  return (
    <div
      className={`rounded-lg border px-5 py-4 ${
        accent
          ? "border-green/20 bg-green-soft"
          : "border-line bg-surface"
      }`}
    >
      <p className="section-label">{label}</p>
      {loading ? (
        <div className="mt-2 h-7 w-20 animate-pulse rounded bg-subtle" />
      ) : (
        <p
          className={`mt-2 text-2xl font-semibold tracking-tight metric-update ${
            accent ? "text-green" : "text-ink"
          }`}
        >
          {value}
        </p>
      )}
      {sub && !loading && <p className="mt-1 text-xs text-muted">{sub}</p>}
    </div>
  );
}
