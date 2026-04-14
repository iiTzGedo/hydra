import type { Metadata } from 'next';
import ProfilePageClient from './client';

export const metadata: Metadata = {
  title: 'Profile',
  description: 'User profile and preferences',
};

export default function Page() {
  return <ProfilePageClient />;
}
