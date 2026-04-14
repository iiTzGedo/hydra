import type { Metadata } from 'next';
import CompareProfilesPageClient from './client';

export const metadata: Metadata = {
  title: 'Compare Profiles',
  description: 'Compare profile versions side by side',
};

export default function Page() {
  return <CompareProfilesPageClient />;
}
