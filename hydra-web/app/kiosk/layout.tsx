'use client';

import { Suspense } from 'react';
import { LoadingSpinner } from '@/components/ui/loading-spinner';

function KioskLoading() {
  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <LoadingSpinner size="lg" />
    </div>
  );
}

export default function KioskLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // No RootLayout wrapper — kiosk renders full-screen without sidebar/header
  return <Suspense fallback={<KioskLoading />}>{children}</Suspense>;
}
