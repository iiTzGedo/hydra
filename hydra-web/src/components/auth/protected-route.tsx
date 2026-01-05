import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/stores/auth-store';
import { ROUTES } from '@/lib/constants';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import type { Role } from '@/types/auth';

interface ProtectedRouteProps {
  children: React.ReactNode;
  roles?: Role[];
  permissions?: string[];
}

export function ProtectedRoute({ children, roles, permissions }: ProtectedRouteProps) {
  const location = useLocation();
  const { isAuthenticated, isLoading, user, hasPermission, hasAnyRole } = useAuthStore();

  // Show loading while checking auth state
  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to={ROUTES.LOGIN} state={{ from: location }} replace />;
  }

  // Check role requirements
  if (roles && roles.length > 0) {
    if (!hasAnyRole(roles)) {
      return <Navigate to={ROUTES.DASHBOARD} replace />;
    }
  }

  // Check permission requirements
  if (permissions && permissions.length > 0) {
    const hasAllPermissions = permissions.every((p) => hasPermission(p));
    if (!hasAllPermissions) {
      return <Navigate to={ROUTES.DASHBOARD} replace />;
    }
  }

  return <>{children}</>;
}
