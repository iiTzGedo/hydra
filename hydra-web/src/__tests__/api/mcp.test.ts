import { describe, expect, it, vi } from 'vitest';
import { waitFor } from '@testing-library/react';
import {
  useCheckMCPServerHealth,
  useCreateMCPServer,
  useDeleteMCPServer,
  useHydraMCPHealth,
  useHydraMCPPrompts,
  useHydraMCPTools,
  useMCPServer,
  useMCPServerHealth,
  useMCPServerPrompts,
  useMCPServerResources,
  useMCPServers,
  useMCPServerTools,
  useUpdateMCPServer,
} from '@/api/mcp';
import { createTestQueryClient, renderWithQuery } from '../msw/test-utils';

describe('MCP API Hooks', () => {
  it('fetches MCP servers', async () => {
    const { result } = renderWithQuery(() => useMCPServers());

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.servers).toHaveLength(2);
    expect(result.current.data?.servers[0].serverId).toBe('hydra-mcp');
  });

  it('disables server detail when serverId is empty', () => {
    const { result } = renderWithQuery(() => useMCPServer(''));

    expect(result.current.isFetching).toBe(false);
    expect(result.current.data).toBeUndefined();
  });

  it('fetches server health, tools, resources, and prompts', async () => {
    const health = renderWithQuery(() => useMCPServerHealth('hydra-mcp')).result;
    const tools = renderWithQuery(() => useMCPServerTools('hydra-mcp')).result;
    const resources = renderWithQuery(() => useMCPServerResources('hydra-mcp')).result;
    const prompts = renderWithQuery(() => useMCPServerPrompts('hydra-mcp')).result;

    await waitFor(() => {
      expect(health.current.isSuccess).toBe(true);
      expect(tools.current.isSuccess).toBe(true);
      expect(resources.current.isSuccess).toBe(true);
      expect(prompts.current.isSuccess).toBe(true);
    });

    expect(health.current.data?.status).toBe('healthy');
    expect(tools.current.data?.tools[0].name).toBe('nodes.list');
    expect(resources.current.data?.resources[0].uri).toContain('hydra://nodes');
    expect(prompts.current.data?.prompts[0].name).toBe('summarize_homelab');
  });

  it('fetches dedicated Hydra MCP endpoints', async () => {
    const health = renderWithQuery(() => useHydraMCPHealth()).result;
    const tools = renderWithQuery(() => useHydraMCPTools()).result;
    const prompts = renderWithQuery(() => useHydraMCPPrompts()).result;

    await waitFor(() => {
      expect(health.current.isSuccess).toBe(true);
      expect(tools.current.isSuccess).toBe(true);
      expect(prompts.current.isSuccess).toBe(true);
    });

    expect(health.current.data?.serverName).toBe('Hydra MCP');
    expect(tools.current.data?.tools).toHaveLength(2);
    expect(prompts.current.data?.prompts).toHaveLength(1);
  });

  it('invalidates the expected keys for MCP mutations', async () => {
    const queryClient = createTestQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const createServer = renderWithQuery(() => useCreateMCPServer(), { queryClient }).result;
    createServer.current.mutate({
      name: 'New Server',
      endpoint: 'http://new-server.local',
    });
    await waitFor(() => expect(createServer.current.isSuccess).toBe(true));

    const updateServer = renderWithQuery(() => useUpdateMCPServer(), { queryClient }).result;
    updateServer.current.mutate({
      serverId: 'docker-mcp',
      data: { enabled: true },
    });
    await waitFor(() => expect(updateServer.current.isSuccess).toBe(true));

    const deleteServer = renderWithQuery(() => useDeleteMCPServer(), { queryClient }).result;
    deleteServer.current.mutate('docker-mcp');
    await waitFor(() => expect(deleteServer.current.isSuccess).toBe(true));

    const checkHealth = renderWithQuery(() => useCheckMCPServerHealth(), { queryClient }).result;
    checkHealth.current.mutate('hydra-mcp');
    await waitFor(() => expect(checkHealth.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['mcp', 'servers'] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['mcp', 'serverStatus', 'docker-mcp'] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['mcp', 'serverStatus', 'hydra-mcp'] });
  });
});
