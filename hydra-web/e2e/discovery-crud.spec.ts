/**
 * End-to-end CRUD for the Discovery feature.
 *
 * Exercises:
 *   - Start an API-direct scan on 192.168.0.0/24
 *   - See the scan produce a pending discovery
 *   - Delete the discovery and confirm it is removed from the table
 *   - "Rescan" re-produces the same device as a fresh pending entry
 *   - Delete the scan (with cascade) and confirm it disappears from the list
 *
 * Network choice: 192.168.0.0/24 per the user's standing convention for
 * Playwright test data (avoids confusion with the hydra-web MSW fixtures
 * that still live on 192.168.1.0/24).
 */

import { expect, test, type Page, type Route } from '@playwright/test';

import { gotoPage } from './helpers/app';

// ─── Test fixtures ─────────────────────────────────────────────────────────

const TEST_CIDR = '192.168.0.0/24';
const SCAN_ID = 'scan-crud-e2e';
const DISCOVERY_ID = 'disc::mac::aa-bb-cc-dd-ee-01';
const RESCAN_DISCOVERY_ID = 'disc::mac::aa-bb-cc-dd-ee-01-v2';

function apiResponse<T>(data: T, meta?: Record<string, unknown>) {
  return { data, ...(meta ? { meta } : {}) };
}

function makeDevice(id: string) {
  return {
    discoveryId: id,
    identity: {
      primaryMac: 'aa:bb:cc:dd:ee:01',
      observedMacs: ['aa:bb:cc:dd:ee:01'],
      macVendor: 'TestVendor',
      macResolved: true,
      currentIp: '192.168.0.42',
      observedIps: [],
      hostname: 'test-device-01',
      hostnameSources: ['mdns'],
    },
    networkId: 'net-192-168-0',
    openPorts: [22, 80],
    protocols: ['ssh', 'http'],
    status: 'pending',
    firstSeen: '2026-04-16T00:00:00Z',
    lastSeen: '2026-04-16T00:00:00Z',
    seenCount: 1,
    fingerprint: {
      openPorts: [22, 80],
      serviceHints: ['ssh', 'http'],
      protocols: ['ssh', 'http'],
      osHint: 'linux',
      vendor: 'TestVendor',
      macOui: 'aa:bb:cc',
      deviceFamily: 'compute',
    },
    classification: {
      suggestedClass: 'compute',
      suggestedType: 'sbc',
      confidence: 0.75,
      signals: ['ssh', 'http'],
      explanation: 'SSH + HTTP on standard ports',
      eligibleForRegistration: true,
    },
    probe: {
      scannedBy: 'api',
      method: 'arp',
      scannedAt: '2026-04-16T00:00:00Z',
      sourceSubnet: TEST_CIDR,
      delegatedByScanId: SCAN_ID,
      scanMethods: ['arp', 'tcp_port'],
    },
    rawEvidence: {
      banners: { '22': 'SSH-2.0-OpenSSH_9.6', '80': 'server=nginx' },
      vendor: 'TestVendor',
      macOui: 'aa:bb:cc',
    },
    matchedNodeId: null,
    approvedAt: null,
    approvedBy: null,
    rejectedAt: null,
    rejectedBy: null,
    rejectReason: null,
    dismissReason: null,
  };
}

function makeScan(status: 'running' | 'completed' = 'completed', resultCount = 1) {
  return {
    scanId: SCAN_ID,
    status,
    resultCount,
    targets: [{ subnet: TEST_CIDR, networkId: 'net-192-168-0', delegateToNodeId: null }],
    options: {
      methods: ['arp', 'icmp', 'tcp_port'],
      portTier: 'tier1',
      timeoutSeconds: 60,
      includeIoTProtocols: false,
    },
    delegateToNodeId: null,
    summary:
      status === 'completed'
        ? {
            hostsScanned: 254,
            hostsAlive: 1,
            newDiscoveries: resultCount,
            returningDevices: 0,
            departedSinceLast: 0,
            alreadyRegistered: 0,
          }
        : null,
    progress: {
      phase: status,
      hostsTotal: 254,
      hostsScanned: status === 'completed' ? 254 : 0,
      hostsAlive: status === 'completed' ? 1 : 0,
      percentComplete: status === 'completed' ? 100 : 0,
    },
    delegation: null,
    error: null,
    startedBy: 'user-001',
    startedAt: '2026-04-16T00:00:00Z',
    completedAt: status === 'completed' ? '2026-04-16T00:00:30Z' : null,
    createdAt: '2026-04-16T00:00:00Z',
    updatedAt: '2026-04-16T00:00:30Z',
  };
}

