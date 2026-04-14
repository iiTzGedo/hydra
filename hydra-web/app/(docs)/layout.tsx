'use client';

import { Suspense } from 'react';
import { RootLayout } from '@/components/layout/root-layout';
import DocsLoading from './loading';

export default function DocsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RootLayout>
      <Suspense fallback={<DocsLoading />}>{children}</Suspense>
    </RootLayout>
  );
}
