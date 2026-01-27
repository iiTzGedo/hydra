import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  Server,
  Network,
  Boxes,
  FolderTree,
  History,
  MessageSquare,
  Settings,
  X,
  ChevronRight,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import { useNodes } from '@/api/nodes';
import { useServices } from '@/api/services';
import { useNetworks } from '@/api/networks';
import { useGroups } from '@/api/groups';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
}

interface SearchResult {
  id: string;
  type: 'node' | 'service' | 'network' | 'group' | 'page';
  title: string;
  subtitle?: string;
  icon: typeof Server;
  route: string;
}

const quickActions: SearchResult[] = [
  { id: 'dashboard', type: 'page', title: 'Dashboard', subtitle: 'Overview', icon: Sparkles, route: ROUTES.DASHBOARD },
  { id: 'nodes', type: 'page', title: 'Nodes', subtitle: 'All nodes', icon: Server, route: ROUTES.NODES },
  { id: 'services', type: 'page', title: 'Services', subtitle: 'All services', icon: Boxes, route: ROUTES.SERVICES },
  { id: 'networks', type: 'page', title: 'Networks', subtitle: 'All networks', icon: Network, route: ROUTES.NETWORKS },
  { id: 'groups', type: 'page', title: 'Groups', subtitle: 'All groups', icon: FolderTree, route: ROUTES.GROUPS },
  { id: 'topology', type: 'page', title: 'Topology', subtitle: 'Infrastructure graph', icon: Network, route: ROUTES.TOPOLOGY },
  { id: 'timemachine', type: 'page', title: 'Time Machine', subtitle: 'Historical state', icon: History, route: ROUTES.TIME_MACHINE },
  { id: 'chat', type: 'page', title: 'AI Chat', subtitle: 'MCP assistant', icon: MessageSquare, route: ROUTES.CHAT },
  { id: 'admin', type: 'page', title: 'Admin', subtitle: 'Settings & users', icon: Settings, route: ROUTES.ADMIN },
];

