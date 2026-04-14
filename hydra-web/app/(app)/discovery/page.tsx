import type { Metadata } from 'next';
import DiscoveryPageClient from './client';

export const metadata: Metadata = {
  title: 'Discovery',
  description: 'Network scanning and device discovery',
};

export default function Page() {
  return <DiscoveryPageClient />;
}
