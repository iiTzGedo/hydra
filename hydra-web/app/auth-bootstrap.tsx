'use client';

import { useMe } from '@/api/auth';

export function AuthBootstrap() {
  useMe();
  return null;
}
