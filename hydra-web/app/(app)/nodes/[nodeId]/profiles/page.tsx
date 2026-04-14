import type { Metadata } from 'next';
import NodeProfilesPageClient from './client';

export const metadata: Metadata = {
  title: 'Node Profiles',
  description: 'Profile history and version comparison',
};

export default function Page() {
  return <NodeProfilesPageClient />;
}
