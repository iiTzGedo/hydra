'use client';

import { QueryClient, HydrationBoundary, dehydrate } from '@tanstack/react-query';
import { queryKeys } from '@/lib/query-client';
import DocsPage from '@/views/docs';

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

interface Props {
  docId: string;
  initialDoc: DocResponse | null;
}

/**
 * Client wrapper that hydrates TanStack Query cache with server-fetched document data.
 * The DocsPage component's useDoc(docId) hook will find the document already cached,
 * rendering content and sections instantly on page load.
 */
export function DocDetailClient({ docId, initialDoc }: Props) {
  const queryClient = new QueryClient();

  if (initialDoc) {
    queryClient.setQueryData(queryKeys.docs.detail(docId), initialDoc);
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <DocsPage />
    </HydrationBoundary>
  );
}
