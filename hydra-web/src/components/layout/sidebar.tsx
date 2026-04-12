import { useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Bell,
  Boxes,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  FileText,
  FolderTree,
  GitFork,
  History,
  LayoutDashboard,
  MenuSquare,
  MessageSquare,
  Network,
  Plug,
  Search,
  Server,
  Settings,
  Shield,
  Terminal,
  User,
  X,
  type LucideIcon,
} from 'lucide-react';
import { useDashboards } from '@/api/dashboards';
import { useUserSettings } from '@/api/settings';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { useAuthStore } from '@/stores/auth-store';
import { useUiStore } from '@/stores/ui-store';
import { getPrimaryNavGroups, getRouteConfig, getUtilityRoutes, type RouteConfig } from '@/router/routes';

const NAV_ICONS: Record<string, LucideIcon> = {
  Bell,
  Boxes,
  FileText,
  FolderTree,
  GitFork,
  History,
  LayoutDashboard,
  MessageSquare,
  Network,
  Plug,
  Search,
  Server,
  Settings,
  Terminal,
  User,
};

interface SidebarNavItem {
  label: string;
  path: string;
  icon: LucideIcon;
  permission?: string;
  isPinnedBoard?: boolean;
}

function routeToNavItem(route: RouteConfig): SidebarNavItem {
  return {
    label: route.navLabel ?? route.title,
    path: route.path.endsWith('/*') ? route.path.slice(0, -2) : route.path,
    icon: NAV_ICONS[route.navIcon ?? 'MenuSquare'] ?? MenuSquare,
    permission: route.permissions?.[0],
  };
}

function getBoardDisplayLabel(board: { isHome?: boolean; name: string }) {
  return board.isHome ? 'Dashboard' : board.name;
}

