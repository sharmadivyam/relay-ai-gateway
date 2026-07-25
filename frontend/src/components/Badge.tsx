type BadgeVariant = "green" | "amber" | "gray" | "red";

interface BadgeProps {
  label: string;
  variant?: BadgeVariant;
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  green: "bg-green-soft text-green border-green/20",
  amber: "bg-warn/10 text-warn border-warn/20",
  gray:  "bg-subtle text-muted border-line",
  red:   "bg-danger/10 text-danger border-danger/20",
};

export function Badge({ label, variant = "gray" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-0.5 text-xs font-medium ${VARIANT_CLASSES[variant]}`}
    >
      {label}
    </span>
  );
}
