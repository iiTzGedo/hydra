import { useAuthStore } from '@/stores/auth-store';
import type { Role } from '@/types/auth';

interface PermissionGateProps {
  children: React.ReactNode;
  permissions?: string[];
  roles?: Role[];
  fallback?: React.ReactNode;
  requireAll?: boolean;
}

export function PermissionGate({
  children,
  permissions,
  roles,
  fallback = null,
  requireAll = true,
}: PermissionGateProps) {
  const { hasPermission, hasAnyRole, hasRole } = useAuthStore();

  if (roles && roles.length > 0) {
    if (requireAll) {
      const hasAllRoles = roles.every((r) => hasRole(r));
      if (!hasAllRoles) return <>{fallback}</>;
    } else {
      if (!hasAnyRole(roles)) return <>{fallback}</>;
    }
  }

  if (permissions && permissions.length > 0) {
    if (requireAll) {
      const hasAllPermissions = permissions.every((p) => hasPermission(p));
      if (!hasAllPermissions) return <>{fallback}</>;
    } else {
      const hasAnyPermission = permissions.some((p) => hasPermission(p));
      if (!hasAnyPermission) return <>{fallback}</>;
    }
  }

  return <>{children}</>;
}
