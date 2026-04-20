import { expect, test, type Page } from '@playwright/test';
import { gotoPage } from './helpers/app';

function apiResponse<T>(data: T, meta?: Record<string, unknown>) {
  return {
    data,
    ...(meta ? { meta } : {}),
  };
}

async function mockAuthenticatedSession(page: Page) {
  // Set a fake session cookie so Next.js middleware allows navigation to protected routes
  await page.context().addCookies([
    {
      name: 'hydra_access',
      value: 'mock-e2e-session',
      domain: 'localhost',
      path: '/',
    },
  ]);

  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        type: 'user',
        userId: 'user-001',
        username: 'system_admin',
        email: 'system_admin@example.com',
        role: 'admin',
        permissions: ['*:*'],
      }),
    });
  });

  await page.route('**/api/v1/auth/session/refresh', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ expiresIn: 3600 }),
    });
  });

  // Mock layout-level endpoints to prevent 401 cascades from the real API
  await page.route('**/api/v1/settings/user', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: { dashboard: { pinnedBoardIds: [] } } }),
    });
  });

  // User settings endpoint — the real API returns ``UserSettingsResponse``
  // directly (not wrapped in ``{data: ...}``). Mirror that shape so
  // ``useUserSettings`` reads ``settings.dashboard.*`` correctly and the
  // ``lastOpenedBoardId`` effect in the dashboard view reaches a fixed point.
  // Returning ``lastOpenedBoardId: 'board-e2e'`` from the start prevents a
  // mutate-refetch loop that otherwise keeps ``isMutating`` true indefinitely.
  const userSettingsBody = {
    userId: 'user-001',
    ui: {},
    views: {},
    notifications: {},
    dashboard: {
      pinnedBoardIds: [],
      lastOpenedBoardId: 'board-e2e',
    },
    updatedAt: '2026-04-06T00:00:00Z',
  };
  await page.route('**/api/v1/settings', async (route) => {
    const method = route.request().method();
    if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(userSettingsBody),
      });
      return;
    }
    if (method === 'PUT' || method === 'PATCH') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(userSettingsBody),
      });
      return;
    }
    await route.fallback();
  });

  await page.route('**/api/v1/notifications**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: [], meta: { total: 0, limit: 50, offset: 0 } }),
    });
  });

  // Sidebar workspace summary queries — answer with empty lists so the
  // dashboard page isn't blocked by unmocked 401s from the real backend.
  for (const resource of ['groups', 'networks', 'nodes']) {
    await page.route(`**/api/v1/${resource}**`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: [],
          meta: { total: 0, limit: 10, offset: 0 },
        }),
      });
    });
  }

  await page.route('**/api/v1/dashboards/templates**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: [], meta: { total: 0, limit: 50, offset: 0 } }),
    });
  });

  await page.route('**/api/v1/dashboards/**/shares', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: [] }),
    });
  });
}

