import { useState } from 'react';
import { Key, Plus, Copy, Check, Loader2, Users, Server } from 'lucide-react';
import { useCreateToken } from '@/api/auth';
import type { Role } from '@/types/user';
import { ROLE_LABELS } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

export function RegistrationTokens() {
  const createMutation = useCreateToken();

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newToken, setNewToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [scope, setScope] = useState<'user' | 'node'>('user');
  const [maxUses, setMaxUses] = useState('1');
  const [expiresInDays, setExpiresInDays] = useState('7');
  const [allowedRoles, setAllowedRoles] = useState<Role[]>(['viewer']);

  const handleCreate = async () => {
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

  const handleCloseModal = () => {
    setShowCreateForm(false);
    setNewToken(null);
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-medium text-foreground">Registration Tokens</h3>
          <p className="text-sm text-muted-foreground">Create tokens for user and node registration</p>
        </div>
        <Button
          onClick={() => setShowCreateForm(true)}
          className=""
        >
          <Plus className="mr-2 h-4 w-4" />
          Create Token
        </Button>
      </div>

      <Dialog open={showCreateForm} onOpenChange={handleCloseModal}>
        <DialogContent className="sm:max-w-md bg-card border-border text-foreground">
          {newToken ? (
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
                <Check className="h-6 w-6 text-success" />
              </div>
              <DialogHeader className="mt-4">
                <DialogTitle className="text-foreground">Token Created</DialogTitle>
                <DialogDescription className="text-muted-foreground">
                  Copy this token now. It won't be shown again.
                </DialogDescription>
              </DialogHeader>
              <div className="mt-4 flex items-center gap-2 rounded-lg bg-muted p-3">
                <code className="flex-1 text-sm font-mono break-all text-left text-success">
                  {newToken}
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
                <DialogTitle className="text-foreground">Create Registration Token</DialogTitle>
              </DialogHeader>

              <div className="space-y-4">
                <div className="space-y-2">
                  <Label className="text-foreground">Token Scope</Label>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant={scope === 'user' ? 'default' : 'outline'}
                      onClick={() => setScope('user')}
                      className={cn(
                        'flex-1',
                        scope === 'user'
                          ? ''
                          : 'border-border text-foreground hover:bg-muted bg-transparent'
                      )}
                    >
                      <Users className="mr-2 h-4 w-4" />
                      User
                    </Button>
                    <Button
                      type="button"
                      variant={scope === 'node' ? 'default' : 'outline'}
                      onClick={() => setScope('node')}
                      className={cn(
                        'flex-1',
                        scope === 'node'
                          ? ''
                          : 'border-border text-foreground hover:bg-muted bg-transparent'
                      )}
                    >
                      <Server className="mr-2 h-4 w-4" />
                      Node
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="maxUses" className="text-foreground">
                    Max Uses
                  </Label>
                  <Input
                    id="maxUses"
                    type="number"
                    value={maxUses}
                    onChange={(e) => setMaxUses(e.target.value)}
                    min="1"
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

                {scope === 'user' && (
                  <div className="space-y-2">
                    <Label className="text-foreground">Allowed Roles</Label>
                    <div className="flex flex-wrap gap-2">
                      {(['admin', 'operator', 'viewer', 'family'] as Role[]).map((role) => (
                        <Badge
                          key={role}
                          variant={allowedRoles.includes(role) ? 'default' : 'outline'}
                          className={cn(
                            'cursor-pointer transition-colors',
                            allowedRoles.includes(role)
                              ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                              : 'border-border text-muted-foreground hover:bg-muted'
                          )}
                          onClick={() => toggleRole(role)}
                        >
                          {ROLE_LABELS[role]}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
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
                  disabled={createMutation.isPending}
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

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-foreground flex items-center gap-2">
            <Key className="h-5 w-5 text-warning" />
            Token Information
          </CardTitle>
          <CardDescription className="text-muted-foreground">
            About registration tokens
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          <p>
            Registration tokens can be created here. Token listing and revocation are not available
            in API v0.3.0, so store tokens securely when created.
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="p-4 rounded-lg bg-muted/60 border border-border">
              <div className="flex items-center gap-2 text-foreground font-medium mb-2">
                <Users className="h-4 w-4 text-primary" />
                User Tokens
              </div>
              <p className="text-xs text-muted-foreground">
                Allow new users to register accounts with specified roles.
              </p>
            </div>
            <div className="p-4 rounded-lg bg-muted/60 border border-border">
              <div className="flex items-center gap-2 text-foreground font-medium mb-2">
                <Server className="h-4 w-4 text-success" />
                Node Tokens
              </div>
              <p className="text-xs text-muted-foreground">
                Allow Hydra agents to register new nodes to the system.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
