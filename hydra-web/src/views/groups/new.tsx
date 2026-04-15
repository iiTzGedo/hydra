import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { useCreateGroup } from '@/api/groups';
import { EntityMultiSelect } from '@/components/ui/entity-multi-select';
import { EnumMultiSelect } from '@/components/ui/enum-multi-select';
import { PageHeader } from '@/components/layout/page-header';
import { NODE_KIND_LABELS, ROUTES, SERVICE_RUNTIME_LABELS } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { getErrorMessage } from '@/lib/api-client';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import type { GroupEntityType, GroupSelectors } from '@/types/group';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const STATUS_OPTIONS = [
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'pending', label: 'Pending' },
  { value: 'archived', label: 'Archived' },
  { value: 'running', label: 'Running' },
  { value: 'stopped', label: 'Stopped' },
  { value: 'paused', label: 'Paused' },
  { value: 'exited', label: 'Exited' },
  { value: 'failed', label: 'Failed' },
  { value: 'restarting', label: 'Restarting' },
  { value: 'unknown', label: 'Unknown' },
];

const KIND_OPTIONS = Object.entries(NODE_KIND_LABELS).map(([value, label]) => ({
  value,
  label,
}));

const RUNTIME_OPTIONS = Object.entries(SERVICE_RUNTIME_LABELS).map(([value, label]) => ({
  value,
  label,
}));

const parseList = (value: string) =>
  value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

export default function NewGroupPage() {
  const router = useRouter();
  const createGroupMutation = useCreateGroup();

  const [groupId, setGroupId] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState('');
  const [types, setTypes] = useState<GroupEntityType[]>(['node']);

  // Selector state — arrays for multi-select components
  const [selectorIds, setSelectorIds] = useState<string[]>([]);
  const [selectorNetworks, setSelectorNetworks] = useState<string[]>([]);
  const [selectorStatuses, setSelectorStatuses] = useState<string[]>([]);
  const [selectorKinds, setSelectorKinds] = useState<string[]>([]);
  const [selectorRuntimes, setSelectorRuntimes] = useState<string[]>([]);
  const [selectorTags, setSelectorTags] = useState<string[]>([]);
  const [tagMode, setTagMode] = useState<'isAny' | 'isAll'>('isAny');

  const [error, setError] = useState<string | null>(null);

  const toggleType = (type: GroupEntityType) => {
    setTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  };

  const buildSelectors = (): GroupSelectors => {
    const selectors: GroupSelectors = {};

    if (selectorIds.length) {
      selectors.id = { isAll: selectorIds };
    }
    if (selectorNetworks.length) {
      selectors.network = { isAny: selectorNetworks };
    }
    if (selectorStatuses.length) {
      selectors.status = { isAny: selectorStatuses };
    }
    if (selectorKinds.length) {
      selectors.kind = { isAny: selectorKinds };
    }
    if (selectorRuntimes.length) {
      selectors.runtime = { isAny: selectorRuntimes };
    }
    if (selectorTags.length) {
      selectors.tags = tagMode === 'isAll' ? { isAll: selectorTags } : { isAny: selectorTags };
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

      router.push(ROUTES.GROUPS);
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Failed to create group'));
    }
  };

  return (
    <div className="p-6">
      <Link
        href={ROUTES.GROUPS}
        className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Groups
      </Link>

      <PageHeader
        title="Create Group"
        description="Define a new dynamic group with selector rules"
      />

      <motion.form
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        onSubmit={handleSubmit}
        className="max-w-2xl space-y-6"
      >
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-lg bg-error/10 p-3 text-sm text-error"
          >
            {error}
          </motion.div>
        )}

        <motion.div
          variants={staggerItemVariants}
          className="rounded-xl border bg-card p-6 shadow-sm"
        >
          <h3 className="text-lg font-semibold mb-4">Basic Information</h3>

          <div className="space-y-4">
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
                rows={3}
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
                placeholder="Comma-separated tags, e.g., critical, monitored"
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
        </motion.div>

        <motion.div
          variants={staggerItemVariants}
          className="rounded-xl border bg-card p-6 shadow-sm"
        >
          <h3 className="text-lg font-semibold mb-4">Selectors</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Add one or more selectors to define group membership rules.
          </p>

          <div className="space-y-4">
            <div>
              <span className="block text-sm font-medium mb-1.5">Node/Service IDs</span>
              <EntityMultiSelect
                entityType="node"
                values={selectorIds}
                onValuesChange={setSelectorIds}
                placeholder="Select nodes or services..."
              />
              <p className="mt-1 text-xs text-muted-foreground">
                IDs must all match when provided.
              </p>
            </div>

            <div>
              <span className="block text-sm font-medium mb-1.5">Networks</span>
              <EntityMultiSelect
                entityType="network"
                values={selectorNetworks}
                onValuesChange={setSelectorNetworks}
                placeholder="Select networks..."
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <span className="block text-sm font-medium mb-1.5">Statuses</span>
                <EnumMultiSelect
                  values={selectorStatuses}
                  onValuesChange={setSelectorStatuses}
                  options={STATUS_OPTIONS}
                  placeholder="Select statuses..."
                />
              </div>
              <div>
                <span className="block text-sm font-medium mb-1.5">Kinds</span>
                <EnumMultiSelect
                  values={selectorKinds}
                  onValuesChange={setSelectorKinds}
                  options={KIND_OPTIONS}
                  placeholder="Select kinds..."
                />
              </div>
            </div>

            <div>
              <span className="block text-sm font-medium mb-1.5">Runtimes</span>
              <EnumMultiSelect
                values={selectorRuntimes}
                onValuesChange={setSelectorRuntimes}
                options={RUNTIME_OPTIONS}
                placeholder="Select runtimes..."
              />
            </div>

            <div>
              <span className="block text-sm font-medium mb-1.5">Tags</span>
              <div className="flex flex-col gap-2 md:flex-row md:items-start">
                <EnumMultiSelect
                  values={selectorTags}
                  onValuesChange={setSelectorTags}
                  options={[]}
                  allowFreeText
                  placeholder="Enter tags..."
                  className="flex-1"
                />
                <Select
                  value={tagMode}
                  onValueChange={(v) => setTagMode(v as 'isAny' | 'isAll')}
                >
                  <SelectTrigger className="w-[160px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="isAny">Match any tag</SelectItem>
                    <SelectItem value="isAll">Match all tags</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        </motion.div>

        <motion.div variants={staggerItemVariants} className="flex items-center gap-3">
          <button
            type="submit"
            disabled={createGroupMutation.isPending}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
              'hover:bg-primary/90 transition-colors',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            {createGroupMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
            Create Group
          </button>
          <Link
            href={ROUTES.GROUPS}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium',
              'hover:bg-muted transition-colors'
            )}
          >
            Cancel
          </Link>
        </motion.div>
      </motion.form>
    </div>
  );
}
