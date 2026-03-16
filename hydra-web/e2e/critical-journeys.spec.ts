import { test, expect, type Page } from '@playwright/test';

const TEST_USER = {
  username: 'system_admin',
  password: 'system12345',
};

async function login(page: Page) {
  await page.goto('/login');
  await page.getByLabel(/username/i).fill(TEST_USER.username);
  await page.getByLabel(/password/i).fill(TEST_USER.password);
  await page.getByRole('button', { name: /sign in|log in|login/i }).click();
  await expect(page).toHaveURL(/dashboard/, { timeout: 10_000 });
}

test.describe('Authentication', () => {
  test('login and redirect to dashboard', async ({ page }) => {
    await login(page);
  });

  test('logout returns to login page', async ({ page }) => {
    await login(page);

    await page.getByText('system_admin').first().click();
    await page.getByText(/log ?out/i).click();
    await expect(page).toHaveURL(/login/, { timeout: 10_000 });
  });

  test('unauthenticated user is redirected to login', async ({ page }) => {
    await page.goto('/login');
    await page.evaluate(() => localStorage.clear());

    await page.goto('/dashboard');
    await expect(page).toHaveURL(/login/, { timeout: 10_000 });
  });
});

test.describe('Authenticated Pages', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('dashboard loads with key widgets', async ({ page }) => {
    await expect(page.locator('h1, [data-testid="page-title"]').first()).toBeVisible();
    // Dashboard should show stats or widgets
    await expect(page.locator('main')).toBeVisible();
  });

  test('nodes page lists nodes', async ({ page }) => {
    await page.goto('/nodes');
    await page.waitForLoadState('networkidle');

    // Page should load and show either nodes or an empty state
    const content = page.locator('main');
    await expect(content).toBeVisible();
  });

  test('services page loads', async ({ page }) => {
    await page.goto('/services');
    await page.waitForLoadState('networkidle');

    const content = page.locator('main');
    await expect(content).toBeVisible();
  });

  test('networks page loads', async ({ page }) => {
    await page.goto('/networks');
    await page.waitForLoadState('networkidle');

    const content = page.locator('main');
    await expect(content).toBeVisible();
  });

  test('topology page supports mode switching and search controls', async ({ page }) => {
    await page.goto('/topology');
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: /Infrastructure Topology/i })).toBeVisible();

    const search = page.getByLabel(/Search nodes/i);
    await search.fill('proxmox');
    await expect(search).toHaveValue('proxmox');

    await page.getByRole('tab', { name: /Network/i }).click();
    await expect(page.getByRole('heading', { name: /Network Topology/i })).toBeVisible();
  });

  test('notifications page loads', async ({ page }) => {
    await page.goto('/notifications');
    await page.waitForLoadState('networkidle');

    const content = page.locator('main');
    await expect(content).toBeVisible();
  });

  test('chat page exposes tools and LLM configuration entry points', async ({ page }) => {
    await page.goto('/chat');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('main')).toBeVisible();
    await page.getByRole('tab', { name: /^Tools$/ }).click();
    await expect(page.getByRole('heading', { name: /Hydra MCP/i })).toBeVisible();

    await page.getByRole('button', { name: /Open LLM settings/i }).click();
    await expect(page.getByRole('heading', { name: /LLM Configurations/i })).toBeVisible();
  });

  test('settings users page exposes user management controls', async ({ page }) => {
    await page.goto('/settings?top=users');
    await page.waitForLoadState('networkidle');

    await expect(page).toHaveURL(/\/settings\?top=users/);
    await expect(
      page.locator('#main-content').getByRole('heading', { name: /^Settings$/ }).first()
    ).toBeVisible();

    const search = page.getByPlaceholder('Search users...');
    await expect(search).toBeVisible();
    await search.fill('system');
    await expect(search).toHaveValue('system');
  });

  test('mcp marketplace supports source management entry points', async ({ page }) => {
    await page.goto('/mcp-marketplace');
    await page.waitForLoadState('networkidle');

    await expect(
      page.locator('#main-content').getByRole('heading', { name: /^MCP Marketplace$/ }).first()
    ).toBeVisible();

    await page.getByRole('tab', { name: /Marketplace Sources/i }).click();
    await expect(
      page.locator('#main-content').getByRole('heading', { name: /^Marketplace Sources$/ })
    ).toBeVisible();

    await page.getByRole('button', { name: /^Add Source$/ }).click();
    await expect(page.getByRole('heading', { name: /Add Marketplace Source/i })).toBeVisible();
  });
});
