import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Server,
  Boxes,
  Network,
  FolderTree,
  GitBranch,
  MessageSquare,
  Terminal,
  Settings,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  X,
  Shield,
  User,
  History,
  Bell,
  Search,
  FileText,
  Plug,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import { useUiStore } from '@/stores/ui-store';
import { useAuthStore } from '@/stores/auth-store';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Separator } from '@/components/ui/separator';

// ── Types ─────────────────────────────────────────────────────────

type NavItemDef = {
  icon: typeof LayoutDashboard;
  label: string;
  path: string;
  permission?: string;
  badge?: number;
};

type NavSection =
  | { type: 'item'; item: NavItemDef }
  | { type: 'group'; icon: typeof LayoutDashboard; label: string; permission?: string; children: NavItemDef[] };

// ── Navigation Structure (matches spec § 25.3) ───────────────────

const mainNavSections: NavSection[] = [
  {
    type: 'item',
    item: { icon: LayoutDashboard, label: 'Dashboard', path: ROUTES.DASHBOARD },
  },
  {
    type: 'group',
    icon: Server,
    label: 'Infrastructure',
    children: [
      { icon: Server, label: 'Nodes', path: ROUTES.NODES, permission: 'nodes:read' },
      { icon: Boxes, label: 'Services', path: ROUTES.SERVICES, permission: 'services:read' },
      { icon: Network, label: 'Networks', path: ROUTES.NETWORKS, permission: 'networks:read' },
      { icon: FolderTree, label: 'Groups', path: ROUTES.GROUPS, permission: 'groups:read' },
    ],
  },
  {
    type: 'item',
    item: { icon: GitBranch, label: 'Topology', path: ROUTES.TOPOLOGY, permission: 'topologies:read' },
  },
  {
    type: 'item',
    item: { icon: Search, label: 'Discovery', path: ROUTES.DISCOVERY, permission: 'discovery:read' },
  },
  {
    type: 'item',
    item: { icon: Terminal, label: 'Command Center', path: ROUTES.COMMANDS, permission: 'commands:read' },
  },
  {
    type: 'item',
    item: { icon: FileText, label: 'Documentation', path: ROUTES.DOCS, permission: 'docs:read' },
  },
  {
    type: 'item',
    item: { icon: History, label: 'Time Machine', path: ROUTES.TIME_MACHINE, permission: 'topologies:read' },
  },
  {
    type: 'item',
    item: { icon: Plug, label: 'Integrations', path: ROUTES.INTEGRATIONS, permission: 'plugins:read' },
  },
  {
    type: 'item',
    item: { icon: MessageSquare, label: 'Chat', path: ROUTES.CHAT },
  },
];

const utilityNavItems: NavItemDef[] = [
  { icon: Bell, label: 'Notifications', path: ROUTES.NOTIFICATIONS },
];

// ── Sidebar Component ─────────────────────────────────────────────

