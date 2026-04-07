import { describe, expect, it } from 'vitest';
import { waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { useCommand, useCommandCatalog, useCommands } from '@/api/commands';
import { renderWithQuery } from '../msw/test-utils';
import { server } from '../msw/server';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080/api/v1';

describe('Commands API Hooks', () => {
  it('fetches command catalog entries with delivery mode metadata', async () => {
    server.use(
      http.get(`${BASE_URL}/command-catalog`, () =>
        HttpResponse.json({
          data: [
            {
              registryId: 'reg::agent::update',
              category: 'agent',
              action: 'update',
              displayName: 'Update Agent',
              description: 'Update agent to new version',
              minimumRole: 'admin',
              requiresConfirmation: true,
              timeout: 120,
              deliveryMode: 'poll_only',
              builtIn: true,
              deprecated: false,
            },
          ],
        })
      )
    );

    const { result } = renderWithQuery(() => useCommandCatalog());

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual([
      expect.objectContaining({
        registryId: 'reg::agent::update',
        category: 'agent',
        deliveryMode: 'poll_only',
      }),
    ]);
  });

  it('fetches command detail including structured result data', async () => {
    server.use(
      http.get(`${BASE_URL}/commands/cmd-abc123`, () =>
        HttpResponse.json({
          data: {
            commandId: 'cmd-abc123',
            registryId: 'reg::agent::probe-network',
            type: 'agent',
            action: 'probe-network',
            target: {
              nodeId: 'server-01',
              serviceId: null,
            },
            parameters: {
              subnet: '192.168.1.0/30',
            },
            status: 'completed',
            executionMethod: 'agent-poll',
            result: {
              success: true,
              output: 'Probe completed',
              exitCode: 0,
              error: null,
              data: {
                hosts: [
                  {
                    ip: '192.168.1.1',
                    reachable: true,
                  },
                ],
              },
            },
            error: null,
            timeoutSeconds: 120,
            retryCount: 0,
            queuePosition: null,
            createdAt: '2026-03-23T10:00:00Z',
            queuedAt: '2026-03-23T10:00:01Z',
            startedAt: '2026-03-23T10:00:02Z',
            completedAt: '2026-03-23T10:00:03Z',
            cancelledAt: null,
            cancelledBy: null,
          },
        })
      )
    );

    const { result } = renderWithQuery(() => useCommand('cmd-abc123'));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.type).toBe('agent');
    expect(result.current.data?.result?.data).toEqual({
      hosts: [{ ip: '192.168.1.1', reachable: true }],
    });
  });

  it('passes serviceId through to command list queries', async () => {
    server.use(
      http.get(`${BASE_URL}/commands`, ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get('nodeId')).toBe('server-01');
        expect(url.searchParams.get('serviceId')).toBe('svc-nginx-a1b2');
        return HttpResponse.json({ data: [] });
      })
    );

    const { result } = renderWithQuery(() =>
      useCommands({ nodeId: 'server-01', serviceId: 'svc-nginx-a1b2' })
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([]);
  });

  it('keeps polling command lists while commands are active', async () => {
    let requestCount = 0;
    server.use(
      http.get(`${BASE_URL}/commands`, () => {
        requestCount += 1;
        return HttpResponse.json({
          data:
            requestCount === 1
              ? [
                  {
                    commandId: 'cmd-abc123',
                    registryId: 'reg::service::restart',
                    type: 'service',
                    target: {
                      nodeId: 'server-01',
                      serviceId: 'svc-nginx-a1b2',
                    },
                    action: 'restart',
                    status: 'queued',
                    createdAt: '2026-03-23T10:00:00Z',
                  },
                ]
              : [
                  {
                    commandId: 'cmd-abc123',
                    registryId: 'reg::service::restart',
                    type: 'service',
                    target: {
                      nodeId: 'server-01',
                      serviceId: 'svc-nginx-a1b2',
                    },
                    action: 'restart',
                    status: 'completed',
                    createdAt: '2026-03-23T10:00:00Z',
                  },
                ],
        });
      })
    );

    const { result } = renderWithQuery(() => useCommands({ nodeId: 'server-01' }));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(requestCount).toBe(1);

    await waitFor(() => expect(requestCount).toBeGreaterThanOrEqual(2), {
      timeout: 4000,
    });
  }, 10000);
});
