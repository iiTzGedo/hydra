import { test, expect } from '@playwright/test';
import { gotoPage } from './helpers/app';

test.describe('P2 Pages', () => {
  test.use({ storageState: 'e2e/.auth/user.json' });

  test('services page loads with service table', async ({ page }) => {
    await gotoPage(page, '/services');

    // Page heading should be visible
    await expect(
      page.locator('#main-content').getByRole('heading', { name: /Service Explorer/i }).first(),
    ).toBeVisible({ timeout: 10_000 });

    // Either a table with services or the empty state should render
    const table = page.locator('#main-content table');
    const emptyState = page.locator('#main-content').getByText(/No services found/i);
    await expect(table.or(emptyState).first()).toBeVisible({ timeout: 10_000 });
  });

  test('service detail page shows service info sections', async ({ page }) => {
    await gotoPage(page, '/services');

    // Try to find a service link in the table
    const serviceLink = page.locator('#main-content table a[href^="/services/"]').first();
    const hasServices = await serviceLink.isVisible({ timeout: 5_000 }).catch(() => false);

    if (hasServices) {
      await serviceLink.click();
      await page.waitForLoadState('networkidle');

      // The detail page shows Service Info, Status, and Host sections
      await expect(page.locator('#main-content').getByText('Service Info')).toBeVisible({
        timeout: 10_000,
      });
      await expect(page.locator('#main-content').getByText('Status')).toBeVisible();
      await expect(page.locator('#main-content').getByText('Host')).toBeVisible();
    } else {
      // No services exist; verify the empty state is shown
      await expect(
        page.locator('#main-content').getByText(/No services found/i),
      ).toBeVisible();
    }
  });

  test('networks page loads network list', async ({ page }) => {
    await gotoPage(page, '/networks', /^Networks$/);

    // Verify either the network list or the empty state renders
    const addButton = page.getByRole('button', { name: /^Add Network$/ });
    await expect(addButton).toBeVisible({ timeout: 10_000 });

    // Either network cards/rows exist or the "No networks found" text
    await expect(
      page.locator('#main-content').getByText(/No networks found|Networks/i),
    ).toBeVisible();
  });

  test('groups page loads with create button', async ({ page }) => {
    await gotoPage(page, '/groups');

    // The page heading should be visible
    await expect(
      page.locator('#main-content').getByRole('heading').first(),
    ).toBeVisible({ timeout: 10_000 });

    // Verify a Create Group button is present
    const createButton = page.getByRole('button', { name: /Create Group/i });
    await expect(createButton).toBeVisible({ timeout: 10_000 });

    // Either a table with groups or the empty state should render
    const table = page.locator('#main-content table');
    const emptyState = page.locator('#main-content').getByText(/No groups found|Create your first group/i);
    await expect(table.or(emptyState).first()).toBeVisible({ timeout: 10_000 });
  });

  test('docs page loads document list', async ({ page }) => {
    await gotoPage(page, '/docs');

    // Page heading
    await expect(
      page.locator('#main-content').getByRole('heading', { name: /Documentation/i }).first(),
    ).toBeVisible({ timeout: 10_000 });

    // Either the document list or the placeholder/empty state
    const docsList = page.locator('#main-content').getByText(/document/i);
    await expect(docsList.first()).toBeVisible({ timeout: 10_000 });
  });

  test('integrations page shows plugin registry', async ({ page }) => {
    await gotoPage(page, '/integrations');

    // Page heading
    await expect(
      page.locator('#main-content').getByRole('heading', { name: /Integrations/i }).first(),
    ).toBeVisible({ timeout: 10_000 });

    // Should have tabs including Registry, Configuration, Health, Node Bindings, Command Routing
    await expect(page.getByRole('tab', { name: /Registry/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /Configuration/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /Health/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /Node Bindings/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /Command Routing/i })).toBeVisible();
  });

  test('settings page has multiple tabs', async ({ page }) => {
    await gotoPage(page, '/settings', /^Settings$/);

    // Verify multiple settings categories are rendered (not just Users)
    await expect(page.locator('#main-content').getByText('General')).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.locator('#main-content').getByText('AI')).toBeVisible();
    await expect(page.locator('#main-content').getByText('Notifications')).toBeVisible();
    await expect(page.locator('#main-content').getByText('Security')).toBeVisible();
    await expect(page.locator('#main-content').getByText('Users')).toBeVisible();

    // Also check the Administration section tabs
    await expect(page.locator('#main-content').getByText('Agent Config')).toBeVisible();
    await expect(page.locator('#main-content').getByText('Audit Log')).toBeVisible();
  });

  test('profile page shows user info', async ({ page }) => {
    await gotoPage(page, '/profile');

    // Page heading
    await expect(
      page.locator('#main-content').getByRole('heading', { name: /Profile/i }).first(),
    ).toBeVisible({ timeout: 10_000 });

    // Should show the logged-in user's username and role
    await expect(page.locator('#main-content').getByText('system_admin')).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.locator('#main-content').getByText(/admin/i)).toBeVisible();

    // Account Information and Security sections should be visible
    await expect(
      page.locator('#main-content').getByText('Account Information'),
    ).toBeVisible();
    await expect(
      page.locator('#main-content').getByText('Security'),
    ).toBeVisible();

    // API Keys section should be present
    await expect(
      page.locator('#main-content').getByText('API Keys'),
    ).toBeVisible();
  });

  test('notifications page loads with filtering', async ({ page }) => {
    await gotoPage(page, '/notifications', /^Notifications$/);

    // Verify tab/filter controls are present
    await expect(page.getByRole('tab', { name: /^Active$/ })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('tab', { name: /^Acknowledged$/ })).toBeVisible();
    await expect(page.getByRole('tab', { name: /^Resolved$/ })).toBeVisible();
    await expect(page.getByRole('tab', { name: /Info/i })).toBeVisible();

    // Either notification items or the "All clear" empty state
    const notificationList = page.locator('#main-content').getByText(/All clear|selected|notification/i);
    await expect(notificationList.first()).toBeVisible({ timeout: 10_000 });
  });
});
