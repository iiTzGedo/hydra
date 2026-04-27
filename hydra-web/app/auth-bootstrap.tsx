'use client';

import { usePathname } from 'next/navigation';
import { useMe } from '@/api/auth';

/**
 * Routes that render without a session — the built-in auth pages and any
 * kiosk board. These must not call `useMe()` because:
 *   - Auth pages are reachable while logged out; hitting /auth/me with no
 *     cookie produces a 401 that the response interceptor tries to recover
 *     from, which is pointless on the login page itself.
 *   - Kiosk boards authenticate via the `?token=` query parameter and are
 *     intended to work on display devices that never had a session cookie.
 *     A 401 on /auth/me there would trigger the interceptor's
 *     `handleLogout()` and redirect the kiosk to /login.
 */
function isPublicRoute(pathname: string | null): boolean {
  if (!pathname) return false;
  if (pathname.startsWith('/kiosk/')) return true;
  if (pathname === '/login' || pathname === '/register') return true;
  if (pathname === '/forgot-password' || pathname === '/reset-password') return true;
  return false;
}

function AuthBootstrapImpl() {
  useMe();
  return null;
}

export function AuthBootstrap() {
  const pathname = usePathname();
  if (isPublicRoute(pathname)) return null;
  return <AuthBootstrapImpl />;
}
