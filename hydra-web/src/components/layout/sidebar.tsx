import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Server,
  Boxes,
  Network,
  FolderTree,
  GitBranch,
  MessageSquare,
  Settings,
  ChevronLeft,
  ChevronRight,
  X,
  Shield,
  User,
  History,
  Bell,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import { useUiStore } from '@/stores/ui-store';
import { useAuthStore } from '@/stores/auth-store';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Separator } from '@/components/ui/separator';

type NavItem = {
  icon: typeof LayoutDashboard;
  label: string;
  path: string;
  permission?: string;
  badge?: number;
};

const mainNavItems: NavItem[] = [
  { icon: LayoutDashboard, label: 'Dashboard', path: ROUTES.DASHBOARD },
  { icon: Server, label: 'Nodes', path: ROUTES.NODES, permission: 'nodes:read' },
  { icon: Boxes, label: 'Services', path: ROUTES.SERVICES, permission: 'services:read' },
  { icon: Network, label: 'Networks', path: ROUTES.NETWORKS, permission: 'networks:read' },
  { icon: FolderTree, label: 'Groups', path: ROUTES.GROUPS, permission: 'groups:read' },
  { icon: GitBranch, label: 'Topology', path: ROUTES.TOPOLOGY, permission: 'topologies:read' },
  { icon: History, label: 'Time Machine', path: ROUTES.TIME_MACHINE, permission: 'topologies:read' },
  { icon: MessageSquare, label: 'Chat', path: ROUTES.CHAT },
];

