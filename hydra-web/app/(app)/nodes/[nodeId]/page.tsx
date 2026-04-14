import type { Metadata } from 'next';
import NodeDetailPageClient from './client';

export const metadata: Metadata = {
  title: 'Node Details',
  description: 'View node configuration and status',
};

export default function Page() {
  return <NodeDetailPageClient />;
}
