import { lazy, type ComponentType, type LazyExoticComponent } from 'react';
import { matchPath } from 'react-router-dom';
import { ROUTES } from '@/lib/constants';
import type { Role } from '@/types/auth';

const LoginPage = lazy(() => import('@/pages/auth/login'));
const RegisterPage = lazy(() => import('@/pages/auth/register'));
const ForgotPasswordPage = lazy(() => import('@/pages/auth/forgot-password'));
const ResetPasswordPage = lazy(() => import('@/pages/auth/reset-password'));

const LegacyDashboardPage = lazy(() => import('@/pages/dashboard/legacy-redirect'));
const DashboardPage = lazy(() => import('@/pages/dashboard'));

const NodesPage = lazy(() => import('@/pages/nodes'));
const NodeDetailPage = lazy(() => import('@/pages/nodes/[nodeId]'));
const NodeProfilesPage = lazy(() => import('@/pages/nodes/[nodeId]/profiles'));
const ProfileDetailPage = lazy(() => import('@/pages/nodes/[nodeId]/profile/[profileId]'));
const ProfileComparePage = lazy(() => import('@/pages/nodes/[nodeId]/profiles/compare'));

const ServicesPage = lazy(() => import('@/pages/services'));
const ServiceDetailPage = lazy(() => import('@/pages/services/[serviceId]'));

const NetworksPage = lazy(() => import('@/pages/networks'));
const NetworkDetailPage = lazy(() => import('@/pages/networks/[networkId]'));
const DiscoveryPage = lazy(() => import('@/pages/discovery'));

const GroupsPage = lazy(() => import('@/pages/groups'));
const GroupDetailPage = lazy(() => import('@/pages/groups/[groupId]'));
const NewGroupPage = lazy(() => import('@/pages/groups/new'));

const TopologyPage = lazy(() => import('@/pages/topology'));
const TimeMachinePage = lazy(() => import('@/pages/timemachine'));
const ChatPage = lazy(() => import('@/pages/chat'));
const CommandsPage = lazy(() => import('@/pages/commands'));
const CommandDetailPage = lazy(() => import('@/pages/commands/[commandId]'));
const DocsPage = lazy(() => import('@/pages/docs'));
const IntegrationsPage = lazy(() => import('@/pages/integrations'));
const MCPMarketplacePage = lazy(() => import('@/pages/mcp/marketplace'));
const NotificationsPage = lazy(() => import('@/pages/notifications'));
const ProfilePage = lazy(() => import('@/pages/profile'));

const SettingsPage = lazy(() => import('@/pages/settings'));

const NotFoundPage = lazy(() => import('@/pages/error/404'));

export type SidebarPlacement = 'primary' | 'utility' | 'hidden';
export type NavGroup = 'infrastructure' | 'operations' | 'knowledge';

export interface RouteConfig {
  path: string;
  element: LazyExoticComponent<ComponentType>;
  title: string;
  requiresAuth: boolean;
  roles?: Role[];
  permissions?: string[];
  navIcon?: string;
  navLabel?: string;
  navGroup?: NavGroup;
  sidebarPlacement?: SidebarPlacement;
  sidebarOrder?: number;
  parentPath?: string;
  parentTitle?: string;
  matchEnd?: boolean;
}

export interface BreadcrumbMeta {
  path: string;
  title: string;
}

