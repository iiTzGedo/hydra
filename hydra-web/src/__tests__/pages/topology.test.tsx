import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import TopologyPage from '@/pages/topology';
import { server } from '../msw/server';
import { renderWithRoute } from '../page-test-utils';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080/api/v1';

vi.mock('@xyflow/react', () => ({
  ReactFlow: ({ children, nodes, edges }: { children: React.ReactNode; nodes: unknown[]; edges: unknown[] }) => (
    <div data-testid="react-flow" data-nodes={nodes.length} data-edges={edges.length}>
      {children}
    </div>
  ),
  Background: () => <div data-testid="flow-background" />,
  Controls: () => <div data-testid="flow-controls" />,
  MiniMap: () => <div data-testid="flow-minimap" />,
  Panel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useNodesState: (initial: unknown[]) => {
    const [nodes, setNodes] = React.useState(initial);
    return [nodes, setNodes, vi.fn()] as const;
  },
  useEdgesState: (initial: unknown[]) => {
    const [edges, setEdges] = React.useState(initial);
    return [edges, setEdges, vi.fn()] as const;
  },
  Position: { Right: 'right', Left: 'left' },
  ConnectionMode: { Loose: 'Loose' },
  MarkerType: { ArrowClosed: 'arrow' },
}));

vi.mock('@/lib/topology-layout', () => ({
  getLayoutedElements: async (nodes: unknown[], edges: unknown[]) => ({ nodes, edges }),
  getGridLayout: (nodes: unknown[]) => nodes,
  getLayoutOptionsForMode: () => ({}),
}));

describe('Topology Page Integration', () => {
  it('renders the topology controls and supports mode, filter, group, and search interactions', async () => {
    const user = userEvent.setup();

    renderWithRoute(<TopologyPage />, {
      path: '/topology',
      route: '/topology',
    });

    expect(await screen.findByText('Infrastructure Topology')).toBeInTheDocument();
    expect(await screen.findByText('3 nodes')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'Network' }));
    expect(await screen.findByText('Network Topology')).toBeInTheDocument();

    await user.click(screen.getByLabelText('Filter node types'));
    await user.click(await screen.findByText('Networking'));
    await waitFor(() => {
      expect(screen.getByLabelText('Filter node types')).toHaveTextContent('Networking');
    });

    await user.click(screen.getByLabelText('Highlight group'));
    await user.click(await screen.findByText('Production Servers'));
    await waitFor(() => {
      expect(screen.getByLabelText('Highlight group')).toHaveTextContent('Production Servers');
    });

    await user.type(screen.getByLabelText('Search nodes'), 'gateway');
    expect(screen.getByDisplayValue('gateway')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /regenerate/i }));
    expect(await screen.findByText('Network Topology')).toBeInTheDocument();
  });

  it('renders the empty state when the latest topology has no graph data', async () => {
    server.use(
      http.get(`${BASE_URL}/topologies/latest`, () =>
        HttpResponse.json({
          data: {
            topologyId: 'topology-empty',
            mode: 'infrastructure',
            version: 1,
            generatedAt: '2026-03-09T12:00:00Z',
            validFrom: '2026-03-09T12:00:00Z',
            stats: {
              nodeCount: 0,
              edgeCount: 0,
              networkCount: 0,
              serviceCount: 0,
              computeTimeMs: 1,
            },
            graph: {
              nodes: [],
              edges: [],
            },
          },
        })
      )
    );

    renderWithRoute(<TopologyPage />, {
      path: '/topology',
      route: '/topology',
    });

    expect(await screen.findByText('No infrastructure topology data')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /generate topology/i })).toBeInTheDocument();
  });
});
