interface SkeletonProps {
  rows?: number;
  className?: string;
}

export function Skeleton({ rows = 1, className = "" }: SkeletonProps) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className={`animate-pulse rounded bg-subtle ${className}`}
        />
      ))}
    </>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4">
          <div className="h-4 w-32 animate-pulse rounded bg-subtle" />
          <div className="h-4 w-24 animate-pulse rounded bg-subtle" />
          <div className="h-4 w-20 animate-pulse rounded bg-subtle" />
          <div className="h-4 flex-1 animate-pulse rounded bg-subtle" />
        </div>
      ))}
    </div>
  );
}
