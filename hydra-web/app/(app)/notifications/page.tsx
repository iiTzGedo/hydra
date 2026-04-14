import type { Metadata } from 'next';
import NotificationsPageClient from './client';

export const metadata: Metadata = {
  title: 'Notifications',
  description: 'System notifications and alerts',
};

export default function Page() {
  return <NotificationsPageClient />;
}
