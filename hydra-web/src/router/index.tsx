'use client';

import { Suspense } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { RootLayout } from '@/components/layout/root-layout';
import { ProtectedRoute } from '@/components/auth/protected-route';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { authRoutes, appRoutes, adminRoutes, errorRoutes } from './routes';
import { ROUTES } from '@/lib/constants';
import { useEffect } from 'react';

function PageLoader() {
  return (
    <div className="flex h-screen items-center justify-center">
      <LoadingSpinner size="lg" />
    </div>
  );
}

/**
 * AnimatedPage - Wraps page content with smooth transition animations
 */
function AnimatedPage({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{
        duration: 0.2,
        ease: [0.16, 1, 0.3, 1],
      }}
    >
      {children}
    </motion.div>
  );
}

/**
 * AnimatedOutlet - Handles page transitions with AnimatePresence
 * In Next.js, renders children instead of <Outlet />
 */
function AnimatedOutlet({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? '/';

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={pathname}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{
          duration: 0.2,
          ease: [0.16, 1, 0.3, 1],
        }}
        className="h-full"
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

/**
 * RedirectHandler - Handles legacy redirects in Next.js
 */
function RedirectHandler() {
  const pathname = usePathname() ?? '/';
  const router = useRouter();

  useEffect(() => {
    if (pathname === '/') {
      router.replace(ROUTES.DASHBOARD);
    } else if (pathname === '/alerts') {
      router.replace(ROUTES.NOTIFICATIONS);
    }
  }, [pathname, router]);

  return null;
}

/**
 * RouteMatcher - Matches current pathname to route config and renders appropriate component
 */
function RouteMatcher() {
  const pathname = usePathname() ?? '/';

  // Check for redirects
  if (pathname === '/' || pathname === '/alerts') {
    return <RedirectHandler />;
  }

  // Check auth routes first (no layout wrapper)
  const authRoute = authRoutes.find((route) => {
    const regex = new RegExp(`^${route.path.replace(/:[\w]+/g, '[^/]+')}$`);
    return regex.test(pathname);
  });

  if (authRoute) {
    return (
      <Suspense fallback={<PageLoader />}>
        <AnimatedPage>
          <authRoute.element />
        </AnimatedPage>
      </Suspense>
    );
  }

  // Check app routes and admin routes (with layout)
  const allProtectedRoutes = [...appRoutes, ...adminRoutes];
  const matchedRoute = allProtectedRoutes
    .sort((a, b) => b.path.length - a.path.length)
    .find((route) => {
      const regex = new RegExp(
        `^${route.path.replace(/\*/g, '.*').replace(/:[\w]+/g, '[^/]+')}${route.matchEnd !== false ? '$' : '(?:/|$)'}`
      );
      return regex.test(pathname);
    });

  if (matchedRoute) {
    return (
      <RootLayout>
        <AnimatedOutlet>
          <ProtectedRoute
            roles={matchedRoute.roles}
            permissions={matchedRoute.permissions}
          >
            <Suspense fallback={<PageLoader />}>
              <matchedRoute.element />
            </Suspense>
          </ProtectedRoute>
        </AnimatedOutlet>
      </RootLayout>
    );
  }

  // Error/404 route
  const errorRoute = errorRoutes[0];
  if (errorRoute) {
    return (
      <Suspense fallback={<PageLoader />}>
        <AnimatedPage>
          <errorRoute.element />
        </AnimatedPage>
      </Suspense>
    );
  }

  return null;
}

export function AppRouter() {
  return (
    <Suspense fallback={<PageLoader />}>
      <RouteMatcher />
    </Suspense>
  );
}
