import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Loader2 } from 'lucide-react';
import { useCreateNetwork } from '@/api/networks';
import { PageHeader } from '@/components/layout/page-header';
import { NetworkList } from '@/components/networks/network-list';
import { NetworkFilters, NetworkFilterState } from '@/components/networks/network-filters';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { cn } from '@/lib/utils';

export default function NetworksPage() {
  const [filters, setFilters] = useState<NetworkFilterState>({
    search: '',
    type: null,
  });
  const createNetworkMutation = useCreateNetwork();

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [networkId, setNetworkId] = useState('');
  const [name, setName] = useState('');
  const [type, setType] = useState<
    'physical' | 'virtual' | 'overlay' | 'vlan' | 'vxlan' | 'bridge' | 'tunnel'
  >('physical');
  const [cidr, setCidr] = useState('');
  const [cidrV6, setCidrV6] = useState('');
  const [gatewayV4, setGatewayV4] = useState('');
  const [gatewayV6, setGatewayV6] = useState('');
  const [vlanId, setVlanId] = useState('');
  const [parentNetworkId, setParentNetworkId] = useState('');
  const [routerNodeId, setRouterNodeId] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState('');
  const [dnsServers, setDnsServers] = useState('');
  const [dnsDomain, setDnsDomain] = useState('');
  const [dnsSearchDomains, setDnsSearchDomains] = useState('');

  const resetForm = () => {
    setNetworkId('');
    setName('');
    setType('physical');
    setCidr('');
    setCidrV6('');
    setGatewayV4('');
    setGatewayV6('');
    setVlanId('');
    setParentNetworkId('');
    setRouterNodeId('');
    setDescription('');
    setTags('');
    setDnsServers('');
    setDnsDomain('');
    setDnsSearchDomains('');
    setFormError(null);
  };

  const handleCreate = async () => {
    setFormError(null);
    if (!networkId.trim() || !name.trim()) {
      setFormError('Network ID and name are required.');
      return;
    }

    try {
      const vlanNumber = Number(vlanId);
      const vlanValue = Number.isFinite(vlanNumber) && vlanNumber > 0 ? vlanNumber : undefined;
      await createNetworkMutation.mutateAsync({
        networkId: networkId.trim(),
        name: name.trim(),
        type,
        cidr: cidr.trim() || undefined,
        cidrV6: cidrV6.trim() || undefined,
        gatewayV4: gatewayV4.trim() || undefined,
        gatewayV6: gatewayV6.trim() || undefined,
        vlanId: vlanValue,
        parentNetworkId: parentNetworkId.trim() || undefined,
        routerNodeId: routerNodeId.trim() || undefined,
        description: description.trim() || undefined,
        tags: tags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean),
        dns:
          dnsServers.trim() || dnsDomain.trim() || dnsSearchDomains.trim()
            ? {
                servers: dnsServers
                  .split(',')
                  .map((server) => server.trim())
                  .filter(Boolean),
                domain: dnsDomain.trim() || undefined,
                searchDomains: dnsSearchDomains
                  .split(',')
                  .map((domain) => domain.trim())
                  .filter(Boolean),
              }
            : undefined,
      });
      setShowCreateForm(false);
      resetForm();
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setFormError(error.response?.data?.detail || 'Failed to create network');
    }
  };

  return (
    <div className="p-6">
      <PageHeader
        title="Networks"
        description="View and manage your network segments"
        actions={
          <button
            onClick={() => {
              resetForm();
              setShowCreateForm(true);
            }}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
              'hover:bg-primary/90 transition-colors'
            )}
          >
            <Plus className="h-4 w-4" />
            Add Network
          </button>
        }
      />

      <AnimatePresence>
        {showCreateForm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
            onClick={() => setShowCreateForm(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-2xl rounded-xl border bg-card p-6 shadow-xl"
            >
              <h3 className="text-lg font-semibold">Create Network</h3>

              {formError && (
                <div className="mt-4 rounded-lg bg-error/10 p-3 text-sm text-error">
                  {formError}
                </div>
              )}

              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium mb-1.5">
                    Network ID <span className="text-error">*</span>
                  </label>
                  <input
                    type="text"
                    value={networkId}
                    onChange={(e) => setNetworkId(e.target.value)}
                    placeholder="e.g., prod-vlan-10"
                    className={cn(
                      'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                      'focus:outline-none focus:ring-2 focus:ring-ring'
                    )}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1.5">
                    Name <span className="text-error">*</span>
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., Production VLAN"
                    className={cn(
                      'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                      'focus:outline-none focus:ring-2 focus:ring-ring'
                    )}
                  />
                </div>
              </div>

              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium mb-1.5">Type</label>
                  <select
                    value={type}
                    onChange={(e) =>
                      setType(
                        e.target.value as
                          | 'physical'
                          | 'virtual'
                          | 'overlay'
                          | 'vlan'
                          | 'vxlan'
                          | 'bridge'
                          | 'tunnel'
                      )
                    }
                    className={cn(
                      'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                      'focus:outline-none focus:ring-2 focus:ring-ring'
                    )}
                  >
                    <option value="physical">Physical</option>
                    <option value="virtual">Virtual</option>
                    <option value="overlay">Overlay</option>
                    <option value="vlan">VLAN</option>
                    <option value="vxlan">VXLAN</option>
                    <option value="bridge">Bridge</option>
                    <option value="tunnel">Tunnel</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1.5">VLAN ID</label>
                  <input
                    type="number"
                    value={vlanId}
                    onChange={(e) => setVlanId(e.target.value)}
                    placeholder="Optional"
                    className={cn(
                      'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                      'focus:outline-none focus:ring-2 focus:ring-ring'
                    )}
                  />
                </div>
              </div>

              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium mb-1.5">CIDR (v4)</label>
                  <input
                    type="text"
                    value={cidr}
                    onChange={(e) => setCidr(e.target.value)}
                    placeholder="e.g., 10.0.10.0/24"
                    className={cn(
                      'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                      'focus:outline-none focus:ring-2 focus:ring-ring'
                    )}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1.5">CIDR (v6)</label>
                  <input
                    type="text"
                    value={cidrV6}
                    onChange={(e) => setCidrV6(e.target.value)}
                    placeholder="Optional IPv6 CIDR"
                    className={cn(
                      'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                      'focus:outline-none focus:ring-2 focus:ring-ring'
                    )}
                  />
                </div>
              </div>

              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium mb-1.5">Gateway v4</label>
                  <input
                    type="text"
                    value={gatewayV4}
                    onChange={(e) => setGatewayV4(e.target.value)}
                    placeholder="Optional"
                    className={cn(
                      'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                      'focus:outline-none focus:ring-2 focus:ring-ring'
                    )}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1.5">Gateway v6</label>
                  <input
                    type="text"
                    value={gatewayV6}
                    onChange={(e) => setGatewayV6(e.target.value)}
                    placeholder="Optional"
                    className={cn(
                      'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                      'focus:outline-none focus:ring-2 focus:ring-ring'
                    )}
                  />
                </div>
              </div>

              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium mb-1.5">Parent Network ID</label>
                  <input
                    type="text"
                    value={parentNetworkId}
                    onChange={(e) => setParentNetworkId(e.target.value)}
                    placeholder="Optional"
                    className={cn(
                      'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                      'focus:outline-none focus:ring-2 focus:ring-ring'
                    )}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1.5">Router Node ID</label>
                  <input
                    type="text"
                    value={routerNodeId}
                    onChange={(e) => setRouterNodeId(e.target.value)}
                    placeholder="Optional"
                    className={cn(
                      'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                      'focus:outline-none focus:ring-2 focus:ring-ring'
                    )}
                  />
                </div>
              </div>

              <div className="mt-4">
                <label className="block text-sm font-medium mb-1.5">Description</label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Optional description"
                  rows={3}
                  className={cn(
                    'w-full rounded-lg border bg-background px-3 py-2 text-sm resize-none',
                    'focus:outline-none focus:ring-2 focus:ring-ring'
                  )}
                />
              </div>

              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium mb-1.5">DNS Servers</label>
                  <input
                    type="text"
                    value={dnsServers}
                    onChange={(e) => setDnsServers(e.target.value)}
                    placeholder="Comma-separated IPs"
                    className={cn(
                      'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                      'focus:outline-none focus:ring-2 focus:ring-ring'
                    )}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1.5">DNS Domain</label>
                  <input
                    type="text"
                    value={dnsDomain}
                    onChange={(e) => setDnsDomain(e.target.value)}
                    placeholder="Optional"
                    className={cn(
                      'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                      'focus:outline-none focus:ring-2 focus:ring-ring'
                    )}
                  />
                </div>
              </div>

              <div className="mt-4">
                <label className="block text-sm font-medium mb-1.5">DNS Search Domains</label>
                <input
                  type="text"
                  value={dnsSearchDomains}
                  onChange={(e) => setDnsSearchDomains(e.target.value)}
                  placeholder="Comma-separated domains"
                  className={cn(
                    'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                    'focus:outline-none focus:ring-2 focus:ring-ring'
                  )}
                />
              </div>

              <div className="mt-4">
                <label className="block text-sm font-medium mb-1.5">Tags</label>
                <input
                  type="text"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  placeholder="Comma-separated tags"
                  className={cn(
                    'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                    'focus:outline-none focus:ring-2 focus:ring-ring'
                  )}
                />
              </div>

              <div className="mt-6 flex gap-2">
                <button
                  onClick={() => setShowCreateForm(false)}
                  className={cn(
                    'flex-1 rounded-lg border px-4 py-2 text-sm font-medium',
                    'hover:bg-muted transition-colors'
                  )}
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreate}
                  disabled={createNetworkMutation.isPending || !networkId.trim() || !name.trim()}
                  className={cn(
                    'flex-1 inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
                    'hover:bg-primary/90 transition-colors',
                    'disabled:opacity-50 disabled:cursor-not-allowed'
                  )}
                >
                  {createNetworkMutation.isPending && (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  )}
                  Create
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        <motion.div variants={staggerItemVariants}>
          <NetworkFilters filters={filters} onFiltersChange={setFilters} />
        </motion.div>

        <motion.div variants={staggerItemVariants}>
          <NetworkList filters={filters} />
        </motion.div>
      </motion.div>
    </div>
  );
}
