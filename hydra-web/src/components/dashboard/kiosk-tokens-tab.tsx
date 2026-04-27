/**
 * KioskTokensTab — manages kiosk display tokens for a dashboard board.
 *
 * Shows a create form (label + TTL preset), a one-time URL banner after
 * successful creation, and the list of active/revoked tokens.
 */

import { useState } from 'react';
import { Check, Copy, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useKioskTokens, useCreateKioskToken, useRevokeKioskToken } from '@/api/dashboards';

const TTL_PRESETS: { value: string; label: string }[] = [
  { value: '1', label: '1 hour' },
  { value: '24', label: '24 hours' },
  { value: '168', label: '7 days' },
  { value: '720', label: '30 days' },
  { value: 'never', label: 'Never expires' },
];

interface KioskTokensTabProps {
  boardId: string;
}

export function KioskTokensTab({ boardId }: KioskTokensTabProps) {
  const { data: tokens = [] } = useKioskTokens(boardId);
  const create = useCreateKioskToken(boardId);
  const revoke = useRevokeKioskToken(boardId);

  const [label, setLabel] = useState('');
  const [ttl, setTtl] = useState('168');
  const [newlyCreated, setNewlyCreated] = useState<{ url: string; label: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const handleCreate = async () => {
    const labelOrDefault = label.trim() || 'Kiosk display';
    const result = await create.mutateAsync({
      label: labelOrDefault,
      ttlHours: ttl === 'never' ? null : Number(ttl),
    });
    const url = `${window.location.origin}/kiosk/${boardId}?token=${result.token}`;
    setNewlyCreated({ url, label: result.label });
    setLabel('');
  };

  const handleCopy = async () => {
    if (!newlyCreated) return;
    await navigator.clipboard.writeText(newlyCreated.url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-4">
      {/* Create section */}
      <section className="space-y-3 rounded-md border p-4">
        <h4 className="text-sm font-medium">Create kiosk link</h4>
        <div className="space-y-2">
          <Label htmlFor="kiosk-label" className="text-xs">
            Label
          </Label>
          <Input
            id="kiosk-label"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Kitchen display"
          />
        </div>
        <div className="space-y-2">
          <Label className="text-xs">Expires</Label>
          <Select value={ttl} onValueChange={setTtl}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TTL_PRESETS.map((t) => (
                <SelectItem key={t.value} value={t.value}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button
          onClick={() => void handleCreate()}
          disabled={create.isPending}
          className="w-full"
        >
          {create.isPending ? 'Creating…' : 'Create link'}
        </Button>
      </section>

      {/* Newly-created token banner — one-time display */}
      {newlyCreated && (
        <div className="space-y-2 rounded-md border border-primary/30 bg-primary/5 p-4">
          <div className="text-sm font-medium">Kiosk URL — {newlyCreated.label}</div>
          <p className="text-xs text-muted-foreground">
            Copy this URL now. It cannot be retrieved later.
          </p>
          <div className="flex gap-2">
            <Input
              value={newlyCreated.url}
              readOnly
              className="font-mono text-xs"
              data-testid="kiosk-token-url-input"
            />
            <Button size="sm" onClick={() => void handleCopy()} aria-label="Copy URL">
              {copied ? (
                <Check className="h-4 w-4" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </Button>
          </div>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setNewlyCreated(null)}
          >
            Done
          </Button>
        </div>
      )}

      {/* Active tokens list */}
      <section>
        <h4 className="mb-2 text-sm font-medium">Active kiosk displays</h4>
        {tokens.length === 0 ? (
          <p className="text-xs text-muted-foreground">No kiosk displays created yet.</p>
        ) : (
          <ul className="space-y-2">
            {tokens.map((t) => {
              const isRevoked = !!t.revokedAt;
              const expiryLabel = t.expiresAt
                ? `Expires ${new Date(t.expiresAt).toLocaleString()}`
                : 'Never expires';
              return (
                <li
                  key={t.tokenId}
                  className="flex items-center gap-2 rounded-md border p-2 text-sm"
                >
                  <div className="flex-1">
                    <div className="font-medium">{t.label}</div>
                    <div className="text-xs text-muted-foreground">
                      {isRevoked ? 'Revoked' : expiryLabel}
                      {t.lastUsedAt &&
                        ` • Last used ${new Date(t.lastUsedAt).toLocaleString()}`}
                    </div>
                  </div>
                  {!isRevoked && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-destructive hover:bg-destructive/10"
                      onClick={() => revoke.mutate(t.tokenId)}
                      aria-label={`Revoke ${t.label}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