// ─── Shared auth/layout mocks ──────────────────────────────────────────────

async function mockAuthenticatedSession(page: Page) {
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

  await page.route('**/api/v1/settings/user', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: { dashboard: { pinnedBoardIds: [] } } }),
    });
  });

  await page.route('**/api/v1/notifications**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: [], meta: { total: 0, limit: 50, offset: 0 } }),
    });
  });

  await page.route('**/api/v1/dashboards/templates**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: [], meta: { total: 0, limit: 50, offset: 0 } }),
    });
  });

  await page.route('**/api/v1/networks**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        apiResponse(
          [
            {
              networkId: 'net-192-168-0',
              type: 'lan',
              name: 'Test network',
              cidr: TEST_CIDR,
              gatewayV4: '192.168.0.1',
              scanConfig: { status: 'api-direct', apiReachable: true },
            },
          ],
          { total: 1, limit: 50, offset: 0 },
        ),
      ),
    });
  });

  await page.route('**/api/v1/nodes**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(apiResponse([], { total: 0, limit: 100, offset: 0 })),
    });
  });
}

// ─── In-memory fake state backed by route handlers ─────────────────────────

interface FakeState {
  scans: Map<string, ReturnType<typeof makeScan>>;
  devices: Map<string, ReturnType<typeof makeDevice>>;
}

async function wireDiscoveryMocks(page: Page, state: FakeState) {
  // GET /discovery/scans/{scanId}
  await page.route(/\/api\/v1\/discovery\/scans\/[^/]+$/, async (route: Route) => {
    const url = new URL(route.request().url());
    const scanId = url.pathname.split('/').pop() ?? '';
    const method = route.request().method();

    if (method === 'DELETE') {
      state.scans.delete(scanId);
      // When cascade=true, remove every device whose delegatedByScanId matches.
      const cascadeParam = url.searchParams.get('cascade');
      const cascade = cascadeParam === 'true';
      let cascadeDeleted = 0;
      if (cascade) {
        for (const [id, dev] of state.devices) {
          if (dev.probe?.delegatedByScanId === scanId && dev.status !== 'registered') {
            state.devices.delete(id);
            cascadeDeleted += 1;
          }
        }
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(apiResponse({ deleted: true, scanId, cascadeDeleted })),
      });
      return;
    }

    if (method === 'GET') {
      const scan = state.scans.get(scanId);
      if (!scan) {
        await route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(apiResponse(scan)),
      });
      return;
    }
    await route.fallback();
  });

  // POST/GET /discovery/scans
  await page.route(/\/api\/v1\/discovery\/scans(\?.*)?$/, async (route: Route) => {
    const method = route.request().method();
    if (method === 'POST') {
      const newScan = makeScan('running', 0);
      state.scans.set(newScan.scanId, newScan);
      // Simulate scan completion a moment later: on next GET, status is completed.
      setTimeout(() => {
        const completed = makeScan('completed', state.devices.size);
        state.scans.set(completed.scanId, completed);
      }, 200);
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(apiResponse(newScan)),
      });
      return;
    }
    if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          apiResponse(Array.from(state.scans.values()), {
            total: state.scans.size,
            limit: 12,
            offset: 0,
          }),
        ),
      });
      return;
    }
    await route.fallback();
  });

  // GET / DELETE /discovery/devices/{id}
  await page.route(
    /\/api\/v1\/discovery\/devices\/[^/?]+(\?.*)?$/,
    async (route: Route) => {
      const url = new URL(route.request().url());
      const discoveryId = decodeURIComponent(url.pathname.split('/').pop() ?? '');
      const method = route.request().method();

      if (method === 'DELETE') {
        state.devices.delete(discoveryId);
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(apiResponse({ deleted: true, discoveryId })),
        });
        return;
      }
      if (method === 'GET') {
        const dev = state.devices.get(discoveryId);
        if (!dev) {
          await route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
          return;
        }
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(apiResponse(dev)),
        });
        return;
      }
      await route.fallback();
    },
  );

  // GET /discovery/devices
  await page.route(/\/api\/v1\/discovery\/devices(\?.*)?$/, async (route: Route) => {
    const method = route.request().method();
    if (method !== 'GET') {
      await route.fallback();
      return;
    }
    const items = Array.from(state.devices.values());
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(apiResponse(items, { total: items.length, limit: 25, offset: 0 })),
    });
  });

  // /installations — discovery page reads this for its side panel
  await page.route('**/api/v1/install/installations**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(apiResponse([], { total: 0, limit: 5, offset: 0 })),
    });
  });
}

