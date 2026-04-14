import type { Metadata } from 'next';
import ProfileDetailPageClient from './client';

export const metadata: Metadata = {
  title: 'Profile Detail',
  description: 'View detailed profile snapshot data',
};

export default function Page() {
  return <ProfileDetailPageClient />;
}
