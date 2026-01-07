import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Menu,
  Search,
  Bell,
  User,
  LogOut,
  Settings,
  Moon,
  Sun,
  Monitor,
  Command,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import { useUiStore } from '@/stores/ui-store';
import { useAuthStore } from '@/stores/auth-store';
import { useTheme } from '@/components/theme-provider';
import { Breadcrumbs } from './breadcrumbs';
import { CommandPalette, useCommandPalette } from '@/components/search/command-palette';

export function Header() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setSidebarMobileOpen } = useUiStore();
  const { user, logout } = useAuthStore();
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const commandPalette = useCommandPalette();

  const handleLogout = () => {
    logout();
    navigate(ROUTES.LOGIN);
  };

  const themeOptions = [
    { value: 'light', label: 'Light', icon: Sun },
    { value: 'dark', label: 'Dark', icon: Moon },
    { value: 'system', label: 'System', icon: Monitor },
  ] as const;

  return (
    <header className="sticky top-0 z-20 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-6">
      <div className="mx-auto flex h-14 w-full max-w-[1600px] items-center gap-4">
        {/* Mobile menu button */}
        <button
          className="md:hidden"
          onClick={() => setSidebarMobileOpen(true)}
        >
          <Menu className="h-5 w-5" />
        </button>

      {/* Breadcrumbs */}
      <div className="hidden flex-1 md:block">
        <Breadcrumbs />
      </div>

      {/* Mobile title */}
      <div className="flex-1 text-center font-semibold md:hidden">
        Hydra
      </div>

      {/* Search (desktop) - Opens command palette */}
      <div className="hidden md:block">
        <button
          onClick={commandPalette.open}
          className={cn(
            'flex h-9 w-64 items-center gap-2 rounded-lg border bg-muted/50 px-3 text-sm text-muted-foreground',
            'hover:bg-muted hover:text-foreground transition-colors'
          )}
        >
          <Search className="h-4 w-4" />
          <span className="flex-1 text-left">Search...</span>
          <kbd className="hidden lg:inline-flex h-5 select-none items-center gap-1 rounded border bg-background px-1.5 font-mono text-xs">
            <Command className="h-3 w-3" />K
          </kbd>
        </button>
      </div>

      {/* Command Palette */}
      <CommandPalette isOpen={commandPalette.isOpen} onClose={commandPalette.close} />

      {/* Notifications */}
      <button className="relative rounded-lg p-2 hover:bg-muted">
        <Bell className="h-5 w-5" />
        {/* Notification badge */}
        {/* <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-error" /> */}
      </button>

        {/* User menu */}
        <div className="relative">
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center gap-2 rounded-lg p-2 hover:bg-muted"
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-medium">
              {user?.username?.charAt(0).toUpperCase() || 'U'}
            </div>
            <span className="hidden text-sm font-medium md:inline">
              {user?.username}
            </span>
          </button>

          {/* Dropdown menu */}
          {userMenuOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setUserMenuOpen(false)}
              />
              <div className="absolute right-0 top-full z-50 mt-2 w-56 rounded-lg border bg-popover p-1 shadow-lg">
                {/* User info */}
                <div className="px-3 py-2 border-b mb-1">
                  <div className="font-medium">{user?.username}</div>
                  <div className="text-xs text-muted-foreground">{user?.email}</div>
                  <div className="mt-1 inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                    {user?.role}
                  </div>
                </div>

                {/* Theme options */}
                <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
                  Theme
                </div>
                {themeOptions.map((option) => {
                  const Icon = option.icon;
                  return (
                    <button
                      key={option.value}
                      onClick={() => {
                        setTheme(option.value);
                      }}
                      className={cn(
                        'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm',
                        'hover:bg-accent',
                        theme === option.value && 'bg-accent'
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      {option.label}
                    </button>
                  );
                })}

                <div className="my-1 border-t" />

                {/* Settings */}
                <button
                  onClick={() => {
                    setUserMenuOpen(false);
                    navigate(ROUTES.ADMIN);
                  }}
                  className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent"
                >
                  <Settings className="h-4 w-4" />
                  Settings
                </button>

                {/* Logout */}
                <button
                  onClick={handleLogout}
                  className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-error hover:bg-error/10"
                >
                  <LogOut className="h-4 w-4" />
                  Logout
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
