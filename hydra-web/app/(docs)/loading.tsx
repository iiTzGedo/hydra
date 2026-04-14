export default function DocsLoading() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="space-y-2">
        <div className="h-4 w-48 rounded bg-muted" />
        <div className="h-8 w-64 rounded bg-muted" />
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div className="h-[300px] rounded-xl border bg-card" />
        <div className="h-[300px] rounded-xl border bg-card" />
        <div className="h-[300px] rounded-xl border bg-card" />
      </div>
    </div>
  );
}
