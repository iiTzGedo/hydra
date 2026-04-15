import { expect, type Page } from '@playwright/test';

export const TEST_USER = {
  username: 'system_admin',
  password: 'system12345',
} as const;

export const SEEDED_NODE = {
  id: 'my-server-01',
  name: 'hydra-dev-machine',
} as const;

export const SEEDED_NOTIFICATION = {
  title: /Node offline: hydra-dev-machine/i,
} as const;

export async function waitForAppShell(page: Page) {
  await expect(page.locator('#sidebar-nav')).toBeVisible({ timeout: 10_000 });
  await expect(page.locator('#main-content')).toBeVisible({ timeout: 10_000 });
}

export async function login(page: Page) {
  await page.goto('/login');
  await page.getByLabel(/username/i).fill(TEST_USER.username);
  await page.getByLabel(/password/i).fill(TEST_USER.password);
  await page.getByRole('button', { name: /sign in|log in|login/i }).click();
  await expect(page).toHaveURL(/dashboard/, { timeout: 10_000 });
  await waitForAppShell(page);
}

export async function gotoPage(
  page: Page,
  path: string,
  heading?: string | RegExp,
) {
  await page.goto(path);

  // Wait for network to settle so the client-side useMe() auth check completes.
  // If the session cookie is expired, the API returns 401, the refresh attempt fails,
  // and the client redirects to /login — all of which happens over the network.
  // Use a short timeout since WebSocket connections can prevent full networkidle.
  await page.waitForLoadState('networkidle', { timeout: 5_000 }).catch(() => {});

  // If we ended up on login (middleware redirect OR client-side auth failure), re-authenticate
  if (page.url().includes('/login')) {
    await login(page);
    await page.goto(path);
  }

  await waitForAppShell(page);

  if (heading) {
    await expect(
      page.locator('#main-content').getByRole('heading', { name: heading }).first(),
    ).toBeVisible();
  }
}

export async function openSeededNode(page: Page) {
  await gotoPage(page, '/nodes');
  const nodeLink = page.locator(`#main-content a[href="/nodes/${SEEDED_NODE.id}"]`).first();
  await expect(nodeLink).toBeVisible();
  await nodeLink.click();
  await expect(page).toHaveURL(new RegExp(`/nodes/${SEEDED_NODE.id}(\\?|$)`));
  await expect(
    page.locator('#main-content').getByRole('heading', { name: new RegExp(SEEDED_NODE.name, 'i') }).first(),
  ).toBeVisible();
}
