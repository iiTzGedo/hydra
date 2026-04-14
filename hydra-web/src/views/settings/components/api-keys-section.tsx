import { useState } from 'react';
import { motion } from 'framer-motion';
import { Fingerprint, Plus, Copy, Check, Loader2, Clock, Trash2, Server, BarChart3 } from 'lucide-react';
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from '@/api/auth';
import { formatDateTime, formatRelativeTime } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

export function ApiKeysSection() {
  const { data: apiKeys, isLoading, error, refetch } = useApiKeys();
  const createMutation = useCreateApiKey();
  const revokeMutation = useRevokeApiKey();

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newApiKey, setNewApiKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [name, setName] = useState('');
  const [expiresInDays, setExpiresInDays] = useState('365');

  const handleCreate = async () => {
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

  const handleCloseModal = () => {
    setShowCreateForm(false);
    setNewApiKey(null);
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-medium text-foreground">API Keys</h3>
          <p className="text-sm text-muted-foreground">
            {apiKeys?.length
              ? `${apiKeys.length} API key${apiKeys.length !== 1 ? 's' : ''}`
              : 'Manage API keys for programmatic access'}
          </p>
        </div>
        <Button
          onClick={() => setShowCreateForm(true)}
          className=""
        >
          <Plus className="mr-2 h-4 w-4" />
          Create API Key
        </Button>
      </div>

      <Dialog open={showCreateForm} onOpenChange={handleCloseModal}>
        <DialogContent className="sm:max-w-md bg-card border-border text-foreground">
          {newApiKey ? (
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
                <Check className="h-6 w-6 text-success" />
              </div>
              <DialogHeader className="mt-4">
                <DialogTitle className="text-foreground">API Key Created</DialogTitle>
                <DialogDescription className="text-muted-foreground">
                  Copy this key now. It won't be shown again.
                </DialogDescription>
              </DialogHeader>
              <div className="mt-4 flex items-center gap-2 rounded-lg bg-muted p-3">
                <code className="flex-1 text-sm font-mono break-all text-left text-success">
                  {newApiKey}
                </code>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleCopy}
                  className="text-muted-foreground hover:text-foreground hover:bg-muted"
                >
                  {copied ? (
                    <Check className="h-4 w-4 text-success" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
              <Button
                onClick={handleCloseModal}
                className="mt-6 w-full "
              >
                Done
              </Button>
            </div>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle className="text-foreground">Create API Key</DialogTitle>
              </DialogHeader>

              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="name" className="text-foreground">
                    Name <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., CI/CD Pipeline"
                    className="bg-muted border-border text-foreground"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="expiresIn" className="text-foreground">
                    Expires in (days)
                  </Label>
                  <Input
                    id="expiresIn"
                    type="number"
                    value={expiresInDays}
                    onChange={(e) => setExpiresInDays(e.target.value)}
                    min="1"
                    className="bg-muted border-border text-foreground"
                  />
                </div>
              </div>

              <div className="mt-6 flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleCloseModal}
                  className="flex-1 border-border text-foreground hover:bg-muted bg-transparent"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleCreate}
                  disabled={createMutation.isPending || !name.trim()}
                  className="flex-1 "
                >
                  {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Create
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {error ? (
        <Card className="bg-card border-border">
          <CardContent className="p-8 text-center">
            <p className="text-destructive">Failed to load API keys</p>
          </CardContent>
        </Card>
      ) : isLoading ? (
        <Card className="bg-card border-border">
          <CardContent className="p-6 space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="h-10 w-10 rounded-lg bg-muted" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-32 bg-muted" />
                  <Skeleton className="h-3 w-48 bg-muted" />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : !apiKeys?.length ? (
        <Card className="bg-card border-border">
          <CardContent className="p-8 text-center">
            <Fingerprint className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold text-foreground">No API keys</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Create an API key for programmatic access
            </p>
          </CardContent>
        </Card>
      ) : (
        <motion.div
          variants={staggerContainerVariants}
          initial="hidden"
          animate="visible"
        >
          <Card className="bg-card border-border">
            <div className="divide-y divide-border">
              {apiKeys.map((apiKey) => (
                <motion.div
                  key={apiKey.keyId}
                  variants={staggerItemVariants}
                  className="flex items-center gap-4 p-4 hover:bg-muted/60 transition-colors group"
                >
                  <div className={`rounded-lg p-2.5 ${apiKey.type === 'node' ? 'bg-blue-500/20' : 'bg-green-500/20'}`}>
                    {apiKey.type === 'node' ? (
                      <Server className="h-5 w-5 text-blue-400" />
                    ) : (
                      <Fingerprint className="h-5 w-5 text-green-400" />
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-foreground">{apiKey.name}</span>
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        apiKey.type === 'node'
                          ? 'bg-blue-500/10 text-blue-400'
                          : 'bg-green-500/10 text-green-400'
                      }`}>
                        {apiKey.type || 'user'}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground flex-wrap">
                      <span className="font-mono">{apiKey.keyId.slice(0, 12)}...</span>
                      {apiKey.nodeId && (
                        <>
                          <span className="text-muted-foreground/50">·</span>
                          <span>{apiKey.nodeId}</span>
                        </>
                      )}
                      <span className="text-muted-foreground/50">·</span>
                      <span>Created {formatRelativeTime(new Date(apiKey.createdAt))}</span>
                    </div>
                  </div>

                  <div className="hidden lg:flex items-center gap-3 text-sm text-muted-foreground">
                    <BarChart3 className="h-4 w-4" />
                    <div className="flex flex-col items-end">
                      <span>{(apiKey.usageCount ?? 0).toLocaleString()} request{apiKey.usageCount !== 1 ? 's' : ''}</span>
                      <span className="text-xs">
                        {apiKey.lastUsedAt
                          ? `Last used ${formatRelativeTime(new Date(apiKey.lastUsedAt))}`
                          : 'Never used'}
                      </span>
                    </div>
                  </div>

                  <div className="hidden md:flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock className="h-4 w-4" />
                    <span>
                      {apiKey.expiresAt
                        ? `Expires ${formatDateTime(apiKey.expiresAt)}`
                        : 'Never expires'}
                    </span>
                  </div>

                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleRevoke(apiKey.keyId)}
                        disabled={revokeMutation.isPending}
                        className="text-destructive hover:text-destructive hover:bg-destructive/10 opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent className="bg-muted border-border text-foreground">
                      Revoke API Key
                    </TooltipContent>
                  </Tooltip>
                </motion.div>
              ))}
            </div>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