export function Sidebar() {
  const location = useLocation();
  const { sidebarCollapsed, sidebarMobileOpen, toggleSidebar, setSidebarMobileOpen } = useUiStore();
  const { hasPermission } = useAuthStore();
  const dashboards = useDashboards({ limit: 50, sortBy: 'updatedAt', sortOrder: 'desc' });
  const userSettings = useUserSettings();
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({
    Dashboard: true,
    Infrastructure: true,
    Operations: true,
    Knowledge: true,
  });

  const currentRoute = getRouteConfig(location.pathname);

  const primaryGroups = getPrimaryNavGroups()
    .map((group) => ({
      ...group,
      items: group.routes
        .map(routeToNavItem)
        .filter((item) => !item.permission || hasPermission(item.permission)),
    }))
    .filter((group) => group.items.length > 0);

  const utilityItems = getUtilityRoutes()
    .map(routeToNavItem)
    .filter((item) => !item.permission || hasPermission(item.permission));

  const dashboardNavItems = useMemo(() => {
    const boardItems = dashboards.data?.items ?? [];
    const pinnedBoardIds = userSettings.data?.dashboard?.pinnedBoardIds ?? [];
    const homeBoard = boardItems.find((board) => board.isHome) ?? null;
    const pinnedBoards = pinnedBoardIds
      .map((id) => boardItems.find((board) => board.boardId === id))
      .filter((board): board is NonNullable<typeof board> => Boolean(board) && board?.boardId !== homeBoard?.boardId);

    const visibleBoards = [homeBoard, ...pinnedBoards]
      .filter((board): board is NonNullable<typeof board> => Boolean(board))
      .slice(0, 5)
      .map((board) => ({
        label: getBoardDisplayLabel(board),
        path: ROUTES.DASHBOARD_BOARD.replace(':boardId', board.boardId),
        icon: LayoutDashboard,
        isPinnedBoard: true,
      }));

    return [
      {
        label: 'All Dashboards',
        path: ROUTES.DASHBOARDS,
        icon: LayoutDashboard,
      },
      ...visibleBoards,
    ];
  }, [dashboards.data?.items, userSettings.data?.dashboard?.pinnedBoardIds]);

  const isActive = (path: string) => {
    if (path === ROUTES.DASHBOARDS) {
      return location.pathname.startsWith('/dashboards') || location.pathname === ROUTES.DASHBOARD;
    }
    if (path.startsWith('/docs')) {
      return location.pathname.startsWith('/docs');
    }
    return location.pathname === path;
  };

  const toggleGroup = (label: string) => {
    setExpandedGroups((current) => ({ ...current, [label]: !current[label] }));
  };

  const NavLink = ({ item }: { item: SidebarNavItem }) => {
    const Icon = item.icon;
    const active = isActive(item.path);

    const content = (
      <Link
        to={item.path}
        aria-label={sidebarCollapsed ? item.label : undefined}
        onClick={() => setSidebarMobileOpen(false)}
        className={cn(
          'group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors',
          active
            ? 'bg-sidebar-accent text-sidebar-foreground'
            : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground',
          sidebarCollapsed && 'justify-center px-2',
        )}
      >
        {active ? (
          <span className="absolute inset-y-2 left-0 w-1 rounded-r-full bg-primary" />
        ) : null}
        <Icon className={cn('h-4 w-4 shrink-0', active && 'text-primary')} />
        {!sidebarCollapsed ? <span className="truncate">{item.label}</span> : null}
      </Link>
    );

    if (!sidebarCollapsed) {
      return content;
    }

    return (
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>{content}</TooltipTrigger>
        <TooltipContent side="right">{item.label}</TooltipContent>
      </Tooltip>
    );
  };

  const NavGroup = ({
    label,
    icon,
    items,
  }: {
    label: string;
    icon: LucideIcon;
    items: SidebarNavItem[];
  }) => {
    const Icon = icon;
    const expanded = expandedGroups[label] ?? true;
    const hasActiveChild = items.some((item) => isActive(item.path));

    if (sidebarCollapsed) {
      return (
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-label={label}
              className={cn(
                'flex w-full items-center justify-center rounded-xl px-2 py-2.5 transition-colors',
                hasActiveChild
                  ? 'bg-sidebar-accent text-sidebar-foreground'
                  : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground',
              )}
            >
              <Icon className={cn('h-4 w-4', hasActiveChild && 'text-primary')} />
            </button>
          </TooltipTrigger>
          <TooltipContent side="right" className="w-56 p-2">
            <div className="mb-2 px-2 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              {label}
            </div>
            <div className="space-y-1">
              {items.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setSidebarMobileOpen(false)}
                  className={cn(
                    'flex items-center gap-2 rounded-lg px-2 py-2 text-sm',
                    isActive(item.path)
                      ? 'bg-muted text-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  <span className="truncate">{item.label}</span>
                </Link>
              ))}
            </div>
          </TooltipContent>
        </Tooltip>
      );
    }

    return (
      <div className="space-y-1">
        <button
          type="button"
          onClick={() => toggleGroup(label)}
          className={cn(
            'flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors',
            hasActiveChild
              ? 'text-sidebar-foreground'
              : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground',
          )}
        >
          <Icon className={cn('h-4 w-4 shrink-0', hasActiveChild && 'text-primary')} />
          <span className="flex-1 truncate text-left">{label}</span>
          <ChevronDown className={cn('h-4 w-4 transition-transform', !expanded && '-rotate-90')} />
        </button>
        {expanded ? (
          <div className="ml-5 space-y-1 border-l border-sidebar-border/50 pl-3">
            {items.map((item) => (
              <NavLink key={item.path} item={item} />
            ))}
          </div>
        ) : null}
      </div>
    );
  };

  const FooterActionLink = ({
    path,
    label,
    icon,
  }: {
    path: string;
    label: string;
    icon: LucideIcon;
  }) => {
    const Icon = icon;
    const active = isActive(path);

    if (sidebarCollapsed) {
      return (
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <Link
              to={path}
              aria-label={label}
              onClick={() => setSidebarMobileOpen(false)}
              className={cn(
                'flex items-center justify-center rounded-xl px-2 py-2.5 transition-colors',
                active
                  ? 'bg-sidebar-accent text-sidebar-foreground'
                  : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground',
              )}
            >
              <Icon className={cn('h-4 w-4', active && 'text-primary')} />
            </Link>
          </TooltipTrigger>
          <TooltipContent side="right">{label}</TooltipContent>
        </Tooltip>
      );
    }

    return (
      <Link
        to={path}
        onClick={() => setSidebarMobileOpen(false)}
        className={cn(
          'flex flex-1 items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-sm transition-colors',
          active
            ? 'bg-sidebar-accent text-sidebar-foreground'
            : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground',
        )}
      >
        <Icon className={cn('h-4 w-4', active && 'text-primary')} />
        <span>{label}</span>
      </Link>
    );
  };

  const sidebarContent = (
    <TooltipProvider>
      <div className="flex h-full flex-col">
        <div className={cn('flex h-16 items-center border-b border-sidebar-border px-4', sidebarCollapsed && 'justify-center px-2')}>
          <Link to={ROUTES.DASHBOARD} className="group flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-primary/80 text-primary-foreground shadow-lg shadow-primary/20">
              <Shield className="h-5 w-5" />
            </div>
            {!sidebarCollapsed ? (
              <div className="min-w-0">
                <div className="truncate text-lg font-semibold text-sidebar-foreground">Hydra</div>
              </div>
            ) : null}
          </Link>

          <button
            type="button"
            aria-label="Close sidebar"
            className="ml-auto text-sidebar-foreground/70 transition-colors hover:text-sidebar-foreground md:hidden"
            onClick={() => setSidebarMobileOpen(false)}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <ScrollArea className="flex-1 px-3 py-4">
          <nav className="space-y-4">
            <NavGroup label="Dashboard" icon={LayoutDashboard} items={dashboardNavItems} />

            {primaryGroups.map((group) => (
              <NavGroup
                key={group.id}
                label={group.label}
                icon={group.id === 'infrastructure' ? Server : group.id === 'operations' ? Terminal : FileText}
                items={group.items}
              />
            ))}

            {utilityItems.length > 0 ? (
              <>
                <Separator className="bg-sidebar-border/60" />
                <nav aria-label="Sidebar utility" className="space-y-1">
                  {utilityItems.map((item) => (
                    <NavLink key={item.path} item={item} />
                  ))}
                </nav>
              </>
            ) : null}
          </nav>
        </ScrollArea>

        <div className="border-t border-sidebar-border p-3">
          <nav
            aria-label="Sidebar account actions"
            className={cn('mb-3 flex gap-1', sidebarCollapsed ? 'flex-col' : 'flex-row')}
          >
            <FooterActionLink path={ROUTES.SETTINGS} label="Settings" icon={Settings} />
            <FooterActionLink path={ROUTES.PROFILE} label="Profile" icon={User} />
          </nav>

          <Button
            variant="ghost"
            size="sm"
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            onClick={toggleSidebar}
            className={cn('w-full text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground', sidebarCollapsed && 'px-2')}
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
      </div>
    </TooltipProvider>
  );

  return (
    <>
      {sidebarMobileOpen ? (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden"
          role="button"
          tabIndex={-1}
          aria-label="Close sidebar"
          onClick={() => setSidebarMobileOpen(false)}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              setSidebarMobileOpen(false);
            }
          }}
        />
      ) : null}

      <div
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-sidebar-border bg-sidebar transition-transform duration-300 md:hidden',
          sidebarMobileOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        {sidebarContent}
      </div>

      <aside
        className={cn(
          'hidden h-screen shrink-0 border-r border-sidebar-border bg-sidebar transition-all duration-300 md:flex',
          sidebarCollapsed ? 'w-20' : 'w-72',
        )}
        aria-label={currentRoute?.title ? `${currentRoute.title} navigation` : 'Primary navigation'}
      >
        {sidebarContent}
      </aside>
    </>
  );
}
