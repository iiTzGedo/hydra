import type { Metadata } from 'next';
import GroupsPageClient from './client';

export const metadata: Metadata = {
  title: 'Groups',
  description: 'Logical infrastructure groupings',
};

export default function Page() {
  return <GroupsPageClient />;
}
