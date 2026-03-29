import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Boxes,
  MoreVertical,
  Eye,
  Server,
  Play,
  Square,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
} from 'lucide-react';
import { toast } from 'sonner';
import { useCreateCommand } from '@/api/commands';
import { useServices } from '@/api/services';
import { ServiceSummary } from '@/types/service';
import { ServiceFilterState } from './service-filters';
import { ROUTES, STATUS_COLORS, SERVICE_RUNTIME_LABELS } from '@/lib/constants';
import { cn, formatRelativeTime } from '@/lib/utils';
import { getErrorMessage } from '@/lib/api-client';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

interface ServiceListProps {
  filters: ServiceFilterState;
}

export function ServiceList({ filters }: ServiceListProps) {
  const [page, setPage] = useState(0);
  const limit = 20;

  const queryFilters = useMemo(() => {
    const f: Record<string, unknown> = { limit, offset: page * limit };
    if (filters.search) f.search = filters.search;
    if (filters.runtime) f.runtime = filters.runtime;
    if (filters.status) f.status = filters.status;
    if (filters.nodeId) f.nodeId = filters.nodeId;
    return f;
  }, [filters, page]);

  const { data, isLoading, error } = useServices(queryFilters);

  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  if (error) {
    return (
      <div className="rounded-xl border bg-card p-8 text-center">
        <p className="text-error">Failed to load services</p>
        <p className="mt-2 text-sm text-muted-foreground">Please try again later</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="rounded-xl border bg-card shadow-sm">
        <div className="divide-y">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex items-center gap-4 p-4">
              <div className="h-10 w-10 animate-pulse rounded-lg bg-muted" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-32 animate-pulse rounded bg-muted" />
                <div className="h-3 w-48 animate-pulse rounded bg-muted" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!data?.items?.length) {
    return (
      <div className="rounded-xl border bg-card p-8 text-center">
        <Boxes className="mx-auto h-12 w-12 text-muted-foreground" />
        <h3 className="mt-4 text-lg font-semibold">No services found</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          {filters.search || filters.runtime || filters.status || filters.nodeId
            ? 'Try adjusting your filters'
            : 'Services will appear here once nodes report them'}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          Showing {data.items.length} of {data.total} services
        </span>
      </div>

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="rounded-xl border bg-card shadow-sm"
      >
        <div className="divide-y">
          <AnimatePresence mode="popLayout">
            {data.items.map((service) => (
              <ServiceRow key={service.id} service={service} />
            ))}
          </AnimatePresence>
        </div>
      </motion.div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className={cn(
              'rounded-lg p-2 hover:bg-muted transition-colors',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm">
            Page {page + 1} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className={cn(
              'rounded-lg p-2 hover:bg-muted transition-colors',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}

type ServiceListItem = ServiceSummary & { id: string };

function ServiceRow({ service }: { service: ServiceListItem }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const createCommand = useCreateCommand();

  const statusColors = STATUS_COLORS[service.status as keyof typeof STATUS_COLORS] || STATUS_COLORS.stopped;
  const runtimeLabel = SERVICE_RUNTIME_LABELS[service.runtime] || service.runtime;

  const handleCommand = async (action: 'start' | 'stop' | 'restart') => {
    try {
      await createCommand.mutateAsync({
        registryId: `reg::service::${action}`,
        target: { nodeId: service.nodeId, serviceId: service.serviceId },
        parameters: {
          serviceId: service.serviceId,
          name: service.name,
          runtime: service.runtime,
        },
      });
      toast.success(`Command queued: ${action} ${service.displayName || service.name}`);
    } catch (err) {
      toast.error(getErrorMessage(err, `Failed to ${action} service`));
    } finally {
      setMenuOpen(false);
    }
  };

  return (
    <motion.div
      variants={staggerItemVariants}
      layout
      className="group flex items-center gap-4 p-4 hover:bg-muted/50 transition-colors"
    >
      <div className="rounded-lg bg-hydra-blue p-2.5">
        <Boxes className="h-5 w-5 text-white" />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <Link
            to={ROUTES.SERVICES + '/' + encodeURIComponent(service.id)}
            className="font-medium hover:text-primary transition-colors truncate"
          >
            {service.displayName || service.name}
          </Link>
          <span
            className={cn(
              'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
              statusColors.bg + '/10',
              statusColors.text
            )}
          >
            <span className={cn('h-1.5 w-1.5 rounded-full', statusColors.dot)} />
            {service.status}
          </span>
        </div>
        <div className="mt-1 flex items-center gap-3 text-sm text-muted-foreground">
          <span className="font-mono text-xs">{service.id}</span>
          {service.version && (
            <>
              <span>•</span>
              <span className="text-xs">v{service.version}</span>
            </>
          )}
        </div>
      </div>

      <div className="hidden md:block">
        <span className="rounded-full bg-muted px-3 py-1 text-sm">
          {runtimeLabel}
        </span>
      </div>

      <div className="hidden lg:block">
        <Link
          to={ROUTES.NODES + '/' + service.nodeId}
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <Server className="h-4 w-4" />
          {service.nodeId}
        </Link>
      </div>

      <div className="hidden md:block text-right text-sm text-muted-foreground">
        {service.lastSeen && formatRelativeTime(new Date(service.lastSeen))}
      </div>

      <div className="relative">
        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className="rounded-lg p-2 hover:bg-muted transition-colors opacity-0 group-hover:opacity-100"
        >
          <MoreVertical className="h-4 w-4" />
        </button>

        {menuOpen && (
          <>
            <div
              className="fixed inset-0 z-40"
              onClick={() => setMenuOpen(false)}
            />
            <div className="absolute right-0 top-full z-50 mt-1 w-40 rounded-lg border bg-popover p-1 shadow-lg">
              <Link
                to={ROUTES.SERVICES + '/' + encodeURIComponent(service.id)}
                className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent"
                onClick={() => setMenuOpen(false)}
              >
                <Eye className="h-4 w-4" />
                View Details
              </Link>
              <Link
                to={ROUTES.NODES + '/' + service.nodeId}
                className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent"
                onClick={() => setMenuOpen(false)}
              >
                <ExternalLink className="h-4 w-4" />
                View Node
              </Link>
              <div className="my-1 border-t" />
              <button
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-success hover:bg-success/10"
                onClick={() => handleCommand('start')}
              >
                <Play className="h-4 w-4" />
                Start
              </button>
              <button
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-warning hover:bg-warning/10"
                onClick={() => handleCommand('restart')}
              >
                <RefreshCw className="h-4 w-4" />
                Restart
              </button>
              <button
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-error hover:bg-error/10"
                onClick={() => handleCommand('stop')}
              >
                <Square className="h-4 w-4" />
                Stop
              </button>
            </div>
          </>
        )}
      </div>
    </motion.div>
  );
}
