import type { Metadata } from 'next';
import CommandDetailPageClient from './client';

export const metadata: Metadata = {
  title: 'Command Details',
  description: 'View command execution details and results',
};

export default function Page() {
  return <CommandDetailPageClient />;
}
