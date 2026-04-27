/**
 * Tests for KioskTokensTab component.
 *
 * Uses MSW handlers (set up in Phase 5) for kiosk token API endpoints and
 * verifies create, copy, and revoke interactions.
 */

import { beforeEach, describe, expect, it } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { server } from '../../msw/server';
import { KioskTokensTab } from '@/components/dashboard/kiosk-tokens-tab';

// Must match BASE_URL in src/__tests__/msw/handlers.ts
const BASE_URL = 'http://127.0.0.1:8080/api/v1';

const BOARD_ID = 'board-001';

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

function renderTab(boardId = BOARD_ID) {
  const qc = createTestQueryClient();
  return {
    qc,
    ...render(
      <QueryClientProvider client={qc}>
        <KioskTokensTab boardId={boardId} />
      </QueryClientProvider>,
    ),
  };
}

beforeEach(() => {
  // Ensure window.location.origin is predictable
  Object.defineProperty(window, 'location', {
    value: { ...window.location, origin: 'http://localhost:3000' },
    writable: true,
    configurable: true,
  });
});

describe('KioskTokensTab', () => {
  it('renders the create form and empty list initially', async () => {
    renderTab();

    // Create form
    expect(screen.getByText('Create kiosk link')).toBeInTheDocument();
    expect(screen.getByLabelText(/label/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create link/i })).toBeInTheDocument();

    // Empty list
    await waitFor(() =>
      expect(screen.getByText('No kiosk displays created yet.')).toBeInTheDocument(),
    );
  });

  it('creates a token and shows the one-time URL banner', async () => {
    const user = userEvent.setup();
    renderTab();

    // Wait for initial empty state
    await waitFor(() => screen.getByText('No kiosk displays created yet.'));

    const labelInput = screen.getByLabelText(/label/i);
    await user.clear(labelInput);
    await user.type(labelInput, 'TV Display');

    await user.click(screen.getByRole('button', { name: /create link/i }));

    // Banner should appear
    await waitFor(() =>
      expect(screen.getByText(/Kiosk URL/i)).toBeInTheDocument(),
    );
    expect(
      screen.getByText(/Copy this URL now\. It cannot be retrieved later/i),
    ).toBeInTheDocument();
  });

  it('URL in the banner contains the raw token value', async () => {
    const user = userEvent.setup();
    renderTab();

    await waitFor(() => screen.getByText('No kiosk displays created yet.'));

    await user.click(screen.getByRole('button', { name: /create link/i }));

    await waitFor(() => screen.getByText(/Kiosk URL/i));

    const urlInput = screen.getByDisplayValue(/\/kiosk\//i) as HTMLInputElement;
    expect(urlInput.value).toContain(`/kiosk/${BOARD_ID}?token=MOCK_RAW_`);
  });

  it('copy button is present after token creation and the URL input contains the token', async () => {
    // jsdom does not implement navigator.clipboard which is called by the copy
    // handler. This test verifies the copy button renders and the URL input
    // contains the correct value (the clipboard mechanics are the browser's
    // responsibility and not testable in jsdom without significant mocking).
    const boardId = 'board-copy-test';
    const user = userEvent.setup();
    renderTab(boardId);

    await waitFor(() => screen.getByText('No kiosk displays created yet.'));

    await user.click(screen.getByRole('button', { name: /create link/i }));

    // Banner appears after mutation succeeds
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /copy url/i })).toBeInTheDocument(),
    );

    // The readonly URL input shows the complete kiosk URL with token
    const urlInput = screen.getByDisplayValue(
      new RegExp(`\\/kiosk\\/${boardId}\\?token=`),
    ) as HTMLInputElement;
    expect(urlInput.readOnly).toBe(true);
    expect(urlInput.value).toContain(`/kiosk/${boardId}?token=MOCK_RAW_`);
  });

  it('shows tokens in the list after they are created', async () => {
    const user = userEvent.setup();
    renderTab();

    await waitFor(() => screen.getByText('No kiosk displays created yet.'));

    // Type a label and create
    await user.type(screen.getByLabelText(/label/i), 'Office TV');
    await user.click(screen.getByRole('button', { name: /create link/i }));

    // After creation, the list should update (MSW persists in kioskTokensByBoard)
    await waitFor(() => expect(screen.getByText('Office TV')).toBeInTheDocument());
  });

  it('revoke button sets the token to Revoked state', async () => {
    const boardId = 'board-revoke-tab-test';
    let tokenRevoked = false;

    // Use a stateful handler: list reflects revoked state, delete marks it revoked
    server.use(
      http.get(`${BASE_URL}/dashboards/${boardId}/kiosk-tokens`, () => {
        return HttpResponse.json({
          success: true,
          data: [
            {
              tokenId: 'kt_abc123',
              boardId,
              label: 'Test Display',
              createdBy: 'user-001',
              createdAt: new Date().toISOString(),
              expiresAt: null,
              revokedAt: tokenRevoked ? new Date().toISOString() : null,
              lastUsedAt: null,
            },
          ],
          meta: { total: 1 },
        });
      }),
      http.delete(`${BASE_URL}/dashboards/${boardId}/kiosk-tokens/kt_abc123`, () => {
        tokenRevoked = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const user = userEvent.setup();
    renderTab(boardId);

    // Wait for the token to appear
    await waitFor(() => expect(screen.getByText('Test Display')).toBeInTheDocument());
    expect(screen.getByText(/Never expires/i)).toBeInTheDocument();

    // Click revoke — useRevokeKioskToken calls invalidateQueries on success
    await user.click(screen.getByRole('button', { name: /revoke test display/i }));

    // After revoke+invalidate the list refetches and shows Revoked
    await waitFor(() => expect(screen.getByText('Revoked')).toBeInTheDocument());

    // Revoke button should no longer be visible for a revoked token
    expect(
      screen.queryByRole('button', { name: /revoke test display/i }),
    ).not.toBeInTheDocument();
  });

  it('sends ttlHours: null when "Never expires" is selected', async () => {
    let capturedBody: { label: string; ttlHours: number | null } | null = null;

    server.use(
      http.post(`${BASE_URL}/dashboards/${BOARD_ID}/kiosk-tokens`, async ({ request }) => {
        capturedBody = (await request.json()) as { label: string; ttlHours: number | null };
        const now = new Date().toISOString();
        return HttpResponse.json(
          {
            success: true,
            data: {
              tokenId: 'kt_never',
              boardId: BOARD_ID,
              label: capturedBody.label,
              createdBy: 'user-001',
              createdAt: now,
              expiresAt: null,
              revokedAt: null,
              lastUsedAt: null,
              token: 'MOCK_NEVER_TOKEN',
            },
          },
          { status: 201 },
        );
      }),
    );

    const user = userEvent.setup();
    renderTab();

    await waitFor(() => screen.getByText('No kiosk displays created yet.'));

    // Open the select and choose "Never expires"
    await user.click(screen.getByRole('combobox'));
    await waitFor(() => screen.getByRole('option', { name: 'Never expires' }));
    await user.click(screen.getByRole('option', { name: 'Never expires' }));

    await user.click(screen.getByRole('button', { name: /create link/i }));

    await waitFor(() => expect(capturedBody).not.toBeNull());
    expect(capturedBody!.ttlHours).toBeNull();
  });

  it('uses "Kiosk display" as the label when the input is left empty', async () => {
    let capturedLabel: string | null = null;

    server.use(
      http.post(`${BASE_URL}/dashboards/${BOARD_ID}/kiosk-tokens`, async ({ request }) => {
        const body = (await request.json()) as { label: string; ttlHours: number | null };
        capturedLabel = body.label;
        const now = new Date().toISOString();
        return HttpResponse.json(
          {
            success: true,
            data: {
              tokenId: 'kt_default',
              boardId: BOARD_ID,
              label: body.label,
              createdBy: 'user-001',
              createdAt: now,
              expiresAt: null,
              revokedAt: null,
              lastUsedAt: null,
              token: 'MOCK_DEFAULT_TOKEN',
            },
          },
          { status: 201 },
        );
      }),
    );

    const user = userEvent.setup();
    renderTab();

    await waitFor(() => screen.getByText('No kiosk displays created yet.'));

    // Leave label blank and click create
    await act(async () => {
      await user.click(screen.getByRole('button', { name: /create link/i }));
    });

    await waitFor(() => expect(capturedLabel).not.toBeNull());
    expect(capturedLabel).toBe('Kiosk display');
  });

  it('done button dismisses the one-time URL banner', async () => {
    const user = userEvent.setup();
    renderTab();

    await waitFor(() => screen.getByText('No kiosk displays created yet.'));

    await user.click(screen.getByRole('button', { name: /create link/i }));

    await waitFor(() => screen.getByText(/Kiosk URL/i));

    await user.click(screen.getByRole('button', { name: /done/i }));

    expect(screen.queryByText(/Kiosk URL/i)).not.toBeInTheDocument();
  });
});
