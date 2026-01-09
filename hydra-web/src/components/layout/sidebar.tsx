import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Server,
  Boxes,
  Network,
  FolderTree,
  GitBranch,
  Clock,
  Bell,
  MessageSquare,
  Settings,
  ChevronLeft,
  ChevronRight,
  X,
  Shield,
  User,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import { useUiStore } from '@/stores/ui-store';
import { useAuthStore } from '@/stores/auth-store';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

type NavItem = {
  icon: typeof LayoutDashboard;
  label: string;
  path: string;
  permission?: string;
};

const mainNavItems: NavItem[] = [
  { icon: LayoutDashboard, label: 'Dashboard', path: ROUTES.DASHBOARD },
  { icon: Server, label: 'Nodes', path: ROUTES.NODES, permission: 'nodes:read' },
  { icon: Boxes, label: 'Services', path: ROUTES.SERVICES, permission: 'services:read' },
  { icon: Network, label: 'Networks', path: ROUTES.NETWORKS, permission: 'networks:read' },
  { icon: FolderTree, label: 'Groups', path: ROUTES.GROUPS, permission: 'groups:read' },
  { icon: GitBranch, label: 'Topology', path: ROUTES.TOPOLOGY, permission: 'topologies:read' },
  { icon: Clock, label: 'Time Machine', path: ROUTES.TIME_MACHINE, permission: 'topologies:read' },
  { icon: MessageSquare, label: 'Chat', path: ROUTES.CHAT },
];

