import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useStartInstallation } from '@/api/discovery';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { getErrorMessage } from '@/lib/api-client';
import type { DiscoveredDevice, StartInstallationRequest } from '@/types/discovery';

type AuthMethod = 'password' | 'key';

interface InstallDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  device: DiscoveredDevice | null;
  onSuccess?: (installationId: string) => void;
}

const AGENT_TIER_OPTIONS = [
  { value: 'lite', label: 'Lite' },
  { value: 'normal', label: 'Normal' },
  { value: 'max', label: 'Max' },
];

export function InstallDialog({
  open,
  onOpenChange,
  device,
  onSuccess,
}: InstallDialogProps) {
  const startInstallation = useStartInstallation();

  const [authMethod, setAuthMethod] = useState<AuthMethod>('password');
  const [form, setForm] = useState({
    host: '',
    port: '22',
    username: 'root',
    password: '',
    privateKey: '',
    passphrase: '',
    agentTier: 'normal',
  });

  // Pre-fill host from device when dialog opens
  const effectiveHost = form.host || device?.identity.currentIp || '';

  const handleSubmit = async () => {
    const host = effectiveHost.trim();
    if (!host) {
      toast.error('Host address is required.');
      return;
    }
    if (!form.username.trim()) {
      toast.error('Username is required.');
      return;
    }
    if (authMethod === 'password' && !form.password) {
      toast.error('Password is required when using password authentication.');
      return;
    }
    if (authMethod === 'key' && !form.privateKey.trim()) {
      toast.error('Private key is required when using SSH key authentication.');
      return;
    }

    const request: StartInstallationRequest = {
      discoveryId: device?.discoveryId,
      targetIp: device ? undefined : host,
      credentials: {
        host,
        port: Number(form.port) || 22,
        username: form.username.trim(),
        ...(authMethod === 'password'
          ? { password: form.password }
          : {
              privateKey: form.privateKey.trim(),
              ...(form.passphrase ? { passphrase: form.passphrase } : {}),
            }),
      },
      agentTier: form.agentTier,
    };

    try {
      const result = await startInstallation.mutateAsync(request);
      toast.success(`Installation started for ${host}.`);
      onOpenChange(false);
      resetForm();
      onSuccess?.(result.installationId);
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to start installation.'));
    }
  };

  const resetForm = () => {
    setForm({
      host: '',
      port: '22',
      username: 'root',
      password: '',
      privateKey: '',
      passphrase: '',
      agentTier: 'normal',
    });
    setAuthMethod('password');
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        onOpenChange(value);
        if (!value) resetForm();
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Install Agent via SSH</DialogTitle>
          <DialogDescription>
            {device
              ? `Deploy the Hydra agent on ${device.identity.hostname || device.identity.currentIp}.`
              : 'Deploy the Hydra agent on a remote host via SSH.'}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="install-host">Host</Label>
              <Input
                id="install-host"
                value={form.host || device?.identity.currentIp || ''}
                onChange={(e) => setForm((f) => ({ ...f, host: e.target.value }))}
                placeholder="192.168.1.100"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="install-port">Port</Label>
              <Input
                id="install-port"
                type="number"
                value={form.port}
                onChange={(e) => setForm((f) => ({ ...f, port: e.target.value }))}
                placeholder="22"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="install-username">Username</Label>
            <Input
              id="install-username"
              value={form.username}
              onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
              placeholder="root"
            />
          </div>

          <div className="space-y-2">
            <Label>Authentication Method</Label>
            <Select
              value={authMethod}
              onValueChange={(value) => setAuthMethod(value as AuthMethod)}
            >
              <SelectTrigger aria-label="Authentication method">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="password">Password</SelectItem>
                <SelectItem value="key">SSH Key</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {authMethod === 'password' ? (
            <div className="space-y-2">
              <Label htmlFor="install-password">Password</Label>
              <Input
                id="install-password"
                type="password"
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                placeholder="SSH password"
              />
            </div>
          ) : (
            <>
              <div className="space-y-2">
                <Label htmlFor="install-private-key">Private Key</Label>
                <Textarea
                  id="install-private-key"
                  rows={4}
                  value={form.privateKey}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, privateKey: e.target.value }))
                  }
                  placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
                  className="font-mono text-xs"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="install-passphrase">Passphrase (optional)</Label>
                <Input
                  id="install-passphrase"
                  type="password"
                  value={form.passphrase}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, passphrase: e.target.value }))
                  }
                  placeholder="Key passphrase"
                />
              </div>
            </>
          )}

          <div className="space-y-2">
            <Label>Agent Tier</Label>
            <Select
              value={form.agentTier}
              onValueChange={(value) => setForm((f) => ({ ...f, agentTier: value }))}
            >
              <SelectTrigger aria-label="Agent tier">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {AGENT_TIER_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={startInstallation.isPending}>
            {startInstallation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Start Installation
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