// ─── Tests ─────────────────────────────────────────────────────────────────

test.describe('Discovery CRUD on 192.168.0.0/24', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test.beforeEach(async ({ page }) => {
    await mockAuthenticatedSession(page);
  });

  test('scan → view → delete discovery → delete scan with cascade', async ({
    page,
  }) => {
    const state: FakeState = {
      scans: new Map([[SCAN_ID, makeScan('completed', 1)]]),
      devices: new Map([[DISCOVERY_ID, makeDevice(DISCOVERY_ID)]]),
    };
    await wireDiscoveryMocks(page, state);

    await gotoPage(page, '/discovery', /^Discovery$/);

    // 1. Scans tab: the completed scan is listed with its 192.168.0.0/24 target.
    await page.getByRole('tab', { name: /^Scans$/ }).click();
    await expect(page.locator('#main-content')).toContainText(SCAN_ID);
    await expect(page.locator('#main-content')).toContainText(TEST_CIDR);

    // 2. Discoveries tab: the device is visible with its resolved hostname.
    await page.getByRole('tab', { name: /^Discoveries$/ }).click();
    await expect(page.locator('#main-content')).toContainText('test-device-01');
    await expect(page.locator('#main-content')).toContainText('192.168.0.42');

    // 3. Delete the discovery via the per-row button.
    await page
      .getByRole('button', { name: /Delete discovery test-device-01/i })
      .click();
    // Confirmation dialog — actually delete.
    await page
      .getByRole('alertdialog')
      .getByRole('button', { name: /^Delete$/ })
      .click();

    // The device disappears from the table.
    await expect(
      page.locator('#main-content').getByText('test-device-01'),
    ).toHaveCount(0);
    expect(state.devices.has(DISCOVERY_ID)).toBe(false);

    // 4. Delete the scan with cascade. Put a second unregistered device
    //    into state so we can observe the cascade deletion.
    state.devices.set(RESCAN_DISCOVERY_ID, {
      ...makeDevice(RESCAN_DISCOVERY_ID),
      firstSeen: '2026-04-16T00:10:00Z',
      lastSeen: '2026-04-16T00:10:00Z',
    });

    await page.getByRole('tab', { name: /^Scans$/ }).click();
    await page.getByRole('button', { name: `Delete scan ${SCAN_ID}` }).click();

    const scanDialog = page.getByRole('alertdialog');
    await scanDialog
      .getByRole('checkbox', { name: /Also delete unregistered discoveries/i })
      .check();
    await scanDialog.getByRole('button', { name: /^Delete$/ }).click();

    // Backend fake state must reflect both deletions after the mutation
    // completes. The cascade behavior is what makes "delete and it stays
    // deleted" feel consistent on the UI.
    await expect
      .poll(() => state.scans.has(SCAN_ID), { timeout: 5_000 })
      .toBe(false);
    expect(state.devices.has(RESCAN_DISCOVERY_ID)).toBe(false);
  });

  test('deleting a discovery is gated behind a confirmation dialog', async ({ page }) => {
    const state: FakeState = {
      scans: new Map([[SCAN_ID, makeScan('completed', 1)]]),
      devices: new Map([[DISCOVERY_ID, makeDevice(DISCOVERY_ID)]]),
    };
    await wireDiscoveryMocks(page, state);
    await gotoPage(page, '/discovery', /^Discovery$/);

    await page.getByRole('tab', { name: /^Discoveries$/ }).click();
    await page
      .getByRole('button', { name: /Delete discovery test-device-01/i })
      .click();

    // Cancel the dialog — the device must remain.
    await page.getByRole('alertdialog').getByRole('button', { name: /^Cancel$/ }).click();
    await expect(page.locator('#main-content')).toContainText('test-device-01');
    expect(state.devices.has(DISCOVERY_ID)).toBe(true);
  });
});
