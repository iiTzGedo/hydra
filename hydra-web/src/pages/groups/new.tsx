import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Plus, Trash2, Loader2 } from 'lucide-react';
import { useCreateGroup } from '@/api/groups';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

interface SelectorForm {
  type: 'tag' | 'class' | 'kind' | 'network' | 'custom';
  operator: 'equals' | 'contains' | 'regex' | 'in';
  value: string;
}

export default function NewGroupPage() {
  const navigate = useNavigate();
  const createGroupMutation = useCreateGroup();

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState('');
  const [selectors, setSelectors] = useState<SelectorForm[]>([
    { type: 'tag', operator: 'equals', value: '' },
  ]);
  const [error, setError] = useState<string | null>(null);

  const addSelector = () => {
    setSelectors([...selectors, { type: 'tag', operator: 'equals', value: '' }]);
  };

  const removeSelector = (index: number) => {
    setSelectors(selectors.filter((_, i) => i !== index));
  };

  const updateSelector = (index: number, field: keyof SelectorForm, value: string) => {
    setSelectors(
      selectors.map((s, i) => (i === index ? { ...s, [field]: value } : s))
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError('Name is required');
      return;
    }

    if (selectors.length === 0) {
      setError('At least one selector is required');
      return;
    }

    const validSelectors = selectors.filter((s) => s.value.trim());
    if (validSelectors.length === 0) {
      setError('At least one selector must have a value');
      return;
    }

    try {
      // Convert form selectors to proper Selector union types
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const formattedSelectors: any[] = validSelectors.map((s) => {
        const values = s.value.split(',').map((v) => v.trim()).filter(Boolean);
        switch (s.type) {
          case 'tag':
            return { type: 'tag', tags: values, mode: 'isAny' };
          case 'class':
            return { type: 'class', classes: values };
          case 'kind':
            return { type: 'kind', kinds: values };
          case 'network':
            return { type: 'network', networkIds: values };
          case 'custom':
            return JSON.parse(s.value);
          default:
            return { type: s.type, [s.type + 's']: values };
        }
      });

      await createGroupMutation.mutateAsync({
        name: name.trim(),
        description: description.trim() || undefined,
        tags: tags
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
        selectors: formattedSelectors,
        entityTypes: 'nodes',
      });

      navigate(ROUTES.GROUPS);
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || 'Failed to create group');
    }
  };

  return (
    <div className="p-6">
      <Link
        to={ROUTES.GROUPS}
        className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Groups
      </Link>

      <PageHeader
        title="Create Group"
        description="Define a new dynamic group with selectors"
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

        {/* Basic Info */}
        <motion.div
          variants={staggerItemVariants}
          className="rounded-xl border bg-card p-6 shadow-sm"
        >
          <h3 className="text-lg font-semibold mb-4">Basic Information</h3>

          <div className="space-y-4">
            <div>
              <label htmlFor="name" className="block text-sm font-medium mb-1.5">
                Name <span className="text-error">*</span>
              </label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., production-servers"
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
          </div>
        </motion.div>

        {/* Selectors */}
        <motion.div
          variants={staggerItemVariants}
          className="rounded-xl border bg-card p-6 shadow-sm"
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold">Selectors</h3>
            <button
              type="button"
              onClick={addSelector}
              className={cn(
                'inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm',
                'border hover:bg-muted transition-colors'
              )}
            >
              <Plus className="h-4 w-4" />
              Add Selector
            </button>
          </div>

          <p className="text-sm text-muted-foreground mb-4">
            Selectors define which nodes belong to this group. Nodes matching any selector will be included.
          </p>

          <div className="space-y-3">
            {selectors.map((selector, index) => (
              <div key={index} className="flex items-start gap-2">
                <select
                  value={selector.type}
                  onChange={(e) => updateSelector(index, 'type', e.target.value)}
                  className={cn(
                    'rounded-lg border bg-background px-3 py-2 text-sm',
                    'focus:outline-none focus:ring-2 focus:ring-ring'
                  )}
                >
                  <option value="tag">Tag</option>
                  <option value="class">Class</option>
                  <option value="kind">Kind</option>
                  <option value="network">Network</option>
                  <option value="custom">Custom</option>
                </select>

                <select
                  value={selector.operator}
                  onChange={(e) => updateSelector(index, 'operator', e.target.value)}
                  className={cn(
                    'rounded-lg border bg-background px-3 py-2 text-sm',
                    'focus:outline-none focus:ring-2 focus:ring-ring'
                  )}
                >
                  <option value="equals">Equals</option>
                  <option value="contains">Contains</option>
                  <option value="regex">Regex</option>
                  <option value="in">In</option>
                </select>

                <input
                  type="text"
                  value={selector.value}
                  onChange={(e) => updateSelector(index, 'value', e.target.value)}
                  placeholder={
                    selector.type === 'custom'
                      ? '{"field": "value"}'
                      : 'Enter value...'
                  }
                  className={cn(
                    'flex-1 rounded-lg border bg-background px-3 py-2 text-sm',
                    'focus:outline-none focus:ring-2 focus:ring-ring',
                    'placeholder:text-muted-foreground'
                  )}
                />

                {selectors.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeSelector(index)}
                    className="rounded-lg p-2 text-error hover:bg-error/10 transition-colors"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </motion.div>

        {/* Actions */}
        <motion.div
          variants={staggerItemVariants}
          className="flex items-center gap-3"
        >
          <button
            type="submit"
            disabled={createGroupMutation.isPending}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
              'hover:bg-primary/90 transition-colors',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            {createGroupMutation.isPending && (
              <Loader2 className="h-4 w-4 animate-spin" />
            )}
            Create Group
          </button>
          <Link
            to={ROUTES.GROUPS}
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
