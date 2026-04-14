import type { Metadata } from 'next';
import NodesPageClient from './client';

export const metadata: Metadata = {
  title: 'Nodes',
  description: 'Infrastructure nodes and compute resources',
};

export default function Page() {
  return <NodesPageClient />;
}
