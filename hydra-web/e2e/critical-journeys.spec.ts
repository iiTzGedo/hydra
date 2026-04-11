import { test, expect } from '@playwright/test';
import {
  SEEDED_NODE,
  SEEDED_NOTIFICATION,
  gotoPage,
  login,
  openSeededNode,
} from './helpers/app';

test.describe('Critical Journeys', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('dashboard surfaces the main application shell', async ({ page }) => {
    await gotoPage(page, '/dashboard');

    await expect(page.locator('#main-content').getByRole('heading').first()).toBeVisible();
    const sidebar = page.locator('#sidebar-nav');

    await expect(sidebar.getByRole('button', { name: /^Dashboard$/ })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: /^All Dashboards$/ })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: /^Dashboard$/ })).toBeVisible();

    await expect(sidebar.getByRole('button', { name: /^Infrastructure$/ })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: /^Topology$/ })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: /^Nodes$/ })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: /^Services$/ })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: /^Networks$/ })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: /^Groups$/ })).toBeVisible();

    await expect(sidebar.getByRole('button', { name: /^Operations$/ })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: /^Discovery$/ })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: /^Command Center$/ })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: /^Integrations$/ })).toBeVisible();

    await expect(sidebar.getByRole('button', { name: /^Knowledge$/ })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: /^Documentation$/ })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: /^Chat$/ })).toBeVisible();
    await expect(sidebar.getByRole('link', { name: /^Time Machine$/ })).toBeVisible();

    await expect(sidebar.getByRole('navigation', { name: /Sidebar utility/i }).getByRole('link', { name: /^Notifications$/ })).toBeVisible();

    const accountActions = sidebar.getByRole('navigation', { name: /Sidebar account actions/i });
    await expect(accountActions.getByRole('link', { name: /^Settings$/ })).toBeVisible();
    await expect(accountActions.getByRole('link', { name: /^Profile$/ })).toBeVisible();

    await expect(sidebar.getByRole('link', { name: /^MCP Marketplace$/ })).toHaveCount(0);
  });

  test('dashboard browser stays on /dashboards and shows the board management view', async ({ page }) => {
    await gotoPage(page, '/dashboards', /^Dashboards$/);

    await expect(page).toHaveURL(/\/dashboards$/);
    await expect(page.locator('#main-content')).toContainText('Browse saved boards, manage pins, and choose your home dashboard.');
    await expect(page.locator('#main-content').getByRole('button', { name: /^New Board$/ })).toBeVisible();
    await expect(page.locator('#main-content').getByRole('heading', { name: /^Dashboard$/ })).toBeVisible();
    await expect(page.locator('#main-content').getByRole('button', { name: /^Open Board$/ })).toBeVisible();
  });

  test('nodes page lists the seeded node and opens its detail view', async ({ page }) => {
    await gotoPage(page, '/nodes');

    await expect(page.locator('#main-content')).toContainText(SEEDED_NODE.name);
    await expect(page.locator('#main-content')).toContainText(SEEDED_NODE.id);

    await openSeededNode(page);
    await expect(page.getByRole('tab', { name: /^Overview$/ })).toBeVisible();
    await expect(page.getByRole('tab', { name: /^Profile$/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /^Profiles$/ })).toBeVisible();
  });

  test('node detail exposes latest profile and profile history entry points', async ({ page }) => {
    await openSeededNode(page);

    await expect(page.getByRole('link', { name: /^Profiles$/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /^Edit$/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /^Archive$/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /Profile History/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /View Latest Profile/i })).toBeVisible();
  });

  test('profile history supports compare flow for the seeded node', async ({ page }) => {
    await gotoPage(page, `/nodes/${SEEDED_NODE.id}/profiles`, /^Profile History$/);

    const profileSelectors = page.getByRole('button', { name: /Select profile/i });
    await expect(profileSelectors.nth(1)).toBeVisible();

    await profileSelectors.first().click();
    await profileSelectors.nth(1).click();

    await page.getByRole('link', { name: /Compare Selected/i }).click();

    await expect(page).toHaveURL(new RegExp(`/nodes/${SEEDED_NODE.id}/profiles/compare`));
    await expect(
      page.locator('#main-content').getByRole('heading', { name: /^Profile Comparison$/ }),
    ).toBeVisible();
    await expect(page.locator('#main-content')).toContainText(/Changes Summary/i);
  });

  test('services page loads the operational view', async ({ page }) => {
    await gotoPage(page, '/services');

    await expect(page.locator('#main-content')).toBeVisible();
    await expect(page.locator('#main-content').getByRole('heading').first()).toBeVisible();
  });

  test('command center launches a command and shows its result detail', async ({ page }) => {
    await page.route('**/api/v1/command-catalog**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: [
            {
              registryId: 'reg::service::restart',
              category: 'service',
              action: 'restart',
              displayName: 'Restart Service',
              description: 'Restart a service',
              minimumRole: 'operator',
              requiresConfirmation: false,
              timeout: 60,
              deliveryMode: 'poll_only',
              builtIn: true,
              deprecated: false,
            },
          ],
        }),
      });
    });

    await page.route('**/api/v1/commands/queue**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            queue: [],
            stats: {
              totalQueued: 0,
              totalExecuting: 0,
              oldestQueuedAt: null,
            },
          },
        }),
      });
    });

    await page.route('**/api/v1/commands', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ data: [] }),
        });
        return;
      }

      if (route.request().method() !== 'POST') {
        await route.fallback();
        return;
      }

      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            commandId: 'cmd-playwright-001',
            registryId: 'reg::service::restart',
            type: 'service',
            target: {
              nodeId: 'server-01',
              serviceId: 'svc-nginx-a1b2',
            },
            action: 'restart',
            status: 'queued',
            executionMethod: 'agent-poll',
            result: null,
            queuePosition: 1,
            queuedAt: '2026-03-23T10:00:00Z',
            completedAt: null,
          },
        }),
      });
    });

    await page.route('**/api/v1/commands/cmd-playwright-001', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            commandId: 'cmd-playwright-001',
            registryId: 'reg::service::restart',
            type: 'service',
            target: {
              nodeId: 'server-01',
              serviceId: 'svc-nginx-a1b2',
            },
            action: 'restart',
            parameters: null,
            status: 'completed',
            executionMethod: 'agent-poll',
            result: {
              success: true,
              output: 'Service restarted successfully',
              exitCode: 0,
              error: null,
            },
            error: null,
            timeoutSeconds: 60,
            retryCount: 0,
            queuePosition: null,
            createdAt: '2026-03-23T10:00:00Z',
            queuedAt: '2026-03-23T10:00:00Z',
            startedAt: '2026-03-23T10:00:02Z',
            completedAt: '2026-03-23T10:00:05Z',
            cancelledAt: null,
            cancelledBy: null,
          },
        }),
      });
    });

    await gotoPage(page, '/commands', /Command Center/i);

    await page.getByText('Restart Service').click();
    await page.getByLabel('Node ID *').fill('server-01');
    await page.getByLabel('Service ID').fill('svc-nginx-a1b2');
    await page.getByRole('button', { name: 'Execute' }).click();
    await expect(page.getByRole('dialog')).not.toBeVisible();

    await page.goto('/commands/cmd-playwright-001');
    await expect(page.locator('#main-content')).toContainText('Command cmd-playwright-001');
    await expect(page.locator('#main-content')).toContainText('Service restarted successfully');
  });

  test('networks page loads the explorer controls', async ({ page }) => {
    await gotoPage(page, '/networks', /^Networks$/);

    await expect(page.getByRole('button', { name: /^Add Network$/ })).toBeVisible();
    await expect(page.locator('#main-content')).toContainText(/No networks found|Networks/i);
  });

  test('topology supports search, mode switching, and node drill-in', async ({ page }) => {
    await gotoPage(page, '/topology', /Infrastructure Topology/i);

    const search = page.getByLabel(/Search nodes/i);
    await search.fill('hydra-dev');
    await expect(search).toHaveValue('hydra-dev');

    await page.getByRole('tab', { name: /Network/i }).click();
    await expect(
      page.locator('#main-content').getByRole('heading', { name: /Network Topology/i }),
    ).toBeVisible();

    await page.getByRole('tab', { name: /Service/i }).click();
    await expect(
      page.locator('#main-content').getByRole('heading', { name: /Service Topology/i }).first(),
    ).toBeVisible();

    await page.getByRole('tab', { name: /Infrastructure/i }).click();
    await page.locator('#main-content').getByText(SEEDED_NODE.name).first().click();
    await expect(page.getByRole('link', { name: /^View Details$/ })).toBeVisible();
  });

  test('notifications supports critical alert details and tab filtering', async ({ page }) => {
    await gotoPage(page, '/notifications', /^Notifications$/);

    await expect(page.getByRole('tab', { name: /^Active$/ })).toHaveAttribute('data-state', 'active');
    await page.getByRole('checkbox', {
      name: /Select Node offline: hydra-dev-machine/i,
    }).first().click();
    await expect(page.locator('#main-content')).toContainText(/1 selected/i);
    await expect(page.getByRole('button', { name: /Delete selected/i })).toBeVisible();
    await page.getByRole('button', { name: /^Clear$/ }).click();
    await expect(page.locator('#main-content')).not.toContainText(/1 selected/i);

    await page.getByRole('tab', { name: /^Info$/ }).click();
    await expect(page.getByRole('tab', { name: /^Info$/ })).toHaveAttribute('data-state', 'active');
    await expect(page.locator('#main-content')).toContainText(/Mark all read|All clear/i);
  });

  test('chat exposes tools, config controls, and llm settings', async ({ page }) => {
    await gotoPage(page, '/chat');

    await expect(page.locator('#main-content')).toContainText(/Connect Hydra MCP|Hydra MCP is unreachable/i);

    await page.getByRole('tab', { name: /^Tools$/ }).click();
    await expect(page.locator('#main-content')).toContainText(/Hydra MCP/i);
    await expect(page.getByRole('link', { name: /Browse MCP Marketplace/i })).toBeVisible();

    await page.getByRole('tab', { name: /^Config$/ }).click();
    await expect(page.locator('#main-content')).toContainText(/Model Configuration/i);
    await expect(page.locator('#main-content')).toContainText(/Reasoning & Search/i);

    await page.getByRole('button', { name: /Open LLM settings/i }).click();
    await expect(page.getByRole('heading', { name: /LLM Configurations/i })).toBeVisible();
    await page.keyboard.press('Escape');
  });

  test('settings users exposes admin search and role actions', async ({ page }) => {
    await gotoPage(page, '/settings?top=users', /^Settings$/);

    const search = page.getByPlaceholder('Search users...');
    await search.fill('system');
    await expect(search).toHaveValue('system');
    await expect(page.locator('#main-content')).toContainText(/system_admin/i);

    await page.getByRole('button', { name: /Actions for system_admin/i }).click();
    await expect(page.getByText(/Change Role/i)).toBeVisible();
    await expect(page.getByRole('menuitem', { name: /^Administrator$/ })).toBeVisible();
    await expect(page.getByRole('menuitem', { name: /Archive User/i })).toBeVisible();
    await page.keyboard.press('Escape');
  });

  test('mcp marketplace supports add, disconnect, reconnect, and remove', async ({ page }) => {
    const serverName = `playwright-e2e-${Date.now()}`;

    await gotoPage(page, '/mcp-marketplace', /^MCP Marketplace$/);
    await page.getByRole('button', { name: /^Add Server$/ }).click();

    const dialog = page.getByRole('dialog');
    await dialog.getByLabel(/Server name/i).fill(serverName);
    await dialog.getByLabel(/Server endpoint URL/i).fill('http://127.0.0.1:65535/mcp');
    await dialog.getByLabel(/Server description/i).fill('Temporary Playwright MCP server');
    await dialog.getByLabel(/Server docs URL/i).fill('https://example.com/mcp');
    await dialog.getByRole('button', { name: /^Add Server$/ }).click();

    await expect(page.locator('#main-content')).toContainText(serverName, { timeout: 10_000 });
    await expect(page.getByRole('button', { name: /^Disconnect$/ })).toBeVisible();

    await page.getByRole('button', { name: /^Disconnect$/ }).click();
    await expect(page.getByRole('button', { name: /^Connect$/ })).toBeVisible();

    await page.getByRole('button', { name: /^Connect$/ }).click();
    await expect(page.getByRole('button', { name: /^Disconnect$/ })).toBeVisible();

    await page.getByRole('button', { name: new RegExp(`^Remove ${serverName}$`) }).click();
    await expect(page.locator('#main-content')).not.toContainText(serverName);
  });
});

test.describe('Authentication', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test('login and redirect to dashboard', async ({ page }) => {
    await login(page);
    await expect(page.locator('#main-content')).toBeVisible();
  });

  test('logout returns to login page', async ({ page }) => {
    await login(page);

    await page.getByText('system_admin').first().click();
    await page.getByText(/log ?out/i).click();
    await expect(page).toHaveURL(/login/, { timeout: 10_000 });
  });

  test('unauthenticated user is redirected to login', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/login/, { timeout: 10_000 });
  });
});
