import { test as setup, expect } from '@playwright/test';

const TEST_USER = {
  username: 'system_admin',
  password: 'system12345',
};

setup('authenticate', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel(/username/i).fill(TEST_USER.username);
  await page.getByLabel(/password/i).fill(TEST_USER.password);
  await page.getByRole('button', { name: /sign in|log in|login/i }).click();

  // Wait for redirect to dashboard
  await expect(page).toHaveURL(/dashboard/, { timeout: 10_000 });

  // Save authenticated state
  await page.context().storageState({ path: 'e2e/.auth/user.json' });
});
