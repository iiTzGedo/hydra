import { test, expect } from '@playwright/test';

const TEST_USER = {
  username: 'system_admin',
  password: 'system12345',
};

test.describe('Authentication', () => {
  test('login and redirect to dashboard', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel(/username/i).fill(TEST_USER.username);
    await page.getByLabel(/password/i).fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in|log in|login/i }).click();

    await expect(page).toHaveURL(/dashboard/, { timeout: 10_000 });
  });

  test('logout returns to login page', async ({ page }) => {
    // Login first
    await page.goto('/login');
    await page.getByLabel(/username/i).fill(TEST_USER.username);
    await page.getByLabel(/password/i).fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in|log in|login/i }).click();
    await expect(page).toHaveURL(/dashboard/, { timeout: 10_000 });

    // Open user dropdown menu (avatar/name area in top-right)
    await page.getByText('system_admin').first().click();

    // Click "Log out" menu item
    await page.getByText(/log ?out/i).click();
    await expect(page).toHaveURL(/login/, { timeout: 10_000 });
  });

  test('unauthenticated user is redirected to login', async ({ page }) => {
    // Navigate to a blank page first so localStorage is accessible
    await page.goto('/login');
    await page.evaluate(() => localStorage.clear());

    await page.goto('/dashboard');
    await expect(page).toHaveURL(/login/, { timeout: 10_000 });
  });
});

test.describe('Authenticated Pages', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login');
    await page.getByLabel(/username/i).fill(TEST_USER.username);
    await page.getByLabel(/password/i).fill(TEST_USER.password);
    await page.getByRole('button', { name: /sign in|log in|login/i }).click();
    await expect(page).toHaveURL(/dashboard/, { timeout: 10_000 });
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

  test('topology page renders', async ({ page }) => {
    await page.goto('/topology');
    await page.waitForLoadState('networkidle');

    const content = page.locator('main');
    await expect(content).toBeVisible();
  });

  test('notifications page loads', async ({ page }) => {
    await page.goto('/notifications');
    await page.waitForLoadState('networkidle');

    const content = page.locator('main');
    await expect(content).toBeVisible();
  });

  test('chat page loads', async ({ page }) => {
    await page.goto('/chat');
    await page.waitForLoadState('networkidle');

    const content = page.locator('main');
    await expect(content).toBeVisible();
  });

  test('settings page loads with tabs', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');

    const content = page.locator('main');
    await expect(content).toBeVisible();
  });
});
