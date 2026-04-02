// User roles
export type Role = 'admin' | 'operator' | 'viewer' | 'family' | 'agent';

// User information (matches API UserInfo from login response)
export interface User {
  userId: string;
  username: string;
  email: string;
  role: Role;
  permissions: string[];
  temporaryRoles: TemporaryRole[];
  // These fields are NOT in the login UserInfo response but may be
  // populated from UserDetailResponse or hook transformations
  createdAt?: string;
  lastLoginAt?: string;
}

export interface TemporaryRole {
  role: Role;
  expiresAt: string;
  grantedBy: string;
  grantedAt: string;
  reason?: string;
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

export interface SessionLoginResponse {
  user: User;
  expiresIn: number;
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
  email?: string;
  role: Role;
  status: 'active' | 'inactive' | 'archived' | 'pending_approval';
  isBootstrap?: boolean;
  message?: string;
  createdAt: string;
  isSystemAccount?: boolean;
  parentUserId?: string;
  apiKey?: string;
  apiKeyId?: string;
  apiKeyExpiresAt?: string;
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
  refreshToken: string;
  expiresIn: number;
  tokenType: string;
}

export interface SessionRefreshResponse {
  expiresIn: number;
}

// Current user/agent info
export interface MeResponse {
  type: 'user' | 'agent';
  userId?: string;
  nodeId?: string;
  username?: string;
  email?: string;
  role?: Role;
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
  tokenId?: string;
  description?: string;
  expiresAt: string;
  maxUses?: number;
  usedCount: number;
  usedBy?: RegistrationTokenUsage[];
  allowedRoles?: Role[];
  scope: 'user' | 'node';
  createdBy: string;
  createdAt?: string;
  isActive?: boolean;
}

export interface RegistrationTokenUsage {
  entityId: string;
  entityType: string;
  usedAt: string;
}

// API Keys
export interface CreateApiKeyRequest {
  name: string;
  roles?: Role[];
  permissions?: string[];
  expiresAt?: string;
}

// ApiKey covers both creation response and list item
export interface ApiKey {
  keyId: string;
  key?: string; // Only returned once at creation
  name: string;
  type?: string; // "user" | "node"
  ownerId?: string;
  nodeId?: string;
  roles?: Role[];
  permissions: string[];
  expiresAt?: string;
  lastUsedAt?: string;
  usageCount?: number;
  createdBy?: string;
  createdAt: string;
}

export interface ApiKeyListResponse {
  apiKeys: ApiKey[];
  total: number;
}

export interface ApiKeyRevokeResponse {
  keyId: string;
  revoked: boolean;
  revokedAt: string;
}
