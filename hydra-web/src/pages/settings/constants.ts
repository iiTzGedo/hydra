import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  User,
  Server,
  Boxes,
  Network,
  FolderTree,
  Settings,
  UserPlus,
  Edit,
  Trash2,
  LogIn,
  LogOut,
  Zap,
} from 'lucide-react';
import type { Role } from '@/types/user';
import type { AuditAction } from '@/types/query';

// Role badge variants
export const roleVariants: Record<Role, 'destructive' | 'warning' | 'default' | 'success' | 'secondary'> = {
  admin: 'destructive',
  operator: 'warning',
  viewer: 'default',
  family: 'success',
  agent: 'secondary',
};

export const roleIcons: Record<Role, typeof Shield> = {
  admin: ShieldAlert,
  operator: ShieldCheck,
  viewer: Shield,
  family: Shield,
  agent: Shield,
};

// Audit log helpers
export const resourceIcons: Record<string, typeof User> = {
  user: User,
  node: Server,
  service: Boxes,
  network: Network,
  group: FolderTree,
  topology: Settings,
  system: Settings,
};

export const actionIcons: Record<AuditAction, typeof User> = {
  create: UserPlus,
  update: Edit,
  delete: Trash2,
  login: LogIn,
  logout: LogOut,
  register: UserPlus,
  execute: Zap,
};

export const actionVariants: Record<AuditAction, 'success' | 'default' | 'destructive' | 'secondary' | 'warning'> = {
  create: 'success',
  update: 'default',
  delete: 'destructive',
  login: 'default',
  logout: 'secondary',
  register: 'success',
  execute: 'warning',
};
