import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import NodeProfilesPage from '@/views/nodes/[nodeId]/profiles';
import ProfileComparePage from '@/views/nodes/[nodeId]/profiles/compare';
import { server } from '../msw/server';
import { renderWithRoute } from '../page-test-utils';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080/api/v1';

describe('Node Profiles Integration', () => {
  it('shows compare actions only after two profiles are selected', async () => {
    const user = userEvent.setup();

    renderWithRoute(<NodeProfilesPage />, {
      path: '/nodes/:nodeId/profiles',
      route: '/nodes/proxmox-01/profiles',
    });

    expect(await screen.findByText('Profile History')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Compare Selected' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Select profile E0-0.0.1.0' }));
    expect(screen.getByText('Select one more profile to compare')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Select profile E0-0.0.1.1' }));

    const compareLink = await screen.findByRole('link', { name: 'Compare Selected' });
    expect(compareLink).toHaveAttribute(
      'href',
      '/nodes/proxmox-01/profiles/compare?a=profile-001&b=profile-002'
    );
  });

  it('renders the no-profiles empty state', async () => {
    server.use(
      http.get(`${BASE_URL}/nodes/proxmox-01/profiles`, () =>
        HttpResponse.json({
          data: [],
          meta: {
            total: 0,
            limit: 50,
            offset: 0,
          },
        })
      )
    );

    renderWithRoute(<NodeProfilesPage />, {
      path: '/nodes/:nodeId/profiles',
      route: '/nodes/proxmox-01/profiles',
    });

    expect(await screen.findByText('No profiles yet')).toBeInTheDocument();
  });

  it('renders the missing-node state when the node does not exist', async () => {
    renderWithRoute(<NodeProfilesPage />, {
      path: '/nodes/:nodeId/profiles',
      route: '/nodes/missing-node/profiles',
    });

    expect(await screen.findByText('Node not found')).toBeInTheDocument();
  });

  it('renders the profile comparison summary', async () => {
    renderWithRoute(<ProfileComparePage />, {
      path: '/nodes/:nodeId/profiles/compare',
      route: '/nodes/proxmox-01/profiles/compare?a=profile-001&b=profile-002',
    });

    expect(await screen.findByText('Profile Comparison')).toBeInTheDocument();
    expect(await screen.findByText('Changes Summary')).toBeInTheDocument();
    expect(screen.getByText('Total Difference')).toBeInTheDocument();
    expect(screen.getByText('services')).toBeInTheDocument();
  });
});
