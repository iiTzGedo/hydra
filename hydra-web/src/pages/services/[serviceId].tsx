import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Boxes,
  Server,
  Tag,
  Globe,
  Container,
} from 'lucide-react';
import { useService } from '@/api/services';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES, STATUS_COLORS, SERVICE_RUNTIME_LABELS } from '@/lib/constants';
import { cn, formatDate, formatRelativeTime } from '@/lib/utils';
import { ServiceControlPanel } from '@/components/commands/service-control-panel';
import { CommandHistoryPanel } from '@/components/commands/command-history-panel';
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
  const exposurePorts = service.exposure?.ports ?? [];
  const exposureEndpoints = service.exposure?.endpoints ?? [];

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
        title={service.displayName || service.name}
        description={`${runtimeLabel} service on ${service.nodeId}`}
      />

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        <ServiceControlPanel
          nodeId={service.nodeId}
          serviceId={service.serviceId}
          serviceName={service.displayName || service.name}
          runtime={service.runtime}
        />

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
                    <span className="font-mono text-sm truncate max-w-[200px]">{service.serviceId}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Name</span>
                    <span className="font-medium">{service.name}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Runtime</span>
                    <span className="font-medium">{runtimeLabel}</span>
                  </div>
                  {service.version && (
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Version</span>
                      <span className="font-mono text-sm">v{service.version}</span>
                    </div>
                  )}
                  {service.image && (
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Image</span>
                      <span className="font-mono text-sm truncate max-w-[200px]">
                        {service.image}
                      </span>
                    </div>
                  )}
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
                    <span className="font-medium capitalize">{service.health?.status || 'N/A'}</span>
                  </div>
                  {service.health?.lastCheck && (
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Last Check</span>
                      <span className="text-sm">
                        {formatRelativeTime(new Date(service.health.lastCheck))}
                      </span>
                    </div>
                  )}
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
                    <span className="text-muted-foreground">First Seen</span>
                    <span className="text-sm">
                      {service.firstSeen ? formatDate(new Date(service.firstSeen)) : 'Unknown'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

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

                {(exposurePorts.length > 0 || exposureEndpoints.length > 0) && (
          <motion.div
            variants={staggerItemVariants}
            className="rounded-xl border bg-card p-6 shadow-sm"
          >
            <div className="flex items-center gap-2 mb-4">
              <Globe className="h-5 w-5" />
              <h3 className="text-lg font-semibold">Exposure</h3>
            </div>

            {exposurePorts.length > 0 && (
              <div className="rounded-lg border overflow-hidden mb-4">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="text-left px-4 py-2">Port</th>
                      <th className="text-left px-4 py-2">Host Port</th>
                      <th className="text-left px-4 py-2">Protocol</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {exposurePorts.map((port, i) => (
                      <tr key={i}>
                        <td className="px-4 py-2 font-mono">{port.port}</td>
                        <td className="px-4 py-2 font-mono">{port.hostPort ?? '-'}</td>
                        <td className="px-4 py-2 uppercase">{port.protocol || 'tcp'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {exposureEndpoints.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-2">Endpoints</h4>
                <div className="space-y-2">
                  {exposureEndpoints.map((endpoint, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm"
                    >
                      <span className="font-mono truncate">{endpoint.url}</span>
                      <span className="text-xs text-muted-foreground uppercase">
                        {endpoint.type}
                        {endpoint.internal ? ' • internal' : ''}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}

                {service.origin && (
          <motion.div
            variants={staggerItemVariants}
            className="rounded-xl border bg-card p-6 shadow-sm"
          >
            <div className="flex items-center gap-2 mb-4">
              <Container className="h-5 w-5" />
              <h3 className="text-lg font-semibold">Origin</h3>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-2">Native ID</h4>
                <div className="font-mono text-sm truncate">{service.origin.nativeId}</div>
              </div>
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-2">Discovered By</h4>
                <div className="text-sm">{service.origin.discoveredBy}</div>
              </div>
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-2">Collected At</h4>
                <div className="text-sm">
                  {formatDate(new Date(service.origin.collectedAt))}
                </div>
              </div>
            </div>
          </motion.div>
        )}

        <CommandHistoryPanel nodeId={service.nodeId} serviceId={service.serviceId} />
      </motion.div>
    </div>
  );
}
