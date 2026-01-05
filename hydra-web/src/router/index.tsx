import { Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
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

export function AppRouter() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        {/* Redirect root to dashboard */}
        <Route path="/" element={<Navigate to={ROUTES.DASHBOARD} replace />} />

        {/* Auth routes - no layout, no auth required */}
        {authRoutes.map((route) => (
          <Route
            key={route.path}
            path={route.path}
            element={
              <Suspense fallback={<PageLoader />}>
                <route.element />
              </Suspense>
            }
          />
        ))}

        {/* Protected app routes - with layout */}
        {appRoutes.map((route) => (
          <Route
            key={route.path}
            path={route.path}
            element={
              <ProtectedRoute
                roles={route.roles}
                permissions={route.permissions}
              >
                <RootLayout>
                  <Suspense fallback={<PageLoader />}>
                    <route.element />
                  </Suspense>
                </RootLayout>
              </ProtectedRoute>
            }
          />
        ))}

        {/* Admin routes - with layout */}
        {adminRoutes.map((route) => (
          <Route
            key={route.path}
            path={route.path}
            element={
              <ProtectedRoute
                roles={route.roles}
                permissions={route.permissions}
              >
                <RootLayout>
                  <Suspense fallback={<PageLoader />}>
                    <route.element />
                  </Suspense>
                </RootLayout>
              </ProtectedRoute>
            }
          />
        ))}

        {/* Error routes */}
        {errorRoutes.map((route) => (
          <Route
            key={route.path}
            path={route.path}
            element={
              <Suspense fallback={<PageLoader />}>
                <route.element />
              </Suspense>
            }
          />
        ))}
      </Routes>
    </Suspense>
  );
}