export function CommandPalette({ isOpen, onClose }: CommandPaletteProps) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: nodesData, isLoading: nodesLoading } = useNodes({ limit: 10 });
  const { data: servicesData, isLoading: servicesLoading } = useServices({ limit: 10 });
  const { data: networksData, isLoading: networksLoading } = useNetworks({ limit: 10 });
  const { data: groupsData, isLoading: groupsLoading } = useGroups({ limit: 10 });

  const isLoading = nodesLoading || servicesLoading || networksLoading || groupsLoading;

  const searchResults = useCallback((): SearchResult[] => {
    const lowerQuery = query.toLowerCase().trim();

    if (!lowerQuery) {
      return quickActions;
    }

    const results: SearchResult[] = [];

    quickActions.forEach((action) => {
      if (action.title.toLowerCase().includes(lowerQuery) ||
          action.subtitle?.toLowerCase().includes(lowerQuery)) {
        results.push(action);
      }
    });

    nodesData?.items.forEach((node) => {
      if (node.displayName.toLowerCase().includes(lowerQuery) ||
          node.nodeId.toLowerCase().includes(lowerQuery) ||
          node.tags?.some(t => t.toLowerCase().includes(lowerQuery))) {
        results.push({
          id: `node-${node.nodeId}`,
          type: 'node',
          title: node.displayName,
          subtitle: `${node.class} • ${node.kind || node.type}`,
          icon: Server,
          route: `${ROUTES.NODES}/${node.nodeId}`,
        });
      }
    });

    servicesData?.items.forEach((service) => {
      if (service.name.toLowerCase().includes(lowerQuery) ||
          service.id.toLowerCase().includes(lowerQuery)) {
        results.push({
          id: `service-${service.id}`,
          type: 'service',
          title: service.name,
          subtitle: `${service.runtime} • ${service.status}`,
          icon: Boxes,
          route: `${ROUTES.SERVICES}/${encodeURIComponent(service.id)}`,
        });
      }
    });

    networksData?.items.forEach((network) => {
      if (network.name.toLowerCase().includes(lowerQuery) ||
          network.networkId.toLowerCase().includes(lowerQuery) ||
          network.cidr?.toLowerCase().includes(lowerQuery)) {
        results.push({
          id: `network-${network.networkId}`,
          type: 'network',
          title: network.name,
          subtitle: network.cidr || network.type,
          icon: Network,
          route: `${ROUTES.NETWORKS}/${network.networkId}`,
        });
      }
    });

    groupsData?.items.forEach((group) => {
      if (group.name.toLowerCase().includes(lowerQuery) ||
          group.id.toLowerCase().includes(lowerQuery)) {
        results.push({
          id: `group-${group.id}`,
          type: 'group',
          title: group.name,
          subtitle: `${(group.memberCount?.nodes || 0) + (group.memberCount?.services || 0)} members`,
          icon: FolderTree,
          route: `${ROUTES.GROUPS}/${group.id}`,
        });
      }
    });

    return results.slice(0, 12);
  }, [query, nodesData, servicesData, networksData, groupsData]);

  const results = searchResults();

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      inputRef.current?.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex((i) => (i + 1) % results.length);
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex((i) => (i - 1 + results.length) % results.length);
          break;
        case 'Enter':
          e.preventDefault();
          if (results[selectedIndex]) {
            handleSelect(results[selectedIndex]);
          }
          break;
        case 'Escape':
          e.preventDefault();
          onClose();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, results, selectedIndex, onClose]);

  const handleSelect = (result: SearchResult) => {
    navigate(result.route);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.1 }}
          className="fixed left-1/2 top-[20%] z-50 w-full max-w-lg -translate-x-1/2"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="rounded-xl border bg-popover shadow-2xl overflow-hidden">
            <div className="flex items-center gap-3 border-b px-4 py-3">
              <Search className="h-5 w-5 text-muted-foreground" />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setSelectedIndex(0);
                }}
                placeholder="Search nodes, services, networks..."
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              />
              {query && (
                <button
                  onClick={() => setQuery('')}
                  className="rounded p-1 hover:bg-muted"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
              <kbd className="hidden sm:inline-flex h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-xs">
                ESC
              </kbd>
            </div>

            <div className="max-h-80 overflow-auto p-2">
              {isLoading && query ? (
                <div className="flex items-center justify-center py-8 text-muted-foreground">
                  <Loader2 className="h-5 w-5 animate-spin mr-2" />
                  <span className="text-sm">Searching...</span>
                </div>
              ) : results.length === 0 ? (
                <div className="py-8 text-center text-muted-foreground">
                  <Search className="mx-auto h-8 w-8 mb-2 opacity-50" />
                  <p className="text-sm">No results found for "{query}"</p>
                </div>
              ) : (
                <div className="space-y-1">
                  {!query && (
                    <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
                      Quick Actions
                    </div>
                  )}
                  {query && (
                    <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
                      Results ({results.length})
                    </div>
                  )}
                  {results.map((result, index) => (
                    <button
                      key={result.id}
                      onClick={() => handleSelect(result)}
                      className={cn(
                        'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left',
                        'hover:bg-accent',
                        selectedIndex === index && 'bg-accent'
                      )}
                    >
                      <div className={cn(
                        'flex h-8 w-8 items-center justify-center rounded-lg',
                        result.type === 'node' && 'bg-compute/10 text-compute',
                        result.type === 'service' && 'bg-success/10 text-success',
                        result.type === 'network' && 'bg-network/10 text-network',
                        result.type === 'group' && 'bg-warning/10 text-warning',
                        result.type === 'page' && 'bg-muted text-muted-foreground'
                      )}>
                        <result.icon className="h-4 w-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium truncate">{result.title}</div>
                        {result.subtitle && (
                          <div className="text-xs text-muted-foreground truncate">
                            {result.subtitle}
                          </div>
                        )}
                      </div>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="border-t px-4 py-2 flex items-center gap-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <kbd className="rounded border bg-muted px-1">↑</kbd>
                <kbd className="rounded border bg-muted px-1">↓</kbd>
                to navigate
              </span>
              <span className="flex items-center gap-1">
                <kbd className="rounded border bg-muted px-1">↵</kbd>
                to select
              </span>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

export function useCommandPalette() {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsOpen((open) => !open);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return {
    isOpen,
    open: () => setIsOpen(true),
    close: () => setIsOpen(false),
    toggle: () => setIsOpen((open) => !open),
  };
}
