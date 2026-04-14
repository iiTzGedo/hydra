import { vi } from 'vitest';
import { ReactElement } from 'react';
import { act, render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createTestQueryClient } from './msw/test-utils';
import { useAuthStore } from '@/stores/auth-store';
import { useChatCacheStore } from '@/stores/chat-cache-store';
import { useDashboardStore } from '@/stores/dashboard-store';
import { useTopologyStore } from '@/stores/topology-store';
import { useUiStore } from '@/stores/ui-store';
import type { User } from '@/types/auth';

// Access shared navigation mock state from global setup
const mockNavState = (globalThis as Record<string, unknown>).__mockNavState as {
  router: {
    push: ReturnType<typeof vi.fn>;
    replace: ReturnType<typeof vi.fn>;
    back: ReturnType<typeof vi.fn>;
    forward: ReturnType<typeof vi.fn>;
    refresh: ReturnType<typeof vi.fn>;
    prefetch: ReturnType<typeof vi.fn>;
  };
  pathname: string;
  searchParams: URLSearchParams;
  params: Record<string, string>;
};

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
    isAuthenticated: false,
    isLoading: false,
  });

  useChatCacheStore.setState({
    messageCache: {},
    contextCache: {},
  });

  useDashboardStore.setState({
    timeRange: 'last24h',
    customTimeRange: null,
    activeBoardId: null,
    isEditMode: false,
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

  // Reset navigation mocks
  mockNavState.router.push.mockReset();
  mockNavState.router.replace.mockReset();
  mockNavState.router.back.mockReset();
  mockNavState.pathname = '/';
  mockNavState.searchParams = new URLSearchParams();
  mockNavState.params = {};
}

export function seedAuthStore(user: User = TEST_ADMIN_USER) {
  useAuthStore.setState({
    user,
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

/**
 * Set up the Next.js navigation mocks for a specific route.
 * Call this before renderWithRoute to configure the mock pathname and params.
 */
export function setMockRoute(route: string, params: Record<string, string> = {}) {
  const [pathname, search] = route.split('?');
  mockNavState.pathname = pathname;
  mockNavState.searchParams = new URLSearchParams(search || '');
  mockNavState.params = params;
}

export function getMockRouter() {
  return mockNavState.router;
}

export function renderWithRoute(
  ui: ReactElement,
  { path, route, queryClient, user = TEST_ADMIN_USER }: RenderWithRouteOptions
) {
  act(() => {
    resetTestStores();
    if (user) {
      seedAuthStore(user);
    }
  });

  // Extract params from path pattern and route
  const pathSegments = path.split('/');
  const routeSegments = route.split('?')[0].split('/');
  const params: Record<string, string> = {};
  pathSegments.forEach((segment, i) => {
    if (segment.startsWith(':') && routeSegments[i]) {
      params[segment.slice(1)] = routeSegments[i];
    }
  });

  setMockRoute(route, params);

  const testQueryClient = queryClient || createTestQueryClient();

  return {
    queryClient: testQueryClient,
    ...render(
      <QueryClientProvider client={testQueryClient}>
        {ui}
      </QueryClientProvider>
    ),
  };
}
