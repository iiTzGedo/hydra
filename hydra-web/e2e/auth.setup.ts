import { expect, test as setup } from '@playwright/test';
import { login, waitForAppShell } from './helpers/app';

setup('authenticate', async ({ page }) => {
  if (process.env.E2E_SKIP_AUTH_SETUP === '1') {
    await page.context().storageState({ path: 'e2e/.auth/user.json' });
    return;
  }

  await login(page);
  await waitForAppShell(page);
  await expect(page.locator('#main-content')).toBeVisible();

  // Save authenticated state
  await page.context().storageState({ path: 'e2e/.auth/user.json' });
});
