import { describe, expect, it } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MCPMarketplacePage from '@/pages/mcp/marketplace';
import { mockState } from '../msw/mock-state';
import { renderWithRoute } from '../page-test-utils';

describe('MCP Marketplace Integration', () => {
  it('renders the configured server list', async () => {
    renderWithRoute(<MCPMarketplacePage />, {
      path: '/mcp-marketplace',
      route: '/mcp-marketplace',
    });

    expect(await screen.findByRole('heading', { name: 'MCP Marketplace' })).toBeInTheDocument();
    expect(await screen.findByText('Hydra MCP')).toBeInTheDocument();
    expect(await screen.findByText('Docker MCP')).toBeInTheDocument();
  });

  it('adds a server through the modal flow', async () => {
    const user = userEvent.setup();

    renderWithRoute(<MCPMarketplacePage />, {
      path: '/mcp-marketplace',
      route: '/mcp-marketplace',
    });

    await user.click(await screen.findByRole('button', { name: 'Add Server' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(screen.getByLabelText('Server name'), 'Grafana MCP');
    await user.type(screen.getByLabelText('Server endpoint URL'), 'http://grafana-mcp.local');
    await user.type(screen.getByLabelText('Server description'), 'Dashboards and alerts');
    await user.click(within(dialog).getByRole('button', { name: 'Add Server' }));

    expect(await screen.findByText('Grafana MCP')).toBeInTheDocument();
  });

  it('connects a server, refreshes health, and shows unhealthy health messaging', async () => {
    const user = userEvent.setup();

    mockState.mcpHealth['docker-mcp'] = {
      serverId: 'docker-mcp',
      status: 'unhealthy',
      message: 'Docker MCP failed authentication',
      checkedAt: '2026-03-09T12:30:00Z',
      tools: ['containers.ps'],
      resources: [],
    };

    renderWithRoute(<MCPMarketplacePage />, {
      path: '/mcp-marketplace',
      route: '/mcp-marketplace',
    });

    const dockerCard = (await screen.findByText('Docker MCP')).closest('[class*="rounded-lg"]');
    expect(dockerCard).not.toBeNull();

    await user.click(within(dockerCard as HTMLElement).getByRole('button', { name: 'Connect' }));

    await waitFor(() => {
      expect(within(dockerCard as HTMLElement).getByText('Docker MCP failed authentication')).toBeInTheDocument();
      expect(within(dockerCard as HTMLElement).getByText('unhealthy')).toBeInTheDocument();
    });
  });

  it('removes a server from the list', async () => {
    const user = userEvent.setup();

    renderWithRoute(<MCPMarketplacePage />, {
      path: '/mcp-marketplace',
      route: '/mcp-marketplace',
    });

    await user.click(await screen.findByRole('button', { name: 'Remove Docker MCP' }));

    await waitFor(() => {
      expect(screen.queryByText('Docker MCP')).not.toBeInTheDocument();
    });
  });
});