export function Sidebar() {
  const location = useLocation();
  const { sidebarCollapsed, sidebarMobileOpen, toggleSidebar, setSidebarMobileOpen } = useUiStore();
  const { hasPermission } = useAuthStore();
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({ Infrastructure: true });

  const isActive = (path: string) =>
    location.pathname === path ||
    (path !== ROUTES.DASHBOARD && location.pathname.startsWith(path));

  const hasGroupPermission = (section: NavSection) => {
    if (section.type === 'item') {
      return !section.item.permission || hasPermission(section.item.permission);
    }
    // Group: show if at least one child is permitted
    if (section.permission && !hasPermission(section.permission)) return false;
    return section.children.some((c) => !c.permission || hasPermission(c.permission));
  };

  const isGroupExpanded = (label: string) => {
    // Auto-expand if any child is active
    const section = mainNavSections.find((s) => s.type === 'group' && s.label === label);
    if (section?.type === 'group' && section.children.some((c) => isActive(c.path))) return true;
    return expandedGroups[label] ?? false;
  };

  const toggleGroup = (label: string) => {
    setExpandedGroups((prev) => ({ ...prev, [label]: !isGroupExpanded(label) }));
  };

  const filteredSections = mainNavSections.filter(hasGroupPermission);
  const filteredUtilityItems = utilityNavItems.filter((item) => !item.permission || hasPermission(item.permission));

  // ── Render Helpers ──────────────────────────────────────────────

  const NavItemLink = ({ item }: { item: NavItemDef }) => {
    const active = isActive(item.path);
    const Icon = item.icon;

    const linkContent = (
      <Link
        to={item.path}
        onClick={() => setSidebarMobileOpen(false)}
        className={cn(
          'flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-all duration-200 relative',
          'hover:bg-sidebar-accent/80',
          active
            ? 'bg-sidebar-accent text-sidebar-foreground'
            : 'text-sidebar-foreground/70 hover:text-sidebar-foreground',
          sidebarCollapsed && 'justify-center px-2'
        )}
      >
        {active && (
          <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-primary rounded-r-full" />
        )}
        <Icon className={cn('h-5 w-5 shrink-0', active && 'text-primary')} />
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

  const NavGroup = ({ section }: { section: Extract<NavSection, { type: 'group' }> }) => {
    const expanded = isGroupExpanded(section.label);
    const GroupIcon = section.icon;
    const hasActiveChild = section.children.some((c) => isActive(c.path));
    const visibleChildren = section.children.filter((c) => !c.permission || hasPermission(c.permission));

    if (sidebarCollapsed) {
      // When collapsed, show group icon with tooltip listing children
      return (
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <button
              className={cn(
                'flex items-center justify-center rounded-md px-2 py-2.5 text-sm font-medium transition-all duration-200 w-full',
                'hover:bg-sidebar-accent/80',
                hasActiveChild
                  ? 'bg-sidebar-accent text-sidebar-foreground'
                  : 'text-sidebar-foreground/70 hover:text-sidebar-foreground'
              )}
            >
              <GroupIcon className={cn('h-5 w-5 shrink-0', hasActiveChild && 'text-primary')} />
            </button>
          </TooltipTrigger>
          <TooltipContent
            side="right"
            className="bg-popover text-popover-foreground border-border p-0"
          >
            <div className="py-1.5">
              <p className="px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                {section.label}
              </p>
              {visibleChildren.map((child) => (
                <Link
                  key={child.path}
                  to={child.path}
                  onClick={() => setSidebarMobileOpen(false)}
                  className={cn(
                    'flex items-center gap-2 px-3 py-1.5 text-sm transition-colors',
                    'hover:bg-accent',
                    isActive(child.path)
                      ? 'text-primary font-medium'
                      : 'text-popover-foreground'
                  )}
                >
                  <child.icon className="h-4 w-4" />
                  {child.label}
                </Link>
              ))}
            </div>
          </TooltipContent>
        </Tooltip>
      );
    }

    return (
      <div>
        <button
          onClick={() => toggleGroup(section.label)}
          className={cn(
            'flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-all duration-200 w-full',
            'hover:bg-sidebar-accent/80',
            hasActiveChild
              ? 'text-sidebar-foreground'
              : 'text-sidebar-foreground/70 hover:text-sidebar-foreground'
          )}
        >
          <GroupIcon className={cn('h-5 w-5 shrink-0', hasActiveChild && 'text-primary')} />
          <span className="truncate flex-1 text-left">{section.label}</span>
          <ChevronDown
            className={cn(
              'h-4 w-4 shrink-0 text-sidebar-foreground/50 transition-transform duration-200',
              !expanded && '-rotate-90'
            )}
          />
        </button>
        {expanded && (
          <div className="ml-4 mt-0.5 space-y-0.5 border-l border-sidebar-border/40 pl-2">
            {visibleChildren.map((child) => (
              <NavItemLink key={child.path} item={child} />
            ))}
          </div>
        )}
      </div>
    );
  };

  // ── Sidebar Content ─────────────────────────────────────────────

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
            {filteredSections.map((section) => {
              if (section.type === 'item') {
                return <NavItemLink key={section.item.path} item={section.item} />;
              }
              return <NavGroup key={section.label} section={section} />;
            })}
          </nav>

          {/* Utility Navigation */}
          {filteredUtilityItems.length > 0 && (
            <>
              <Separator className="my-4 bg-sidebar-border/50" />
              <nav className="flex flex-col gap-1">
                {filteredUtilityItems.map((item) => (
                  <NavItemLink key={item.path} item={item} />
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
          role="button"
          tabIndex={-1}
          aria-label="Close sidebar"
          onClick={() => setSidebarMobileOpen(false)}
          onKeyDown={(e) => { if (e.key === 'Escape') setSidebarMobileOpen(false); }}
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
