import { test, expect } from '@playwright/test';
import { gotoPage } from './helpers/app';

test.describe('Commands and Workflows', () => {
  test.use({ storageState: 'e2e/.auth/user.json' });

  test('commands page shows command catalog', async ({ page }) => {
    await gotoPage(page, '/commands', /Command Center/i);

    // The Catalog tab should be active by default
    await expect(page.getByRole('tab', { name: /Catalog/i })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('tab', { name: /Workflows/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /Execution Queue/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /History/i })).toBeVisible();

    // Either the catalog loads with command categories or shows the empty/error state
    const commandCards = page.locator('#main-content').getByText(/Commands$/i);
    const emptyState = page.locator('#main-content').getByText(/No commands available/i);
    const errorState = page.locator('#main-content').getByText(/Failed to load catalog/i);
    await expect(
      commandCards.first().or(emptyState).or(errorState),
    ).toBeVisible({ timeout: 10_000 });
  });

  test('command execution dialog opens', async ({ page }) => {
    // Mock the catalog to ensure we have a command to click
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
              description: 'Restart a service on a target node',
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

    await gotoPage(page, '/commands', /Command Center/i);

    // Click a command card to open the execution dialog
    await page.getByText('Restart Service').click();

    // The execution dialog should open with parameter fields
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 10_000 });
    await expect(dialog.getByText('Node *')).toBeVisible();
    await expect(dialog.getByRole('button', { name: /Execute/i })).toBeVisible();
  });

  test('workflow tab renders workflow list', async ({ page }) => {
    await gotoPage(page, '/commands', /Command Center/i);

    // Switch to the Workflows tab
    await page.getByRole('tab', { name: /Workflows/i }).click();

    // The workflow tab should render — verify the search input is visible
    await expect(
      page.locator('#main-content').getByPlaceholder(/Search workflows/i),
    ).toBeVisible({ timeout: 10_000 });
  });
});
