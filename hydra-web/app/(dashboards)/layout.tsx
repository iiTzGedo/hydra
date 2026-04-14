'use client';

import { Suspense } from 'react';
import { RootLayout } from '@/components/layout/root-layout';
import DashboardsLoading from './loading';

export default function DashboardsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RootLayout>
      <Suspense fallback={<DashboardsLoading />}>{children}</Suspense>
    </RootLayout>
  );
}
