'use client';

import { Suspense } from 'react';
import { RootLayout } from '@/components/layout/root-layout';
import AppLoading from './loading';

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RootLayout>
      <Suspense fallback={<AppLoading />}>{children}</Suspense>
    </RootLayout>
  );
}
