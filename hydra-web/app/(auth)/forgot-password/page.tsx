import type { Metadata } from 'next';
import ForgotPasswordPageClient from './client';

export const metadata: Metadata = {
  title: 'Forgot Password',
  description: 'Reset your Hydra account password',
};

export default function Page() {
  return <ForgotPasswordPageClient />;
}
