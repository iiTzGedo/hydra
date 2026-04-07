import { test as setup } from '@playwright/test';
import { login } from './helpers/app';

setup('authenticate', async ({ page }) => {
  if (process.env.E2E_SKIP_AUTH_SETUP === '1') {
    await page.context().storageState({ path: 'e2e/.auth/user.json' });
    return;
  }

  await login(page);

  // Save authenticated state
  await page.context().storageState({ path: 'e2e/.auth/user.json' });
});
