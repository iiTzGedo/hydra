/**
 * Standard loading skeleton for data-backed widgets.
 *
 * Renders animated shimmer bars that match the widget body height.
 */

export function WidgetLoadingState() {
  return (
    <div className="flex h-full flex-col gap-3 p-1">
      <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
      <div className="h-4 w-1/2 animate-pulse rounded bg-muted" />
      <div className="h-8 w-full animate-pulse rounded bg-muted" />
      <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
    </div>
  );
}
