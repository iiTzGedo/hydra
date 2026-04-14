import type { Metadata } from 'next';
import ServicesPageClient from './client';

export const metadata: Metadata = {
  title: 'Services',
  description: 'Service workloads across infrastructure',
};

export default function Page() {
  return <ServicesPageClient />;
}
