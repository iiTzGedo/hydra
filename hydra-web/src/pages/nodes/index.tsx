import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Copy, Check, Loader2 } from 'lucide-react';
import { useRegisterNode } from '@/api/nodes';
import { PageHeader } from '@/components/layout/page-header';
import { NodeList } from '@/components/nodes/node-list';
import { NodeFilters, NodeFilterState } from '@/components/nodes/node-filters';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { cn } from '@/lib/utils';
import type { NodeKind } from '@/types/node';

export default function NodesPage() {
  const [filters, setFilters] = useState<NodeFilterState>({
    search: '',
    class: null,
    type: null,
    kind: null,
    status: null,
  });
  const registerMutation = useRegisterNode();

  const [showRegisterForm, setShowRegisterForm] = useState(false);
  const [newApiKey, setNewApiKey] = useState<string | null>(null);
  const [registeredNodeId, setRegisteredNodeId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [nodeId, setNodeId] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [nodeClass, setNodeClass] = useState<'compute' | 'networking' | 'iot'>('compute');
  const [nodeType, setNodeType] = useState<'physical' | 'logical'>('physical');
  const [kind, setKind] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState('');
  const [parentNodeId, setParentNodeId] = useState('');

  const resetForm = () => {
    setNodeId('');
    setDisplayName('');
    setNodeClass('compute');
    setNodeType('physical');
    setKind('');
    setDescription('');
    setTags('');
    setParentNodeId('');
    setFormError(null);
  };

  const handleCopy = async () => {
    if (newApiKey) {
      await navigator.clipboard.writeText(newApiKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleRegister = async () => {
    setFormError(null);
    if (!nodeId.trim() || !displayName.trim()) {
      setFormError('Node ID and display name are required.');
      return;
    }

    try {
      const result = await registerMutation.mutateAsync({
        nodeId: nodeId.trim(),
        class: nodeClass,
        type: nodeType,
        kind: (kind.trim() || undefined) as NodeKind | undefined,
        displayName: displayName.trim(),
        description: description.trim() || undefined,
        tags: tags
          .split(',')
          .map((tag) => tag.trim())
          .filter(Boolean),
        parentNodeId: parentNodeId.trim() || undefined,
      });
      setNewApiKey(result.apiKey);
      setRegisteredNodeId(result.nodeId);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setFormError(error.response?.data?.detail || 'Failed to register node');
    }
  };

  return (
    <div className="p-6">
      <PageHeader
        title="Nodes"
        description="Manage your infrastructure nodes"
        actions={
          <button
            onClick={() => {
              resetForm();
              setNewApiKey(null);
              setRegisteredNodeId(null);
              setShowRegisterForm(true);
            }}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
              'hover:bg-primary/90 transition-colors'
            )}
          >
            <Plus className="h-4 w-4" />
            Add Node
          </button>
        }
      />

      <AnimatePresence>
        {showRegisterForm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
            onClick={() => {
              setShowRegisterForm(false);
              setNewApiKey(null);
              setRegisteredNodeId(null);
            }}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-lg rounded-xl border bg-card p-6 shadow-xl"
            >
              {newApiKey ? (
                <div className="text-center">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
                    <Check className="h-6 w-6 text-success" />
                  </div>
                  <h3 className="mt-4 text-lg font-semibold">Node Registered</h3>
                  <p className="mt-2 text-sm text-muted-foreground">
                    API key for {registeredNodeId}. Copy this key now. It won&apos;t be shown again.
                  </p>
                  <div className="mt-4 flex items-center gap-2 rounded-lg bg-muted p-3">
                    <code className="flex-1 text-sm font-mono break-all">{newApiKey}</code>
                    <button
                      onClick={handleCopy}
                      className="rounded-lg p-2 hover:bg-background transition-colors"
                    >
                      {copied ? (
                        <Check className="h-4 w-4 text-success" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                  <button
                    onClick={() => {
                      setShowRegisterForm(false);
                      setNewApiKey(null);
                      setRegisteredNodeId(null);
                    }}
                    className={cn(
                      'mt-6 w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
                      'hover:bg-primary/90 transition-colors'
                    )}
                  >
                    Done
                  </button>
                </div>
              ) : (
                <>
                  <h3 className="text-lg font-semibold">Register Node</h3>

                  {formError && (
                    <div className="mt-4 rounded-lg bg-error/10 p-3 text-sm text-error">
                      {formError}
                    </div>
                  )}

                  <div className="mt-4 space-y-4">
                    <div>
                      <label className="block text-sm font-medium mb-1.5">
                        Node ID <span className="text-error">*</span>
                      </label>
                      <input
                        type="text"
                        value={nodeId}
                        onChange={(e) => setNodeId(e.target.value)}
                        placeholder="e.g., core-router-01"
                        className={cn(
                          'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                          'focus:outline-none focus:ring-2 focus:ring-ring'
                        )}
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium mb-1.5">
                        Display Name <span className="text-error">*</span>
                      </label>
                      <input
                        type="text"
                        value={displayName}
                        onChange={(e) => setDisplayName(e.target.value)}
                        placeholder="e.g., Core Router"
                        className={cn(
                          'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                          'focus:outline-none focus:ring-2 focus:ring-ring'
                        )}
                      />
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                      <div>
                        <label className="block text-sm font-medium mb-1.5">Class</label>
                        <select
                          value={nodeClass}
                          onChange={(e) =>
                            setNodeClass(e.target.value as 'compute' | 'networking' | 'iot')
                          }
                          className={cn(
                            'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                            'focus:outline-none focus:ring-2 focus:ring-ring'
                          )}
                        >
                          <option value="compute">Compute</option>
                          <option value="networking">Networking</option>
                          <option value="iot">IoT</option>
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-1.5">Type</label>
                        <select
                          value={nodeType}
                          onChange={(e) =>
                            setNodeType(e.target.value as 'physical' | 'logical')
                          }
                          className={cn(
                            'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                            'focus:outline-none focus:ring-2 focus:ring-ring'
                          )}
                        >
                          <option value="physical">Physical</option>
                          <option value="logical">Logical</option>
                        </select>
                      </div>
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                      <div>
                        <label className="block text-sm font-medium mb-1.5">Kind</label>
                        <input
                          type="text"
                          value={kind}
                          onChange={(e) => setKind(e.target.value)}
                          placeholder="e.g., router, vm, sensor"
                          className={cn(
                            'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                            'focus:outline-none focus:ring-2 focus:ring-ring'
                          )}
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-1.5">Parent Node ID</label>
                        <input
                          type="text"
                          value={parentNodeId}
                          onChange={(e) => setParentNodeId(e.target.value)}
                          placeholder="Optional parent node"
                          className={cn(
                            'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                            'focus:outline-none focus:ring-2 focus:ring-ring'
                          )}
                        />
                      </div>
                    </div>

                    <div>
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

                    <div>
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
                  </div>

                  <div className="mt-6 flex gap-2">
                    <button
                      onClick={() => {
                        setShowRegisterForm(false);
                        setNewApiKey(null);
                        setRegisteredNodeId(null);
                      }}
                      className={cn(
                        'flex-1 rounded-lg border px-4 py-2 text-sm font-medium',
                        'hover:bg-muted transition-colors'
                      )}
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleRegister}
                      disabled={registerMutation.isPending || !nodeId.trim() || !displayName.trim()}
                      className={cn(
                        'flex-1 inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
                        'hover:bg-primary/90 transition-colors',
                        'disabled:opacity-50 disabled:cursor-not-allowed'
                      )}
                    >
                      {registerMutation.isPending && (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      )}
                      Register
                    </button>
                  </div>
                </>
              )}
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
          <NodeFilters filters={filters} onFiltersChange={setFilters} />
        </motion.div>

        <motion.div variants={staggerItemVariants}>
          <NodeList filters={filters} />
        </motion.div>
      </motion.div>
    </div>
  );
}
