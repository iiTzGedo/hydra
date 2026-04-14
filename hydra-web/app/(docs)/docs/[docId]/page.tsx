import type { Metadata } from 'next';
import { serverFetch } from '@/lib/server-api-client';
import { DocDetailClient } from './doc-detail-client';

interface PageProps {
  params: Promise<{ docId: string }>;
}

interface DocResponse {
  docId: string;
  title: string;
  description?: string;
  category: string;
  status: string;
  sections: Array<{
    title: string;
    content: string;
    source: string;
    order: number;
  }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { docId } = await params;

  try {
    const doc = await serverFetch<DocResponse>(`/docs/${docId}`);
    return {
      title: doc.title,
      description: doc.description || `Documentation: ${doc.title}`,
    };
  } catch {
    return {
      title: 'Document',
    };
  }
}

export default async function DocDetailPage({ params }: PageProps) {
  const { docId } = await params;
  let doc: DocResponse | null = null;

  try {
    doc = await serverFetch<DocResponse>(`/docs/${docId}`);
  } catch {
    // Client will retry via TanStack Query
  }

  return <DocDetailClient docId={docId} initialDoc={doc} />;
}
