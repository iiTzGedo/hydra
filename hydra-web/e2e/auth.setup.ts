import { test as setup } from '@playwright/test';
import { login } from './helpers/app';

setup('authenticate', async ({ page }) => {
  await login(page);

  // Save authenticated state
  await page.context().storageState({ path: 'e2e/.auth/user.json' });
});
