/**
 * Widget component registry.
 *
 * Maps widget type identifiers from the API registry to React components.
 * Components receive the full WidgetComponentProps contract per spec §14.3.
 *
 * Existing "composite" widgets (stats-cards, capacity-overview, etc.) that
 * fetch their own data are wrapped to match the WidgetComponentProps
 * interface. New Wave 2 widgets accept data exclusively through props from
 * the useWidgetData hook.
 */

import { type ComponentType } from 'react';
import type { WidgetComponentProps } from '@/types/dashboard';

export type { WidgetComponentProps };

// ── Existing composite widgets (Wave 1 — self-fetching) ─────────────

import { CapacityOverview } from '@/components/dashboard/capacity-overview';
import { MiniTopology } from '@/components/dashboard/mini-topology';
import { NodeStatusGrid } from '@/components/dashboard/node-status-grid';
import { RecentActivity } from '@/components/dashboard/recent-activity';
import { ServiceSummary } from '@/components/dashboard/service-summary';
import { StatsCards } from '@/components/dashboard/stats-cards';

function wrapComponent(Component: ComponentType): ComponentType<WidgetComponentProps> {
  const Wrapped: ComponentType<WidgetComponentProps> = () => <Component />;
  Wrapped.displayName = `Widget(${Component.displayName ?? Component.name ?? 'Anonymous'})`;
  return Wrapped;
}

// ── Data Display ────────────────────────────────────────────────────

import { MetricCardWidget } from './data-display/metric-card';
import { GaugeWidget } from './data-display/gauge';
import { ProgressBarWidget } from './data-display/progress-bar';
import { SparklineWidget } from './data-display/sparkline';
import { StatGroupWidget } from './data-display/stat-group';
import { DonutChartWidget } from './data-display/donut-chart';

// ── Status & Health ─────────────────────────────────────────────────

import { StatusGridWidget } from './status-health/status-grid';
import { HealthMatrixWidget } from './status-health/health-matrix';
import { NodeStatusCardWidget } from './status-health/node-status-card';
import { ServiceStatusBarWidget } from './status-health/service-status-bar';
import { UptimeBarWidget } from './status-health/uptime-bar';

// ── Tables & Lists ──────────────────────────────────────────────────

import { EntityTableWidget } from './tables-lists/entity-table';
import { ServiceListWidget } from './tables-lists/service-list';
import { ActivityFeedWidget } from './tables-lists/activity-feed';
import { AlertListWidget } from './tables-lists/alert-list';
import { LogViewerWidget } from './tables-lists/log-viewer';

// ── Charts & Graphs ─────────────────────────────────────────────────

import { LineChartWidget } from './charts-graphs/line-chart-widget';
import { BarChartWidget } from './charts-graphs/bar-chart-widget';
import { AreaChartWidget } from './charts-graphs/area-chart-widget';
import { HeatmapWidget } from './charts-graphs/heatmap-widget';

// ── Topology & Maps ─────────────────────────────────────────────────

import { NetworkMapWidget } from './topology-maps/network-map-widget';

// ── Controls & Actions (Wave 3 — placeholder) ──────────────────────

import { QuickActionWidget } from './controls-actions/quick-action-widget';
import { CommandTriggerWidget } from './controls-actions/command-trigger-widget';
import { ServiceControlWidget } from './controls-actions/service-control-widget';
import { WorkflowTriggerWidget } from './controls-actions/workflow-trigger-widget';

// ── Infrastructure ──────────────────────────────────────────────────

import { NodeSummaryWidget } from './infrastructure/node-summary-widget';
import { CapacityPanelWidget } from './infrastructure/capacity-panel-widget';
import { NetworkSummaryWidget } from './infrastructure/network-summary-widget';
import { ProfileDiffWidget } from './infrastructure/profile-diff-widget';

// ── Time & History ──────────────────────────────────────────────────

import { TimeMachineScrubberWidget } from './time-history/time-machine-scrubber-widget';
import { ChangeLogWidget } from './time-history/change-log-widget';
import { ProfileTimelineWidget } from './time-history/profile-timeline-widget';

// ── External & Embed ────────────────────────────────────────────────

import { HtmlBlockWidget } from './external-embed/html-block-widget';

// ── Existing config-backed widgets (inline) ─────────────────────────

import { Clock3, Rss, Bookmark, ExternalLink, CloudSun } from 'lucide-react';

