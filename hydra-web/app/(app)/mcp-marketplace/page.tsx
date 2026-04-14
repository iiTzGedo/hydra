import type { Metadata } from 'next';
import McpMarketplacePageClient from './client';

export const metadata: Metadata = {
  title: 'MCP Marketplace',
  description: 'Browse and manage MCP server connections',
};

export default function Page() {
  return <McpMarketplacePageClient />;
}
