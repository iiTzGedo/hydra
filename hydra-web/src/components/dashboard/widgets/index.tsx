/**
 * Widget component registry.
 *
 * Maps widget type identifiers from the API registry to React components.
 * The API registry now only advertises implemented widgets; placeholder
 * mappings remain here only so older saved boards can still render safely.
 */

import { type ComponentType } from 'react';
import { CloudSun, ExternalLink, Rss, Clock3, Bookmark } from 'lucide-react';

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

function ClockWidget({ config }: WidgetComponentProps) {
  const timezone = typeof config?.timezone === 'string' ? config.timezone : undefined;
  const now = new Date();
  const formatter = new Intl.DateTimeFormat([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZone: timezone,
  });

  return (
    <div className="flex h-full flex-col justify-center gap-2">
      <div className="flex items-center gap-2 text-muted-foreground">
        <Clock3 className="h-4 w-4" />
        <span className="text-sm">{timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone}</span>
      </div>
      <div className="text-3xl font-semibold tracking-tight">{formatter.format(now)}</div>
    </div>
  );
}

function RssWidget({ config }: WidgetComponentProps) {
  const feedUrl = typeof config?.feedUrl === 'string' ? config.feedUrl : '';
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Rss className="h-4 w-4 text-orange-500" />
        Feed Source
      </div>
      <div className="rounded-xl border border-border/60 bg-muted/20 p-3 text-sm text-muted-foreground">
        {feedUrl || 'Configure a feed URL to surface external updates here.'}
      </div>
      {feedUrl ? (
        <a
          href={feedUrl}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 text-sm text-primary"
        >
          Open feed
          <ExternalLink className="h-4 w-4" />
        </a>
      ) : null}
    </div>
  );
}

function BookmarkGridWidget({ config }: WidgetComponentProps) {
  const rawLinks = typeof config?.linksMarkdown === 'string' ? config.linksMarkdown : '';
  const links = rawLinks
    .split('\n')
    .map((entry) => entry.trim())
    .filter(Boolean)
    .slice(0, 8);

  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {links.length > 0 ? links.map((link) => (
        <div key={link} className="rounded-xl border border-border/60 p-3 text-sm">
          <div className="flex items-center gap-2">
            <Bookmark className="h-4 w-4 text-primary" />
            <span className="truncate">{link}</span>
          </div>
        </div>
      )) : (
        <div className="rounded-xl border border-dashed border-border/70 p-4 text-sm text-muted-foreground sm:col-span-2">
          Add bookmark definitions in widget settings to build a launch grid.
        </div>
      )}
    </div>
  );
}

function IframeWidget({ config }: WidgetComponentProps) {
  const src = typeof config?.src === 'string' ? config.src : '';
  if (!src) {
    return (
      <div className="rounded-xl border border-dashed border-border/70 p-4 text-sm text-muted-foreground">
        Configure a trusted embed URL to render an external dashboard here.
      </div>
    );
  }

  return (
    <iframe
      src={src}
      title={typeof config?.title === 'string' ? config.title : 'Embedded dashboard'}
      className="h-full min-h-0 w-full rounded-xl border border-border/60"
      allowFullScreen={Boolean(config?.allowFullscreen)}
    />
  );
}

function MarkdownWidget({ config }: WidgetComponentProps) {
  const markdown = typeof config?.markdown === 'string' ? config.markdown : '';
  return (
    <div className="rounded-xl border border-border/60 bg-muted/20 p-4">
      <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-6">
        {markdown || 'Add markdown content to turn this widget into a quick note, checklist, or runbook callout.'}
      </pre>
    </div>
  );
}

function WeatherWidget({ config }: WidgetComponentProps) {
  const location = typeof config?.location === 'string' ? config.location : 'Set a location';
  const units = typeof config?.units === 'string' ? config.units : 'metric';
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium">
        <CloudSun className="h-4 w-4 text-amber-500" />
        {location}
      </div>
      <div className="text-4xl font-semibold tracking-tight">--</div>
      <div className="text-sm text-muted-foreground">
        Weather providers plug in here. Units: {units}.
      </div>
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
  'hydra::clock': ClockWidget,
  'hydra::rss-feed': RssWidget,
  'hydra::bookmark-grid': BookmarkGridWidget,
  'hydra::iframe': IframeWidget,
  'hydra::markdown': MarkdownWidget,
  'hydra::weather': WeatherWidget,
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