const utilityNavItems: NavItem[] = [
  { icon: Bell, label: 'Notifications', path: ROUTES.NOTIFICATIONS },
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

  const filteredUtilityItems = utilityNavItems.filter((item) => {
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
          'flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-all duration-200 relative',
          'hover:bg-sidebar-accent/80',
          isActive 
            ? 'bg-sidebar-accent text-sidebar-foreground' 
            : 'text-sidebar-foreground/70 hover:text-sidebar-foreground',
          sidebarCollapsed && 'justify-center px-2'
        )}
      >
        {/* Active indicator */}
        {isActive && (
          <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-primary rounded-r-full" />
        )}
        <Icon className={cn("h-5 w-5 shrink-0", isActive && "text-primary")} />
        {!sidebarCollapsed && <span className="truncate">{item.label}</span>}
        {!sidebarCollapsed && item.badge !== undefined && item.badge > 0 && (
          <span className="ml-auto flex h-5 min-w-[20px] items-center justify-center rounded-full bg-primary px-1.5 text-[10px] font-medium text-primary-foreground">
            {item.badge > 99 ? '99+' : item.badge}
          </span>
        )}
      </Link>
    );

    if (sidebarCollapsed) {
      return (
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>{linkContent}</TooltipTrigger>
          <TooltipContent 
            side="right" 
            className="bg-popover text-popover-foreground border-border flex items-center gap-2"
          >
            {item.label}
            {item.badge !== undefined && item.badge > 0 && (
              <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-primary px-1 text-[9px] font-medium text-primary-foreground">
                {item.badge}
              </span>
            )}
          </TooltipContent>
        </Tooltip>
      );
    }

    return linkContent;
  };

  const sidebarContent = (
    <TooltipProvider>
      <>
        {/* Logo Section */}
        <div
          className={cn(
            'flex h-16 items-center border-b border-sidebar-border px-4 shrink-0',
            sidebarCollapsed && 'justify-center px-2'
          )}
        >
          <Link to={ROUTES.DASHBOARD} className="flex items-center gap-3 group">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-primary/80 text-primary-foreground shadow-lg shadow-primary/20 shrink-0 transition-transform duration-200 group-hover:scale-105">
              <Shield className="h-5 w-5" />
            </div>
            {!sidebarCollapsed && (
              <div className="flex flex-col">
                <span className="text-lg font-bold text-sidebar-foreground leading-tight">Hydra</span>
                <span className="text-[10px] text-sidebar-foreground/50 uppercase tracking-wider">Infrastructure</span>
              </div>
            )}
          </Link>

          <button
            className="ml-auto md:hidden text-sidebar-foreground/70 hover:text-sidebar-foreground transition-colors"
            onClick={() => setSidebarMobileOpen(false)}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Main Navigation */}
        <ScrollArea className="flex-1 px-3 py-4">
          <nav className="flex flex-col gap-1">
            {filteredMainItems.map((item) => (
              <NavItem key={item.path} item={item} />
            ))}
          </nav>

          {/* Utility Navigation */}
          {filteredUtilityItems.length > 0 && (
            <>
              <Separator className="my-4 bg-sidebar-border/50" />
              <nav className="flex flex-col gap-1">
                {filteredUtilityItems.map((item) => (
                  <NavItem key={item.path} item={item} />
                ))}
              </nav>
            </>
          )}
        </ScrollArea>

        {/* Bottom Actions */}
        <div className="border-t border-sidebar-border p-3 shrink-0 space-y-3">
          {/* Settings & Profile Row */}
          <div className={cn('flex gap-1', sidebarCollapsed ? 'flex-col' : 'flex-row')}>
            {sidebarCollapsed ? (
              <>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <Link
                      to={ROUTES.SETTINGS}
                      onClick={() => setSidebarMobileOpen(false)}
                      className={cn(
                        'flex items-center justify-center rounded-md px-2 py-2.5 text-sm font-medium transition-all duration-200',
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
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <Link
                      to={ROUTES.PROFILE}
                      onClick={() => setSidebarMobileOpen(false)}
                      className={cn(
                        'flex items-center justify-center rounded-md px-2 py-2.5 text-sm font-medium transition-all duration-200',
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
              </>
            ) : (
              <>
                <Link
                  to={ROUTES.SETTINGS}
                  onClick={() => setSidebarMobileOpen(false)}
                  className={cn(
                    'flex-1 flex items-center justify-center gap-2 rounded-md px-3 py-2.5 text-sm font-medium transition-all duration-200',
                    'hover:bg-sidebar-accent hover:text-sidebar-foreground',
                    location.pathname === ROUTES.SETTINGS
                      ? 'bg-sidebar-accent text-sidebar-foreground'
                      : 'text-sidebar-foreground/70'
                  )}
                >
                  <Settings className="h-4 w-4" />
                  <span>Settings</span>
                </Link>
                <Link
                  to={ROUTES.PROFILE}
                  onClick={() => setSidebarMobileOpen(false)}
                  className={cn(
                    'flex-1 flex items-center justify-center gap-2 rounded-md px-3 py-2.5 text-sm font-medium transition-all duration-200',
                    'hover:bg-sidebar-accent hover:text-sidebar-foreground',
                    location.pathname === ROUTES.PROFILE
                      ? 'bg-sidebar-accent text-sidebar-foreground'
                      : 'text-sidebar-foreground/70'
                  )}
                >
                  <User className="h-4 w-4" />
                  <span>Profile</span>
                </Link>
              </>
            )}
          </div>

          {/* Collapse Toggle */}
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleSidebar}
            className={cn(
              'w-full text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground transition-all duration-200',
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
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden animate-in fade-in duration-200"
          onClick={() => setSidebarMobileOpen(false)}
        />
      )}

      {/* Mobile sidebar */}
      <div
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-72 flex-col bg-sidebar border-r border-sidebar-border md:hidden',
          'transform transition-transform duration-300 ease-out',
          sidebarMobileOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {sidebarContent}
      </div>

      {/* Desktop sidebar */}
      <aside
        className={cn(
          'hidden h-screen flex-col border-r border-sidebar-border bg-sidebar transition-all duration-300 ease-out shrink-0 md:flex',
          sidebarCollapsed ? 'w-20' : 'w-72'
        )}
      >
        {sidebarContent}
      </aside>
    </>
  );
}
