import type { Metadata } from 'next';
import TimeMachinePageClient from './client';

export const metadata: Metadata = {
  title: 'Time Machine',
  description: 'Historical infrastructure state navigation',
};

export default function Page() {
  return <TimeMachinePageClient />;
}
