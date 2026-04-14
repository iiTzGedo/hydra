import { describe, expect, it } from 'vitest';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MCPMarketplacePage from '@/views/mcp/marketplace';
import { queryKeys } from '@/lib/query-client';
import type { MCPServerListResponse } from '@/api/mcp';
import { renderWithRoute } from '../page-test-utils';

describe('MCP Marketplace Integration', () => {
  it('renders the marketplace page with default non-built-in server actions', async () => {
    const { queryClient } = renderWithRoute(<MCPMarketplacePage />, {
      path: '/mcp-marketplace',
      route: '/mcp-marketplace',
    });

    expect(await screen.findByRole('heading', { name: 'MCP Marketplace' })).toBeInTheDocument();
    await waitFor(() => {
      const servers = queryClient.getQueryData<MCPServerListResponse>(queryKeys.mcp.servers());
      expect(servers?.servers).toHaveLength(2);
    });
    expect(screen.queryByText('No MCP servers configured')).not.toBeInTheDocument();
    expect(await screen.findByRole('tab', { name: 'Servers (2)' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Disconnect' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Connect' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Remove Docker MCP' })).toBeInTheDocument();
  });

  it('adds a server through the modal flow', async () => {
    const user = userEvent.setup();

    const { queryClient } = renderWithRoute(<MCPMarketplacePage />, {
      path: '/mcp-marketplace',
      route: '/mcp-marketplace',
    });

    await user.click(await screen.findByRole('button', { name: 'Add Server' }));
    const dialog = await screen.findByRole('dialog');
    await act(async () => {
      fireEvent.change(screen.getByLabelText('Server name'), { target: { value: 'Grafana MCP' } });
      fireEvent.change(screen.getByLabelText('Server endpoint URL'), {
        target: { value: 'http://grafana-mcp.local' },
      });
      fireEvent.change(screen.getByLabelText('Server description'), {
        target: { value: 'Dashboards and alerts' },
      });
      await user.click(within(dialog).getByRole('button', { name: 'Add Server' }));
    });

    await waitFor(() => {
      const servers = queryClient.getQueryData<MCPServerListResponse>(queryKeys.mcp.servers());
      expect(servers?.servers.some((server) => server.name === 'Grafana MCP')).toBe(true);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    expect(await screen.findByText('Grafana MCP')).toBeInTheDocument();
  });

  it('shows the marketplace sources tab and add-source entry point', async () => {
    const user = userEvent.setup();

    renderWithRoute(<MCPMarketplacePage />, {
      path: '/mcp-marketplace',
      route: '/mcp-marketplace',
    });

    await user.click(await screen.findByRole('tab', { name: /Marketplace Sources/i }));

    expect(await screen.findByText('Hydra Registry')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Add Source' })).toBeInTheDocument();
  });
});
