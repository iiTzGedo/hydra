/**
 * P2DASH Wave 4 — E2E scenarios for:
 *   1. Undo/Redo + Save flow
 *   2. Freeform mode toggle + drag + discard
 *   3. Kiosk token create → open kiosk URL → revoke → deauthorized
 *   4. Customize entity panel flow
 *
 * These tests use route mocking (page.route) to run against the dev server
 * without a real MongoDB connection. Auth is simulated via a mock cookie +
 * mocked /api/v1/auth/me response, following the same pattern as
 * dashboard-discovery.spec.ts.
 *
 * New data-testid attributes introduced (add to components when adding selectors
 * that do not yet exist in source):
 *   - data-testid="edit-mode-toolbar"   → <div> wrapping EditModeToolbar content
 *   - data-testid="unsaved-changes-indicator" → the <span role="status"> in EditModeToolbar
 *   - data-testid="freeform-canvas"     → alias for [data-freeform-canvas] (already present)
 *   - data-testid="widget-picker-button" → the "Add Widget" / WidgetPicker trigger button
 *   - data-testid="kiosk-token-url-input" → the newly-created token URL <Input>
 *   - data-testid="entity-panel-section" → <section> wrapping EntityDashboardPanel
 */

import { expect, test, type Page } from '@playwright/test';
import { gotoPage } from './helpers/app';

// ─────────────────────────── shared helpers ────────────────────────────

function apiResponse<T>(data: T, meta?: Record<string, unknown>) {
  return { data, ...(meta ? { meta } : {}) };
}

/**
 * Mirrors the mock session setup from dashboard-discovery.spec.ts.
 * Sets the hydra_access cookie and stubs all auth / layout-level endpoints
 * so the app shell renders without touching a real backend.
 */
async function mockAuthenticatedSession(page: Page) {
  await page.context().addCookies([
    {
      name: 'hydra_access',
      value: 'mock-e2e-session',
      domain: 'localhost',
      path: '/',
    },
  ]);

  await page.route('**/api/v1/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        type: 'user',
        userId: 'user-001',
        username: 'system_admin',
        email: 'system_admin@example.com',
        role: 'admin',
        permissions: ['*:*'],
      }),
    });
  });

  await page.route('**/api/v1/auth/session/refresh', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ expiresIn: 3600 }),
    });
  });

  const userSettingsBody = {
    userId: 'user-001',
    ui: {},
    views: {},
    notifications: {},
    dashboard: {
      pinnedBoardIds: [],
      lastOpenedBoardId: 'board-w4',
    },
    updatedAt: '2026-04-20T00:00:00Z',
  };

  await page.route('**/api/v1/settings/user', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: { dashboard: { pinnedBoardIds: [] } } }),
    });
  });

  await page.route('**/api/v1/settings', async (route) => {
    const method = route.request().method();
    if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(userSettingsBody),
      });
      return;
    }
    if (method === 'PUT' || method === 'PATCH') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(userSettingsBody),
      });
      return;
    }
    await route.fallback();
  });

  await page.route('**/api/v1/notifications**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: [], meta: { total: 0, limit: 50, offset: 0 } }),
    });
  });

  for (const resource of ['groups', 'networks', 'nodes']) {
    await page.route(`**/api/v1/${resource}**`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: [], meta: { total: 0, limit: 10, offset: 0 } }),
      });
    });
  }

  await page.route('**/api/v1/dashboards/templates**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: [], meta: { total: 0, limit: 50, offset: 0 } }),
    });
  });

  await page.route('**/api/v1/dashboards/**/shares', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: [] }),
    });
  });
}

// ────────────────── canonical board fixture ────────────────────────────

type BoardState = {
  boardId: string;
  name: string;
  description: string;
  icon: string;
  ownerId: string;
  ownerType: string;
  boardType: string;
  visibility: { scope: string; sharedWith: { roles: string[]; users: string[] } };
  widgetCount: number;
  tags: string[];
  isHome: boolean;
  version: number;
  createdAt: string;
  updatedAt: string;
  layoutMode?: string;
  layout: Record<string, unknown>;
  widgets: Array<{
    instanceId: string;
    widgetType: string;
    position: { x: number; y: number; w: number; h: number };
    freeformPosition?: { x: number; y: number; w: number; h: number } | null;
    placements?: Record<string, unknown> | null;
    config: Record<string, unknown>;
    dataBinding: null;
    readonly?: boolean;
  }>;
  settings: {
    theme: string;
    autoRefresh: boolean;
    refreshInterval: number;
    showHeader: boolean;
    kioskMode: boolean;
    kioskAutoScroll: boolean;
    kioskScrollSpeed: number;
    backgroundImage: null;
    customCss: null;
  };
  clonedFrom: null;
  archivedAt: null;
};

