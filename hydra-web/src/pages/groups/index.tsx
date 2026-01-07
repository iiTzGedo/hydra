import { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, X, Loader2, CheckCircle2, FolderTree } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { GroupList } from '@/components/groups/group-list';
import { GroupFilters, GroupFilterState } from '@/components/groups/group-filters';
import { useCreateGroup } from '@/api/groups';
import { ROUTES } from '@/lib/constants';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { cn } from '@/lib/utils';
import type { GroupEntityType, GroupSelectors } from '@/types/group';

const parseList = (value: string) =>
  value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

export default function GroupsPage() {
  const [filters, setFilters] = useState<GroupFilterState>({
    search: '',
  });

  // Modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createdGroupId, setCreatedGroupId] = useState<string | null>(null);

  // Form state
  const [groupId, setGroupId] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState('');
  const [types, setTypes] = useState<GroupEntityType[]>(['node']);
  const [selectorIds, setSelectorIds] = useState('');
  const [selectorNetworks, setSelectorNetworks] = useState('');
  const [selectorStatuses, setSelectorStatuses] = useState('');
  const [selectorKinds, setSelectorKinds] = useState('');
  const [selectorRuntimes, setSelectorRuntimes] = useState('');
  const [selectorTags, setSelectorTags] = useState('');
  const [tagMode, setTagMode] = useState<'isAny' | 'isAll'>('isAny');
  const [error, setError] = useState<string | null>(null);

  const createGroupMutation = useCreateGroup();

  const resetForm = () => {
    setGroupId('');
    setName('');
    setDescription('');
    setTags('');
    setTypes(['node']);
    setSelectorIds('');
    setSelectorNetworks('');
    setSelectorStatuses('');
    setSelectorKinds('');
    setSelectorRuntimes('');
    setSelectorTags('');
    setTagMode('isAny');
    setError(null);
    setCreatedGroupId(null);
  };

  const handleOpenModal = () => {
    resetForm();
    setShowCreateModal(true);
  };

  const handleCloseModal = () => {
    setShowCreateModal(false);
    resetForm();
  };

  const toggleType = (type: GroupEntityType) => {
    setTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  };

  const buildSelectors = (): GroupSelectors => {
    const selectors: GroupSelectors = {};

    const ids = parseList(selectorIds);
    if (ids.length) {
      selectors.id = { isAll: ids };
    }

    const networks = parseList(selectorNetworks);
    if (networks.length) {
      selectors.network = { isAny: networks };
    }

    const statuses = parseList(selectorStatuses);
    if (statuses.length) {
      selectors.status = { isAny: statuses };
    }

    const kinds = parseList(selectorKinds);
    if (kinds.length) {
      selectors.kind = { isAny: kinds };
    }

    const runtimes = parseList(selectorRuntimes);
    if (runtimes.length) {
      selectors.runtime = { isAny: runtimes };
    }

    const tagValues = parseList(selectorTags);
    if (tagValues.length) {
      selectors.tags = tagMode === 'isAll' ? { isAll: tagValues } : { isAny: tagValues };
    }

    return selectors;
  };

  const hasSelectors = () => {
    const selectors = buildSelectors();
    return Object.keys(selectors).length > 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!groupId.trim()) {
      setError('Group ID is required');
      return;
    }

    if (!name.trim()) {
      setError('Name is required');
      return;
    }

    if (!types.length) {
      setError('Select at least one entity type');
      return;
    }

    if (!hasSelectors()) {
      setError('At least one selector is required');
      return;
    }

    try {
      await createGroupMutation.mutateAsync({
        groupId: groupId.trim(),
        name: name.trim(),
        description: description.trim() || undefined,
        tags: parseList(tags),
        types,
        selectors: buildSelectors(),
      });

      setCreatedGroupId(groupId.trim());
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || 'Failed to create group');
    }
  };

  return (
    <div className="p-6">
      <PageHeader
        title="Groups"
        description="Organize infrastructure with dynamic selectors"
        actions={
          <button
            onClick={handleOpenModal}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
              'hover:bg-primary/90 transition-colors'
            )}
          >
            <Plus className="h-4 w-4" />
            Create Group
          </button>
        }
      />

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        <motion.div variants={staggerItemVariants}>
          <GroupFilters filters={filters} onFiltersChange={setFilters} />
        </motion.div>

        <motion.div variants={staggerItemVariants}>
          <GroupList filters={filters} />
        </motion.div>
      </motion.div>

      {/* Create Group Modal */}
      <AnimatePresence>
        {showCreateModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
            onClick={handleCloseModal}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="relative w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto rounded-xl border bg-card shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header */}
              <div className="sticky top-0 z-10 flex items-center justify-between border-b bg-card px-6 py-4">
                <h2 className="text-lg font-semibold">Create Group</h2>
                <button
                  onClick={handleCloseModal}
                  className="rounded-lg p-1 hover:bg-muted"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {/* Content */}
              <div className="p-6">
                {createdGroupId ? (
                  // Success state
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="text-center py-6"
                  >
                    <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-success/10">
                      <CheckCircle2 className="h-8 w-8 text-success" />
                    </div>
                    <h3 className="text-lg font-semibold mb-2">Group Created!</h3>
                    <p className="text-sm text-muted-foreground mb-6">
                      Your group <span className="font-mono text-foreground">{createdGroupId}</span> has been created successfully.
                    </p>
                    <div className="flex flex-col gap-3">
                      <Link
                        to={`${ROUTES.GROUPS}/${createdGroupId}`}
                        className={cn(
                          'inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
                          'hover:bg-primary/90 transition-colors'
                        )}
                      >
                        <FolderTree className="h-4 w-4" />
                        View Group
                      </Link>
                      <button
                        onClick={handleCloseModal}
                        className={cn(
                          'inline-flex items-center justify-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium',
                          'hover:bg-muted transition-colors'
                        )}
                      >
                        Close
                      </button>
                    </div>
                  </motion.div>
                ) : (
                  // Form
                  <form onSubmit={handleSubmit} className="space-y-6">
                    {error && (
                      <motion.div
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="rounded-lg bg-error/10 p-3 text-sm text-error"
                      >
                        {error}
                      </motion.div>
                    )}

                    {/* Basic Info */}
                    <div className="space-y-4">
                      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                        Basic Information
                      </h3>

                      <div>
                        <label htmlFor="groupId" className="block text-sm font-medium mb-1.5">
                          Group ID <span className="text-error">*</span>
                        </label>
                        <input
                          id="groupId"
                          type="text"
                          value={groupId}
                          onChange={(e) => setGroupId(e.target.value)}
                          placeholder="e.g., production-servers"
                          className={cn(
                            'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                            'focus:outline-none focus:ring-2 focus:ring-ring',
                            'placeholder:text-muted-foreground'
                          )}
                        />
                      </div>

                      <div>
                        <label htmlFor="name" className="block text-sm font-medium mb-1.5">
                          Name <span className="text-error">*</span>
                        </label>
                        <input
                          id="name"
                          type="text"
                          value={name}
                          onChange={(e) => setName(e.target.value)}
                          placeholder="e.g., Production Servers"
                          className={cn(
                            'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                            'focus:outline-none focus:ring-2 focus:ring-ring',
                            'placeholder:text-muted-foreground'
                          )}
                        />
                      </div>

                      <div>
                        <label htmlFor="description" className="block text-sm font-medium mb-1.5">
                          Description
                        </label>
                        <textarea
                          id="description"
                          value={description}
                          onChange={(e) => setDescription(e.target.value)}
                          placeholder="Optional description of the group"
                          rows={2}
                          className={cn(
                            'w-full rounded-lg border bg-background px-3 py-2 text-sm resize-none',
                            'focus:outline-none focus:ring-2 focus:ring-ring',
                            'placeholder:text-muted-foreground'
                          )}
                        />
                      </div>

                      <div>
                        <label htmlFor="tags" className="block text-sm font-medium mb-1.5">
                          Tags
                        </label>
                        <input
                          id="tags"
                          type="text"
                          value={tags}
                          onChange={(e) => setTags(e.target.value)}
                          placeholder="Comma-separated tags"
                          className={cn(
                            'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                            'focus:outline-none focus:ring-2 focus:ring-ring',
                            'placeholder:text-muted-foreground'
                          )}
                        />
                      </div>

                      <div>
                        <span className="block text-sm font-medium mb-2">Entity Types</span>
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={() => toggleType('node')}
                            className={cn(
                              'rounded-full border px-3 py-1 text-sm',
                              types.includes('node')
                                ? 'bg-primary text-primary-foreground border-primary'
                                : 'hover:bg-muted'
                            )}
                          >
                            Nodes
                          </button>
                          <button
                            type="button"
                            onClick={() => toggleType('service')}
                            className={cn(
                              'rounded-full border px-3 py-1 text-sm',
                              types.includes('service')
                                ? 'bg-primary text-primary-foreground border-primary'
                                : 'hover:bg-muted'
                            )}
                          >
                            Services
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Selectors */}
                    <div className="space-y-4">
                      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                        Selectors
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        Add one or more selector lists. Each list uses comma-separated values.
                      </p>

                      <div>
                        <label className="block text-sm font-medium mb-1.5">Node/Service IDs</label>
                        <input
                          type="text"
                          value={selectorIds}
                          onChange={(e) => setSelectorIds(e.target.value)}
                          placeholder="e.g., node-01, node-02"
                          className={cn(
                            'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                            'focus:outline-none focus:ring-2 focus:ring-ring'
                          )}
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-1.5">Networks</label>
                        <input
                          type="text"
                          value={selectorNetworks}
                          onChange={(e) => setSelectorNetworks(e.target.value)}
                          placeholder="e.g., prod-vlan-10"
                          className={cn(
                            'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                            'focus:outline-none focus:ring-2 focus:ring-ring'
                          )}
                        />
                      </div>

                      <div className="grid gap-4 grid-cols-2">
                        <div>
                          <label className="block text-sm font-medium mb-1.5">Statuses</label>
                          <input
                            type="text"
                            value={selectorStatuses}
                            onChange={(e) => setSelectorStatuses(e.target.value)}
                            placeholder="e.g., active"
                            className={cn(
                              'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                              'focus:outline-none focus:ring-2 focus:ring-ring'
                            )}
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium mb-1.5">Kinds</label>
                          <input
                            type="text"
                            value={selectorKinds}
                            onChange={(e) => setSelectorKinds(e.target.value)}
                            placeholder="e.g., vm, router"
                            className={cn(
                              'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                              'focus:outline-none focus:ring-2 focus:ring-ring'
                            )}
                          />
                        </div>
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-1.5">Runtimes</label>
                        <input
                          type="text"
                          value={selectorRuntimes}
                          onChange={(e) => setSelectorRuntimes(e.target.value)}
                          placeholder="e.g., docker, kubernetes"
                          className={cn(
                            'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                            'focus:outline-none focus:ring-2 focus:ring-ring'
                          )}
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium mb-1.5">Tags</label>
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                          <input
                            type="text"
                            value={selectorTags}
                            onChange={(e) => setSelectorTags(e.target.value)}
                            placeholder="e.g., critical, edge"
                            className={cn(
                              'flex-1 rounded-lg border bg-background px-3 py-2 text-sm',
                              'focus:outline-none focus:ring-2 focus:ring-ring'
                            )}
                          />
                          <select
                            value={tagMode}
                            onChange={(e) => setTagMode(e.target.value as 'isAny' | 'isAll')}
                            className={cn(
                              'rounded-lg border bg-background px-3 py-2 text-sm',
                              'focus:outline-none focus:ring-2 focus:ring-ring'
                            )}
                          >
                            <option value="isAny">Match any</option>
                            <option value="isAll">Match all</option>
                          </select>
                        </div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-3 pt-2">
                      <button
                        type="submit"
                        disabled={createGroupMutation.isPending}
                        className={cn(
                          'flex-1 inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
                          'hover:bg-primary/90 transition-colors',
                          'disabled:opacity-50 disabled:cursor-not-allowed'
                        )}
                      >
                        {createGroupMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                        Create Group
                      </button>
                      <button
                        type="button"
                        onClick={handleCloseModal}
                        className={cn(
                          'inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium',
                          'hover:bg-muted transition-colors'
                        )}
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
