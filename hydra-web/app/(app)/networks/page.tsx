import type { Metadata } from 'next';
import NetworksPageClient from './client';

export const metadata: Metadata = {
  title: 'Networks',
  description: 'Network spaces and connectivity',
};

export default function Page() {
  return <NetworksPageClient />;
}
