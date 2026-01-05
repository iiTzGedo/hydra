import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Clock,
  Cpu,
  MemoryStick,
  HardDrive,
  Wifi,
  Package,
  Boxes,
  Copy,
  Check,
} from 'lucide-react';
import { useState } from 'react';
import { useNode } from '@/api/nodes';
import { useProfile } from '@/api/profiles';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES } from '@/lib/constants';
import { cn, formatDate, formatBytes } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

export default function ProfileDetailPage() {
  const { nodeId, profileId } = useParams<{ nodeId: string; profileId: string }>();
  const { data: node, isLoading: nodeLoading } = useNode(nodeId!);
  const { data: profile, isLoading: profileLoading } = useProfile(profileId!);

  const isLoading = nodeLoading || profileLoading;

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

  if (!node || !profile) {
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
          <Clock className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">Profile not found</h3>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <Link
        to={`${ROUTES.NODES}/${nodeId}/profiles`}
        className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Profile History
      </Link>

      <PageHeader
        title={`Profile ${profile.version}`}
        description={`Captured on ${formatDate(new Date(profile.submittedAt))}`}
      />

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        {/* Profile metadata */}
        <motion.div
          variants={staggerItemVariants}
          className="rounded-xl border bg-card p-6 shadow-sm"
        >
          <div className="grid gap-4 md:grid-cols-4">
            <div>
              <span className="text-sm text-muted-foreground">Version</span>
              <div className="mt-1 font-mono font-medium">{profile.version}</div>
            </div>
            <div>
              <span className="text-sm text-muted-foreground">Node</span>
              <div className="mt-1">
                <Link to={`${ROUTES.NODES}/${nodeId}`} className="text-primary hover:underline">
                  {nodeId}
                </Link>
              </div>
            </div>
            <div>
              <span className="text-sm text-muted-foreground">Submitted</span>
              <div className="mt-1">{formatDate(new Date(profile.submittedAt))}</div>
            </div>
            <div>
              <span className="text-sm text-muted-foreground">Sections</span>
              <div className="mt-1">{Object.keys(profile.sections || {}).length} sections</div>
            </div>
          </div>
        </motion.div>

        {/* Hardware section */}
        {profile.sections?.hardware && (
          <ProfileSection
            title="Hardware"
            icon={<Cpu className="h-5 w-5" />}
          >
            <div className="grid gap-4 md:grid-cols-2">
              {profile.sections.hardware.cpu && (
                <div className="rounded-lg border p-4">
                  <h4 className="font-medium mb-2">CPU</h4>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Model</span>
                      <span>{profile.sections.hardware.cpu.model}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Cores</span>
                      <span>{profile.sections.hardware.cpu.cores}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Threads</span>
                      <span>{profile.sections.hardware.cpu.threads}</span>
                    </div>
                  </div>
                </div>
              )}
              {profile.sections.hardware.memory && (
                <div className="rounded-lg border p-4">
                  <h4 className="font-medium mb-2">Memory</h4>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Total</span>
                      <span>{Math.round((profile.sections.hardware.memory.total || 0) / (1024 * 1024 * 1024))} GB</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </ProfileSection>
        )}

        {/* Storage section */}
        {profile.sections?.storage && (
          <ProfileSection
            title="Storage"
            icon={<HardDrive className="h-5 w-5" />}
          >
            {profile.sections.storage.disks?.length > 0 && (
              <div className="space-y-3">
                <h4 className="font-medium">Disks</h4>
                <div className="rounded-lg border overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="text-left px-4 py-2">Device</th>
                        <th className="text-left px-4 py-2">Model</th>
                        <th className="text-right px-4 py-2">Size</th>
                        <th className="text-left px-4 py-2">Type</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {profile.sections.storage.disks.map((disk: Record<string, unknown>, i: number) => (
                        <tr key={i}>
                          <td className="px-4 py-2 font-mono">{String(disk.device)}</td>
                          <td className="px-4 py-2">{String(disk.model || '-')}</td>
                          <td className="px-4 py-2 text-right">{formatBytes(Number(disk.size_bytes) || 0)}</td>
                          <td className="px-4 py-2">{String(disk.type || '-')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </ProfileSection>
        )}

        {/* Network section */}
        {profile.sections?.network && (
          <ProfileSection
            title="Network"
            icon={<Wifi className="h-5 w-5" />}
          >
            <div className="space-y-4">
              {profile.sections.network.hostname && (
                <div>
                  <span className="text-sm text-muted-foreground">Hostname</span>
                  <div className="font-mono">{profile.sections.network.hostname}</div>
                </div>
              )}

              {profile.sections.network.interfaces?.length > 0 && (
                <div className="space-y-3">
                  <h4 className="font-medium">Interfaces</h4>
                  <div className="grid gap-3 md:grid-cols-2">
                    {profile.sections.network.interfaces.map((iface: Record<string, unknown>, i: number) => (
                      <div key={i} className="rounded-lg border p-3">
                        <div className="flex items-center justify-between">
                          <span className="font-mono font-medium">{String(iface.name)}</span>
                          <span
                            className={cn(
                              'rounded-full px-2 py-0.5 text-xs',
                              iface.state === 'up' ? 'bg-success/10 text-success' : 'bg-muted text-muted-foreground'
                            )}
                          >
                            {String(iface.state)}
                          </span>
                        </div>
                        {iface.mac && (
                          <div className="mt-1 text-xs text-muted-foreground font-mono">
                            {String(iface.mac)}
                          </div>
                        )}
                        {Array.isArray(iface.addresses) && iface.addresses.length > 0 && (
                          <div className="mt-2 space-y-1">
                            {(iface.addresses as string[]).map((addr, j) => (
                              <div key={j} className="text-sm font-mono">
                                {addr}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </ProfileSection>
        )}

        {/* Software section */}
        {profile.sections?.software && (
          <ProfileSection
            title="Software"
            icon={<Package className="h-5 w-5" />}
          >
            {profile.sections.software.os && (
              <div className="rounded-lg border p-4">
                <h4 className="font-medium mb-2">Operating System</h4>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Name</span>
                    <span>{profile.sections.software.os.name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Version</span>
                    <span>{profile.sections.software.os.version}</span>
                  </div>
                  {profile.sections.software.os.kernel && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Kernel</span>
                      <span>{profile.sections.software.os.kernel}</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </ProfileSection>
        )}

        {/* Services section */}
        {profile.sections?.services && (
          <ProfileSection
            title="Services"
            icon={<Boxes className="h-5 w-5" />}
          >
            <div className="text-sm text-muted-foreground">
              {Array.isArray(profile.sections.services)
                ? `${profile.sections.services.length} services discovered`
                : 'Service data available'}
            </div>
          </ProfileSection>
        )}

        {/* Raw JSON */}
        <motion.div variants={staggerItemVariants}>
          <RawJsonSection data={profile} />
        </motion.div>
      </motion.div>
    </div>
  );
}

function ProfileSection({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <motion.div
      variants={staggerItemVariants}
      className="rounded-xl border bg-card p-6 shadow-sm"
    >
      <div className="flex items-center gap-2 mb-4">
        {icon}
        <h3 className="text-lg font-semibold">{title}</h3>
      </div>
      {children}
    </motion.div>
  );
}

function RawJsonSection({ data }: { data: unknown }) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const jsonString = JSON.stringify(data, null, 2);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
      <div className="flex items-center justify-between p-4 border-b">
        <h3 className="font-semibold">Raw JSON</h3>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm hover:bg-muted transition-colors"
          >
            {copied ? <Check className="h-4 w-4 text-success" /> : <Copy className="h-4 w-4" />}
            {copied ? 'Copied!' : 'Copy'}
          </button>
          <button
            onClick={() => setExpanded(!expanded)}
            className="rounded-lg px-3 py-1.5 text-sm hover:bg-muted transition-colors"
          >
            {expanded ? 'Collapse' : 'Expand'}
          </button>
        </div>
      </div>
      <pre
        className={cn(
          'p-4 text-xs font-mono bg-muted/30 overflow-auto',
          expanded ? 'max-h-[600px]' : 'max-h-[200px]'
        )}
      >
        {jsonString}
      </pre>
    </div>
  );
}
