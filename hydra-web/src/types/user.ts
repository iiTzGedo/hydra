import { ListParams } from './api';
import { Role, TemporaryRole, User } from './auth';

// Re-export for convenience
export type { Role, User } from './auth';

// User status
export type UserStatus = 'active' | 'inactive' | 'archived';

// User summary (for list views)
export interface UserSummary {
  userId: string;
  username: string;
  email: string;
  role: Role;
  status: UserStatus;
  createdAt: string;
  lastLogin?: string;
  lastLoginAt?: string;
}

// Full user details (renamed to avoid conflict with auth.ts User)
export interface UserDetails extends UserSummary {
  permissions: string[];
  temporaryRoles: TemporaryRole[];
  metadata?: Record<string, unknown>;
}

// User list params
export interface UserListParams extends ListParams {
  role?: Role;
  status?: UserStatus;
}

export interface UserListResponse {
  users: UserSummary[];
  total: number;
  limit: number;
  offset: number;
}

// Elevate role request
export interface ElevateRoleRequest {
  newRole: Role;
}

// Grant temporary role request
export interface GrantTemporaryRoleRequest {
  role: Role;
  durationHours: number;
}
