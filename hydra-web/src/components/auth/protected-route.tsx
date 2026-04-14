import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
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
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, isLoading, hasPermission, hasAnyRole } = useAuthStore();

  useEffect(() => {
    if (isLoading) return;

    if (!isAuthenticated) {
      router.replace(ROUTES.LOGIN);
      return;
    }

    if (roles && roles.length > 0 && !hasAnyRole(roles)) {
      router.replace(ROUTES.DASHBOARD);
      return;
    }

    if (permissions && permissions.length > 0) {
      const hasAllPermissions = permissions.every((p) => hasPermission(p));
      if (!hasAllPermissions) {
        router.replace(ROUTES.DASHBOARD);
      }
    }
  }, [isLoading, isAuthenticated, roles, permissions, hasAnyRole, hasPermission, router, pathname]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  if (roles && roles.length > 0 && !hasAnyRole(roles)) {
    return null;
  }

  if (permissions && permissions.length > 0) {
    const hasAllPermissions = permissions.every((p) => hasPermission(p));
    if (!hasAllPermissions) {
      return null;
    }
  }

  return <>{children}</>;
}
