import type { Metadata } from 'next';
import { serverFetch } from '@/lib/server-api-client';
import { DocsClient } from './docs-client';

export const metadata: Metadata = {
  title: 'Documentation',
  description: 'Hydra infrastructure documentation portal',
};

interface DocsTreeNode {
  docId: string;
  title: string;
  category: string;
  children?: DocsTreeNode[];
}

export default async function DocsPage() {
  let tree: DocsTreeNode[] = [];

  try {
    tree = await serverFetch<DocsTreeNode[]>('/docs/tree');
  } catch {
    // Client will retry via TanStack Query
  }

  return <DocsClient initialTree={tree} />;
}
