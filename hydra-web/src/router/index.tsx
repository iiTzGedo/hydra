import { Suspense } from 'react';
import { Routes, Route, Navigate, useLocation, Outlet } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { RootLayout } from '@/components/layout/root-layout';
import { ProtectedRoute } from '@/components/auth/protected-route';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { authRoutes, appRoutes, adminRoutes, errorRoutes } from './routes';
import { ROUTES } from '@/lib/constants';

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
 */
function AnimatedOutlet() {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
        transition={{
          duration: 0.2,
          ease: [0.16, 1, 0.3, 1],
        }}
        className="h-full"
      >
        <Outlet />
      </motion.div>
    </AnimatePresence>
  );
}

/**
 * LayoutWithAnimation - Root layout with animated outlet
 */
function LayoutWithAnimation() {
  return (
    <RootLayout>
      <AnimatedOutlet />
    </RootLayout>
  );
}

export function AppRouter() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        {/* Redirect root to dashboard */}
        <Route path="/" element={<Navigate to={ROUTES.DASHBOARD} replace />} />
        {/* Legacy alerts redirect */}
        <Route path="/alerts" element={<Navigate to={ROUTES.NOTIFICATIONS} replace />} />
        {/* Auth routes - no layout, no auth required */}
        {authRoutes.map((route) => (
          <Route
            key={route.path}
            path={route.path}
            element={
              <Suspense fallback={<PageLoader />}>
                <AnimatedPage>
                  <route.element />
                </AnimatedPage>
              </Suspense>
            }
          />
        ))}

        {/* Protected app routes - with layout and animations */}
        <Route element={<LayoutWithAnimation />}>
          {appRoutes.map((route) => (
            <Route
              key={route.path}
              path={route.path}
              element={
                <ProtectedRoute
                  roles={route.roles}
                  permissions={route.permissions}
                >
                  <Suspense fallback={<PageLoader />}>
                    <route.element />
                  </Suspense>
                </ProtectedRoute>
              }
            />
          ))}
        </Route>

        {/* Admin routes - with layout and animations */}
        <Route element={<LayoutWithAnimation />}>
          {adminRoutes.map((route) => (
            <Route
              key={route.path}
              path={route.path}
              element={
                <ProtectedRoute
                  roles={route.roles}
                  permissions={route.permissions}
                >
                  <Suspense fallback={<PageLoader />}>
                    <route.element />
                  </Suspense>
                </ProtectedRoute>
              }
            />
          ))}
        </Route>

        {/* Error routes */}
        {errorRoutes.map((route) => (
          <Route
            key={route.path}
            path={route.path}
            element={
              <Suspense fallback={<PageLoader />}>
                <AnimatedPage>
                  <route.element />
                </AnimatedPage>
              </Suspense>
            }
          />
        ))}
      </Routes>
    </Suspense>
  );
}
