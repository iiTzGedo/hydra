import { useState } from 'react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { PageHeaderLayout } from '@/components/layout/page-header-layout';
import { useAuthStore } from '@/stores/auth-store';
import { useApiKeys, useCreateApiKey, useRevokeApiKey, useChangePassword } from '@/api/auth';
import { formatRelativeTime, formatDateTime } from '@/lib/utils';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  User,
  Mail,
  Shield,
  Key,
  Clock,
  Plus,
  Trash2,
  Copy,
  Check,
  AlertTriangle,
  Fingerprint,
  Loader2,
} from 'lucide-react';

export default function ProfilePage() {
  useDocumentTitle('Profile');

  const { user } = useAuthStore();
  const { data: apiKeys, isLoading: isLoadingKeys, error: keysError } = useApiKeys();
  const createMutation = useCreateApiKey();
  const revokeMutation = useRevokeApiKey();
  const changePasswordMutation = useChangePassword();

  const [showCreateTokenModal, setShowCreateTokenModal] = useState(false);
  const [showTokenResult, setShowTokenResult] = useState(false);
  const [generatedToken, setGeneratedToken] = useState('');
  const [copiedToken, setCopiedToken] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const [tokenName, setTokenName] = useState('');
  const [tokenExpiryDays, setTokenExpiryDays] = useState('90');

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState(false);

  const handleCreateToken = async () => {
    try {
      const days = tokenExpiryDays === 'never' ? null : parseInt(tokenExpiryDays);
      const expiresAt = days ? new Date(Date.now() + days * 24 * 60 * 60 * 1000).toISOString() : undefined;

      const result = await createMutation.mutateAsync({
        name: tokenName,
        expiresAt,
      });

      if (result.key) {
        setGeneratedToken(result.key);
        setShowCreateTokenModal(false);
        setShowTokenResult(true);
      }
      setTokenName('');
      setTokenExpiryDays('90');
    } catch {
      // Error handled by mutation
    }
  };

  const handleRevokeKey = async (keyId: string) => {
    try {
      await revokeMutation.mutateAsync(keyId);
    } catch {
      // Error handled by mutation
    }
  };

  const handleChangePassword = async () => {
    setPasswordError(null);
    setPasswordSuccess(false);

    if (!currentPassword || !newPassword) {
      setPasswordError('Please fill in both fields');
      return;
    }

    if (newPassword.length < 8) {
      setPasswordError('New password must be at least 8 characters');
      return;
    }

    try {
      await changePasswordMutation.mutateAsync({
        currentPassword,
        newPassword,
      });
      setPasswordSuccess(true);
      setCurrentPassword('');
      setNewPassword('');
    } catch {
      setPasswordError('Failed to change password. Please check your current password.');
    }
  };

  const copyToken = async (token: string, id?: string) => {
    await navigator.clipboard.writeText(token);
    if (id) {
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } else {
      setCopiedToken(true);
      setTimeout(() => setCopiedToken(false), 2000);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeaderLayout
        title="Profile"
        subtitle="Manage your account settings and preferences"
        showBackButton={false}
      />

      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-foreground flex items-center gap-2">
              <User className="h-5 w-5 text-primary" />
              Account Information
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center gap-6">
              <Avatar className="h-20 w-20">
                <AvatarFallback className="bg-primary text-primary-foreground text-2xl">
                  {user?.username?.charAt(0)?.toUpperCase() || 'U'}
                </AvatarFallback>
              </Avatar>
              <div className="space-y-1">
                <h3 className="text-xl font-semibold text-foreground">
                  {user?.username || 'User'}
                </h3>
                <p className="text-muted-foreground">@{user?.username || 'user'}</p>
                <div className="flex items-center gap-2 mt-2">
                  <Badge variant="destructive" className="gap-1">
                    <Shield className="mr-1 h-3 w-3" />
                    {user?.role || 'viewer'}
                  </Badge>
                  <Badge variant="outline" className="border-success/30 text-success">
                    Active
                  </Badge>
                </div>
              </div>
            </div>

            <Separator className="bg-border" />

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label className="text-foreground">Username</Label>
                <Input
                  value={user?.username || ''}
                  disabled
                  className="bg-muted border-border text-muted-foreground"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-foreground">User ID</Label>
                <Input
                  value={user?.userId || ''}
                  disabled
                  className="bg-muted border-border text-muted-foreground font-mono text-sm"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-foreground">Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    value={user?.email || ''}
                    disabled
                    className="bg-muted border-border text-muted-foreground pl-9"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label className="text-foreground">Member Since</Label>
                <div className="relative">
                  <Clock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    value={user?.createdAt ? new Date(user.createdAt).toLocaleDateString() : '-'}
                    disabled
                    className="bg-muted border-border text-muted-foreground pl-9"
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-foreground flex items-center gap-2">
              <Shield className="h-5 w-5 text-destructive" />
              Security
            </CardTitle>
            <CardDescription className="text-muted-foreground">
              Manage your security preferences
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-foreground font-medium">Two-factor authentication</p>
                <p className="text-sm text-muted-foreground">Add an extra layer of security</p>
              </div>
              <Button
                variant="outline"
                className="border-border text-foreground bg-transparent hover:bg-muted"
                disabled
              >
                Coming Soon
              </Button>
            </div>

            <Separator className="bg-border" />

            <div className="space-y-3">
              <Label className="text-foreground">Change Password</Label>
              <Input
                type="password"
                placeholder="Current password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="bg-background border-border text-foreground"
              />
              <Input
                type="password"
                placeholder="New password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="bg-background border-border text-foreground"
              />
              {passwordError && (
                <p className="text-sm text-destructive">{passwordError}</p>
              )}
              {passwordSuccess && (
                <p className="text-sm text-success">Password changed successfully</p>
              )}
              <Button
                variant="outline"
                onClick={handleChangePassword}
                disabled={changePasswordMutation.isPending}
                className="border-border text-foreground bg-transparent hover:bg-muted"
              >
                {changePasswordMutation.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Update Password
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="bg-card border-border">
        <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <CardTitle className="text-foreground flex items-center gap-2">
              <Key className="h-5 w-5 text-warning" />
              API Keys
            </CardTitle>
            <CardDescription className="text-muted-foreground">
              Manage your personal API keys for programmatic access
            </CardDescription>
          </div>
          <Button onClick={() => setShowCreateTokenModal(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Create API Key
          </Button>
        </CardHeader>
        <CardContent>
          {isLoadingKeys ? (
            <div className="space-y-4">
              {[...Array(2)].map((_, i) => (
                <div key={i} className="flex items-center gap-4 p-4 rounded-lg bg-muted/30">
                  <Skeleton className="h-10 w-10 rounded-lg" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-3 w-48" />
                  </div>
                </div>
              ))}
            </div>
          ) : keysError ? (
            <div className="p-8 text-center">
              <p className="text-destructive">Failed to load API keys</p>
            </div>
          ) : !apiKeys?.length ? (
            <div className="p-8 text-center">
              <Fingerprint className="mx-auto h-12 w-12 text-muted-foreground" />
              <h3 className="mt-4 text-lg font-semibold text-foreground">No API keys</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                Create an API key for CLI access or integrations
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {apiKeys.map((key) => (
                <div
                  key={key.keyId}
                  className="flex items-center gap-4 p-4 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors group"
                >
                  <div className="rounded-lg bg-warning/20 p-2.5">
                    <Fingerprint className="h-5 w-5 text-warning" />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-foreground">{key.name}</div>
                    <div className="mt-1 flex items-center gap-3 text-sm text-muted-foreground flex-wrap">
                      <span className="font-mono">{key.keyId.slice(0, 12)}...</span>
                      <span>Created {formatRelativeTime(new Date(key.createdAt))}</span>
                    </div>
                  </div>

                  <div className="hidden md:flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock className="h-4 w-4" />
                    <span>
                      {key.expiresAt
                        ? `Expires ${formatDateTime(key.expiresAt)}`
                        : 'Never expires'}
                    </span>
                  </div>

                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => copyToken(key.keyId, key.keyId)}
                    className="text-muted-foreground hover:text-foreground"
                  >
                    {copiedId === key.keyId ? (
                      <Check className="h-4 w-4 text-success" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>

                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRevokeKey(key.keyId)}
                    disabled={revokeMutation.isPending}
                    className="text-destructive hover:text-destructive hover:bg-destructive/10 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={showCreateTokenModal} onOpenChange={setShowCreateTokenModal}>
        <DialogContent className="bg-popover border-border text-foreground max-w-md">
          <DialogHeader>
            <DialogTitle>Create API Key</DialogTitle>
            <DialogDescription className="text-muted-foreground">
              Generate a new API key for CLI access or integrations.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="tokenName" className="text-foreground">
                Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="tokenName"
                placeholder="e.g., CLI Access"
                value={tokenName}
                onChange={(e) => setTokenName(e.target.value)}
                className="bg-background border-border text-foreground"
              />
            </div>

            <div className="space-y-2">
              <Label className="text-foreground">Expiration</Label>
              <div className="flex gap-2 flex-wrap">
                {['30', '90', '365', 'never'].map((days) => (
                  <Button
                    key={days}
                    type="button"
                    variant={tokenExpiryDays === days ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setTokenExpiryDays(days)}
                    className={
                      tokenExpiryDays !== days
                        ? 'border-border text-foreground hover:bg-muted bg-transparent'
                        : ''
                    }
                  >
                    {days === 'never' ? 'Never' : `${days} days`}
                  </Button>
                ))}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowCreateTokenModal(false)}
              className="border-border text-foreground hover:bg-muted bg-transparent"
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateToken}
              disabled={!tokenName.trim() || createMutation.isPending}
            >
              {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              <Key className="mr-2 h-4 w-4" />
              Generate
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showTokenResult} onOpenChange={setShowTokenResult}>
        <DialogContent className="bg-popover border-border text-foreground max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Check className="h-5 w-5 text-success" />
              API Key Created
            </DialogTitle>
            <DialogDescription className="text-muted-foreground">
              Copy your key now. You won't be able to see it again.
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            <div className="p-4 rounded-lg bg-muted/60 border border-border">
              <div className="flex items-center justify-between gap-2">
                <code className="text-success text-sm break-all flex-1">{generatedToken}</code>
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-muted-foreground hover:text-foreground shrink-0"
                  onClick={() => copyToken(generatedToken)}
                >
                  {copiedToken ? (
                    <Check className="h-4 w-4 text-success" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>

            <div className="flex items-start gap-2 mt-4 p-3 rounded-lg bg-warning/10 border border-warning/20">
              <AlertTriangle className="h-5 w-5 text-warning shrink-0 mt-0.5" />
              <div>
                <p className="text-sm text-warning font-medium">Important</p>
                <p className="text-xs text-warning/80">
                  Make sure to copy your key now. For security reasons, it won't be shown again.
                </p>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button onClick={() => setShowTokenResult(false)} className="w-full">
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
