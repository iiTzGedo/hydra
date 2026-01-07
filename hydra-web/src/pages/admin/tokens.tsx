import { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft,
  Plus,
  Copy,
  Check,
  Users,
  Server,
  Loader2,
} from 'lucide-react';
import { useCreateToken } from '@/api/auth';
import { PageHeader } from '@/components/layout/page-header';
import { ROUTES, ROLE_LABELS } from '@/lib/constants';
import { cn } from '@/lib/utils';
import type { Role } from '@/types/auth';

export default function TokensPage() {
  const createMutation = useCreateToken();

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newToken, setNewToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Create form state
  const [scope, setScope] = useState<'user' | 'node'>('user');
  const [maxUses, setMaxUses] = useState('1');
  const [expiresInDays, setExpiresInDays] = useState('7');
  const [allowedRoles, setAllowedRoles] = useState<Role[]>(['viewer']);

  const handleCreate = async () => {
    // Convert days to seconds
    const days = parseInt(expiresInDays) || 7;
    const expiresIn = days * 24 * 60 * 60;

    const result = await createMutation.mutateAsync({
      scope,
      maxUses: parseInt(maxUses) || 1,
      expiresIn,
      allowedRoles: scope === 'user' ? allowedRoles : undefined,
    });
    setNewToken(result.token);
  };

  const handleCopy = async () => {
    if (newToken) {
      await navigator.clipboard.writeText(newToken);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const toggleRole = (role: Role) => {
    setAllowedRoles((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]
    );
  };

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
        title="Registration Tokens"
        description="Create tokens for user and node registration"
        actions={
          <button
            onClick={() => setShowCreateForm(true)}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
              'hover:bg-primary/90 transition-colors'
            )}
          >
            <Plus className="h-4 w-4" />
            Create Token
          </button>
        }
      />

      {/* Create Token Modal */}
      <AnimatePresence>
        {showCreateForm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
            onClick={() => {
              setShowCreateForm(false);
              setNewToken(null);
            }}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-md rounded-xl border bg-card p-6 shadow-xl"
            >
              {newToken ? (
                <div className="text-center">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
                    <Check className="h-6 w-6 text-success" />
                  </div>
                  <h3 className="mt-4 text-lg font-semibold">Token Created</h3>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Copy this token now. It won't be shown again.
                  </p>
                  <div className="mt-4 flex items-center gap-2 rounded-lg bg-muted p-3">
                    <code className="flex-1 text-sm font-mono break-all">{newToken}</code>
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
                      setNewToken(null);
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
                  <h3 className="text-lg font-semibold">Create Registration Token</h3>

                  <div className="mt-4 space-y-4">
                    {/* Scope */}
                    <div>
                      <label className="block text-sm font-medium mb-2">Token Scope</label>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setScope('user')}
                          className={cn(
                            'flex-1 flex items-center justify-center gap-2 rounded-lg border px-4 py-2 text-sm',
                            scope === 'user' ? 'border-primary bg-primary/10' : 'hover:bg-muted'
                          )}
                        >
                          <Users className="h-4 w-4" />
                          User
                        </button>
                        <button
                          type="button"
                          onClick={() => setScope('node')}
                          className={cn(
                            'flex-1 flex items-center justify-center gap-2 rounded-lg border px-4 py-2 text-sm',
                            scope === 'node' ? 'border-primary bg-primary/10' : 'hover:bg-muted'
                          )}
                        >
                          <Server className="h-4 w-4" />
                          Node
                        </button>
                      </div>
                    </div>

                    {/* Max uses */}
                    <div>
                      <label className="block text-sm font-medium mb-1.5">Max Uses</label>
                      <input
                        type="number"
                        value={maxUses}
                        onChange={(e) => setMaxUses(e.target.value)}
                        min="1"
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

                    {/* Allowed roles (for user tokens) */}
                    {scope === 'user' && (
                      <div>
                        <label className="block text-sm font-medium mb-2">Allowed Roles</label>
                        <div className="flex flex-wrap gap-2">
                          {(['admin', 'operator', 'viewer', 'family'] as Role[]).map((role) => (
                            <button
                              key={role}
                              type="button"
                              onClick={() => toggleRole(role)}
                              className={cn(
                                'rounded-full px-3 py-1 text-sm border transition-colors',
                                allowedRoles.includes(role)
                                  ? 'border-primary bg-primary/10 text-primary'
                                  : 'hover:bg-muted'
                              )}
                            >
                              {ROLE_LABELS[role]}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
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
                      disabled={createMutation.isPending}
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

      <div className="rounded-xl border bg-card p-6 text-sm text-muted-foreground">
        Registration tokens can be created here. Token listing and revocation are not available
        in API v0.3.0, so store tokens securely when created.
      </div>
    </div>
  );
}