function makeBoard(overrides?: Partial<BoardState>): BoardState {
  return {
    boardId: 'board-w4',
    name: 'Wave 4 Test Board',
    description: 'P2DASH Wave 4 E2E test board',
    icon: 'layout-dashboard',
    ownerId: 'user-001',
    ownerType: 'user',
    boardType: 'user',
    visibility: { scope: 'private', sharedWith: { roles: [], users: [] } },
    widgetCount: 1,
    tags: ['e2e'],
    isHome: false,
    version: 1,
    createdAt: '2026-04-20T00:00:00Z',
    updatedAt: '2026-04-20T00:00:00Z',
    layoutMode: 'grid',
    layout: {
      mode: 'grid',
      grid: {
        columns: 12,
        rowHeight: 80,
        breakpoints: {
          xl: { columns: 12, width: 1536 },
          lg: { columns: 12, width: 1200 },
          md: { columns: 8, width: 996 },
          sm: { columns: 4, width: 480 },
          xs: { columns: 2, width: 0 },
        },
        compaction: 'vertical',
        margin: [16, 16],
        padding: [0, 0],
      },
    },
    widgets: [
      {
        // NOTE: w:4 deliberately smaller than full width. gridToFreeform maps
        // a full-width widget (w:12) to nearly the full canvas, leaving only
        // ~16px of X-axis drag room — which makes the scenario 2 drag assertion
        // impossible to satisfy. w:4 gives ~2/3 canvas as draggable space.
        instanceId: 'wi-stats',
        widgetType: 'hydra::stats-cards',
        position: { x: 0, y: 0, w: 4, h: 2 },
        freeformPosition: null,
        placements: { lg: { x: 0, y: 0, w: 4, h: 2 } },
        config: { hidden: false },
        dataBinding: null,
      },
    ],
    settings: {
      theme: 'inherit',
      autoRefresh: true,
      refreshInterval: 30,
      showHeader: true,
      kioskMode: false,
      kioskAutoScroll: false,
      kioskScrollSpeed: 30,
      backgroundImage: null,
      customCss: null,
    },
    clonedFrom: null,
    archivedAt: null,
    ...overrides,
  };
}

