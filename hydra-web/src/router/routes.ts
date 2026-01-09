import { lazy } from 'react';
import { ROUTES } from '@/lib/constants';
import type { Role } from '@/types/auth';

// Lazy load all pages for code splitting
const LoginPage = lazy(() => import('@/pages/auth/login'));
const RegisterPage = lazy(() => import('@/pages/auth/register'));
const ForgotPasswordPage = lazy(() => import('@/pages/auth/forgot-password'));
const ResetPasswordPage = lazy(() => import('@/pages/auth/reset-password'));

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

const GroupsPage = lazy(() => import('@/pages/groups'));
const GroupDetailPage = lazy(() => import('@/pages/groups/[groupId]'));
const NewGroupPage = lazy(() => import('@/pages/groups/new'));

const TopologyPage = lazy(() => import('@/pages/topology'));
const TimeMachinePage = lazy(() => import('@/pages/timemachine'));
const ChatPage = lazy(() => import('@/pages/chat'));
const MCPMarketplacePage = lazy(() => import('@/pages/mcp/marketplace'));
const AlertsPage = lazy(() => import('@/pages/alerts'));
const ProfilePage = lazy(() => import('@/pages/profile'));

const SettingsPage = lazy(() => import('@/pages/settings'));

const NotFoundPage = lazy(() => import('@/pages/error/404'));

export interface RouteConfig {
  path: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  element: React.LazyExoticComponent<React.ComponentType<any>>;
  title: string;
  requiresAuth: boolean;
  roles?: Role[];
  permissions?: string[];
  showInNav?: boolean;
  navIcon?: string;
  children?: RouteConfig[];
}

// Auth routes (no auth required)
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

// Main app routes (auth required)
export const appRoutes: RouteConfig[] = [
  {
    path: ROUTES.DASHBOARD,
    element: DashboardPage,
    title: 'Dashboard',
    requiresAuth: true,
    showInNav: true,
    navIcon: 'LayoutDashboard',
  },
  {
    path: ROUTES.NODES,
    element: NodesPage,
    title: 'Nodes',
    requiresAuth: true,
    permissions: ['nodes:read'],
    showInNav: true,
    navIcon: 'Server',
  },
  {
    path: ROUTES.NODE_DETAIL,
    element: NodeDetailPage,
    title: 'Node Details',
    requiresAuth: true,
    permissions: ['nodes:read'],
  },
  {
    path: ROUTES.NODE_PROFILES,
    element: NodeProfilesPage,
    title: 'Profile History',
    requiresAuth: true,
    permissions: ['profiles:read'],
  },
  {
    path: ROUTES.NODE_PROFILES_COMPARE,
    element: ProfileComparePage,
    title: 'Compare Profiles',
    requiresAuth: true,
    permissions: ['profiles:read'],
  },
  {
    path: ROUTES.NODE_PROFILE,
    element: ProfileDetailPage,
    title: 'Profile Details',
    requiresAuth: true,
    permissions: ['profiles:read'],
  },
  {
    path: ROUTES.SERVICES,
    element: ServicesPage,
    title: 'Services',
    requiresAuth: true,
    permissions: ['services:read'],
    showInNav: true,
    navIcon: 'Boxes',
  },
  {
    path: ROUTES.SERVICE_DETAIL,
    element: ServiceDetailPage,
    title: 'Service Details',
    requiresAuth: true,
    permissions: ['services:read'],
  },
  {
    path: ROUTES.NETWORKS,
    element: NetworksPage,
    title: 'Networks',
    requiresAuth: true,
    permissions: ['networks:read'],
    showInNav: true,
    navIcon: 'Network',
  },
  {
    path: ROUTES.NETWORK_DETAIL,
    element: NetworkDetailPage,
    title: 'Network Details',
    requiresAuth: true,
    permissions: ['networks:read'],
  },
  {
    path: ROUTES.GROUPS,
    element: GroupsPage,
    title: 'Groups',
    requiresAuth: true,
    permissions: ['groups:read'],
    showInNav: true,
    navIcon: 'FolderTree',
  },
  {
    path: ROUTES.GROUP_NEW,
    element: NewGroupPage,
    title: 'New Group',
    requiresAuth: true,
    permissions: ['groups:create'],
  },
  {
    path: ROUTES.GROUP_DETAIL,
    element: GroupDetailPage,
    title: 'Group Details',
    requiresAuth: true,
    permissions: ['groups:read'],
  },
  {
    path: ROUTES.TOPOLOGY,
    element: TopologyPage,
    title: 'Topology',
    requiresAuth: true,
    permissions: ['topologies:read'],
    showInNav: true,
    navIcon: 'GitFork',
  },
  {
    path: ROUTES.TIME_MACHINE,
    element: TimeMachinePage,
    title: 'Time Machine',
    requiresAuth: true,
    permissions: ['topologies:read'],
    showInNav: true,
    navIcon: 'History',
  },
  {
    path: ROUTES.CHAT,
    element: ChatPage,
    title: 'Chat',
    requiresAuth: true,
    showInNav: true,
    navIcon: 'MessageSquare',
  },
  {
    path: ROUTES.MCP_MARKETPLACE,
    element: MCPMarketplacePage,
    title: 'MCP Marketplace',
    requiresAuth: true,
    showInNav: true,
    navIcon: 'Store',
  },
  {
    path: ROUTES.ALERTS,
    element: AlertsPage,
    title: 'Alerts',
    requiresAuth: true,
    showInNav: true,
    navIcon: 'Bell',
  },
  {
    path: ROUTES.PROFILE,
    element: ProfilePage,
    title: 'Profile',
    requiresAuth: true,
    showInNav: false,
  },
];

// Settings route (unified, replaces admin routes)
export const adminRoutes: RouteConfig[] = [
  {
    path: ROUTES.SETTINGS,
    element: SettingsPage,
    title: 'Settings',
    requiresAuth: true,
    showInNav: true,
    navIcon: 'Settings',
  },
];

// Error routes
export const errorRoutes: RouteConfig[] = [
  {
    path: '*',
    element: NotFoundPage,
    title: 'Not Found',
    requiresAuth: false,
  },
];

// All routes combined
export const allRoutes = [...authRoutes, ...appRoutes, ...adminRoutes, ...errorRoutes];
