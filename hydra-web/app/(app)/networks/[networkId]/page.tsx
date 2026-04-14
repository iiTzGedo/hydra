import type { Metadata } from 'next';
import NetworkDetailPageClient from './client';

export const metadata: Metadata = {
  title: 'Network Details',
  description: 'View network space configuration',
};

export default function Page() {
  return <NetworkDetailPageClient />;
}
