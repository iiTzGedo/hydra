import { useNavigate, useLocation } from 'react-router-dom';
import {
  Menu,
  Search,
  Bell,
  LogOut,
  Settings,
  Moon,
  Sun,
  Monitor,
  User,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import { useUiStore } from '@/stores/ui-store';
import { useAuthStore } from '@/stores/auth-store';
import { useTheme } from '@/components/theme-provider';
import { CommandPalette, useCommandPalette } from '@/components/search/command-palette';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuSubContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
} from '@/components/ui/dropdown-menu';

// Page title mapping
const pathTitles: Record<string, string> = {
  '/': 'Dashboard',
  '/dashboard': 'Dashboard',
  '/nodes': 'Node Explorer',
  '/services': 'Service Explorer',
  '/networks': 'Network Explorer',
  '/groups': 'Group Management',
  '/topology': 'Topology Viewer',
  '/time-machine': 'Time Machine',
  '/timemachine': 'Time Machine',
  '/alerts': 'Notifications',
  '/chat': 'MCP Chat',
  '/mcp-marketplace': 'MCP Marketplace',
  '/profile': 'Profile',
  '/settings': 'Settings',
};

function getPageTitle(pathname: string): string {
  // Direct match
  if (pathTitles[pathname]) {
    return pathTitles[pathname];
  }

  // Check for detail pages
  if (pathname.startsWith('/nodes/')) return 'Node Details';
  if (pathname.startsWith('/services/')) return 'Service Details';
  if (pathname.startsWith('/networks/')) return 'Network Details';
  if (pathname.startsWith('/groups/')) return 'Group Details';

  return 'Hydra';
}

export function Header() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setSidebarMobileOpen } = useUiStore();
  const { user, logout } = useAuthStore();
  const { theme, setTheme } = useTheme();
  const commandPalette = useCommandPalette();

  const pageTitle = getPageTitle(location.pathname);

  const handleLogout = () => {
    logout();
    navigate(ROUTES.LOGIN);
  };

  // Mock alerts (in real app, fetch from API)
  const unacknowledgedAlerts = 3;
  const criticalAlerts = 1;

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-background px-4 sm:px-6 shrink-0">
      {/* Left side - Page title */}
      <div className="flex items-center gap-4 min-w-0">
        {/* Mobile menu button */}
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden text-muted-foreground"
          onClick={() => setSidebarMobileOpen(true)}
        >
          <Menu className="h-5 w-5" />
        </Button>
        <h1 className="text-lg font-semibold text-foreground truncate">{pageTitle}</h1>
      </div>

      {/* Right side - Search, notifications, user */}
      <div className="flex items-center gap-2 sm:gap-4">
        {/* Search - Hidden on mobile */}
        <div className="relative hidden sm:block">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Global search..."
            onClick={commandPalette.open}
            readOnly
            className="w-48 bg-muted/60 border-input pl-9 text-sm text-foreground placeholder:text-muted-foreground cursor-pointer lg:w-96"
          />
          <kbd className="absolute right-3 top-1/2 -translate-y-1/2 rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground hidden lg:inline">
            ⌘K
          </kbd>
        </div>

        {/* Mobile search button */}
        <Button
          variant="ghost"
          size="icon"
          className="sm:hidden text-muted-foreground"
          onClick={commandPalette.open}
        >
          <Search className="h-5 w-5" />
        </Button>

        {/* Command Palette */}
        <CommandPalette isOpen={commandPalette.isOpen} onClose={commandPalette.close} />

        {/* Theme Toggle */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          className="text-muted-foreground"
        >
          {theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </Button>

        {/* Notifications */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="relative text-muted-foreground"
            >
              <Bell className="h-5 w-5" />
              {unacknowledgedAlerts > 0 && (
                <span
                  className={cn(
                    'absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-medium text-white',
                    criticalAlerts > 0 ? 'bg-destructive' : 'bg-warning'
                  )}
                >
                  {unacknowledgedAlerts}
                </span>
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-80">
            <DropdownMenuLabel>Alerts</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="flex flex-col items-start gap-1 p-3">
              <div className="flex items-center gap-2">
                <Badge variant="destructive" className="text-[10px]">critical</Badge>
                <span className="text-sm font-medium text-foreground">High CPU Usage</span>
              </div>
              <span className="text-xs text-muted-foreground">proxmox-01 CPU at 95%</span>
            </DropdownMenuItem>
            <DropdownMenuItem className="flex flex-col items-start gap-1 p-3">
              <div className="flex items-center gap-2">
                <Badge variant="warning" className="text-[10px]">warning</Badge>
                <span className="text-sm font-medium text-foreground">Service Unhealthy</span>
              </div>
              <span className="text-xs text-muted-foreground">nginx container health check failing</span>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <a href="/alerts" className="text-center text-sm text-primary hover:text-primary/80 justify-center">
                View all alerts
              </a>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* User Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="flex items-center gap-2 px-2">
              <Avatar className="h-8 w-8">
                <AvatarFallback className="bg-primary text-primary-foreground text-sm">
                  {user?.username?.charAt(0).toUpperCase() || 'A'}
                </AvatarFallback>
              </Avatar>
              <span className="text-sm text-foreground hidden sm:inline">
                {user?.username || 'Admin'}
              </span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>My Account</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => navigate('/profile')}
              className="cursor-pointer"
            >
              <User className="mr-2 h-4 w-4" />
              Profile
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => navigate(ROUTES.SETTINGS)}
              className="cursor-pointer"
            >
              <Settings className="mr-2 h-4 w-4" />
              Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={handleLogout}
              className="text-destructive focus:text-destructive cursor-pointer"
            >
              <LogOut className="mr-2 h-4 w-4" />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