export function Sidebar() {
  const location = useLocation();
  const { sidebarCollapsed, sidebarMobileOpen, toggleSidebar, setSidebarMobileOpen } = useUiStore();
  const { hasPermission } = useAuthStore();

  const filteredMainItems = mainNavItems.filter((item) => {
    if (item.permission) {
      return hasPermission(item.permission);
    }
    return true;
  });

  const NavItem = ({ item }: { item: NavItem }) => {
    const isActive = location.pathname === item.path ||
      (item.path !== ROUTES.DASHBOARD && location.pathname.startsWith(item.path));
    const Icon = item.icon;

    const linkContent = (
      <Link
        to={item.path}
        onClick={() => setSidebarMobileOpen(false)}
        className={cn(
          'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
          'hover:bg-sidebar-accent hover:text-sidebar-foreground',
          isActive ? 'bg-sidebar-accent text-sidebar-foreground' : 'text-sidebar-foreground/70',
          sidebarCollapsed && 'justify-center px-2'
        )}
      >
        <Icon className="h-5 w-5 shrink-0" />
        {!sidebarCollapsed && <span className="truncate">{item.label}</span>}
      </Link>
    );

    if (sidebarCollapsed) {
      return (
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>{linkContent}</TooltipTrigger>
          <TooltipContent side="right" className="bg-popover text-popover-foreground border-border">
            {item.label}
          </TooltipContent>
        </Tooltip>
      );
    }

    return linkContent;
  };

  const sidebarContent = (
    <TooltipProvider>
      <>
        {/* Logo */}
        <div
          className={cn(
            'flex h-14 items-center border-b border-sidebar-border px-4 shrink-0',
            sidebarCollapsed && 'justify-center px-2'
          )}
        >
          <Link to={ROUTES.DASHBOARD} className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-sidebar-primary text-sidebar-primary-foreground shrink-0">
              <Shield className="h-5 w-5" />
            </div>
            {!sidebarCollapsed && (
              <span className="text-lg font-semibold text-sidebar-foreground">Hydra</span>
            )}
          </Link>

          {/* Mobile close button */}
          <button
            className="ml-auto md:hidden text-sidebar-foreground/70 hover:text-sidebar-foreground"
            onClick={() => setSidebarMobileOpen(false)}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Main Navigation */}
        <ScrollArea className="flex-1 px-3 py-4">
          <nav className="flex flex-col gap-2">
            {filteredMainItems.map((item) => (
              <NavItem key={item.path} item={item} />
            ))}
          </nav>
        </ScrollArea>

        {/* Bottom Section - Settings, Profile, Collapse */}
        <div className="border-t border-sidebar-border p-3 shrink-0 space-y-2">
          {/* Settings & Profile Icons */}
          <div className={cn('flex gap-1', sidebarCollapsed ? 'flex-col' : 'flex-row')}>
            {/* Settings */}
            {sidebarCollapsed ? (
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Link
                    to={ROUTES.SETTINGS}
                    onClick={() => setSidebarMobileOpen(false)}
                    className={cn(
                      'flex items-center justify-center rounded-md px-2 py-2 text-sm font-medium transition-colors',
                      'hover:bg-sidebar-accent hover:text-sidebar-foreground',
                      location.pathname === ROUTES.SETTINGS
                        ? 'bg-sidebar-accent text-sidebar-foreground'
                        : 'text-sidebar-foreground/70'
                    )}
                  >
                    <Settings className="h-5 w-5" />
                  </Link>
                </TooltipTrigger>
                <TooltipContent side="right" className="bg-popover text-popover-foreground border-border">
                  Settings
                </TooltipContent>
              </Tooltip>
            ) : (
              <Link
                to={ROUTES.SETTINGS}
                onClick={() => setSidebarMobileOpen(false)}
                className={cn(
                  'flex-1 flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  'hover:bg-sidebar-accent hover:text-sidebar-foreground',
                  location.pathname === ROUTES.SETTINGS
                    ? 'bg-sidebar-accent text-sidebar-foreground'
                    : 'text-sidebar-foreground/70'
                )}
              >
                <Settings className="h-5 w-5" />
              </Link>
            )}

            {/* Profile */}
            {sidebarCollapsed ? (
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Link
                    to={ROUTES.PROFILE}
                    onClick={() => setSidebarMobileOpen(false)}
                    className={cn(
                      'flex items-center justify-center rounded-md px-2 py-2 text-sm font-medium transition-colors',
                      'hover:bg-sidebar-accent hover:text-sidebar-foreground',
                      location.pathname === ROUTES.PROFILE
                        ? 'bg-sidebar-accent text-sidebar-foreground'
                        : 'text-sidebar-foreground/70'
                    )}
                  >
                    <User className="h-5 w-5" />
                  </Link>
                </TooltipTrigger>
                <TooltipContent side="right" className="bg-popover text-popover-foreground border-border">
                  Profile
                </TooltipContent>
              </Tooltip>
            ) : (
              <Link
                to={ROUTES.PROFILE}
                onClick={() => setSidebarMobileOpen(false)}
                className={cn(
                  'flex-1 flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  'hover:bg-sidebar-accent hover:text-sidebar-foreground',
                  location.pathname === ROUTES.PROFILE
                    ? 'bg-sidebar-accent text-sidebar-foreground'
                    : 'text-sidebar-foreground/70'
                )}
              >
                <User className="h-5 w-5" />
              </Link>
            )}
          </div>

          {/* Collapse Toggle */}
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleSidebar}
            className={cn(
              'w-full text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground',
              sidebarCollapsed && 'px-2'
            )}
          >
            {sidebarCollapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <>
                <ChevronLeft className="h-4 w-4" />
                <span className="ml-2">Collapse</span>
              </>
            )}
          </Button>
        </div>
      </>
    </TooltipProvider>
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
          'fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-sidebar border-r border-sidebar-border md:hidden',
          'transform transition-transform duration-200',
          sidebarMobileOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {sidebarContent}
      </div>

      {/* Desktop sidebar */}
      <aside
        className={cn(
          'hidden h-screen flex-col border-r border-sidebar-border bg-sidebar transition-all duration-300 shrink-0 md:flex',
          sidebarCollapsed ? 'w-16' : 'w-64'
        )}
      >
        {sidebarContent}
      </aside>
    </>
  );
}
