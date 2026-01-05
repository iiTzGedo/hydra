import { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft,
  Fingerprint,
  Plus,
  Copy,
  Check,
  Trash2,
  Clock,
  Loader2,
} from 'lucide-react';
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from '@/api/auth';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES } from '@/lib/constants';
import { cn, formatDate, formatRelativeTime } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

export default function ApiKeysPage() {
  const { data: apiKeys, isLoading, error, refetch } = useApiKeys();
  const createMutation = useCreateApiKey();
  const revokeMutation = useRevokeApiKey();

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newApiKey, setNewApiKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Create form state
  const [name, setName] = useState('');
  const [expiresInDays, setExpiresInDays] = useState('365');

  const handleCreate = async () => {
    // Calculate expiresAt from days
    const days = parseInt(expiresInDays) || 365;
    const expiresAt = new Date(Date.now() + days * 24 * 60 * 60 * 1000).toISOString();

    const result = await createMutation.mutateAsync({
      name,
      expiresAt,
    });
    setNewApiKey(result.key ?? null);
    setName('');
    refetch();
  };

  const handleCopy = async () => {
    if (newApiKey) {
      await navigator.clipboard.writeText(newApiKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleRevoke = async (keyId: string) => {
    await revokeMutation.mutateAsync(keyId);
    refetch();
  };

  if (error) {
    return (
      <div className="p-6">
        <Link
          to={ROUTES.ADMIN}
          className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Admin
        </Link>
        <div className="rounded-xl border bg-card p-8 text-center">
          <p className="text-error">Failed to load API keys</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <Link
        to={ROUTES.ADMIN}
        className="inline-flex items-center gap-2 text-muted-foreground hover:text-foreground mb-4"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Admin
      </Link>

      <PageHeader
        title="API Keys"
        description="Manage API keys for programmatic access"
        actions={
          <button
            onClick={() => setShowCreateForm(true)}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
              'hover:bg-primary/90 transition-colors'
            )}
          >
            <Plus className="h-4 w-4" />
            Create API Key
          </button>
        }
      />

      {/* Create API Key Modal */}
      <AnimatePresence>
        {showCreateForm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
            onClick={() => {
              setShowCreateForm(false);
              setNewApiKey(null);
            }}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-md rounded-xl border bg-card p-6 shadow-xl"
            >
              {newApiKey ? (
                <div className="text-center">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
                    <Check className="h-6 w-6 text-success" />
                  </div>
                  <h3 className="mt-4 text-lg font-semibold">API Key Created</h3>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Copy this key now. It won't be shown again.
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
                      setShowCreateForm(false);
                      setNewApiKey(null);
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
                  <h3 className="text-lg font-semibold">Create API Key</h3>

                  <div className="mt-4 space-y-4">
                    {/* Name */}
                    <div>
                      <label className="block text-sm font-medium mb-1.5">
                        Name <span className="text-error">*</span>
                      </label>
                      <input
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="e.g., CI/CD Pipeline"
                        className={cn(
                          'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                          'focus:outline-none focus:ring-2 focus:ring-ring'
                        )}
                      />
                    </div>

                    {/* Expires in */}
                    <div>
                      <label className="block text-sm font-medium mb-1.5">Expires in (days)</label>
                      <input
                        type="number"
                        value={expiresInDays}
                        onChange={(e) => setExpiresInDays(e.target.value)}
                        min="1"
                        className={cn(
                          'w-full rounded-lg border bg-background px-3 py-2 text-sm',
                          'focus:outline-none focus:ring-2 focus:ring-ring'
                        )}
                      />
                    </div>
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
                      disabled={createMutation.isPending || !name.trim()}
                      className={cn(
                        'flex-1 inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
                        'hover:bg-primary/90 transition-colors',
                        'disabled:opacity-50 disabled:cursor-not-allowed'
                      )}
                    >
                      {createMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                      Create
                    </button>
                  </div>
                </>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* API key list */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : !apiKeys?.length ? (
        <div className="rounded-xl border bg-card p-8 text-center">
          <Fingerprint className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No API keys</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Create an API key for programmatic access
          </p>
        </div>
      ) : (
        <motion.div
          variants={staggerContainerVariants}
          initial="hidden"
          animate="visible"
          className="rounded-xl border bg-card shadow-sm"
        >
          <div className="divide-y">
            {apiKeys.map((apiKey) => (
              <motion.div
                key={apiKey.keyId}
                variants={staggerItemVariants}
                className="flex items-center gap-4 p-4 hover:bg-muted/50 transition-colors group"
              >
                <div className="rounded-lg bg-iot p-2.5">
                  <Fingerprint className="h-5 w-5 text-white" />
                </div>

                <div className="flex-1 min-w-0">
                  <div className="font-medium">{apiKey.name}</div>
                  <div className="mt-1 flex items-center gap-3 text-sm text-muted-foreground">
                    <span className="font-mono">{apiKey.keyId.slice(0, 8)}...</span>
                    <span>•</span>
                    <span>Created {formatRelativeTime(new Date(apiKey.createdAt))}</span>
                  </div>
                </div>

                <div className="hidden md:flex items-center gap-2 text-sm text-muted-foreground">
                  <Clock className="h-4 w-4" />
                  <span>
                    {apiKey.expiresAt
                      ? `Expires ${formatRelativeTime(new Date(apiKey.expiresAt))}`
                      : 'Never expires'}
                  </span>
                </div>

                <button
                  onClick={() => handleRevoke(apiKey.keyId)}
                  disabled={revokeMutation.isPending}
                  className="rounded-lg p-2 text-error hover:bg-error/10 transition-colors opacity-0 group-hover:opacity-100"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </motion.div>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
}