function ClockWidget({ config }: WidgetComponentProps) {
  const timezone = typeof config?.timezone === 'string' ? config.timezone : undefined;
  const now = new Date();
  const formatter = new Intl.DateTimeFormat([], {
    hour: '2-digit', minute: '2-digit', second: '2-digit', timeZone: timezone,
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
        <Rss className="h-4 w-4 text-orange-500" /> Feed Source
      </div>
      <div className="rounded-xl border border-border/60 bg-muted/20 p-3 text-sm text-muted-foreground">
        {feedUrl || 'Configure a feed URL to surface external updates here.'}
      </div>
      {feedUrl ? (
        <a href={feedUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-sm text-primary">
          Open feed <ExternalLink className="h-4 w-4" />
        </a>
      ) : null}
    </div>
  );
}

function BookmarkGridWidget({ config }: WidgetComponentProps) {
  const rawLinks = typeof config?.linksMarkdown === 'string' ? config.linksMarkdown : '';
  const links = rawLinks.split('\n').map((e) => e.trim()).filter(Boolean).slice(0, 8);
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {links.length > 0 ? links.map((link) => (
        <div key={link} className="rounded-xl border border-border/60 p-3 text-sm">
          <div className="flex items-center gap-2">
            <Bookmark className="h-4 w-4 text-primary" /> <span className="truncate">{link}</span>
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
        <CloudSun className="h-4 w-4 text-amber-500" /> {location}
      </div>
      <div className="text-4xl font-semibold tracking-tight">--</div>
      <div className="text-sm text-muted-foreground">Weather providers plug in here. Units: {units}.</div>
    </div>
  );
}

// ── System & Meta ───────────────────────────────────────────────────

import { IntegrationHealthWidget } from './system-meta/integration-health-widget';
import { AgentGridWidget } from './system-meta/agent-grid-widget';
import { AuditStreamWidget } from './system-meta/audit-stream-widget';
import { ApiStatusWidget } from './system-meta/api-status-widget';
import { McpQueryWidget } from './system-meta/mcp-query-widget';
import { ExecutionQueueWidget } from './system-meta/execution-queue-widget';

// ── Component registry ──────────────────────────────────────────────

// Widgets that use typed generics (WidgetComponentProps<SpecificData>) are
// structurally compatible but TypeScript's strict variance rejects the
// assignment. A single cast at the registry boundary avoids per-widget noise.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyWidgetComponent = ComponentType<WidgetComponentProps<any, any>>;

export const WIDGET_COMPONENTS: Record<string, AnyWidgetComponent> = {
  // Existing composites (self-fetching, wrapped)
  'hydra::stats-cards': wrapComponent(StatsCards),
  'hydra::capacity-overview': wrapComponent(CapacityOverview),
  'hydra::service-summary': wrapComponent(ServiceSummary),
  'hydra::recent-activity': wrapComponent(RecentActivity),
  'hydra::mini-topology': wrapComponent(MiniTopology),
  'hydra::node-status-grid': wrapComponent(NodeStatusGrid),

  // Data Display
  'hydra::metric-card': MetricCardWidget,
  'hydra::gauge': GaugeWidget,
  'hydra::progress-bar': ProgressBarWidget,
  'hydra::sparkline': SparklineWidget,
  'hydra::stat-group': StatGroupWidget,
  'hydra::donut-chart': DonutChartWidget,

  // Status & Health
  'hydra::status-grid': StatusGridWidget,
  'hydra::health-matrix': HealthMatrixWidget,
  'hydra::node-status-card': NodeStatusCardWidget,
  'hydra::service-status-bar': ServiceStatusBarWidget,
  'hydra::uptime-bar': UptimeBarWidget,

  // Tables & Lists
  'hydra::entity-table': EntityTableWidget,
  'hydra::service-list': ServiceListWidget,
  'hydra::activity-feed': ActivityFeedWidget,
  'hydra::alert-list': AlertListWidget,
  'hydra::log-viewer': LogViewerWidget,

  // Charts & Graphs
  'hydra::line-chart': LineChartWidget,
  'hydra::bar-chart': BarChartWidget,
  'hydra::area-chart': AreaChartWidget,
  'hydra::heatmap': HeatmapWidget,

  // Topology & Maps
  'hydra::network-map': NetworkMapWidget,

  // Controls & Actions (Wave 3 placeholders)
  'hydra::quick-action': QuickActionWidget,
  'hydra::command-trigger': CommandTriggerWidget,
  'hydra::service-control': ServiceControlWidget,
  'hydra::workflow-trigger': WorkflowTriggerWidget,

  // Infrastructure
  'hydra::node-summary': NodeSummaryWidget,
  'hydra::capacity-panel': CapacityPanelWidget,
  'hydra::network-summary': NetworkSummaryWidget,
  'hydra::profile-diff': ProfileDiffWidget,

  // Time & History
  'hydra::time-machine-scrubber': TimeMachineScrubberWidget,
  'hydra::change-log': ChangeLogWidget,
  'hydra::profile-timeline': ProfileTimelineWidget,

  // External & Embed (config-backed)
  'hydra::clock': ClockWidget,
  'hydra::rss-feed': RssWidget,
  'hydra::bookmark-grid': BookmarkGridWidget,
  'hydra::iframe': IframeWidget,
  'hydra::markdown': MarkdownWidget,
  'hydra::weather': WeatherWidget,
  'hydra::html-block': HtmlBlockWidget,

  // System & Meta
  'hydra::integration-health': IntegrationHealthWidget,
  'hydra::agent-grid': AgentGridWidget,
  'hydra::audit-stream': AuditStreamWidget,
  'hydra::api-status': ApiStatusWidget,
  'hydra::mcp-query': McpQueryWidget,
  'hydra::execution-queue': ExecutionQueueWidget,
};

/**
 * Look up the component for a given widget type.
 * Returns `null` when no component is registered.
 */
export function getWidgetComponent(
  widgetType: string,
): AnyWidgetComponent | null {
  return WIDGET_COMPONENTS[widgetType] ?? null;
}
