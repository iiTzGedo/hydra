import type { Metadata } from 'next';
import NewGroupPageClient from './client';

export const metadata: Metadata = {
  title: 'New Group',
  description: 'Create a new infrastructure group',
};

export default function Page() {
  return <NewGroupPageClient />;
}
