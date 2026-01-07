// User roles
export type Role = 'admin' | 'operator' | 'viewer' | 'family' | 'agent';

// User information
export interface User {
  userId: string;
  username: string;
  email: string;
  role: Role;
  permissions: string[];
  temporaryRoles?: TemporaryRole[];
  createdAt: string;
  lastLoginAt?: string;
}

export interface TemporaryRole {
  role: Role;
  expiresAt: string;
  grantedBy: string;
  grantedAt: string;
}

// Login
export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  tokenType: string;
  user: User;
}

// Registration
export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  role?: Role; // Optional - defaults to 'viewer' for self-registration
  registrationToken?: string;
}

export interface RegisterResponse {
  userId: string;
  username: string;
  email: string;
  role: Role;
  status: 'active' | 'pending_approval';
  message?: string;
  isBootstrap?: boolean;
  createdAt: string;
}

// Password reset
export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  newPassword: string;
}

export interface ChangePasswordRequest {
  currentPassword: string;
  newPassword: string;
}

// Token refresh
export interface RefreshRequest {
  refreshToken: string;
}

export interface RefreshResponse {
  accessToken: string;
  expiresIn: number;
  tokenType: string;
}

// Current user/agent info
export interface MeResponse {
  type: 'user' | 'agent';
  userId?: string;
  nodeId?: string;
  username?: string;
  email?: string;
  role: Role;
  permissions: string[];
}

// Pending approvals
export interface PendingUser {
  userId: string;
  username: string;
  email: string;
  role: Role;
  requestedAt: string;
}

export interface ApprovalsResponse {
  pendingUsers: PendingUser[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApproveRequest {
  userId?: string;
  username?: string;
}

// Registration tokens
export interface CreateRegistrationTokenRequest {
  description?: string;
  expiresIn?: number;
  maxUses?: number;
  allowedRoles?: Role[];
  scope?: 'user' | 'node';
}

export interface RegistrationToken {
  token: string;
  description?: string;
  expiresAt: string;
  maxUses?: number;
  usedCount: number;
  allowedRoles?: Role[];
  scope: 'user' | 'node';
  createdBy: string;
  createdAt?: string;
}

// API Keys
export interface CreateApiKeyRequest {
  name: string;
  roles?: Role[];
  permissions?: string[];
  expiresAt?: string;
}

export interface ApiKey {
  keyId: string;
  key?: string; // Only returned once at creation
  name: string;
  roles?: Role[];
  permissions: string[];
  expiresAt?: string;
  lastUsedAt?: string;
  createdBy?: string;
  createdAt: string;
}

export interface ApiKeyListResponse {
  apiKeys: ApiKey[];
  total: number;
}
