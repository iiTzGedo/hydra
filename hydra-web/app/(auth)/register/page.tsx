import type { Metadata } from 'next';
import RegisterPageClient from './client';

export const metadata: Metadata = {
  title: 'Create Account',
  description: 'Create a new Hydra account',
};

export default function Page() {
  return <RegisterPageClient />;
}
