import type { Metadata } from 'next';
import CommandsPageClient from './client';

export const metadata: Metadata = {
  title: 'Command Center',
  description: 'Execute and monitor infrastructure commands',
};

export default function Page() {
  return <CommandsPageClient />;
}
