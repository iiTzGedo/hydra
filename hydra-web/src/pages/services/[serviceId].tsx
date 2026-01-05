import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Boxes,
  Server,
  Play,
  Square,
  RefreshCw,
  Clock,
  Tag,
  Globe,
  Container,
  ExternalLink,
} from 'lucide-react';
import { useService } from '@/api/services';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES, STATUS_COLORS, SERVICE_RUNTIME_LABELS } from '@/lib/constants';
import { cn, formatDate, formatRelativeTime } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

export default function ServiceDetailPage() {
  const { serviceId } = useParams<{ serviceId: string }>();
  const decodedServiceId = decodeURIComponent(serviceId || '');
  const { data: service, isLoading, error } = useService(decodedServiceId);

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="h-8 w-48 animate-pulse rounded bg-muted mb-6" />
        <div className="space-y-6">
          <div className="h-32 animate-pulse rounded-xl bg-muted" />
          <div className="h-64 animate-pulse rounded-xl bg-muted" />
        </div>
      </div>
    );
  }

  if (error || !service) {
    return (
      <div className="p-6">
        <Link
          to={ROUTES.SERVICES}
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Services
        </Link>
        <div className="rounded-xl border bg-card p-8 text-center">
          <Boxes className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">Service not found</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            The service "{decodedServiceId}" could not be found
          </p>
        </div>
      </div>
    );
  }

  const statusColors = STATUS_COLORS[service.status] || STATUS_COLORS.stopped;
  const runtimeLabel = SERVICE_RUNTIME_LABELS[service.runtime] || service.runtime;

  return (
    <div className="p-6">
      <Link
        to={ROUTES.SERVICES}
        className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Services
      </Link>

      <PageHeader
        title={service.name}
        description={`${runtimeLabel} service on ${service.nodeId}`}
        actions={
          <div className="flex items-center gap-2">
            <button
              className={cn(
                'inline-flex items-center gap-2 rounded-lg border border-success/50 px-4 py-2 text-sm font-medium text-success',
                'hover:bg-success/10 transition-colors'
              )}
            >
              <Play className="h-4 w-4" />
              Start
            </button>
            <button
              className={cn(
                'inline-flex items-center gap-2 rounded-lg border border-warning/50 px-4 py-2 text-sm font-medium text-warning',
                'hover:bg-warning/10 transition-colors'
              )}
            >
              <RefreshCw className="h-4 w-4" />
              Restart
            </button>
            <button
              className={cn(
                'inline-flex items-center gap-2 rounded-lg border border-error/50 px-4 py-2 text-sm font-medium text-error',
                'hover:bg-error/10 transition-colors'
              )}
            >
              <Square className="h-4 w-4" />
              Stop
            </button>
          </div>
        }
      />

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        {/* Overview card */}
        <motion.div
          variants={staggerItemVariants}
          className="rounded-xl border bg-card p-6 shadow-sm"
        >
          <div className="flex items-start gap-6">
            <div className="rounded-xl bg-hydra-blue p-4">
              <Boxes className="h-8 w-8 text-white" />
            </div>

            <div className="flex-1 grid gap-6 md:grid-cols-3">
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-3">Service Info</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">ID</span>
                    <span className="font-mono text-sm truncate max-w-[200px]">{service.id}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Name</span>
                    <span className="font-medium">{service.name}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Runtime</span>
                    <span className="font-medium">{runtimeLabel}</span>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-3">Status</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Status</span>
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
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Health</span>
                    <span className="font-medium capitalize">{service.health || 'N/A'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Last Seen</span>
                    <span className="text-sm">
                      {service.lastSeen
                        ? formatRelativeTime(new Date(service.lastSeen))
                        : 'Never'}
                    </span>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-3">Host</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Node</span>
                    <Link
                      to={ROUTES.NODES + '/' + service.nodeId}
                      className="flex items-center gap-1 text-primary hover:underline"
                    >
                      <Server className="h-4 w-4" />
                      {service.nodeId}
                    </Link>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Created</span>
                    <span className="text-sm">
                      {service.createdAt ? formatDate(new Date(service.createdAt)) : 'Unknown'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Tags */}
          {service.tags && service.tags.length > 0 && (
            <div className="mt-6 pt-6 border-t">
              <h4 className="flex items-center gap-2 text-sm font-medium text-muted-foreground mb-3">
                <Tag className="h-4 w-4" />
                Tags
              </h4>
              <div className="flex flex-wrap gap-2">
                {service.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full bg-muted px-3 py-1 text-sm"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}
        </motion.div>

        {/* Ports */}
        {service.ports && service.ports.length > 0 && (
          <motion.div
            variants={staggerItemVariants}
            className="rounded-xl border bg-card p-6 shadow-sm"
          >
            <div className="flex items-center gap-2 mb-4">
              <Globe className="h-5 w-5" />
              <h3 className="text-lg font-semibold">Exposed Ports</h3>
            </div>

            {service.portMappings && service.portMappings.length > 0 ? (
              <div className="rounded-lg border overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="text-left px-4 py-2">Internal</th>
                      <th className="text-left px-4 py-2">External</th>
                      <th className="text-left px-4 py-2">Protocol</th>
                      <th className="text-left px-4 py-2">Host</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {service.portMappings.map((port, i) => (
                      <tr key={i}>
                        <td className="px-4 py-2 font-mono">{port.internal}</td>
                        <td className="px-4 py-2 font-mono">{port.external || '-'}</td>
                        <td className="px-4 py-2 uppercase">{port.protocol}</td>
                        <td className="px-4 py-2 font-mono">{port.host || '0.0.0.0'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {service.ports.map((port, i) => (
                  <span
                    key={i}
                    className="rounded-lg bg-muted px-3 py-1 font-mono text-sm"
                  >
                    {port}
                  </span>
                ))}
              </div>
            )}
          </motion.div>
        )}

        {/* Container details (for Docker/Podman) */}
        {(service.runtime === 'docker' || service.runtime === 'podman') && service.metadata && (
          <motion.div
            variants={staggerItemVariants}
            className="rounded-xl border bg-card p-6 shadow-sm"
          >
            <div className="flex items-center gap-2 mb-4">
              <Container className="h-5 w-5" />
              <h3 className="text-lg font-semibold">Container Details</h3>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              {service.metadata.image && (
                <div className="rounded-lg border p-4">
                  <h4 className="text-sm font-medium text-muted-foreground mb-2">Image</h4>
                  <div className="font-mono text-sm truncate">{String(service.metadata.image)}</div>
                </div>
              )}
              {service.metadata.containerId && (
                <div className="rounded-lg border p-4">
                  <h4 className="text-sm font-medium text-muted-foreground mb-2">Container ID</h4>
                  <div className="font-mono text-sm truncate">{String(service.metadata.containerId)}</div>
                </div>
              )}
            </div>

            {/* Environment variables */}
            {service.metadata.environment && Object.keys(service.metadata.environment).length > 0 && (
              <div className="mt-4">
                <h4 className="text-sm font-medium text-muted-foreground mb-2">Environment</h4>
                <div className="rounded-lg bg-muted/50 p-3 max-h-48 overflow-auto">
                  {Object.entries(service.metadata.environment as Record<string, string>).map(([key, value]) => (
                    <div key={key} className="flex gap-2 text-sm font-mono">
                      <span className="text-muted-foreground">{key}=</span>
                      <span className="truncate">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Volumes */}
            {service.metadata.volumes && Array.isArray(service.metadata.volumes) && service.metadata.volumes.length > 0 && (
              <div className="mt-4">
                <h4 className="text-sm font-medium text-muted-foreground mb-2">Volumes</h4>
                <div className="space-y-2">
                  {(service.metadata.volumes as string[]).map((volume, i) => (
                    <div key={i} className="rounded-lg border p-2 text-sm font-mono">
                      {volume}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}

        {/* Labels */}
        {service.labels && Object.keys(service.labels).length > 0 && (
          <motion.div
            variants={staggerItemVariants}
            className="rounded-xl border bg-card p-6 shadow-sm"
          >
            <h3 className="text-lg font-semibold mb-4">Labels</h3>
            <div className="grid gap-2 md:grid-cols-2">
              {Object.entries(service.labels).map(([key, value]) => (
                <div key={key} className="flex items-start gap-2 rounded-lg bg-muted/50 px-3 py-2">
                  <span className="text-muted-foreground truncate flex-shrink-0">{key}</span>
                  <span className="font-mono text-sm truncate">{value}</span>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}
