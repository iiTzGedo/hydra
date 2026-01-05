import { Link, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  LayoutDashboard,
  Server,
  Boxes,
  Network,
  FolderTree,
  GitFork,
  History,
  MessageSquare,
  Settings,
  ChevronLeft,
  ChevronRight,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import { useUiStore } from '@/stores/ui-store';
import { useAuthStore } from '@/stores/auth-store';
import { sidebarVariants } from '@/lib/animations';
import type { Role } from '@/types/auth';

type NavItem = {
  icon: typeof LayoutDashboard;
  label: string;
  path: string;
  permission?: string;
  roles?: Role[];
};

const navItems: NavItem[] = [
  { icon: LayoutDashboard, label: 'Dashboard', path: ROUTES.DASHBOARD },
  { icon: Server, label: 'Nodes', path: ROUTES.NODES, permission: 'nodes:read' },
  { icon: Boxes, label: 'Services', path: ROUTES.SERVICES, permission: 'services:read' },
  { icon: Network, label: 'Networks', path: ROUTES.NETWORKS, permission: 'networks:read' },
  { icon: FolderTree, label: 'Groups', path: ROUTES.GROUPS, permission: 'groups:read' },
  { icon: GitFork, label: 'Topology', path: ROUTES.TOPOLOGY, permission: 'topologies:read' },
  { icon: History, label: 'Time Machine', path: ROUTES.TIME_MACHINE, permission: 'topologies:read' },
  { icon: MessageSquare, label: 'Chat', path: ROUTES.CHAT },
];

const adminItems: NavItem[] = [
  { icon: Settings, label: 'Admin', path: ROUTES.ADMIN, roles: ['admin' as Role] },
];

export function Sidebar() {
  const location = useLocation();
  const { sidebarCollapsed, sidebarMobileOpen, toggleSidebar, setSidebarMobileOpen } = useUiStore();
  const { hasPermission, hasAnyRole } = useAuthStore();

  const filteredNavItems = navItems.filter((item) => {
    if (item.permission) {
      return hasPermission(item.permission);
    }
    return true;
  });

  const filteredAdminItems = adminItems.filter((item) => {
    if (item.roles) {
      return hasAnyRole(item.roles);
    }
    return true;
  });

  const NavLink = ({ item }: { item: NavItem }) => {
    const isActive = location.pathname === item.path || location.pathname.startsWith(item.path + '/');
    const Icon = item.icon;

    return (
      <Link
        to={item.path}
        onClick={() => setSidebarMobileOpen(false)}
        className={cn(
          'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
          'hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
          isActive
            ? 'bg-sidebar-primary text-sidebar-primary-foreground'
            : 'text-sidebar-foreground'
        )}
      >
        <Icon className="h-5 w-5 shrink-0" />
        {!sidebarCollapsed && <span>{item.label}</span>}
      </Link>
    );
  };

  const sidebarContent = (
    <>
      {/* Logo */}
      <div className="flex h-14 items-center border-b border-sidebar-border px-4">
        <Link to={ROUTES.DASHBOARD} className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-hydra-blue text-white font-bold">
            H
          </div>
          {!sidebarCollapsed && (
            <span className="text-lg font-semibold text-sidebar-foreground">Hydra</span>
          )}
        </Link>

        {/* Mobile close button */}
        <button
          className="ml-auto md:hidden"
          onClick={() => setSidebarMobileOpen(false)}
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-2 py-4">
        {filteredNavItems.map((item) => (
          <NavLink key={item.path} item={item} />
        ))}

        {filteredAdminItems.length > 0 && (
          <>
            <div className="my-4 border-t border-sidebar-border" />
            {filteredAdminItems.map((item) => (
              <NavLink key={item.path} item={item} />
            ))}
          </>
        )}
      </nav>

      {/* Collapse button (desktop only) */}
      <div className="hidden border-t border-sidebar-border p-2 md:block">
        <button
          onClick={toggleSidebar}
          className={cn(
            'flex w-full items-center justify-center rounded-lg p-2',
            'hover:bg-sidebar-accent text-sidebar-foreground'
          )}
        >
          {sidebarCollapsed ? (
            <ChevronRight className="h-5 w-5" />
          ) : (
            <ChevronLeft className="h-5 w-5" />
          )}
        </button>
      </div>
    </>
  );

  return (
    <>
      {/* Mobile overlay */}
      {sidebarMobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setSidebarMobileOpen(false)}
        />
      )}

      {/* Mobile sidebar */}
      <div
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-60 flex-col bg-sidebar md:hidden',
          'transform transition-transform duration-200',
          sidebarMobileOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {sidebarContent}
      </div>

      {/* Desktop sidebar */}
      <motion.aside
        initial={false}
        animate={sidebarCollapsed ? 'collapsed' : 'expanded'}
        variants={sidebarVariants}
        className="fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-sidebar-border bg-sidebar md:flex"
      >
        {sidebarContent}
      </motion.aside>
    </>
  );
}
