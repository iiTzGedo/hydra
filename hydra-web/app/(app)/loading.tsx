export default function AppLoading() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Page header skeleton */}
      <div className="space-y-2">
        <div className="h-4 w-48 rounded bg-muted" />
        <div className="h-8 w-64 rounded bg-muted" />
      </div>

      {/* Stats cards skeleton */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-24 rounded-xl border bg-card p-4">
            <div className="h-3 w-20 rounded bg-muted mb-3" />
            <div className="h-6 w-10 rounded bg-muted" />
          </div>
        ))}
      </div>

      {/* Content area skeleton */}
      <div className="rounded-xl border bg-card p-6">
        <div className="space-y-4">
          <div className="h-4 w-full max-w-md rounded bg-muted" />
          <div className="h-4 w-full max-w-sm rounded bg-muted" />
          <div className="h-4 w-full max-w-lg rounded bg-muted" />
        </div>
      </div>
    </div>
  );
}
