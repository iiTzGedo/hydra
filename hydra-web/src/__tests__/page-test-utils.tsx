import { ReactElement } from 'react';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { createTestQueryClient } from './msw/test-utils';
import { useAuthStore } from '@/stores/auth-store';
import { useChatCacheStore } from '@/stores/chat-cache-store';
import { useTopologyStore } from '@/stores/topology-store';
import { useUiStore } from '@/stores/ui-store';
import type { User } from '@/types/auth';

export const TEST_ADMIN_USER: User = {
  userId: 'user-001',
  username: 'system_admin',
  email: 'admin@example.com',
  role: 'admin',
  permissions: ['*:*'],
  temporaryRoles: [],
  createdAt: '2026-01-01T08:00:00Z',
};

export function resetTestStores() {
  localStorage.clear();

  useAuthStore.setState({
    user: null,
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false,
    isLoading: false,
  });

  useChatCacheStore.setState({
    messageCache: {},
    contextCache: {},
  });

  useUiStore.setState({
    sidebarCollapsed: false,
    sidebarMobileOpen: false,
    theme: 'system',
    topologyMode: 'infrastructure',
    timeMachineTimestamp: null,
    nodesView: { layout: 'list', sortField: 'displayName', sortDirection: 'asc' },
    networksView: { layout: 'list', sortField: 'displayName', sortDirection: 'asc' },
    servicesView: { layout: 'list', sortField: 'displayName', sortDirection: 'asc' },
    groupsView: { layout: 'list', sortField: 'displayName', sortDirection: 'asc' },
    profilesView: { layout: 'list', sortField: 'submittedAt', sortDirection: 'desc' },
  });

  useTopologyStore.setState({
    selectedNodeId: null,
    selectedGroupId: null,
    highlightedNodeIds: [],
    isSubgraphPanelOpen: false,
    viewports: {
      infrastructure: null,
      network: null,
      service: null,
    },
  });
}

export function seedAuthStore(user: User = TEST_ADMIN_USER) {
  useAuthStore.setState({
    user,
    accessToken: 'test-access-token',
    refreshToken: 'test-refresh-token',
    isAuthenticated: true,
    isLoading: false,
  });
}

interface RenderWithRouteOptions {
  path: string;
  route: string;
  queryClient?: QueryClient;
  user?: User | null;
}

export function renderWithRoute(
  ui: ReactElement,
  { path, route, queryClient, user = TEST_ADMIN_USER }: RenderWithRouteOptions
) {
  resetTestStores();
  if (user) {
    seedAuthStore(user);
  }

  const testQueryClient = queryClient || createTestQueryClient();

  return {
    queryClient: testQueryClient,
    ...render(
      <QueryClientProvider client={testQueryClient}>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path={path} element={ui} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    ),
  };
}
