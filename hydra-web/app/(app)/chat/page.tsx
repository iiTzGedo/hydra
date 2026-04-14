import type { Metadata } from 'next';
import ChatPageClient from './client';

export const metadata: Metadata = {
  title: 'Chat',
  description: 'AI-powered infrastructure assistant',
};

export default function Page() {
  return <ChatPageClient />;
}