const routeMeta: RouteConfig[] = [
  {
    path: ROUTES.DASHBOARD,
    element: LegacyDashboardPage,
    title: 'Dashboard',
    requiresAuth: true,
    matchEnd: true,
  },
  {
    path: ROUTES.DASHBOARDS,
    element: DashboardPage,
    title: 'Dashboards',
    requiresAuth: true,
    navIcon: 'LayoutDashboard',
    navLabel: 'All Dashboards',
    sidebarPlacement: 'hidden',
    matchEnd: true,
  },
  {
    path: ROUTES.DASHBOARD_BOARD,
    element: DashboardPage,
    title: 'Dashboard',
    requiresAuth: true,
    parentPath: ROUTES.DASHBOARDS,
    parentTitle: 'Dashboards',
  },
  {
    path: ROUTES.TOPOLOGY,
    element: TopologyPage,
    title: 'Topology',
    requiresAuth: true,
    permissions: ['topologies:read'],
    navIcon: 'GitFork',
    navGroup: 'infrastructure',
    sidebarPlacement: 'primary',
    matchEnd: true,
  },
  {
    path: ROUTES.NODES,
    element: NodesPage,
    title: 'Nodes',
    requiresAuth: true,
    permissions: ['nodes:read'],
    navIcon: 'Server',
    navGroup: 'infrastructure',
    sidebarPlacement: 'primary',
    matchEnd: true,
  },
  {
    path: ROUTES.NODE_DETAIL,
    element: NodeDetailPage,
    title: 'Node Details',
    requiresAuth: true,
    permissions: ['nodes:read'],
    parentPath: ROUTES.NODES,
    parentTitle: 'Nodes',
  },
  {
    path: ROUTES.NODE_PROFILES,
    element: NodeProfilesPage,
    title: 'Profile History',
    requiresAuth: true,
    permissions: ['profiles:read'],
    parentPath: ROUTES.NODE_DETAIL,
    parentTitle: 'Node Details',
  },
  {
    path: ROUTES.NODE_PROFILES_COMPARE,
    element: ProfileComparePage,
    title: 'Compare Profiles',
    requiresAuth: true,
    permissions: ['profiles:read'],
    parentPath: ROUTES.NODE_PROFILES,
    parentTitle: 'Profile History',
  },
  {
    path: ROUTES.NODE_PROFILE,
    element: ProfileDetailPage,
    title: 'Profile Details',
    requiresAuth: true,
    permissions: ['profiles:read'],
    parentPath: ROUTES.NODE_PROFILES,
    parentTitle: 'Profile History',
  },
  {
    path: ROUTES.SERVICES,
    element: ServicesPage,
    title: 'Services',
    requiresAuth: true,
    permissions: ['services:read'],
    navIcon: 'Boxes',
    navGroup: 'infrastructure',
    sidebarPlacement: 'primary',
    matchEnd: true,
  },
  {
    path: ROUTES.SERVICE_DETAIL,
    element: ServiceDetailPage,
    title: 'Service Details',
    requiresAuth: true,
    permissions: ['services:read'],
    parentPath: ROUTES.SERVICES,
    parentTitle: 'Services',
  },
  {
    path: ROUTES.NETWORKS,
    element: NetworksPage,
    title: 'Networks',
    requiresAuth: true,
    permissions: ['networks:read'],
    navIcon: 'Network',
    navGroup: 'infrastructure',
    sidebarPlacement: 'primary',
    matchEnd: true,
  },
  {
    path: ROUTES.NETWORK_DETAIL,
    element: NetworkDetailPage,
    title: 'Network Details',
    requiresAuth: true,
    permissions: ['networks:read'],
    parentPath: ROUTES.NETWORKS,
    parentTitle: 'Networks',
  },
  {
    path: ROUTES.GROUPS,
    element: GroupsPage,
    title: 'Groups',
    requiresAuth: true,
    permissions: ['groups:read'],
    navIcon: 'FolderTree',
    navGroup: 'infrastructure',
    sidebarPlacement: 'primary',
    matchEnd: true,
  },
  {
    path: ROUTES.GROUP_NEW,
    element: NewGroupPage,
    title: 'New Group',
    requiresAuth: true,
    permissions: ['groups:create'],
    parentPath: ROUTES.GROUPS,
    parentTitle: 'Groups',
  },
  {
    path: ROUTES.GROUP_DETAIL,
    element: GroupDetailPage,
    title: 'Group Details',
    requiresAuth: true,
    permissions: ['groups:read'],
    parentPath: ROUTES.GROUPS,
    parentTitle: 'Groups',
  },
  {
    path: ROUTES.DISCOVERY,
    element: DiscoveryPage,
    title: 'Discovery',
    requiresAuth: true,
    permissions: ['discovery:read'],
    navIcon: 'Search',
    navGroup: 'operations',
    sidebarPlacement: 'primary',
    matchEnd: true,
  },
  {
    path: ROUTES.COMMANDS,
    element: CommandsPage,
    title: 'Command Center',
    requiresAuth: true,
    permissions: ['commands:read'],
    navIcon: 'Terminal',
    navGroup: 'operations',
    sidebarPlacement: 'primary',
    matchEnd: true,
  },
  {
    path: ROUTES.COMMAND_DETAIL,
    element: CommandDetailPage,
    title: 'Command Details',
    requiresAuth: true,
    permissions: ['commands:read'],
    parentPath: ROUTES.COMMANDS,
    parentTitle: 'Command Center',
  },
  {
    path: ROUTES.INTEGRATIONS,
    element: IntegrationsPage,
    title: 'Integrations',
    requiresAuth: true,
    permissions: ['plugins:read'],
    navIcon: 'Plug',
    navGroup: 'operations',
    sidebarPlacement: 'primary',
    matchEnd: true,
  },
  {
    path: ROUTES.DOCS_WILDCARD,
    element: DocsPage,
    title: 'Documentation',
    requiresAuth: true,
    permissions: ['docs:read'],
    navIcon: 'FileText',
    navGroup: 'knowledge',
    sidebarPlacement: 'primary',
    matchEnd: false,
  },
  {
    path: ROUTES.CHAT,
    element: ChatPage,
    title: 'Chat',
    requiresAuth: true,
    navIcon: 'MessageSquare',
    navGroup: 'knowledge',
    sidebarPlacement: 'primary',
    matchEnd: true,
  },
  {
    path: ROUTES.TIME_MACHINE,
    element: TimeMachinePage,
    title: 'Time Machine',
    requiresAuth: true,
    permissions: ['topologies:read'],
    navIcon: 'History',
    navGroup: 'knowledge',
    sidebarPlacement: 'primary',
    matchEnd: true,
  },
  {
    path: ROUTES.NOTIFICATIONS,
    element: NotificationsPage,
    title: 'Notifications',
    requiresAuth: true,
    permissions: ['notifications:read'],
    navIcon: 'Bell',
    sidebarPlacement: 'utility',
    sidebarOrder: 1,
    matchEnd: true,
  },
  {
    path: ROUTES.SETTINGS,
    element: SettingsPage,
    title: 'Settings',
    requiresAuth: true,
    navIcon: 'Settings',
    sidebarPlacement: 'hidden',
    matchEnd: true,
  },
  {
    path: ROUTES.PROFILE,
    element: ProfilePage,
    title: 'Profile',
    requiresAuth: true,
    navIcon: 'User',
    sidebarPlacement: 'hidden',
    matchEnd: true,
  },
  {
    path: ROUTES.MCP_MARKETPLACE,
    element: MCPMarketplacePage,
    title: 'MCP Marketplace',
    requiresAuth: true,
    navIcon: 'Store',
    sidebarPlacement: 'hidden',
    matchEnd: true,
  },
];

