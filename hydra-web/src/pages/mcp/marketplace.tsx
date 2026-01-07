/**
 * MCP Marketplace Page
 * Configure MCP servers without static marketplace data
 */

import { useState } from 'react';
import { motion } from 'framer-motion';
import { ExternalLink, Plus, Server, AlertCircle } from 'lucide-react';
import { useMCPStore } from '@/stores/mcp-store';
import { cn } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import type { MCPServerCategory } from '@/types/mcp';

const categories: MCPServerCategory[] = [
  'infrastructure',
  'monitoring',
  'version-control',
  'databases',
  'cloud',
  'development',
  'other',
];

export default function MCPMarketplacePage() {
  const { servers, addServer } = useMCPStore();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState<MCPServerCategory>('other');
  const [docsUrl, setDocsUrl] = useState('');

  const handleAdd = () => {
    if (!name.trim()) return;
    addServer({
      name: name.trim(),
      description: description.trim() || 'Custom MCP server',
      type: endpoint ? 'remote' : 'custom',
      category,
      endpoint: endpoint.trim() || undefined,
      docsUrl: docsUrl.trim() || undefined,
    });
    setName('');
    setEndpoint('');
    setDescription('');
    setDocsUrl('');
    setCategory('other');
    setShowForm(false);
  };

  return (
    <div className="container mx-auto max-w-6xl p-6 space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold">MCP Servers</h1>
          <p className="text-muted-foreground">
            Configure MCP servers for the chat interface. No marketplace feed is bundled in the
            web app.
          </p>
        </div>
        <button
          onClick={() => setShowForm((open) => !open)}
          className={cn(
            'inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
            'hover:bg-primary/90 transition-colors'
          )}
        >
          <Plus className="h-4 w-4" />
          Add Server
        </button>
      </div>

      {showForm && (
        <div className="rounded-xl border bg-card p-6">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">Name</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                placeholder="e.g., Hydra MCP"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Endpoint (ws://)</label>
              <input
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                placeholder="ws://hydra-mcp:3000"
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <label className="text-sm font-medium">Description</label>
              <input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                placeholder="Optional description"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value as MCPServerCategory)}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
              >
                {categories.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat.replace('-', ' ')}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Docs URL</label>
              <input
                value={docsUrl}
                onChange={(e) => setDocsUrl(e.target.value)}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
                placeholder="https://..."
              />
            </div>
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <button
              onClick={() => setShowForm(false)}
              className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted"
            >
              Cancel
            </button>
            <button
              onClick={handleAdd}
              disabled={!name.trim()}
              className={cn(
                'rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
                'hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              Save
            </button>
          </div>
        </div>
      )}

      {servers.length === 0 ? (
        <div className="rounded-xl border bg-card p-8 text-center">
          <Server className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No MCP servers configured</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Add a server to enable MCP tools in the chat interface.
          </p>
        </div>
      ) : (
        <motion.div
          variants={staggerContainerVariants}
          initial="hidden"
          animate="visible"
          className="grid gap-4 md:grid-cols-2"
        >
          {servers.map((server) => (
            <motion.div
              key={server.id}
              variants={staggerItemVariants}
              className="rounded-xl border bg-card p-5 shadow-sm space-y-3"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        'h-2 w-2 rounded-full',
                        server.status === 'connected' && 'bg-green-500',
                        server.status === 'disconnected' && 'bg-gray-400',
                        server.status === 'error' && 'bg-red-500'
                      )}
                    />
                    <h3 className="font-semibold">{server.name}</h3>
                  </div>
                  <p className="text-sm text-muted-foreground">{server.description}</p>
                </div>
                {server.status === 'error' && (
                  <AlertCircle className="h-4 w-4 text-error" />
                )}
              </div>
              {server.endpoint && (
                <div className="text-xs text-muted-foreground font-mono">
                  {server.endpoint}
                </div>
              )}
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span className="capitalize">{server.category.replace('-', ' ')}</span>
                {server.docsUrl && (
                  <a
                    href={server.docsUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline"
                  >
                    Docs
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
              {server.error && (
                <p className="text-xs text-error">{server.error}</p>
              )}
            </motion.div>
          ))}
        </motion.div>
      )}
    </div>
  );
}
