import type { Metadata } from 'next';
import IntegrationsPageClient from './client';

export const metadata: Metadata = {
  title: 'Integrations',
  description: 'Plugin and integration management',
};

export default function Page() {
  return <IntegrationsPageClient />;
}