export const authRoutes: RouteConfig[] = [
  {
    path: ROUTES.LOGIN,
    element: LoginPage,
    title: 'Login',
    requiresAuth: false,
  },
  {
    path: ROUTES.REGISTER,
    element: RegisterPage,
    title: 'Register',
    requiresAuth: false,
  },
  {
    path: ROUTES.FORGOT_PASSWORD,
    element: ForgotPasswordPage,
    title: 'Forgot Password',
    requiresAuth: false,
  },
  {
    path: ROUTES.RESET_PASSWORD,
    element: ResetPasswordPage,
    title: 'Reset Password',
    requiresAuth: false,
  },
];

export const appRoutes: RouteConfig[] = routeMeta.filter((route) => route.path !== ROUTES.SETTINGS);

export const adminRoutes: RouteConfig[] = routeMeta.filter((route) => route.path === ROUTES.SETTINGS);

export const errorRoutes: RouteConfig[] = [
  {
    path: '*',
    element: NotFoundPage,
    title: 'Not Found',
    requiresAuth: false,
  },
];

export const allRoutes = [...authRoutes, ...routeMeta, ...errorRoutes];

export function getRouteConfig(pathname: string): RouteConfig | undefined {
  const normalizedPath = pathname === '/' ? ROUTES.DASHBOARD : pathname;

  return [...routeMeta]
    .sort((a, b) => b.path.length - a.path.length)
    .find((route) =>
      Boolean(
        matchPath(
          {
            path: route.path,
            end: route.matchEnd ?? true,
          },
          normalizedPath,
        ),
      ),
    );
}

export function getRouteTitle(pathname: string): string {
  return getRouteConfig(pathname)?.title ?? 'Hydra';
}

export function getRouteBreadcrumbs(pathname: string): BreadcrumbMeta[] {
  const current = getRouteConfig(pathname);
  if (!current) {
    return [{ path: pathname, title: 'Current Page' }];
  }

  const crumbs: BreadcrumbMeta[] = [];
  let pointer: RouteConfig | undefined = current;
  const seen = new Set<string>();

  while (pointer) {
    if (seen.has(pointer.path)) {
      break;
    }
    seen.add(pointer.path);

    crumbs.unshift({
      path: pointer.path,
      title: pointer.parentTitle && pointer.path === pointer.parentPath
        ? pointer.parentTitle
        : pointer.title,
    });

    if (!pointer.parentPath) {
      break;
    }

    const parent = routeMeta.find((route) => route.path === pointer?.parentPath);
    if (!parent) {
      crumbs.unshift({ path: pointer.parentPath, title: pointer.parentTitle ?? 'Parent' });
      break;
    }
    pointer = parent;
  }

  return crumbs;
}

export function getPrimaryNavGroups() {
  return [
    {
      id: 'infrastructure' as const,
      label: 'Infrastructure',
      routes: routeMeta.filter(
        (route) =>
          route.sidebarPlacement === 'primary'
          && route.navGroup === 'infrastructure',
      ),
    },
    {
      id: 'operations' as const,
      label: 'Operations',
      routes: routeMeta.filter(
        (route) =>
          route.sidebarPlacement === 'primary'
          && route.navGroup === 'operations',
      ),
    },
    {
      id: 'knowledge' as const,
      label: 'Knowledge',
      routes: routeMeta.filter(
        (route) =>
          route.sidebarPlacement === 'primary'
          && route.navGroup === 'knowledge',
      ),
    },
  ];
}

export function getUtilityRoutes() {
  return routeMeta
    .filter((route) => route.sidebarPlacement === 'utility')
    .sort((a, b) => (a.sidebarOrder ?? 100) - (b.sidebarOrder ?? 100));
}
