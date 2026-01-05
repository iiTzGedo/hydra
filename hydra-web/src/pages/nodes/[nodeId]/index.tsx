import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Server,
  Network,
  Cpu,
  ArrowLeft,
  Edit,
  Archive,
  RefreshCw,
  Clock,
  Tag,
  Info,
  HardDrive,
  Wifi,
  Package,
  Boxes,
} from 'lucide-react';
import { useNode } from '@/api/nodes';
import { useNodeProfiles, useLatestProfile } from '@/api/profiles';
import { useNodeServices } from '@/api/services';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES, NODE_CLASS_COLORS, NODE_KIND_LABELS, STATUS_COLORS } from '@/lib/constants';
import { cn, formatDate, formatRelativeTime } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

const classIcons = {
  compute: Server,
  networking: Network,
  iot: Cpu,
};

export default function NodeDetailPage() {
  const { nodeId } = useParams<{ nodeId: string }>();
  const { data: node, isLoading, error } = useNode(nodeId!);
  const { data: latestProfile } = useLatestProfile(nodeId!);
  const { data: services } = useNodeServices(nodeId!);

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

  if (error || !node) {
    return (
      <div className="p-6">
        <Link
          to={ROUTES.NODES}
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Nodes
        </Link>
        <div className="rounded-xl border bg-card p-8 text-center">
          <Server className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">Node not found</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            The node "{nodeId}" could not be found
          </p>
        </div>
      </div>
    );
  }

  const Icon = classIcons[node.class] || Server;
  const colors = NODE_CLASS_COLORS[node.class];
  const statusColors = STATUS_COLORS[node.status] || STATUS_COLORS.inactive;
  const kindLabel = NODE_KIND_LABELS[node.kind as keyof typeof NODE_KIND_LABELS] || node.kind;

  return (
    <div className="p-6">
      <Link
        to={ROUTES.NODES}
        className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Nodes
      </Link>

      <PageHeader
        title={node.id}
        description={node.displayName || `${node.class} node - ${kindLabel}`}
        actions={
          <div className="flex items-center gap-2">
            <Link
              to={ROUTES.NODES + '/' + node.id + '/profiles'}
              className={cn(
                'inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium',
                'hover:bg-muted transition-colors'
              )}
            >
              <RefreshCw className="h-4 w-4" />
              Profiles
            </Link>
            <button
              className={cn(
                'inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium',
                'hover:bg-muted transition-colors'
              )}
            >
              <Edit className="h-4 w-4" />
              Edit
            </button>
            <button
              className={cn(
                'inline-flex items-center gap-2 rounded-lg border border-error/50 px-4 py-2 text-sm font-medium text-error',
                'hover:bg-error/10 transition-colors'
              )}
            >
              <Archive className="h-4 w-4" />
              Archive
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
            <div className={cn('rounded-xl p-4', colors?.bg || 'bg-muted')}>
              <Icon className="h-8 w-8 text-white" />
            </div>

            <div className="flex-1 grid gap-6 md:grid-cols-3">
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-3">Classification</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Class</span>
                    <span className="font-medium capitalize">{node.class}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Type</span>
                    <span className="font-medium capitalize">{node.type}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Kind</span>
                    <span className="font-medium">{kindLabel}</span>
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
                      {node.status}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Profile Version</span>
                    <span className="font-mono text-sm">{node.profileVersion || '-'}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Last Profiled</span>
                    <span className="text-sm">
                      {node.lastProfileAt
                        ? formatRelativeTime(new Date(node.lastProfileAt))
                        : 'Never'}
                    </span>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-3">Timestamps</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Registered</span>
                    <span className="text-sm">{formatDate(new Date(node.registeredAt))}</span>
                  </div>
                  {node.updatedAt && (
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Updated</span>
                      <span className="text-sm">{formatDate(new Date(node.updatedAt))}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Tags */}
          {node.tags && node.tags.length > 0 && (
            <div className="mt-6 pt-6 border-t">
              <h4 className="flex items-center gap-2 text-sm font-medium text-muted-foreground mb-3">
                <Tag className="h-4 w-4" />
                Tags
              </h4>
              <div className="flex flex-wrap gap-2">
                {node.tags.map((tag) => (
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

          {/* Custom metadata */}
          {node.metadata && Object.keys(node.metadata).length > 0 && (
            <div className="mt-6 pt-6 border-t">
              <h4 className="flex items-center gap-2 text-sm font-medium text-muted-foreground mb-3">
                <Info className="h-4 w-4" />
                Metadata
              </h4>
              <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
                {Object.entries(node.metadata).map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
                    <span className="text-muted-foreground">{key}</span>
                    <span className="font-mono text-sm">{String(value)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </motion.div>

        {/* Profile Summary */}
        {latestProfile && (
          <motion.div
            variants={staggerItemVariants}
            className="rounded-xl border bg-card p-6 shadow-sm"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Latest Profile</h3>
              <Link
                to={ROUTES.NODES + '/' + node.id + '/profiles/' + latestProfile.id}
                className="text-sm text-primary hover:underline"
              >
                View full profile
              </Link>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {latestProfile.sections?.hardware && (
                <ProfileSection
                  icon={<Cpu className="h-4 w-4" />}
                  title="Hardware"
                  items={[
                    latestProfile.sections.hardware.cpu?.model,
                    `${Math.round((latestProfile.sections.hardware.memory?.total || 0) / (1024 * 1024 * 1024))} GB RAM`,
                  ].filter(Boolean) as string[]}
                />
              )}
              {latestProfile.sections?.storage && (
                <ProfileSection
                  icon={<HardDrive className="h-4 w-4" />}
                  title="Storage"
                  items={[
                    `${latestProfile.sections.storage.disks?.length || 0} disks`,
                    `${latestProfile.sections.storage.filesystems?.length || 0} filesystems`,
                  ]}
                />
              )}
              {latestProfile.sections?.network && (
                <ProfileSection
                  icon={<Wifi className="h-4 w-4" />}
                  title="Network"
                  items={[
                    `${latestProfile.sections.network.interfaces?.length || 0} interfaces`,
                    latestProfile.sections.network.hostname,
                  ].filter(Boolean) as string[]}
                />
              )}
              {latestProfile.sections?.software && (
                <ProfileSection
                  icon={<Package className="h-4 w-4" />}
                  title="Software"
                  items={[
                    latestProfile.sections.software.os?.name,
                    latestProfile.sections.software.os?.version,
                  ].filter(Boolean) as string[]}
                />
              )}
            </div>
          </motion.div>
        )}

        {/* Services */}
        {services?.items && services.items.length > 0 && (
          <motion.div
            variants={staggerItemVariants}
            className="rounded-xl border bg-card p-6 shadow-sm"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Services ({services.total})</h3>
              <Link
                to={ROUTES.SERVICES + '?node=' + node.id}
                className="text-sm text-primary hover:underline"
              >
                View all services
              </Link>
            </div>

            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {services.items.slice(0, 6).map((service) => (
                <Link
                  key={service.id}
                  to={ROUTES.SERVICES + '/' + encodeURIComponent(service.id)}
                  className="flex items-center gap-3 rounded-lg border p-3 hover:bg-muted/50 transition-colors"
                >
                  <Boxes className="h-5 w-5 text-muted-foreground" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">{service.name}</div>
                    <div className="text-xs text-muted-foreground">{service.runtime}</div>
                  </div>
                  <span
                    className={cn(
                      'h-2 w-2 rounded-full',
                      service.status === 'running' ? 'bg-success' : 'bg-muted-foreground'
                    )}
                  />
                </Link>
              ))}
            </div>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}

function ProfileSection({
  icon,
  title,
  items,
}: {
  icon: React.ReactNode;
  title: string;
  items: string[];
}) {
  return (
    <div className="rounded-lg border p-4">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="font-medium">{title}</span>
      </div>
      <div className="space-y-1">
        {items.map((item, i) => (
          <div key={i} className="text-sm text-muted-foreground truncate">
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}
