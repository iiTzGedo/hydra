import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { HistoricalTopology, TimelineResponse } from '@/types/timemachine';
import TimeMachinePage from '@/views/timemachine';
import { renderWithRoute } from '../page-test-utils';

const {
  mockRouterPush,
  mockUseTimeline,
  mockUseTopologyStateAt,
} = vi.hoisted(() => ({
  mockRouterPush: vi.fn(),
  mockUseTimeline: vi.fn(),
  mockUseTopologyStateAt: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockRouterPush,
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => '/timemachine',
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
}));

vi.mock('@/api/timemachine', () => ({
  useTimeline: (...args: unknown[]) => mockUseTimeline(...args),
  useTopologyStateAt: (...args: unknown[]) => mockUseTopologyStateAt(...args),
}));

vi.mock('@/components/timemachine/calendar-view', () => ({
  CalendarView: ({
    selectedDate,
    onSelectDate,
  }: {
    selectedDate: Date | null;
    onSelectDate: (date: Date) => void;
  }) => (
    <div>
      <p>Calendar mock</p>
      <p>{selectedDate ? `Selected calendar date: ${selectedDate.toISOString()}` : 'No date selected'}</p>
      <button type="button" onClick={() => onSelectDate(new Date('2026-03-10T12:00:00Z'))}>
        Pick March 10
      </button>
    </div>
  ),
}));

vi.mock('@/components/timemachine/historical-topology', () => ({
  HistoricalTopology: ({
    timestamp,
    topologyState,
    isLoading,
  }: {
    timestamp: Date;
    topologyState: {
      nodes?: Array<{ id: string }>;
      edges?: Array<{ from: string; to: string }>;
    } | null;
    isLoading: boolean;
  }) => (
    <div data-testid="historical-topology">
      <p>{isLoading ? 'Topology loading' : 'Topology ready'}</p>
      <p>{`Topology timestamp: ${timestamp.toISOString()}`}</p>
      <p>{`Nodes captured: ${topologyState?.nodes?.length ?? 0}`}</p>
    </div>
  ),
}));

const TIMELINE: TimelineResponse = {
  events: [
    {
      eventId: 'event-001',
      eventType: 'node_registered',
      timestamp: '2026-03-10T09:30:00.000Z',
      entityType: 'node',
      entityId: 'node-alpha',
      description: 'Registered alpha node',
      metadata: { source: 'agent' },
    },
    {
      eventId: 'event-002',
      eventType: 'node_archived',
      timestamp: '2026-03-12T15:00:00.000Z',
      entityType: 'node',
      entityId: 'node-beta',
      description: 'Archived beta node',
      metadata: { reason: 'maintenance' },
    },
  ],
  since: '2026-03-09T00:00:00.000Z',
  until: '2026-03-13T00:00:00.000Z',
  total: 2,
};

function createTopology(timestamp: string): HistoricalTopology {
  const isArchived = timestamp.startsWith('2026-03-12');

  return {
    timestamp,
    mode: 'infrastructure',
    topologyId: isArchived ? 'topology-beta' : 'topology-alpha',
    version: isArchived ? 2 : 1,
    generatedAt: timestamp,
    stats: {},
    graph: {
      nodes: [
        {
          id: isArchived ? 'node-beta' : 'node-alpha',
          type: 'topology',
          label: isArchived ? 'node-beta' : 'node-alpha',
          position: { x: 0, y: 0 },
          data: {
            class: 'compute',
            kind: isArchived ? 'vm' : 'server',
            status: isArchived ? 'archived' : 'online',
          },
        },
      ],
      edges: [],
    },
  };
}

describe('Time Machine Integration', () => {
  beforeEach(() => {
    mockRouterPush.mockReset();
    mockUseTimeline.mockReset();
    mockUseTopologyStateAt.mockReset();

    mockUseTimeline.mockReturnValue({
      data: TIMELINE,
      isLoading: false,
    });

    mockUseTopologyStateAt.mockImplementation((timestamp: string) => ({
      data: timestamp ? createTopology(timestamp) : undefined,
      isLoading: false,
    }));
  });

  it('selects the latest event by default, keeps topology in sync, and supports calendar-driven reselection', async () => {
    const user = userEvent.setup();

    renderWithRoute(<TimeMachinePage />, {
      path: '/timemachine',
      route: '/timemachine',
    });

    expect(await screen.findByRole('heading', { name: 'Time Machine' })).toBeInTheDocument();

    // Details panel renders the event label as an h3; the Timeline card uses a p.
    // Waiting for the h3 is how we confirm the default selection (latest event).
    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 3, name: 'Node Archived' })).toBeInTheDocument();
    });
    expect(screen.getByText('Topology timestamp: 2026-03-12T15:00:00.000Z')).toBeInTheDocument();
    expect(screen.getByText('Nodes captured: 1')).toBeInTheDocument();

    const timelineEvent = screen
      .getAllByText('Registered alpha node')
      .find((element) => element.tagName.toLowerCase() === 'p');

    if (!timelineEvent) {
      throw new Error('Expected timeline entry for the older registered-node event');
    }
    await user.click(timelineEvent);

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 3, name: 'Node Registered' })).toBeInTheDocument();
    });
    expect(screen.getByText('Topology timestamp: 2026-03-10T09:30:00.000Z')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'View node' }));
    expect(mockRouterPush).toHaveBeenCalledWith('/nodes/node-alpha');

    await user.click(screen.getByRole('tab', { name: 'Calendar' }));
    expect(await screen.findByText('Calendar mock')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Pick March 10' }));

    await waitFor(() => {
      expect(screen.getByText('Selected calendar date: 2026-03-10T09:30:00.000Z')).toBeInTheDocument();
    });
    expect(screen.getByText('Topology timestamp: 2026-03-10T09:30:00.000Z')).toBeInTheDocument();
  });

  it('renders the no-events states when the selected range is empty', async () => {
    mockUseTimeline.mockReturnValue({
      data: {
        ...TIMELINE,
        events: [],
        total: 0,
      },
      isLoading: false,
    });

    renderWithRoute(<TimeMachinePage />, {
      path: '/timemachine',
      route: '/timemachine',
    });

    expect(await screen.findByText('No events in selected range')).toBeInTheDocument();
    expect(screen.getByText('No events to display')).toBeInTheDocument();
    expect(screen.getByText('Select an event to view details')).toBeInTheDocument();
  });
});