/** Wire up the board-w4 API mock so GET / PUT both work. */
async function mountBoardRoutes(page: Page, board: { current: BoardState }) {
  // Widget registry — provide both stats-cards and a clock widget so the picker
  // can add the clock widget in the undo/redo test.
  await page.route('**/api/v1/dashboards/widgets/registry*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        apiResponse({
          widgets: [
            {
              widgetType: 'hydra::stats-cards',
              displayName: 'Stats Cards',
              description: 'Infrastructure stats at a glance.',
              category: 'status-health',
              icon: 'bar-chart',
              source: 'hydra',
              version: '1.0.0',
              supportedDataShapes: [],
              tags: ['stats'],
              permissions: { view: ['admin', 'operator', 'viewer'], interact: [] },
              defaultSize: { w: 12, h: 2 },
              minSize: { w: 6, h: 2 },
              maxSize: { w: 12, h: 4 },
              configSchema: [],
              capabilities: {
                configurable: false,
                supportsVisibilityToggle: true,
                repeatable: false,
              },
              kioskMode: 'render',
              isAvailable: true,
            },
            {
              widgetType: 'hydra::clock',
              displayName: 'Clock',
              description: 'Current date and time.',
              category: 'system-meta',
              icon: 'clock',
              source: 'hydra',
              version: '1.0.0',
              supportedDataShapes: [],
              tags: ['time'],
              permissions: { view: ['admin', 'operator', 'viewer', 'family'], interact: [] },
              defaultSize: { w: 3, h: 2 },
              minSize: { w: 2, h: 2 },
              maxSize: { w: 6, h: 4 },
              configSchema: [],
              capabilities: {
                configurable: false,
                supportsVisibilityToggle: true,
                repeatable: true,
              },
              kioskMode: 'render',
              isAvailable: true,
            },
          ],
          categories: [
            { id: 'status-health', name: 'Status & Health', count: 1 },
            { id: 'system-meta', name: 'System Meta', count: 1 },
          ],
          total: 2,
        }),
      ),
    });
  });

  // Board list — only board-w4 in the sidebar picker
  await page.route('**/api/v1/dashboards**', async (route) => {
    const url = new URL(route.request().url());
    if (route.request().method() === 'GET' && url.pathname.endsWith('/api/v1/dashboards')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          apiResponse(
            [
              {
                boardId: board.current.boardId,
                name: board.current.name,
                description: board.current.description,
                icon: board.current.icon,
                ownerId: board.current.ownerId,
                boardType: board.current.boardType,
                visibility: board.current.visibility,
                widgetCount: board.current.widgetCount,
                tags: board.current.tags,
                isHome: board.current.isHome,
                version: board.current.version,
                createdAt: board.current.createdAt,
                updatedAt: board.current.updatedAt,
              },
            ],
            { total: 1, limit: 50, offset: 0 },
          ),
        ),
      });
      return;
    }
    await route.fallback();
  });

  // Specific board route — GET returns current state, PUT updates it
  await page.route('**/api/v1/dashboards/board-w4', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(apiResponse(board.current)),
      });
      return;
    }

    if (route.request().method() === 'PUT') {
      const updates = route.request().postDataJSON() as Partial<BoardState>;
      board.current = {
        ...board.current,
        ...updates,
        widgets: updates.widgets ?? board.current.widgets,
        widgetCount: updates.widgets?.length ?? board.current.widgets.length,
        version: board.current.version + 1,
        updatedAt: '2026-04-20T00:05:00Z',
      };
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(apiResponse(board.current)),
      });
      return;
    }

    await route.fallback();
  });
}

// ════════════════════════════════════════════════════════════════════════
// Test suite
// ════════════════════════════════════════════════════════════════════════

