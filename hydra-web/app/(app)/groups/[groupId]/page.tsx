import type { Metadata } from 'next';
import GroupDetailPageClient from './client';

export const metadata: Metadata = {
  title: 'Group Details',
  description: 'View and manage group membership',
};

export default function Page() {
  return <GroupDetailPageClient />;
}
