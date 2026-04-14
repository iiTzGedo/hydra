import type { Metadata } from 'next';
import ResetPasswordPageClient from './client';

export const metadata: Metadata = {
  title: 'Reset Password',
  description: 'Set a new password for your Hydra account',
};

export default function Page() {
  return <ResetPasswordPageClient />;
}
