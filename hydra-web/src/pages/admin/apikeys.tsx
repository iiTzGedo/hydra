import { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
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
import { formatDateTime, formatRelativeTime } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
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
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

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

  const handleCloseModal = () => {
    setShowCreateForm(false);
    setNewApiKey(null);
  };

  if (error) {
    return (
      <div className="p-6">
        <Button variant="ghost" size="sm" asChild className="mb-6">
          <Link to={ROUTES.ADMIN}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Admin
          </Link>
        </Button>
        <Card>
          <CardContent className="p-8 text-center">
            <p className="text-destructive">Failed to load API keys</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <TooltipProvider>
      <div className="p-6">
        <Button variant="ghost" size="sm" asChild className="mb-4">
          <Link to={ROUTES.ADMIN}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Admin
          </Link>
        </Button>

        <PageHeader
          title="API Keys"
          description="Manage API keys for programmatic access"
          actions={
            <Button onClick={() => setShowCreateForm(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create API Key
            </Button>
          }
        />

        {/* Create API Key Dialog */}
        <Dialog open={showCreateForm} onOpenChange={handleCloseModal}>
          <DialogContent className="sm:max-w-md">
            {newApiKey ? (
              <div className="text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
                  <Check className="h-6 w-6 text-success" />
                </div>
                <DialogHeader className="mt-4">
                  <DialogTitle>API Key Created</DialogTitle>
                  <DialogDescription>
                    Copy this key now. It won't be shown again.
                  </DialogDescription>
                </DialogHeader>
                <div className="mt-4 flex items-center gap-2 rounded-lg bg-muted p-3">
                  <code className="flex-1 text-sm font-mono break-all text-left">{newApiKey}</code>
                  <Button variant="ghost" size="icon" onClick={handleCopy}>
                    {copied ? (
                      <Check className="h-4 w-4 text-success" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
                <Button onClick={handleCloseModal} className="mt-6 w-full">
                  Done
                </Button>
              </div>
            ) : (
              <>
                <DialogHeader>
                  <DialogTitle>Create API Key</DialogTitle>
                </DialogHeader>

                <div className="space-y-4">
                  {/* Name */}
                  <div className="space-y-2">
                    <Label htmlFor="name">
                      Name <span className="text-destructive">*</span>
                    </Label>
                    <Input
                      id="name"
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="e.g., CI/CD Pipeline"
                    />
                  </div>

                  {/* Expires in */}
                  <div className="space-y-2">
                    <Label htmlFor="expiresIn">Expires in (days)</Label>
                    <Input
                      id="expiresIn"
                      type="number"
                      value={expiresInDays}
                      onChange={(e) => setExpiresInDays(e.target.value)}
                      min="1"
                    />
                  </div>
                </div>

                <div className="mt-6 flex gap-2">
                  <Button variant="outline" onClick={handleCloseModal} className="flex-1">
                    Cancel
                  </Button>
                  <Button
                    onClick={handleCreate}
                    disabled={createMutation.isPending || !name.trim()}
                    className="flex-1"
                  >
                    {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Create
                  </Button>
                </div>
              </>
            )}
          </DialogContent>
        </Dialog>

        {/* API key list */}
        {isLoading ? (
          <Card>
            <CardContent className="p-6 space-y-4">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="flex items-center gap-4">
                  <Skeleton className="h-10 w-10 rounded-lg" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-3 w-48" />
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        ) : !apiKeys?.length ? (
          <Card>
            <CardContent className="p-8 text-center">
              <Fingerprint className="mx-auto h-12 w-12 text-muted-foreground" />
              <h3 className="mt-4 text-lg font-semibold">No API keys</h3>
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
            <Card>
              <div className="divide-y">
                {apiKeys.map((apiKey) => (
                  <motion.div
                    key={apiKey.keyId}
                    variants={staggerItemVariants}
                    className="flex items-center gap-4 p-4 hover:bg-muted/50 transition-colors group"
                  >
                    <div className="rounded-lg bg-iot p-2.5">
                      <Fingerprint className="h-5 w-5 text-foreground" />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="font-medium">{apiKey.name}</div>
                      <div className="mt-1 flex items-center gap-3 text-sm text-muted-foreground">
                        <span className="font-mono">{apiKey.keyId.slice(0, 8)}...</span>
                        <span>-</span>
                        <span>Created {formatRelativeTime(new Date(apiKey.createdAt))}</span>
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
                      <TooltipContent>Revoke API Key</TooltipContent>
                    </Tooltip>
                  </motion.div>
                ))}
              </div>
            </Card>
          </motion.div>
        )}
      </div>
    </TooltipProvider>
  );
}
