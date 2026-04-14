import type { Metadata } from 'next';
import SettingsPageClient from './client';

export const metadata: Metadata = {
  title: 'Settings',
  description: 'System administration and configuration',
};

export default function Page() {
  return <SettingsPageClient />;
}
