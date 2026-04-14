'use client';

import { QueryClient, HydrationBoundary, dehydrate } from '@tanstack/react-query';
import { queryKeys } from '@/lib/query-client';
import DocsPage from '@/views/docs';

interface DocsTreeNode {
  docId: string;
  title: string;
  category: string;
  children?: DocsTreeNode[];
}

interface Props {
  initialTree: DocsTreeNode[];
}

/**
 * Client wrapper that hydrates TanStack Query cache with server-fetched docs tree.
 * The DocsPage component's useDocsTree() hook will find the tree already cached,
 * rendering the navigation sidebar instantly on page load.
 */
export function DocsClient({ initialTree }: Props) {
  const queryClient = new QueryClient();

  if (initialTree.length > 0) {
    queryClient.setQueryData(queryKeys.docs.tree(), initialTree);
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <DocsPage />
    </HydrationBoundary>
  );
}
