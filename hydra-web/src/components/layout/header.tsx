import { useNavigate, useLocation } from 'react-router-dom';
import { Menu, Search, LogOut, Settings, Moon, Sun, User, Command } from 'lucide-react';
import { ROUTES } from '@/lib/constants';
import { useUiStore } from '@/stores/ui-store';
import { useAuthStore } from '@/stores/auth-store';
import { useTheme } from '@/components/theme-provider';
import { CommandPalette, useCommandPalette } from '@/components/search/command-palette';
import { NotificationBell } from '@/components/notifications/notification-bell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import { getRouteTitle } from '@/router/routes';
import { usePageTitleStore } from '@/stores/page-title-store';

/**
 * Header - Main application header
 *
 * Features:
 * - Page title (dynamic from page-title-store, falling back to route metadata)
 * - Global search with keyboard shortcut
 * - Theme toggle
 * - Notification bell with popup panel
 * - User menu
 *
 */
export function Header() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setSidebarMobileOpen } = useUiStore();
  const { user, logout } = useAuthStore();
  const { theme, setTheme } = useTheme();
  const commandPalette = useCommandPalette();
  const dynamicTitle = usePageTitleStore((s) => s.title);

  const pageTitle = dynamicTitle ?? getRouteTitle(location.pathname);

  const handleLogout = () => {
    logout();
    navigate(ROUTES.LOGIN);
  };

  return (
    <header
      className={cn(
        'flex h-14 items-center justify-between',
        'border-b border-border',
        'bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60',
        'px-4 sm:px-6',
        'shrink-0 sticky top-0 z-30'
      )}
    >
      {/* Left section - Mobile menu + Page title */}
      <div className="flex items-center gap-4 min-w-0 flex-1">
        {/* Mobile menu toggle — matches sidebar md breakpoint */}
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden text-muted-foreground hover:text-foreground -ml-2"
          onClick={() => setSidebarMobileOpen(true)}
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </Button>

        <div className="min-w-0">
          <h1 className="truncate text-lg font-semibold text-foreground">{pageTitle}</h1>
        </div>
      </div>

      {/* Right section - Search, Theme, Notifications, User */}
      <div className="flex items-center gap-2 sm:gap-4">
        {/* Search */}
        <div className="relative hidden lg:block">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none"
            aria-hidden="true"
          />
          <Input
            placeholder="Search..."
            onClick={commandPalette.open}
            readOnly
            className={cn(
              'w-48 lg:w-64 bg-muted/50 border-input pl-9 pr-20 text-sm',
              'text-foreground placeholder:text-muted-foreground',
              'cursor-pointer hover:bg-muted transition-colors'
            )}
            aria-label="Search (Cmd+K)"
          />
          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
            <kbd className="hidden lg:inline-flex h-5 items-center justify-center rounded border bg-muted px-1.5 text-[10px] font-medium text-muted-foreground">
              <Command className="h-3 w-3 mr-0.5" />
              K
            </kbd>
          </div>
        </div>

        {/* Mobile search button */}
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden text-muted-foreground hover:text-foreground"
          onClick={commandPalette.open}
          aria-label="Search"
        >
          <Search className="h-5 w-5" />
        </Button>

        <CommandPalette isOpen={commandPalette.isOpen} onClose={commandPalette.close} />

        {/* Theme toggle */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          className="text-muted-foreground hover:text-foreground hidden sm:flex"
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {theme === 'dark' ? (
            <Sun className="h-5 w-5" aria-hidden="true" />
          ) : (
            <Moon className="h-5 w-5" aria-hidden="true" />
          )}
        </Button>

        {/* Notifications */}
        <NotificationBell />

        {/* User menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              className="flex items-center gap-2 px-2 hover:bg-muted transition-colors"
            >
              <Avatar className="h-8 w-8 ring-2 ring-border">
                <AvatarFallback className="bg-primary/10 text-primary text-sm font-medium">
                  {user?.username?.charAt(0).toUpperCase() || 'A'}
                </AvatarFallback>
              </Avatar>
              <div className="hidden sm:flex flex-col items-start">
                <span className="text-sm font-medium text-foreground leading-tight">
                  {user?.username || 'Admin'}
                </span>
                <span className="text-[10px] text-muted-foreground capitalize">
                  {user?.role || 'Administrator'}
                </span>
              </div>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-medium">{user?.username || 'Admin'}</p>
                <p className="text-xs text-muted-foreground truncate">
                  {user?.email || 'admin@hydra.local'}
                </p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => navigate('/profile')} className="cursor-pointer">
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
            <DropdownMenuSeparator className="sm:hidden" />
            <DropdownMenuItem
              className="cursor-pointer sm:hidden"
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            >
              {theme === 'dark' ? (
                <Sun className="mr-2 h-4 w-4" />
              ) : (
                <Moon className="mr-2 h-4 w-4" />
              )}
              {theme === 'dark' ? 'Light mode' : 'Dark mode'}
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
