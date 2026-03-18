import { test, expect } from '@playwright/test';
import {
  SEEDED_NODE,
  SEEDED_NOTIFICATION,
  gotoPage,
  login,
  openSeededNode,
} from './helpers/app';

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

test.describe('Critical Journeys', () => {
  test('dashboard surfaces the main application shell', async ({ page }) => {
    await gotoPage(page, '/dashboard');

    await expect(page.locator('#main-content').getByRole('heading').first()).toBeVisible();
    await expect(page.locator('#sidebar-nav').getByRole('link', { name: /^Nodes$/ })).toBeVisible();
    await expect(page.locator('#sidebar-nav').getByRole('link', { name: /^Topology$/ })).toBeVisible();
    await expect(page.locator('#sidebar-nav').getByRole('link', { name: /^Notifications$/ })).toBeVisible();
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
