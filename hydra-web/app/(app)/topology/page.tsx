import type { Metadata } from 'next';
import TopologyPageClient from './client';

export const metadata: Metadata = {
  title: 'Topology',
  description: 'Infrastructure topology visualization',
};

export default function Page() {
  return <TopologyPageClient />;
}
