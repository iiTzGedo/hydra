import { describe, expect, it } from 'vitest';
import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import SettingsPage from '@/pages/settings';
import { UserManagement } from '@/pages/settings/components/user-management';
import { server } from '../msw/server';
import { renderWithRoute } from '../page-test-utils';

const BASE_URL = 'http://localhost:8080/api/v1';

describe('Settings Users Integration', () => {
  it('renders the users tab when selected through query params', async () => {
    renderWithRoute(<SettingsPage />, {
      path: '/settings',
      route: '/settings?top=users',
    });

    expect(await screen.findByRole('heading', { name: 'Settings' })).toBeInTheDocument();
    expect(await screen.findByPlaceholderText('Search users...')).toBeInTheDocument();
    expect(await screen.findByText('Agent Storage')).toBeInTheDocument();
  });

  it('renders the empty users state', async () => {
    server.use(
      http.get(`${BASE_URL}/users`, () =>
        HttpResponse.json({
          users: [],
          total: 0,
          limit: 10,
          offset: 0,
        })
      )
    );

    renderWithRoute(<UserManagement />, {
      path: '/',
      route: '/',
    });

    expect(await screen.findByText('No users found')).toBeInTheDocument();
  });

  it('renders the error state when the users request fails', async () => {
    server.use(
      http.get(`${BASE_URL}/users`, () =>
        HttpResponse.json(
          {
            error: {
              code: 'USERS_FAILED',
              message: 'Failed to load users',
            },
          },
          { status: 500 }
        )
      )
    );

    renderWithRoute(<UserManagement />, {
      path: '/',
      route: '/',
    });

    expect(await screen.findByText('Failed to load users')).toBeInTheDocument();
  });

  it('supports user search and pagination', async () => {
    const user = userEvent.setup();

    renderWithRoute(<UserManagement />, {
      path: '/',
      route: '/',
    });

    expect(await screen.findByText('Showing 10 of 12 users')).toBeInTheDocument();

    await act(async () => {
      await user.click(screen.getByRole('button', { name: 'Go to next page' }));
    });
    expect(await screen.findByText('Page 2 of 2')).toBeInTheDocument();

    await act(async () => {
      await user.clear(screen.getByPlaceholderText('Search users...'));
      await user.type(screen.getByPlaceholderText('Search users...'), 'search');
    });

    await waitFor(() => {
      expect(screen.getByText('Showing 1 of 1 users')).toBeInTheDocument();
    });
    expect(screen.getByText('search_match')).toBeInTheDocument();
  });

  it('supports elevating and archiving a user from the row actions menu', async () => {
    const user = userEvent.setup();

    renderWithRoute(<UserManagement />, {
      path: '/',
      route: '/',
    });

    expect(await screen.findByText('viewer_one')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Actions for viewer_one' }));
    await user.click(await screen.findByRole('menuitem', { name: 'Operator' }));

    await waitFor(() => {
      const row = screen.getByText('viewer_one').closest('div');
      expect(row).not.toBeNull();
      expect(screen.getAllByText('Operator').length).toBeGreaterThan(0);
    });

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Actions for viewer_one' })
      ).toHaveAttribute('aria-expanded', 'false');
    });

    await user.click(screen.getByRole('button', { name: 'Actions for viewer_one' }));
    await user.click(await screen.findByRole('menuitem', { name: 'Archive User' }));

    await waitFor(() => {
      const archivedBadges = screen.getAllByText('Archived');
      expect(archivedBadges.length).toBeGreaterThan(0);
    });
  });
});
