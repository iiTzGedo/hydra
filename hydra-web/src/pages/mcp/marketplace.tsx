/**
 * MCP Marketplace Page
 * Browse and connect to suggested MCP servers
 */

import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Search,
  ExternalLink,
  Plus,
  Check,
  Server,
  Activity,
  GitBranch,
  Database,
  Cloud,
  Code,
  Folder,
  Box,
  BarChart2,
  GitMerge,
  Layers,
  Terminal,
  Star,
} from 'lucide-react';
import {
  SUGGESTED_MCP_SERVERS,
  getMCPCategories,
  MCP_CATEGORY_LABELS,
  searchMCPServers,
} from '@/lib/mcp-marketplace';
import { useMCPStore } from '@/stores/mcp-store';
import { cn } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import type { SuggestedMCPServer, MCPServerCategory } from '@/types/mcp';

// Icon mapping
const iconMap: Record<string, React.ElementType> = {
  server: Server,
  activity: Activity,
  'git-branch': GitBranch,
  database: Database,
  cloud: Cloud,
  code: Code,
  folder: Folder,
  box: Box,
  'bar-chart-2': BarChart2,
  'git-merge': GitMerge,
  layers: Layers,
  terminal: Terminal,
};

// Category colors
const categoryColors: Record<MCPServerCategory, string> = {
  infrastructure: 'bg-blue-500',
  monitoring: 'bg-green-500',
  'version-control': 'bg-purple-500',
  databases: 'bg-orange-500',
  cloud: 'bg-cyan-500',
  development: 'bg-pink-500',
  other: 'bg-gray-500',
};

export default function MCPMarketplacePage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const { servers, addServer } = useMCPStore();

  const categories = getMCPCategories();

  // Filter servers based on search and category
  const filteredServers = searchQuery
    ? searchMCPServers(searchQuery)
    : selectedCategory
    ? SUGGESTED_MCP_SERVERS.filter((s) => s.category === selectedCategory)
    : SUGGESTED_MCP_SERVERS;

  // Check if a server is already added
  const isServerAdded = (serverId: string) => {
    return servers.some((s) => s.id === serverId || s.name === serverId);
  };

  const handleAddServer = (server: SuggestedMCPServer) => {
    if (!isServerAdded(server.id)) {
      addServer({
        name: server.name,
        description: server.description,
        type: server.id === 'hydra-mcp' ? 'builtin' : 'remote',
        category: server.category,
        docsUrl: server.docsUrl,
      });
    }
  };

  return (
    <div className="container mx-auto max-w-7xl p-6 space-y-8">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-3xl font-bold">MCP Marketplace</h1>
        <p className="text-muted-foreground">
          Connect MCP servers to enhance your AI assistant with specialized tools and resources.
          These servers extend your assistant&apos;s capabilities for infrastructure management.
        </p>
      </div>

      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search MCP servers..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setSelectedCategory(null)}
            className={cn(
              'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
              !selectedCategory
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted hover:bg-muted/80'
            )}
          >
            All
          </button>
          {categories.map((category) => (
            <button
              key={category}
              onClick={() => setSelectedCategory(category)}
              className={cn(
                'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                selectedCategory === category
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted hover:bg-muted/80'
              )}
            >
              {MCP_CATEGORY_LABELS[category] || category}
            </button>
          ))}
        </div>
      </div>

      {/* Server Grid */}
      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3"
      >
        {filteredServers.map((server) => (
          <ServerCard
            key={server.id}
            server={server}
            isAdded={isServerAdded(server.id)}
            onAdd={() => handleAddServer(server)}
          />
        ))}
      </motion.div>

      {filteredServers.length === 0 && (
        <div className="text-center py-12">
          <Server className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No servers found</h3>
          <p className="text-muted-foreground">Try adjusting your search or filters</p>
        </div>
      )}

      {/* Info Section */}
      <div className="border rounded-xl p-6 bg-muted/30 space-y-4">
        <h2 className="text-lg font-semibold">About MCP Servers</h2>
        <p className="text-muted-foreground">
          MCP (Model Context Protocol) servers expose tools and resources that AI assistants can
          use to interact with external systems. By connecting multiple MCP servers, you can give
          your assistant access to:
        </p>
        <ul className="list-disc list-inside text-muted-foreground space-y-1">
          <li>Infrastructure data from Hydra (nodes, services, networks, profiles)</li>
          <li>Real-time metrics from Prometheus and Grafana</li>
          <li>Code repositories from GitHub or GitLab</li>
          <li>Cloud resources from AWS, GCP, or Azure</li>
          <li>Container orchestration with Kubernetes and Docker</li>
        </ul>
        <p className="text-muted-foreground">
          Each server provides specialized capabilities. The Hydra MCP server is built-in and
          provides infrastructure context. Add more servers to enhance your assistant&apos;s
          abilities.
        </p>
      </div>
    </div>
  );
}

interface ServerCardProps {
  server: SuggestedMCPServer;
  isAdded: boolean;
  onAdd: () => void;
}

function ServerCard({ server, isAdded, onAdd }: ServerCardProps) {
  const Icon = iconMap[server.icon] || Server;

  return (
    <motion.div
      variants={staggerItemVariants}
      className="border rounded-xl p-5 bg-card hover:shadow-lg transition-shadow space-y-4"
    >
      {/* Header */}
      <div className="flex items-start gap-3">
        <div
          className={cn(
            'p-2.5 rounded-lg text-white',
            categoryColors[server.category]
          )}
        >
          <Icon className="h-5 w-5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold truncate">{server.name}</h3>
            {server.isPopular && (
              <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
            )}
          </div>
          <span className="text-xs text-muted-foreground capitalize">
            {MCP_CATEGORY_LABELS[server.category]}
          </span>
        </div>
      </div>

      {/* Description */}
      <p className="text-sm text-muted-foreground line-clamp-2">{server.description}</p>

      {/* Features */}
      <div className="space-y-1">
        <p className="text-xs font-medium text-muted-foreground">Key Features:</p>
        <ul className="text-xs text-muted-foreground space-y-0.5">
          {server.features.slice(0, 3).map((feature, i) => (
            <li key={i} className="truncate">
              • {feature}
            </li>
          ))}
        </ul>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 pt-2">
        {isAdded ? (
          <button
            disabled
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-green-500/10 text-green-600"
          >
            <Check className="h-4 w-4" />
            Added
          </button>
        ) : server.id === 'hydra-mcp' ? (
          <button
            disabled
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-primary/10 text-primary"
          >
            <Check className="h-4 w-4" />
            Built-in
          </button>
        ) : (
          <button
            onClick={onAdd}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Add
          </button>
        )}
        <a
          href={server.docsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="p-2 rounded-lg border hover:bg-muted transition-colors"
          title="View Documentation"
        >
          <ExternalLink className="h-4 w-4" />
        </a>
      </div>

      {/* Install Command */}
      {server.installCommand && (
        <div className="pt-2 border-t">
          <p className="text-xs text-muted-foreground mb-1">Install:</p>
          <code className="text-xs bg-muted px-2 py-1 rounded block truncate">
            {server.installCommand}
          </code>
        </div>
      )}
    </motion.div>
  );
}
