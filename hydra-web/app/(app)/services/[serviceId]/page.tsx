import type { Metadata } from 'next';
import ServiceDetailPageClient from './client';

export const metadata: Metadata = {
  title: 'Service Details',
  description: 'View service configuration and status',
};

export default function Page() {
  return <ServiceDetailPageClient />;
}
