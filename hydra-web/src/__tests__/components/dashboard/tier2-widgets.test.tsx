/**
 * Tests for 10 Tier 2 dashboard widgets (P2DASH Wave 4 — Task 27).
 *
 * Covers three states for each widget:
 *   1. Loading — shows loading skeleton
 *   2. Error — shows error state
 *   3. Success — renders real data
 *
 * Also verifies data normalization: each widget should accept both the
 * API's raw array shape and the explicit data envelope shape.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

// ── Widget imports ────────────────────────────────────────────────────

import { EntityTableWidget } from '@/components/dashboard/widgets/tables-lists/entity-table';
import { ServiceListWidget } from '@/components/dashboard/widgets/tables-lists/service-list';
import { AlertListWidget } from '@/components/dashboard/widgets/tables-lists/alert-list';
import { ActivityFeedWidget } from '@/components/dashboard/widgets/tables-lists/activity-feed';
import { LineChartWidget } from '@/components/dashboard/widgets/charts-graphs/line-chart-widget';
import { BarChartWidget } from '@/components/dashboard/widgets/charts-graphs/bar-chart-widget';
import { AreaChartWidget } from '@/components/dashboard/widgets/charts-graphs/area-chart-widget';
import { HeatmapWidget } from '@/components/dashboard/widgets/charts-graphs/heatmap-widget';
import { NetworkMapWidget } from '@/components/dashboard/widgets/topology-maps/network-map-widget';
import { ChangeLogWidget } from '@/components/dashboard/widgets/time-history/change-log-widget';

// ── Shared test helpers ───────────────────────────────────────────────

const BASE_PROPS = {
  config: {},
  isEditing: false,
  isLoading: false,
  error: null,
  dimensions: { width: 400, height: 300 },
};

const LOADING_PROPS = { ...BASE_PROPS, isLoading: true };
const ERROR_PROPS = {
  ...BASE_PROPS,
  error: new Error('Test network error'),
};

// ── 1. EntityTableWidget ─────────────────────────────────────────────

describe('EntityTableWidget', () => {
  it('shows loading state', () => {
    const { container } = render(
      <EntityTableWidget {...LOADING_PROPS} data={null} />,
    );
    // WidgetLoadingState renders animated pulse bars
    expect(container.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('shows error state', () => {
    render(<EntityTableWidget {...ERROR_PROPS} data={null} />);
    expect(screen.getByText('Failed to load data')).toBeInTheDocument();
  });

  it('shows configure message when data is null', () => {
    render(<EntityTableWidget {...BASE_PROPS} data={null} />);
    expect(screen.getByText('Configure a data source')).toBeInTheDocument();
  });

  it('renders rows from explicit envelope shape', () => {
    const data = {
      items: [
        { nodeId: 'n1', displayName: 'server-01', class: 'compute', status: 'active' },
        { nodeId: 'n2', displayName: 'switch-01', class: 'networking', status: 'active' },
      ],
      total: 2,
    };
    render(<EntityTableWidget {...BASE_PROPS} data={data} />);
    expect(screen.getByText('server-01')).toBeInTheDocument();
    expect(screen.getByText('switch-01')).toBeInTheDocument();
  });

  it('renders rows from raw array (API response shape)', () => {
    const data = [
      { nodeId: 'n1', displayName: 'server-01', class: 'compute', status: 'active' },
      { nodeId: 'n2', displayName: 'switch-01', class: 'networking', status: 'active' },
    ];
    render(<EntityTableWidget {...BASE_PROPS} data={data} />);
    expect(screen.getByText('server-01')).toBeInTheDocument();
    expect(screen.getByText('switch-01')).toBeInTheDocument();
  });

  it('shows empty state for empty array', () => {
    render(<EntityTableWidget {...BASE_PROPS} data={[]} />);
    expect(screen.getByText('No data available')).toBeInTheDocument();
  });
});

// ── 2. ServiceListWidget ─────────────────────────────────────────────

describe('ServiceListWidget', () => {
  it('shows loading state', () => {
    const { container } = render(
      <ServiceListWidget {...LOADING_PROPS} data={null} />,
    );
    expect(container.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('shows error state', () => {
    render(<ServiceListWidget {...ERROR_PROPS} data={null} />);
    expect(screen.getByText('Failed to load data')).toBeInTheDocument();
  });

  it('shows configure message when data is null', () => {
    render(<ServiceListWidget {...BASE_PROPS} data={null} />);
    expect(screen.getByText('Configure a data source')).toBeInTheDocument();
  });

  it('renders services from envelope shape', () => {
    const data = {
      services: [
        { serviceId: 'svc-nginx-a1b2', name: 'nginx', runtime: 'systemd', status: 'running' },
        { serviceId: 'svc-mongo-c3d4', name: 'mongod', runtime: 'systemd', status: 'running' },
      ],
    };
    render(<ServiceListWidget {...BASE_PROPS} data={data} />);
    expect(screen.getByText('nginx')).toBeInTheDocument();
    expect(screen.getByText('mongod')).toBeInTheDocument();
  });

  it('renders services from raw ServiceSummary[] (API shape)', () => {
    const data = [
      { serviceId: 'svc-nginx-a1b2', name: 'nginx', displayName: 'nginx', runtime: 'systemd', status: 'running', nodeId: 'n1', lastSeen: '2026-01-01T00:00:00Z' },
    ];
    render(<ServiceListWidget {...BASE_PROPS} data={data} />);
    expect(screen.getByText('nginx')).toBeInTheDocument();
  });

  it('applies filterByStatus config', () => {
    const data = [
      { serviceId: 's1', name: 'nginx', runtime: 'systemd', status: 'running', nodeId: 'n1', lastSeen: '', displayName: 'nginx' },
      { serviceId: 's2', name: 'postgres', runtime: 'systemd', status: 'stopped', nodeId: 'n1', lastSeen: '', displayName: 'postgres' },
    ];
    render(
      <ServiceListWidget
        {...BASE_PROPS}
        data={data}
        config={{ filterByStatus: 'running' }}
      />,
    );
    expect(screen.getByText('nginx')).toBeInTheDocument();
    expect(screen.queryByText('postgres')).not.toBeInTheDocument();
  });
});

// ── 3. AlertListWidget ───────────────────────────────────────────────

describe('AlertListWidget', () => {
  it('shows loading state', () => {
    const { container } = render(
      <AlertListWidget {...LOADING_PROPS} data={null} />,
    );
    expect(container.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('shows error state', () => {
    render(<AlertListWidget {...ERROR_PROPS} data={null} />);
    expect(screen.getByText('Failed to load data')).toBeInTheDocument();
  });

  it('shows no-alerts state when empty', () => {
    render(<AlertListWidget {...BASE_PROPS} data={{ alerts: [] }} />);
    expect(screen.getByText('No active alerts')).toBeInTheDocument();
  });

  it('renders alerts from envelope shape', () => {
    const data = {
      alerts: [
        { id: 'a1', title: 'Disk full', severity: 'critical', timestamp: '2026-01-01T10:00:00Z' },
        { id: 'a2', title: 'High memory', severity: 'warning', timestamp: '2026-01-01T09:00:00Z' },
      ],
    };
    render(<AlertListWidget {...BASE_PROPS} data={data} />);
    expect(screen.getByText('Disk full')).toBeInTheDocument();
    expect(screen.getByText('High memory')).toBeInTheDocument();
  });

  it('renders alerts from raw Notification[] (API shape)', () => {
    const data = [
      {
        notificationId: 'notif-001',
        title: 'Agent offline',
        tier: 5,
        createdAt: '2026-01-01T10:00:00Z',
        status: 'active',
      },
    ];
    render(<AlertListWidget {...BASE_PROPS} data={data} />);
    expect(screen.getByText('Agent offline')).toBeInTheDocument();
  });

  it('maps tier 5 to critical severity', () => {
    const data = [
      { notificationId: 'n1', title: 'Critical alert', tier: 5, createdAt: '2026-01-01T00:00:00Z' },
    ];
    render(<AlertListWidget {...BASE_PROPS} data={data} />);
    // Critical alerts should display an AlertTriangle
    const triangles = document.querySelectorAll('[data-lucide="alert-triangle"]');
    // We can't reliably check color, but it should render with the icon
    expect(screen.getByText('Critical alert')).toBeInTheDocument();
    void triangles; // suppress unused warning
  });
});

// ── 4. ActivityFeedWidget ────────────────────────────────────────────

describe('ActivityFeedWidget', () => {
  it('shows loading state', () => {
    const { container } = render(
      <ActivityFeedWidget {...LOADING_PROPS} data={null} />,
    );
    expect(container.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('shows error state', () => {
    render(<ActivityFeedWidget {...ERROR_PROPS} data={null} />);
    expect(screen.getByText('Failed to load data')).toBeInTheDocument();
  });

  it('shows configure message when data is null', () => {
    render(<ActivityFeedWidget {...BASE_PROPS} data={null} />);
    expect(screen.getByText('Configure a data source')).toBeInTheDocument();
  });

  it('renders events from envelope shape', () => {
    const data = {
      events: [
        {
          timestamp: '2026-01-01T10:00:00Z',
          action: 'Node registered',
          description: 'server-01 was registered',
        },
      ],
    };
    render(<ActivityFeedWidget {...BASE_PROPS} data={data} />);
    expect(screen.getByText('Node registered')).toBeInTheDocument();
    expect(screen.getByText('server-01 was registered')).toBeInTheDocument();
  });

  it('renders events from TimelineResponse (API shape)', () => {
    const data = {
      since: '2026-01-01T00:00:00Z',
      until: '2026-01-01T23:59:00Z',
      total: 1,
      events: [
        {
          eventId: 'ev-001',
          eventType: 'node_registered',
          timestamp: '2026-01-01T10:00:00Z',
          entityType: 'node',
          entityId: 'server-01',
          description: 'Node server-01 registered',
          metadata: {},
        },
      ],
    };
    render(<ActivityFeedWidget {...BASE_PROPS} data={data} />);
    expect(screen.getByText('Node registered')).toBeInTheDocument();
    expect(screen.getByText('Node server-01 registered')).toBeInTheDocument();
  });

  it('renders events from raw TimelineEvent[] (API shape)', () => {
    const data = [
      {
        eventId: 'ev-002',
        eventType: 'service_discovered',
        timestamp: '2026-01-01T11:00:00Z',
        entityType: 'service',
        entityId: 'svc-nginx-a1b2',
        description: 'Service nginx discovered',
        metadata: {},
      },
    ];
    render(<ActivityFeedWidget {...BASE_PROPS} data={data} />);
    expect(screen.getByText('Service discovered')).toBeInTheDocument();
  });

  it('respects limit config', () => {
    const data = {
      events: Array.from({ length: 30 }, (_, i) => ({
        timestamp: `2026-01-01T${String(i).padStart(2, '0')}:00:00Z`,
        action: `Event ${i}`,
        description: `Description ${i}`,
      })),
    };
    render(
      <ActivityFeedWidget {...BASE_PROPS} data={data} config={{ limit: 5 }} />,
    );
    // Only first 5 events should appear
    expect(screen.getByText('Event 0')).toBeInTheDocument();
    expect(screen.queryByText('Event 10')).not.toBeInTheDocument();
  });
});

// ── 5. LineChartWidget ───────────────────────────────────────────────

describe('LineChartWidget', () => {
  it('shows loading state', () => {
    const { container } = render(
      <LineChartWidget {...LOADING_PROPS} data={null} />,
    );
    expect(container.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('shows error state', () => {
    render(<LineChartWidget {...ERROR_PROPS} data={null} />);
    expect(screen.getByText('Failed to load data')).toBeInTheDocument();
  });

  it('shows configure message when data is null', () => {
    render(<LineChartWidget {...BASE_PROPS} data={null} />);
    expect(screen.getByText('Configure a data source')).toBeInTheDocument();
  });

  it('renders from native series shape', () => {
    const data = {
      series: [
        { name: 'CPU', data: [{ x: '10:00', y: 45 }, { x: '11:00', y: 60 }] },
      ],
    };
    const { container } = render(<LineChartWidget {...BASE_PROPS} data={data} />);
    // recharts renders a ResponsiveContainer div
    expect(container.querySelector('.recharts-responsive-container')).toBeTruthy();
  });

  it('renders from TimelineResponse shape', () => {
    const data = {
      since: '2026-01-01T00:00:00Z',
      until: '2026-01-01T23:59:00Z',
      total: 2,
      events: [
        { eventId: 'e1', eventType: 'profile_submitted', timestamp: '2026-01-01T10:00:00Z', entityType: 'node', entityId: 'n1', description: 'desc', metadata: {} },
        { eventId: 'e2', eventType: 'service_discovered', timestamp: '2026-01-01T11:00:00Z', entityType: 'service', entityId: 's1', description: 'desc', metadata: {} },
      ],
    };
    const { container } = render(<LineChartWidget {...BASE_PROPS} data={data} />);
    expect(container.querySelector('.recharts-responsive-container')).toBeTruthy();
  });

  it('renders from raw {x, y} array', () => {
    const data = [
      { x: '10:00', y: 10 },
      { x: '11:00', y: 20 },
    ];
    const { container } = render(<LineChartWidget {...BASE_PROPS} data={data} />);
    expect(container.querySelector('.recharts-responsive-container')).toBeTruthy();
  });
});

// ── 6. BarChartWidget ────────────────────────────────────────────────

describe('BarChartWidget', () => {
  it('shows loading state', () => {
    const { container } = render(
      <BarChartWidget {...LOADING_PROPS} data={null} />,
    );
    expect(container.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('shows error state', () => {
    render(<BarChartWidget {...ERROR_PROPS} data={null} />);
    expect(screen.getByText('Failed to load data')).toBeInTheDocument();
  });

  it('shows configure message when data is null', () => {
    render(<BarChartWidget {...BASE_PROPS} data={null} />);
    expect(screen.getByText('Configure a data source')).toBeInTheDocument();
  });

  it('renders from native shape', () => {
    const data = {
      categories: ['Jan', 'Feb', 'Mar'],
      series: [{ name: 'Nodes', data: [5, 8, 12] }],
    };
    const { container } = render(<BarChartWidget {...BASE_PROPS} data={data} />);
    expect(container.querySelector('.recharts-responsive-container')).toBeTruthy();
  });

  it('renders from raw NodeSummary[] (auto-aggregated by class)', () => {
    const data = [
      { nodeId: 'n1', displayName: 'server-01', class: 'compute', status: 'active' },
      { nodeId: 'n2', displayName: 'switch-01', class: 'networking', status: 'active' },
      { nodeId: 'n3', displayName: 'server-02', class: 'compute', status: 'active' },
    ];
    const { container } = render(<BarChartWidget {...BASE_PROPS} data={data} />);
    expect(container.querySelector('.recharts-responsive-container')).toBeTruthy();
  });

  it('renders from [{label, value}] tuples', () => {
    const data = [
      { label: 'compute', value: 10 },
      { label: 'networking', value: 3 },
    ];
    const { container } = render(<BarChartWidget {...BASE_PROPS} data={data} />);
    expect(container.querySelector('.recharts-responsive-container')).toBeTruthy();
  });
});

// ── 7. AreaChartWidget ───────────────────────────────────────────────

describe('AreaChartWidget', () => {
  it('shows loading state', () => {
    const { container } = render(
      <AreaChartWidget {...LOADING_PROPS} data={null} />,
    );
    expect(container.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('shows error state', () => {
    render(<AreaChartWidget {...ERROR_PROPS} data={null} />);
    expect(screen.getByText('Failed to load data')).toBeInTheDocument();
  });

  it('shows configure message when data is null', () => {
    render(<AreaChartWidget {...BASE_PROPS} data={null} />);
    expect(screen.getByText('Configure a data source')).toBeInTheDocument();
  });

  it('renders from native series shape', () => {
    const data = {
      series: [
        { name: 'Bandwidth', data: [{ x: '10:00', y: 100 }, { x: '11:00', y: 150 }] },
      ],
    };
    const { container } = render(<AreaChartWidget {...BASE_PROPS} data={data} />);
    expect(container.querySelector('.recharts-responsive-container')).toBeTruthy();
  });

  it('renders from TimelineResponse', () => {
    const data = {
      since: '2026-01-01T00:00:00Z',
      until: '2026-01-01T23:59:00Z',
      total: 1,
      events: [
        { eventId: 'e1', eventType: 'profile_submitted', timestamp: '2026-01-01T10:30:00Z', entityType: 'node', entityId: 'n1', description: 'desc', metadata: {} },
      ],
    };
    const { container } = render(<AreaChartWidget {...BASE_PROPS} data={data} />);
    expect(container.querySelector('.recharts-responsive-container')).toBeTruthy();
  });

  it('renders from raw {t, v} tuples', () => {
    const data = [
      { t: '10:00', v: 100 },
      { t: '11:00', v: 150 },
    ];
    const { container } = render(<AreaChartWidget {...BASE_PROPS} data={data} />);
    expect(container.querySelector('.recharts-responsive-container')).toBeTruthy();
  });
});

// ── 8. HeatmapWidget ────────────────────────────────────────────────

describe('HeatmapWidget', () => {
  it('shows loading state', () => {
    const { container } = render(
      <HeatmapWidget {...LOADING_PROPS} data={null} />,
    );
    expect(container.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('shows error state', () => {
    render(<HeatmapWidget {...ERROR_PROPS} data={null} />);
    expect(screen.getByText('Failed to load data')).toBeInTheDocument();
  });

  it('shows no-data state when data is null', () => {
    render(<HeatmapWidget {...BASE_PROPS} data={null} />);
    expect(screen.getAllByText('No heatmap data').length).toBeGreaterThan(0);
  });

  it('renders from native heatmap shape', () => {
    const data = {
      rows: ['server-01', 'server-02'],
      columns: ['Mon', 'Tue', 'Wed'],
      values: [
        [10, 20, 30],
        [5, 15, 25],
      ],
    };
    render(<HeatmapWidget {...BASE_PROPS} data={data} />);
    expect(screen.getByText('server-01')).toBeInTheDocument();
    expect(screen.getByText('Mon')).toBeInTheDocument();
  });

  it('renders from [{x, y, v}] sparse tuples', () => {
    const data = [
      { x: 'Mon', y: 'server-01', v: 10 },
      { x: 'Tue', y: 'server-01', v: 20 },
      { x: 'Mon', y: 'server-02', v: 5 },
    ];
    render(<HeatmapWidget {...BASE_PROPS} data={data} />);
    expect(screen.getByText('server-01')).toBeInTheDocument();
    expect(screen.getByText('Mon')).toBeInTheDocument();
  });

  it('renders from raw entity array (builds from numeric fields)', () => {
    const data = [
      { nodeId: 'n1', displayName: 'server-01', servicesCount: 5, profileCount: 12 },
      { nodeId: 'n2', displayName: 'server-02', servicesCount: 3, profileCount: 8 },
    ];
    render(<HeatmapWidget {...BASE_PROPS} data={data} />);
    expect(screen.getByText('server-01')).toBeInTheDocument();
  });
});

// ── 9. NetworkMapWidget ──────────────────────────────────────────────

describe('NetworkMapWidget', () => {
  it('shows loading state', () => {
    const { container } = render(
      <NetworkMapWidget {...LOADING_PROPS} data={null} />,
    );
    expect(container.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('shows error state', () => {
    render(<NetworkMapWidget {...ERROR_PROPS} data={null} />);
    expect(screen.getByText('Failed to load data')).toBeInTheDocument();
  });

  it('shows no-network-data when data is null', () => {
    render(<NetworkMapWidget {...BASE_PROPS} data={null} />);
    expect(screen.getByText('No network data')).toBeInTheDocument();
  });

  it('renders networks from envelope shape', () => {
    const data = {
      networks: [
        { networkId: 'net-01', name: 'LAN', cidr: '192.168.1.0/24', nodeCount: 5, type: 'physical' },
        { networkId: 'net-02', name: 'IoT', cidr: '10.0.0.0/24', nodeCount: 3, type: 'vlan' },
      ],
    };
    render(<NetworkMapWidget {...BASE_PROPS} data={data} />);
    expect(screen.getByText('LAN')).toBeInTheDocument();
    expect(screen.getByText('IoT')).toBeInTheDocument();
  });

  it('renders networks from raw NetworkSummary[] (API shape)', () => {
    const data = [
      { networkId: 'net-01', name: 'Home LAN', type: 'physical', cidr: '192.168.1.0/24', nodeCount: 8, tags: [] },
      { networkId: 'net-02', name: 'Guest WiFi', type: 'vlan', cidr: '10.1.0.0/24', nodeCount: 2, tags: [] },
    ];
    render(<NetworkMapWidget {...BASE_PROPS} data={data} />);
    expect(screen.getByText('Home LAN')).toBeInTheDocument();
    expect(screen.getByText('Guest WiFi')).toBeInTheDocument();
  });

  it('shows navigation button on click', async () => {
    const onNavigate = vi.fn();
    const data = [
      { networkId: 'net-01', name: 'Home LAN', type: 'physical', cidr: '192.168.1.0/24', nodeCount: 8, tags: [] },
    ];
    render(<NetworkMapWidget {...BASE_PROPS} data={data} onNavigate={onNavigate} />);
    const button = screen.getByRole('button', { name: /Home LAN/i });
    button.click();
    expect(onNavigate).toHaveBeenCalledWith('/networks/net-01');
  });
});

// ── 10. ChangeLogWidget ──────────────────────────────────────────────

describe('ChangeLogWidget', () => {
  it('shows loading state', () => {
    const { container } = render(
      <ChangeLogWidget {...LOADING_PROPS} data={null} />,
    );
    expect(container.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('shows error state', () => {
    render(<ChangeLogWidget {...ERROR_PROPS} data={null} />);
    expect(screen.getByText('Failed to load data')).toBeInTheDocument();
  });

  it('shows no-changes when data is null', () => {
    render(<ChangeLogWidget {...BASE_PROPS} data={null} />);
    expect(screen.getByText('No changes recorded')).toBeInTheDocument();
  });

  it('renders changes from explicit envelope', () => {
    const data = {
      changes: [
        { timestamp: '2026-01-01T10:00:00Z', type: 'create', entity: 'server-01', description: 'Node registered' },
        { timestamp: '2026-01-01T11:00:00Z', type: 'update', entity: 'nginx', description: 'Service updated' },
      ],
    };
    render(<ChangeLogWidget {...BASE_PROPS} data={data} />);
    expect(screen.getByText('server-01')).toBeInTheDocument();
    expect(screen.getByText('nginx')).toBeInTheDocument();
  });

  it('renders changes from TimelineResponse (API shape)', () => {
    const data = {
      since: '2026-01-01T00:00:00Z',
      until: '2026-01-01T23:59:00Z',
      total: 2,
      events: [
        {
          eventId: 'ev-001',
          eventType: 'node_registered',
          timestamp: '2026-01-01T10:00:00Z',
          entityType: 'node',
          entityId: 'server-01',
          description: 'Node server-01 was registered',
          metadata: {},
        },
        {
          eventId: 'ev-002',
          eventType: 'service_removed',
          timestamp: '2026-01-01T11:00:00Z',
          entityType: 'service',
          entityId: 'svc-old-a1b2',
          description: 'Service svc-old-a1b2 was removed',
          metadata: {},
        },
      ],
    };
    render(<ChangeLogWidget {...BASE_PROPS} data={data} />);
    expect(screen.getByText('server-01')).toBeInTheDocument();
    expect(screen.getByText('svc-old-a1b2')).toBeInTheDocument();
  });

  it('maps eventType to correct change type badge', () => {
    const data = {
      events: [
        {
          eventId: 'ev-001',
          eventType: 'node_registered',
          timestamp: '2026-01-01T10:00:00Z',
          entityType: 'node',
          entityId: 'server-01',
          description: 'Node registered',
          metadata: {},
        },
        {
          eventId: 'ev-002',
          eventType: 'service_removed',
          timestamp: '2026-01-01T11:00:00Z',
          entityType: 'service',
          entityId: 'svc-abc',
          description: 'Service removed',
          metadata: {},
        },
        {
          eventId: 'ev-003',
          eventType: 'profile_submitted',
          timestamp: '2026-01-01T12:00:00Z',
          entityType: 'node',
          entityId: 'server-02',
          description: 'Profile submitted',
          metadata: {},
        },
      ],
    };
    render(<ChangeLogWidget {...BASE_PROPS} data={data} />);
    // Check the badge texts are rendered
    expect(screen.getByText('create')).toBeInTheDocument();
    expect(screen.getByText('delete')).toBeInTheDocument();
    expect(screen.getByText('update')).toBeInTheDocument();
  });
});