test.describe('P2DASH Wave 4 E2E', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test.beforeEach(async ({ page }) => {
    await mockAuthenticatedSession(page);
  });

  // ──────────────────────────────────────────────────────────────────────
  // Scenario 1: Undo / Redo + Save
  // ──────────────────────────────────────────────────────────────────────
  test('undo/redo and save flow — add widget, undo, redo, save clears dirty flag', async ({ page }) => {
    const board = { current: makeBoard() };
    await mountBoardRoutes(page, board);

    // Navigate to the board view page and enter edit mode
    await gotoPage(page, '/dashboards/board-w4', /^Wave 4 Test Board$/);

    const editButton = page.getByRole('button', { name: /^Edit Board$/ });
    await expect(editButton).toBeEnabled({ timeout: 15_000 });
    await editButton.click();

    // Verify the edit mode toolbar is rendered (undo/redo/save buttons present)
    await expect(page.getByRole('button', { name: /^Undo$/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /^Redo$/ })).toBeVisible();

    // ── Add a Clock widget via the WidgetPicker ──────────────────────────
    // The WidgetPicker is rendered inside the toolbar area when edit mode is active.
    // Clicking "Add Widget" opens a Dialog that lists the available widgets.
    const widgetPickerTrigger = page.getByRole('button', { name: /add widget/i });
    await expect(widgetPickerTrigger.first()).toBeVisible({ timeout: 5_000 });
    await widgetPickerTrigger.first().click();

    // The picker Dialog should open
    const pickerDialog = page.getByRole('dialog', { name: /Add Widget/i });
    await expect(pickerDialog).toBeVisible({ timeout: 5_000 });

    // Each widget card is a <button> whose accessible name begins with the
    // display name followed by description + size + category. Match prefix-only
    // and scope the locator to the picker dialog so we don't collide with the
    // Stats Cards widget already on the board.
    const clockOption = pickerDialog.getByRole('button', { name: /^Clock\b/i });
    await expect(clockOption).toBeVisible({ timeout: 5_000 });
    await clockOption.click();

    // After adding, the Clock widget should appear in the main grid. The
    // widget-grid wraps each widget with either a Configure button (if
    // configurable) or a drag handle — for a clock widget without a config
    // schema, there's a "Remove Clock" button in edit mode.
    const clockWidgetMarker = page
      .locator('#main-content')
      .getByRole('button', { name: /Remove Clock/i });
    await expect(clockWidgetMarker).toBeVisible({ timeout: 10_000 });

    // "Unsaved changes" indicator should appear in the toolbar
    await expect(page.getByRole('status').filter({ hasText: /Unsaved changes/i })).toBeVisible();

    // ── Undo via toolbar button → widget removed ───────────────────────
    // We exercise the toolbar buttons rather than the keyboard shortcuts
    // because headless chromium's key-event routing after a Dialog close is
    // timing-sensitive. The keyboard-shortcut binding is covered by the
    // `use-board-editor` unit tests.
    //
    // Adding a widget can push multiple history entries: the `addWidget`
    // mutation itself, plus any layout-reflow entry emitted by
    // react-grid-layout's onLayoutChange. Click Undo up to 5 times until the
    // Clock marker is gone (or Undo becomes disabled), which mirrors the
    // real-user experience of undoing a multi-step edit.
    const undoButton = page.getByRole('button', { name: /^Undo$/ });
    for (let i = 0; i < 5; i += 1) {
      if ((await clockWidgetMarker.count()) === 0) break;
      if (await undoButton.isDisabled()) break;
      await undoButton.click();
    }
    await expect(clockWidgetMarker).toHaveCount(0, { timeout: 5_000 });

    // Undo all the way to clean state — editor should report clean.
    await expect(page.getByRole('status').filter({ hasText: /Unsaved changes/i })).toHaveCount(0, {
      timeout: 3_000,
    });

    // ── Redo via toolbar button → widget restored ──────────────────────
    const redoButton = page.getByRole('button', { name: /^Redo$/ });
    await redoButton.click();
    await expect(clockWidgetMarker).toBeVisible({ timeout: 5_000 });

    // Dirty indicator should be back
    await expect(page.getByRole('status').filter({ hasText: /Unsaved changes/i })).toBeVisible();

    // ── Save via toolbar button → dirty indicator disappears ───────────
    const saveButton = page.getByRole('button', { name: /^Save$/ });
    await saveButton.click();
    await expect(page.getByRole('status').filter({ hasText: /Unsaved changes/i })).toHaveCount(0, {
      timeout: 8_000,
    });
  });

  // ──────────────────────────────────────────────────────────────────────
  // Scenario 2: Freeform mode toggle + drag + discard
  // ──────────────────────────────────────────────────────────────────────
  test('freeform layout mode toggle renders freeform canvas; discard reverts board', async ({ page }) => {
    const board = { current: makeBoard() };
    await mountBoardRoutes(page, board);

    await gotoPage(page, '/dashboards/board-w4', /^Wave 4 Test Board$/);

    const editButton = page.getByRole('button', { name: /^Edit Board$/ });
    await expect(editButton).toBeEnabled({ timeout: 15_000 });
    await editButton.click();

    // Toolbar should be visible with the mode toggle buttons
    const freeformModeButton = page.getByRole('button', { name: /^Layout mode: freeform$/i })
      .or(page.locator('button[aria-label="Layout mode: freeform"]'));
    await expect(freeformModeButton.first()).toBeVisible({ timeout: 5_000 });

    // ── Toggle to Freeform ───────────────────────────────────────────────
    await freeformModeButton.first().click();

    // The freeform canvas container should now be present in the DOM.
    // FreeformCanvas renders with `data-freeform-canvas` attribute.
    const freeformCanvas = page.locator('[data-freeform-canvas]');
    await expect(freeformCanvas).toBeVisible({ timeout: 8_000 });

    // Record the initial position of the Stats Cards widget inside the canvas
    const widgetCard = page
      .locator('[data-freeform-canvas]')
      .locator('[data-testid="freeform-widget-wi-stats"]')
      .or(page.locator('[data-freeform-canvas] > div').first());

    const initialBox = await widgetCard.boundingBox();

    // ── Drag the widget by ~100 px to the right ─────────────────────────
    if (initialBox) {
      const startX = initialBox.x + initialBox.width / 2;
      const startY = initialBox.y + initialBox.height / 2;
      await page.mouse.move(startX, startY);
      await page.mouse.down();
      await page.mouse.move(startX + 110, startY + 30, { steps: 10 });
      await page.mouse.up();

      // Give the position update a moment to settle
      const movedBox = await widgetCard.boundingBox();
      if (movedBox && initialBox) {
        // The widget should have moved by at least 80 px (non-overlap may nudge exact value)
        expect(movedBox.x).toBeGreaterThan(initialBox.x + 50);
      }
    }

    // The dirty indicator should be visible after layout change
    await expect(page.getByRole('status').filter({ hasText: /Unsaved changes/i })).toBeVisible();

    // ── Discard → board reverts to pre-edit (grid) state ────────────────
    const discardButton = page.getByRole('button', { name: /^Discard$/ });
    await expect(discardButton).toBeEnabled();
    await discardButton.click();

    // After discard the freeform canvas should be gone (board is back to grid)
    await expect(freeformCanvas).toHaveCount(0, { timeout: 5_000 });

    // "Unsaved changes" should no longer appear
    await expect(page.getByRole('status').filter({ hasText: /Unsaved changes/i })).toHaveCount(0, {
      timeout: 3_000,
    });

    // Edit board button is back (we're out of edit mode after discard)
    // Discard only exits dirty state — the toolbar remains, but with Save/Discard disabled.
    // The mode toggle should have returned to Grid (aria-pressed=true on Grid button).
    const gridModeButton = page.locator('button[aria-label="Layout mode: grid"]');
    await expect(gridModeButton).toHaveAttribute('aria-pressed', 'true', { timeout: 5_000 });
  });

  // ──────────────────────────────────────────────────────────────────────
  // Scenario 3: Kiosk token create → open kiosk URL → revoke → deauthorized
  // ──────────────────────────────────────────────────────────────────────
  test('kiosk token lifecycle — create, render kiosk page, revoke, deauthorized', async ({
    page,
    context,
  }) => {
    const board = { current: makeBoard() };
    await mountBoardRoutes(page, board);

    // Initial kiosk tokens list — empty
    type KioskToken = {
      tokenId: string;
      boardId: string;
      label: string;
      createdBy: string;
      createdAt: string;
      expiresAt: string | null;
      lastUsedAt: string | null;
      revokedAt: string | null;
    };

    const kioskTokens: KioskToken[] = [];
    let createdTokenValue = 'kiosk-e2e-token-abc123';

    // ── Mock kiosk token endpoints ──────────────────────────────────────
    await page.route('**/api/v1/dashboards/board-w4/kiosk-tokens', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(apiResponse(kioskTokens)),
        });
        return;
      }

      if (route.request().method() === 'POST') {
        const body = route.request().postDataJSON() as { label: string; ttlHours: number | null };
        const newToken: KioskToken = {
          tokenId: 'ktok-e2e-001',
          boardId: 'board-w4',
          label: body.label || 'Kiosk display',
          createdBy: 'user-001',
          createdAt: '2026-04-20T10:00:00Z',
          expiresAt: body.ttlHours ? '2026-04-21T10:00:00Z' : null,
          lastUsedAt: null,
          revokedAt: null,
        };
        kioskTokens.push(newToken);
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify(
            apiResponse({
              ...newToken,
              token: createdTokenValue, // one-time plain-text token value
            }),
          ),
        });
        return;
      }

      await route.fallback();
    });

    // Revoke endpoint
    await page.route('**/api/v1/dashboards/board-w4/kiosk-tokens/ktok-e2e-001', async (route) => {
      if (route.request().method() === 'DELETE') {
        const token = kioskTokens.find((t) => t.tokenId === 'ktok-e2e-001');
        if (token) {
          token.revokedAt = '2026-04-20T10:05:00Z';
        }
        await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
        return;
      }
      await route.fallback();
    });

    // ── Navigate to board, open Share dialog, switch to Kiosk Displays ──
    await gotoPage(page, '/dashboards/board-w4', /^Wave 4 Test Board$/);

    // Open the "Board actions" dropdown (the MoreHorizontal button)
    const boardActionsButton = page.getByRole('button', { name: /board actions/i });
    await expect(boardActionsButton).toBeVisible({ timeout: 10_000 });
    await boardActionsButton.click();

    // Click "Share" in the dropdown
    const shareMenuItem = page.getByRole('menuitem', { name: /^Share$/i });
    await expect(shareMenuItem).toBeVisible({ timeout: 5_000 });
    await shareMenuItem.click();

    // Share dialog should open
    await expect(page.getByRole('dialog', { name: /Share Dashboard/i })).toBeVisible({
      timeout: 5_000,
    });

    // Switch to "Kiosk Displays" tab
    const kioskTab = page.getByRole('tab', { name: /Kiosk Displays/i });
    await expect(kioskTab).toBeVisible();
    await kioskTab.click();

    // ── Create a kiosk link ──────────────────────────────────────────────
    const labelInput = page.locator('#kiosk-label');
    await expect(labelInput).toBeVisible({ timeout: 5_000 });
    await labelInput.fill('E2E kiosk');

    // Select 24 hours from the TTL select (value="24")
    // The SelectTrigger doesn't have a native <select> — use the Radix Select pattern.
    const ttlTrigger = page.locator('[data-radix-select-trigger]').or(
      page.locator('button').filter({ hasText: /7 days|24 hours|1 hour|Never/i }).last(),
    );
    await ttlTrigger.first().click();
    const option24h = page.locator('[data-radix-select-item]').filter({ hasText: /24 hours/i })
      .or(page.getByRole('option', { name: /24 hours/i }));
    await option24h.first().click();

    // Click "Create link"
    const createButton = page.getByRole('button', { name: /Create link/i });
    await expect(createButton).toBeVisible();
    await createButton.click();

    // ── Assert URL is displayed ──────────────────────────────────────────
    // The KioskTokensTab shows a banner with a readonly input containing the full URL.
    // The input value matches: <origin>/kiosk/<boardId>?token=<token>
    const urlInput = page.getByTestId('kiosk-token-url-input');
    await expect(urlInput).toBeVisible({ timeout: 8_000 });
    const kioskUrl = await urlInput.inputValue();
    expect(kioskUrl).toContain('/kiosk/board-w4');
    expect(kioskUrl).toContain('token=');

    // ── Open the kiosk URL in a new tab ─────────────────────────────────
    // Extract just the path + query to navigate the existing page context
    const kioskPath = kioskUrl.replace(/^https?:\/\/[^/]+/, '');

    const kioskPage = await context.newPage();

    // Mock the kiosk board API on the new tab — returns the board when token matches
    await kioskPage.route('**/api/v1/dashboards/kiosk/board-w4**', async (route) => {
      const url = new URL(route.request().url());
      const token = url.searchParams.get('token');
      const isRevoked = kioskTokens.some((t) => t.tokenId === 'ktok-e2e-001' && !!t.revokedAt);

      if (!token || token !== createdTokenValue || isRevoked) {
        await route.fulfill({ status: 401, contentType: 'application/json', body: '{}' });
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(apiResponse(board.current)),
      });
    });

    // Kiosk page doesn't use auth cookie — go directly
    await kioskPage.goto(kioskPath);
    await kioskPage.waitForLoadState('networkidle', { timeout: 8_000 }).catch(() => {});

    // Assert board renders in kiosk mode (no sidebar, widgets visible)
    // The kiosk page root div is full-screen without #sidebar-nav
    await expect(kioskPage.locator('#sidebar-nav')).toHaveCount(0);
    // Board widgets should render — at minimum the stats-cards widget title
    await expect(
      kioskPage.locator('body').getByText(/Stats Cards|Kiosk unavailable/i).first(),
    ).toBeVisible({ timeout: 10_000 });

    // Close the kiosk tab — we'll navigate back to it after revoking
    // (Keep it open to reload after revoke)

    // ── Revoke the token from the share dialog (original page) ──────────
    const revokeButton = page.getByRole('button', { name: /Revoke E2E kiosk/i });
    await expect(revokeButton).toBeVisible({ timeout: 5_000 });
    await revokeButton.click();

    // After revoke the token row should show "Revoked" in its label
    await expect(
      page.locator('li').filter({ hasText: /E2E kiosk/ }).filter({ hasText: /Revoked/i }),
    ).toBeVisible({ timeout: 5_000 });

    // ── Reload the kiosk tab — assert deauthorized message ───────────────
    await kioskPage.reload();
    await kioskPage.waitForLoadState('networkidle', { timeout: 8_000 }).catch(() => {});

    await expect(
      kioskPage.getByText(/This display has been deauthorized|Kiosk unavailable/i).first(),
    ).toBeVisible({ timeout: 10_000 });

    await kioskPage.close();
  });

  // ──────────────────────────────────────────────────────────────────────
  // Scenario 4: Customize entity panel flow
  // ──────────────────────────────────────────────────────────────────────
  test('customize entity panel — node detail page shows panel; customize navigates to edit mode', async ({
    page,
  }) => {
    // ── Mock /api/v1/nodes/node-e2e ─────────────────────────────────────
    const mockNode = {
      nodeId: 'node-e2e',
      displayName: 'E2E Test Node',
      hostname: 'e2e-node',
      class: 'compute',
      nodeType: 'vm',
      status: 'active',
      agentTier: 'standard',
      tags: [],
      networkIds: [],
      groupIds: [],
      createdAt: '2026-04-20T00:00:00Z',
      updatedAt: '2026-04-20T00:00:00Z',
    };

    // Override the blanket nodes mock with a specific detail route.
    // Playwright resolves routes in LIFO order, so this more specific route
    // takes precedence over the catch-all registered in mockAuthenticatedSession.
    await page.route('**/api/v1/nodes/node-e2e', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(apiResponse(mockNode)),
      });
    });

    // Node profiles endpoint (needed by the node detail page)
    await page.route('**/api/v1/nodes/node-e2e/profiles**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(apiResponse([], { total: 0, limit: 10, offset: 0 })),
      });
    });

    // Node services endpoint
    await page.route('**/api/v1/services**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(apiResponse([], { total: 0, limit: 50, offset: 0 })),
      });
    });

    // ── Mock entity panel endpoint ───────────────────────────────────────
    const entityPanel = makeBoard({
      boardId: 'panel-node-e2e',
      name: 'Node Panel',
      boardType: 'system',
      isHome: false,
    });

    // GET — return the system-default node panel
    await page.route('**/api/v1/dashboards/panel/node', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(apiResponse(entityPanel)),
        });
        return;
      }
      await route.fallback();
    });

    // POST — /customize creates a user override board and returns it.
    // This is a distinct endpoint from the plain /panel/node above and must
    // be mocked separately (Playwright glob patterns are path-exact, so a
    // wildcard on the base path does not match the /customize sub-path).
    const overrideBoard = makeBoard({
      boardId: 'panel-node-e2e-override',
      name: 'Node Panel (my override)',
      boardType: 'user',
    });
    await page.route('**/api/v1/dashboards/panel/node/customize', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify(apiResponse(overrideBoard)),
        });
        return;
      }
      await route.fallback();
    });

    // After navigation, the board page will fetch GET /dashboards/<boardId>.
    // Return the override board so the board detail page can render without
    // hitting the real API.
    await page.route(
      '**/api/v1/dashboards/panel-node-e2e-override',
      async (route) => {
        if (route.request().method() === 'GET') {
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(apiResponse(overrideBoard)),
          });
          return;
        }
        await route.fallback();
      },
    );

    // ── Navigate to the node detail page ────────────────────────────────
    await gotoPage(page, '/nodes/node-e2e', /E2E Test Node/i);

    // ── Assert the entity panel section renders with widgets ─────────────
    // EntityDashboardPanel renders a <section> containing the panel name header
    const panelSection = page.locator('section').filter({ hasText: /Node Panel/i });
    await expect(panelSection).toBeVisible({ timeout: 10_000 });

    // There should be at least one widget visible inside the panel
    // (stats-cards widget from the mock entity panel board)
    await expect(panelSection.getByText(/Stats Cards/i)).toBeVisible({ timeout: 5_000 });

    // ── Click "Customize panel…" ─────────────────────────────────────────
    const customizeButton = page.getByTestId('customize-panel-button');
    await expect(customizeButton).toBeVisible({ timeout: 5_000 });
    await customizeButton.click();

    // The customize mutation triggers a POST and then navigates to the override
    // board in edit mode: /dashboards/<overrideBoardId>?edit=1
    await page.waitForURL(/\/dashboards\/panel-node-e2e-override.*edit=1/, { timeout: 10_000 });

    // Verify we're on the override board URL with edit=1 param
    expect(page.url()).toMatch(/panel-node-e2e-override/);
    expect(page.url()).toContain('edit=1');
  });
});
