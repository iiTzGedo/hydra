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
  History,
  GitBranch,
  Globe,
  FolderTree,
} from 'lucide-react';
import { useNode } from '@/api/nodes';
import { useNodeProfiles, useLatestProfile } from '@/api/profiles';
import { useNodeServices } from '@/api/services';
import { useSubgraph } from '@/api/topologies';
import { useGroups } from '@/api/groups';
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
  const { data: profiles } = useNodeProfiles(nodeId!, { limit: 5 });
  const { data: subgraph } = useSubgraph(nodeId!, { depth: 1, includeServices: true, includeNetworks: true });
  const { data: allGroups } = useGroups({ limit: 100 });

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

        {/* Profile History Timeline */}
        {profiles?.items && profiles.items.length > 0 && (
          <motion.div
            variants={staggerItemVariants}
            className="rounded-xl border bg-card p-6 shadow-sm"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="flex items-center gap-2 text-lg font-semibold">
                <History className="h-5 w-5" />
                Profile History
              </h3>
              <Link
                to={ROUTES.NODES + '/' + node.id + '/profiles'}
                className="text-sm text-primary hover:underline"
              >
                View all profiles
              </Link>
            </div>

            <div className="relative">
              {/* Timeline line */}
              <div className="absolute left-[11px] top-2 bottom-2 w-0.5 bg-border" />

              <div className="space-y-4">
                {profiles.items.map((profile, index) => (
                  <Link
                    key={profile.id || profile.profileId}
                    to={ROUTES.NODES + '/' + node.id + '/profiles/' + (profile.id || profile.profileId)}
                    className="relative flex items-start gap-4 pl-8 group"
                  >
                    {/* Timeline dot */}
                    <div
                      className={cn(
                        'absolute left-0 top-1 h-6 w-6 rounded-full border-2 flex items-center justify-center',
                        index === 0
                          ? 'border-primary bg-primary/10'
                          : 'border-muted-foreground/30 bg-background group-hover:border-primary/50'
                      )}
                    >
                      <span className={cn(
                        'h-2 w-2 rounded-full',
                        index === 0 ? 'bg-primary' : 'bg-muted-foreground/50'
                      )} />
                    </div>

                    <div className="flex-1 min-w-0 rounded-lg border p-3 group-hover:bg-muted/50 transition-colors">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-sm font-medium">{profile.version}</span>
                        <span className="text-xs text-muted-foreground">
                          {formatRelativeTime(new Date(profile.submittedAt))}
                        </span>
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">
                        {profile.sectionsIncluded?.length || 0} sections
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          </motion.div>
        )}

        {/* Networks */}
        {node.networkIds && node.networkIds.length > 0 && (
          <motion.div
            variants={staggerItemVariants}
            className="rounded-xl border bg-card p-6 shadow-sm"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="flex items-center gap-2 text-lg font-semibold">
                <Globe className="h-5 w-5" />
                Networks ({node.networkIds.length})
              </h3>
              <Link
                to={ROUTES.NETWORKS}
                className="text-sm text-primary hover:underline"
              >
                View all networks
              </Link>
            </div>

            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {node.networkIds.map((networkId) => {
                const membership = node.networks?.find(n => n.networkId === networkId);
                return (
                  <Link
                    key={networkId}
                    to={ROUTES.NETWORKS + '/' + networkId}
                    className="flex items-center gap-3 rounded-lg border p-3 hover:bg-muted/50 transition-colors"
                  >
                    <Network className="h-5 w-5 text-muted-foreground" />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{networkId}</div>
                      {membership && (
                        <div className="text-xs text-muted-foreground space-y-0.5">
                          {membership.ipAddress && <div>IP: {membership.ipAddress}</div>}
                          {membership.interfaceName && <div>Interface: {membership.interfaceName}</div>}
                        </div>
                      )}
                    </div>
                  </Link>
                );
              })}
            </div>
          </motion.div>
        )}

        {/* Groups containing this node */}
        {allGroups?.items && allGroups.items.length > 0 && (() => {
          // Filter groups that might contain this node by checking tags overlap
          const nodeGroups = allGroups.items.filter(group => {
            // Check if node tags overlap with group tags
            if (group.tags && node.tags) {
              if (node.tags.some(tag => group.tags.includes(tag))) {
                return true;
              }
            }
            // Groups with 'node' type that have members might contain this node
            if (group.types?.includes('node') && group.memberCount?.nodes > 0) {
              return true;
            }
            return false;
          });

          if (nodeGroups.length === 0) return null;

          return (
            <motion.div
              variants={staggerItemVariants}
              className="rounded-xl border bg-card p-6 shadow-sm"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="flex items-center gap-2 text-lg font-semibold">
                  <FolderTree className="h-5 w-5" />
                  Related Groups ({nodeGroups.length})
                </h3>
                <Link
                  to={ROUTES.GROUPS}
                  className="text-sm text-primary hover:underline"
                >
                  View all groups
                </Link>
              </div>

              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {nodeGroups.slice(0, 6).map((group) => (
                  <Link
                    key={group.id}
                    to={ROUTES.GROUPS + '/' + group.id}
                    className="flex items-center gap-3 rounded-lg border p-3 hover:bg-muted/50 transition-colors"
                  >
                    <FolderTree className="h-5 w-5 text-muted-foreground" />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{group.name}</div>
                      <div className="text-xs text-muted-foreground capitalize">
                        {group.types?.join(', ')}
                      </div>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {(group.memberCount?.nodes || 0) + (group.memberCount?.services || 0)} members
                    </span>
                  </Link>
                ))}
              </div>
            </motion.div>
          );
        })()}

        {/* Topology Subgraph */}
        {subgraph?.graph && (
          <motion.div
            variants={staggerItemVariants}
            className="rounded-xl border bg-card p-6 shadow-sm"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="flex items-center gap-2 text-lg font-semibold">
                <GitBranch className="h-5 w-5" />
                Node Connections
              </h3>
              <Link
                to={ROUTES.TOPOLOGY}
                className="text-sm text-primary hover:underline"
              >
                View full topology
              </Link>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              {/* Stats */}
              <div className="space-y-3">
                <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
                  <span className="text-muted-foreground">Connected Nodes</span>
                  <span className="font-medium">{subgraph.stats.nodeCount}</span>
                </div>
                <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
                  <span className="text-muted-foreground">Connections</span>
                  <span className="font-medium">{subgraph.stats.edgeCount}</span>
                </div>
                <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
                  <span className="text-muted-foreground">Services</span>
                  <span className="font-medium">{subgraph.stats.serviceCount}</span>
                </div>
                <div className="flex items-center justify-between rounded-lg bg-muted/50 px-3 py-2">
                  <span className="text-muted-foreground">Networks</span>
                  <span className="font-medium">{subgraph.stats.networkCount}</span>
                </div>
              </div>

              {/* Connected nodes list */}
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-2">Adjacent Nodes</h4>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {subgraph.graph.nodes
                    .filter(n => n.id !== nodeId)
                    .slice(0, 8)
                    .map((graphNode) => {
                      const NodeIcon = graphNode.data.class === 'networking'
                        ? Network
                        : graphNode.data.class === 'iot'
                          ? Cpu
                          : Server;
                      return (
                        <Link
                          key={graphNode.id}
                          to={ROUTES.NODES + '/' + (graphNode.data.nodeId || graphNode.id)}
                          className="flex items-center gap-2 rounded-lg border p-2 hover:bg-muted/50 transition-colors"
                        >
                          <NodeIcon className="h-4 w-4 text-muted-foreground" />
                          <span className="text-sm truncate">{graphNode.label}</span>
                          {graphNode.data.status && (
                            <span
                              className={cn(
                                'ml-auto h-2 w-2 rounded-full',
                                graphNode.data.status === 'active' ? 'bg-success' : 'bg-muted-foreground'
                              )}
                            />
                          )}
                        </Link>
                      );
                    })}
                </div>
              </div>
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
