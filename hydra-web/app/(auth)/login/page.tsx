import type { Metadata } from 'next';
import LoginPageClient from './client';

export const metadata: Metadata = {
  title: 'Sign In',
  description: 'Sign in to your Hydra account',
};

export default function Page() {
  return <LoginPageClient />;
}
