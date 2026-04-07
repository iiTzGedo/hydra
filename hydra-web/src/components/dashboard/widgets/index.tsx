/**
 * Widget component registry.
 *
 * Maps widget type identifiers from the API registry to React components.
 * The API registry now only advertises implemented widgets; placeholder
 * mappings remain here only so older saved boards can still render safely.
 */

import { type ComponentType } from 'react';

// Eagerly imported components (already implemented in Wave 1/2)
import { CapacityOverview } from '@/components/dashboard/capacity-overview';
import { MiniTopology } from '@/components/dashboard/mini-topology';
import { NodeStatusGrid } from '@/components/dashboard/node-status-grid';
import { RecentActivity } from '@/components/dashboard/recent-activity';
import { ServiceSummary } from '@/components/dashboard/service-summary';
import { StatsCards } from '@/components/dashboard/stats-cards';

/** Props that every widget component receives. */
export interface WidgetComponentProps {
  config?: Record<string, unknown>;
}

/** Wrapper to adapt existing zero-prop components to the WidgetComponentProps interface. */
function wrapComponent(Component: ComponentType): ComponentType<WidgetComponentProps> {
  const Wrapped: ComponentType<WidgetComponentProps> = () => <Component />;
  Wrapped.displayName = `Widget(${Component.displayName ?? Component.name ?? 'Anonymous'})`;
  return Wrapped;
}

/**
 * Placeholder component for legacy widget types that may still exist on
 * previously saved boards but are no longer advertised in the registry.
 */
function PlaceholderWidget({ config }: WidgetComponentProps) {
  const label = (config as { __widgetType?: string })?.__widgetType ?? 'Widget';
  return (
    <div className="flex flex-col items-center justify-center h-full gap-2 text-muted-foreground">
      <div className="text-sm font-medium">{label}</div>
      <div className="text-xs">Coming soon</div>
    </div>
  );
}

/** Widget type to component mapping. */
export const WIDGET_COMPONENTS: Record<string, ComponentType<WidgetComponentProps>> = {
  'hydra::stats-cards': wrapComponent(StatsCards),
  'hydra::capacity-overview': wrapComponent(CapacityOverview),
  'hydra::service-summary': wrapComponent(ServiceSummary),
  'hydra::recent-activity': wrapComponent(RecentActivity),
  'hydra::mini-topology': wrapComponent(MiniTopology),
  'hydra::node-status-grid': wrapComponent(NodeStatusGrid),
  'hydra::command-queue': PlaceholderWidget,
  'hydra::network-map': PlaceholderWidget,
  'hydra::alert-list': PlaceholderWidget,
  'hydra::profile-timeline': PlaceholderWidget,
  'hydra::discovery-feed': PlaceholderWidget,
  'hydra::doc-status': PlaceholderWidget,
};

/**
 * Look up the component for a given widget type.
 *
 * Returns `null` when no component is registered for the type, allowing
 * callers to render a fallback.
 */
export function getWidgetComponent(
  widgetType: string,
): ComponentType<WidgetComponentProps> | null {
  return WIDGET_COMPONENTS[widgetType] ?? null;
}