test.describe('Dashboard and Discovery', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test.beforeEach(async ({ page }) => {
    await mockAuthenticatedSession(page);
  });

  test('dashboard widget settings persist through the editor flow', async ({ page }) => {
    let board = {
      boardId: 'board-e2e',
      name: 'Operations Overview',
      description: 'Browser test dashboard',
      icon: 'layout-dashboard',
      ownerId: 'user-001',
      ownerType: 'user',
      boardType: 'user',
      visibility: { scope: 'private', sharedWith: { roles: [], users: [] } },
      widgetCount: 1,
      tags: ['starter'],
      isHome: true,
      version: 1,
      createdAt: '2026-04-06T00:00:00Z',
      updatedAt: '2026-04-06T00:00:00Z',
      layout: {
        columns: 12,
        rowHeight: 80,
        breakpoints: {
          xl: { columns: 12, width: 1536 },
          lg: { columns: 12, width: 1200 },
          md: { columns: 8, width: 996 },
          sm: { columns: 4, width: 480 },
          xs: { columns: 2, width: 0 },
        },
      },
      widgets: [
        {
          instanceId: 'wi-service-summary',
          widgetType: 'hydra::service-summary',
          position: { x: 0, y: 0, w: 6, h: 4 },
          config: { hidden: false },
          dataBinding: null,
        },
      ],
      settings: {
        theme: 'inherit',
        autoRefresh: true,
        refreshInterval: 30,
        showHeader: true,
        kioskMode: false,
        kioskAutoScroll: false,
        kioskScrollSpeed: 30,
        backgroundImage: null,
        customCss: null,
      },
      clonedFrom: null,
      archivedAt: null,
    };

    await page.route('**/api/v1/dashboards/widgets/registry*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          apiResponse({
            widgets: [
              {
                widgetType: 'hydra::service-summary',
                displayName: 'Service Summary',
                description: 'Overview of service health and operational status.',
                category: 'status-health',
                icon: 'activity',
                source: 'hydra',
                version: '1.0.0',
                supportedDataShapes: ['array-of-service-status'],
                tags: ['services', 'health'],
                permissions: { view: ['admin', 'operator', 'viewer', 'family'], interact: [] },
                defaultSize: { w: 6, h: 4 },
                minSize: { w: 4, h: 3 },
                maxSize: { w: 12, h: 6 },
                configSchema: [
                  {
                    key: 'title',
                    label: 'Title',
                    fieldType: 'text',
                    description: 'Optional display title override for the widget header.',
                    placeholder: 'Leave blank to use the default title',
                    options: [],
                  },
                  {
                    key: 'subtitle',
                    label: 'Subtitle',
                    fieldType: 'text',
                    description: 'Short supporting text shown under the title.',
                    placeholder: 'Optional supporting context',
                    options: [],
                  },
                  {
                    key: 'collapsible',
                    label: 'Collapsible',
                    fieldType: 'boolean',
                    description: 'Allow the widget body to be collapsed from the header.',
                    options: [],
                  },
                  {
                    key: 'defaultCollapsed',
                    label: 'Start collapsed',
                    fieldType: 'boolean',
                    description: 'Collapse the widget body when the board first loads.',
                    options: [],
                  },
                ],
                capabilities: {
                  configurable: true,
                  supportsVisibilityToggle: true,
                  repeatable: false,
                },
              },
            ],
            categories: [{ id: 'status-health', name: 'Status & Health', count: 1 }],
            total: 1,
          }),
        ),
      });
    });

    // Register catch-all FIRST — Playwright checks routes in reverse registration order,
    // so the more specific board-e2e route (registered after) takes priority.
    await page.route('**/api/v1/dashboards**', async (route) => {
      const url = new URL(route.request().url());
      if (route.request().method() === 'GET' && url.pathname.endsWith('/api/v1/dashboards')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(
            apiResponse(
              [
                {
                  boardId: board.boardId,
                  name: board.name,
                  description: board.description,
                  icon: board.icon,
                  ownerId: board.ownerId,
                  boardType: board.boardType,
                  visibility: board.visibility,
                  widgetCount: board.widgetCount,
                  tags: board.tags,
                  isHome: board.isHome,
                  version: board.version,
                  createdAt: board.createdAt,
                  updatedAt: board.updatedAt,
                },
              ],
              { total: 1, limit: 50, offset: 0 },
            ),
          ),
        });
        return;
      }

      await route.fallback();
    });

    // Specific board route AFTER the catch-all so it takes priority in Playwright's LIFO order
    await page.route('**/api/v1/dashboards/board-e2e', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(apiResponse(board)),
        });
        return;
      }

      if (route.request().method() === 'PUT') {
        const updates = route.request().postDataJSON() as Partial<typeof board>;
        board = {
          ...board,
          ...updates,
          widgets: updates.widgets ?? board.widgets,
          widgetCount: updates.widgets?.length ?? board.widgets.length,
          version: board.version + 1,
          updatedAt: '2026-04-06T00:05:00Z',
        };

        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(apiResponse(board)),
        });
        return;
      }

      await route.fallback();
    });

    await page.route('**/api/v1/services**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          apiResponse(
            [
              {
                serviceId: 'svc-01',
                nodeId: 'node-01',
                name: 'nginx',
                displayName: 'Nginx',
                runtime: 'docker',
                status: 'running',
              },
            ],
            { total: 1, limit: 100, offset: 0 },
          ),
        ),
      });
    });

    // Navigate to the board view page (not the management page)
    await gotoPage(page, '/dashboards/board-e2e', /^Dashboard$/);

    // Wait for the board data to load and Edit Board to become enabled, then enter edit mode
    const editButton = page.getByRole('button', { name: /^Edit Board$/ });
    await expect(editButton).toBeEnabled({ timeout: 15_000 });
    await editButton.click();

    // In edit mode the widget list lives inside the Customize popover — open
    // it so the per-widget Configure buttons become clickable.
    await page.getByRole('button', { name: /^Customize$/ }).click();
    await page.getByRole('button', { name: /Configure Service Summary/i }).click();
    await page.locator('#widget-config-title').fill('Executive Services');
    await page.getByRole('button', { name: /^Save Settings$/ }).click();

    await expect(
      page.locator('#main-content').getByRole('heading', { name: /^Executive Services$/ }).first(),
    ).toBeVisible();
  });

  test('discovery review can register a pending device from the browser', async ({ page }) => {
    const device = {
      discoveryId: 'disc-e2e',
      identity: {
        primaryMac: 'AA:BB:CC:DD:EE:FF',
        currentIp: '10.0.10.24',
        hostname: 'edge-router-01',
        reverseDns: [],
      },
      networkId: 'net-edge',
      openPorts: [22, 80],
      protocols: ['ssh', 'http'],
      status: 'pending',
      firstSeen: '2026-04-06T00:00:00Z',
      lastSeen: '2026-04-06T00:05:00Z',
      seenCount: 2,
      fingerprint: {
        openPorts: [22, 80],
        serviceHints: ['ssh', 'http'],
        protocols: ['ssh', 'http'],
        osHint: 'linux',
        vendor: 'Acme',
        macOui: 'AA:BB:CC',
        deviceFamily: 'edge-router',
      },
      classification: {
        suggestedClass: 'networking',
        suggestedType: 'router',
        confidence: 0.92,
        signals: ['ssh', 'http'],
        explanation: 'Open management ports and router vendor signature',
        eligibleForRegistration: true,
      },
      probe: {
        scannedBy: 'scanner-max-01',
        method: 'tcp_port',
        scannedAt: '2026-04-06T00:05:00Z',
        sourceSubnet: '10.0.10.0/24',
        delegatedByScanId: 'scan-e2e',
        scanMethods: ['arp', 'tcp_port'],
      },
      rawEvidence: {
        macAddress: 'AA:BB:CC:DD:EE:FF',
        arpResponses: ['10.0.10.24'],
        banners: { '80': 'nginx' },
        vendor: 'Acme',
        macOui: 'AA:BB:CC',
      },
      matchedNodeId: null,
      approvedAt: null,
      approvedBy: null,
      rejectedAt: null,
      rejectedBy: null,
      rejectReason: null,
      dismissReason: null,
    };

    await page.route('**/api/v1/nodes**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          apiResponse(
            [
              {
                nodeId: 'scanner-max-01',
                displayName: 'Scanner Max 01',
                status: 'active',
                agentTier: 'max',
              },
            ],
            { total: 1, limit: 100, offset: 0 },
          ),
        ),
      });
    });

    await page.route('**/api/v1/discovery/scans/scan-e2e', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          apiResponse({
            scanId: 'scan-e2e',
            status: 'completed',
            resultCount: 1,
            targets: [{ subnet: '10.0.10.0/24' }],
            options: {
              methods: ['arp', 'tcp_port'],
              portTier: 'tier1',
              timeoutSeconds: 60,
              includeIoTProtocols: false,
            },
            summary: {
              hostsScanned: 32,
              hostsAlive: 3,
              newDiscoveries: 1,
              returningDevices: 0,
              errors: [],
            },
            progress: {
              phase: 'completed',
              hostsTotal: 32,
              hostsScanned: 32,
              hostsAlive: 3,
              percentComplete: 100,
            },
            delegation: {
              nodeId: 'scanner-max-01',
              commandId: 'cmd-scan-e2e',
              deliveryMode: 'poll_only',
              requestedAt: '2026-04-06T00:00:00Z',
              startedAt: '2026-04-06T00:01:00Z',
              completedAt: '2026-04-06T00:05:00Z',
            },
            createdAt: '2026-04-06T00:00:00Z',
            startedAt: '2026-04-06T00:01:00Z',
            completedAt: '2026-04-06T00:05:00Z',
            updatedAt: '2026-04-06T00:05:00Z',
          }),
        ),
      });
    });

    await page.route('**/api/v1/discovery/scans**', async (route) => {
      const url = new URL(route.request().url());
      if (route.request().method() === 'GET' && url.pathname.endsWith('/api/v1/discovery/scans')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(
            apiResponse(
              [
                {
                  scanId: 'scan-e2e',
                  status: 'completed',
                  resultCount: 1,
                  targets: [{ subnet: '10.0.10.0/24' }],
                  progress: {
                    phase: 'completed',
                    hostsTotal: 32,
                    hostsScanned: 32,
                    hostsAlive: 3,
                    percentComplete: 100,
                  },
                  createdAt: '2026-04-06T00:00:00Z',
                  updatedAt: '2026-04-06T00:05:00Z',
                },
              ],
              { total: 1, limit: 12, offset: 0 },
            ),
          ),
        });
        return;
      }

      await route.fallback();
    });

    await page.route('**/api/v1/discovery/devices/disc-e2e/approve', async (route) => {
      device.status = 'registered';
      device.matchedNodeId = 'edge-router-01';

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          apiResponse({
            discoveryId: 'disc-e2e',
            status: 'registered',
            matchedNodeId: 'edge-router-01',
          }),
        ),
      });
    });

    // The Register Node button now uses the dedicated `/register` endpoint
    // (spec §2.7.5). Historically it multiplexed through `/approve`.
    await page.route('**/api/v1/discovery/devices/disc-e2e/register', async (route) => {
      device.status = 'registered';
      device.matchedNodeId = 'edge-router-01';

      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(
          apiResponse({
            nodeId: 'edge-router-01',
            registeredBy: 'user-001',
            registeredAt: '2026-04-06T00:05:00Z',
            status: 'registered',
            fromDiscovery: 'disc-e2e',
          }),
        ),
      });
    });

    await page.route('**/api/v1/discovery/devices/disc-e2e', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(apiResponse(device)),
      });
    });

    await page.route('**/api/v1/discovery/devices**', async (route) => {
      const url = new URL(route.request().url());
      if (url.pathname.endsWith('/api/v1/discovery/devices')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(apiResponse([device], { total: 1, limit: 25, offset: 0 })),
        });
        return;
      }

      await route.fallback();
    });

    await gotoPage(page, '/discovery', /^Discovery$/);

    await page.getByRole('tab', { name: /^Discoveries$/ }).click();
    await expect(page.locator('#main-content')).toContainText('edge-router-01');
    await page.getByRole('button', { name: /^Register Node$/ }).click();

    await expect(page.locator('#main-content')).toContainText(/Linked node:/i);
    await expect(page.getByRole('link', { name: /^edge-router-01$/ })).toBeVisible();
  });
});
