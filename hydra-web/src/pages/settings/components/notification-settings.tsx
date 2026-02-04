import { useEffect, useState } from 'react';
import {
  Bell,
  Clock,
  Mail,
  Monitor,
  Save,
  Server,
  Shield,
  Terminal,
  Cpu,
  Network,
} from 'lucide-react';
import { toast } from 'sonner';
import { useUpdateUserSettings, useUserSettings } from '@/api/settings';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { Slider } from '@/components/ui/slider';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';

const TIER_LABELS: Record<number, { label: string; color: string }> = {
  1: { label: 'User (Low)', color: 'text-blue-400' },
  2: { label: 'System (Green)', color: 'text-green-400' },
  3: { label: 'Warning', color: 'text-yellow-400' },
  4: { label: 'High', color: 'text-orange-400' },
  5: { label: 'Critical', color: 'text-red-400' },
};

interface NotificationForm {
  // Delivery channels
  emailEnabled: boolean;
  browserEnabled: boolean;
  // Minimum tiers
  browserMinTier: number;
  emailMinTier: number;
  // Category toggles
  nodeNotifications: boolean;
  serviceNotifications: boolean;
  profileNotifications: boolean;
  securityNotifications: boolean;
  systemNotifications: boolean;
  commandNotifications: boolean;
  // Quiet hours
  quietHoursEnabled: boolean;
  quietHoursStart: string;
  quietHoursEnd: string;
  quietHoursMinTier: number;
}

const DEFAULT_FORM: NotificationForm = {
  emailEnabled: true,
  browserEnabled: true,
  browserMinTier: 3,
  emailMinTier: 4,
  nodeNotifications: true,
  serviceNotifications: true,
  profileNotifications: false,
  securityNotifications: true,
  systemNotifications: true,
  commandNotifications: true,
  quietHoursEnabled: false,
  quietHoursStart: '22:00',
  quietHoursEnd: '07:00',
  quietHoursMinTier: 5,
};

function TierBadge({ tier }: { tier: number }) {
  const info = TIER_LABELS[tier] || TIER_LABELS[3];
  return (
    <Badge variant="outline" className={`${info.color} border-current text-xs`}>
      {info.label}
    </Badge>
  );
}

export function NotificationSettings() {
  const { data: settings } = useUserSettings();
  const updateUserSettings = useUpdateUserSettings();

  const [form, setForm] = useState<NotificationForm>(DEFAULT_FORM);

  useEffect(() => {
    if (!settings) return;
    const n = settings.notifications;
    setForm({
      emailEnabled: n.emailEnabled ?? DEFAULT_FORM.emailEnabled,
      browserEnabled: n.browserEnabled ?? DEFAULT_FORM.browserEnabled,
      browserMinTier: n.browserMinTier ?? DEFAULT_FORM.browserMinTier,
      emailMinTier: n.emailMinTier ?? DEFAULT_FORM.emailMinTier,
      nodeNotifications: n.nodeNotifications ?? DEFAULT_FORM.nodeNotifications,
      serviceNotifications: n.serviceNotifications ?? DEFAULT_FORM.serviceNotifications,
      profileNotifications: n.profileNotifications ?? DEFAULT_FORM.profileNotifications,
      securityNotifications: n.securityNotifications ?? DEFAULT_FORM.securityNotifications,
      systemNotifications: n.systemNotifications ?? DEFAULT_FORM.systemNotifications,
      commandNotifications: n.commandNotifications ?? DEFAULT_FORM.commandNotifications,
      quietHoursEnabled: n.quietHoursEnabled ?? DEFAULT_FORM.quietHoursEnabled,
      quietHoursStart: n.quietHoursStart ?? DEFAULT_FORM.quietHoursStart,
      quietHoursEnd: n.quietHoursEnd ?? DEFAULT_FORM.quietHoursEnd,
      quietHoursMinTier: n.quietHoursMinTier ?? DEFAULT_FORM.quietHoursMinTier,
    });
  }, [settings]);

  const update = <K extends keyof NotificationForm>(key: K, value: NotificationForm[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    if (!settings) return;
    try {
      await updateUserSettings.mutateAsync({
        notifications: {
          emailEnabled: form.emailEnabled,
          browserEnabled: form.browserEnabled,
          browserMinTier: form.browserMinTier,
          emailMinTier: form.emailMinTier,
          nodeNotifications: form.nodeNotifications,
          serviceNotifications: form.serviceNotifications,
          profileNotifications: form.profileNotifications,
          securityNotifications: form.securityNotifications,
          systemNotifications: form.systemNotifications,
          commandNotifications: form.commandNotifications,
          quietHoursEnabled: form.quietHoursEnabled,
          quietHoursStart: form.quietHoursStart,
          quietHoursEnd: form.quietHoursEnd,
          quietHoursMinTier: form.quietHoursMinTier,
        },
      });
      toast.success('Notification settings updated');
    } catch {
      toast.error('Failed to update notification settings');
    }
  };

  return (
    <div className="space-y-6">
      {/* Delivery Channels */}
      <Card className="bg-card border-border">
        <CardHeader className="pb-4">
          <CardTitle className="text-foreground flex items-center gap-2 text-base">
            <Bell className="h-4 w-4 text-warning" />
            Delivery Channels
          </CardTitle>
          <CardDescription className="text-muted-foreground text-xs">
            Configure how you receive notifications
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Browser */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Monitor className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-foreground text-sm font-medium">Browser notifications</p>
                  <p className="text-xs text-muted-foreground">Show in-app notification toasts</p>
                </div>
              </div>
              <Switch
                checked={form.browserEnabled}
                onCheckedChange={(checked) => update('browserEnabled', checked)}
              />
            </div>
            {form.browserEnabled && (
              <div className="ml-6 space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-xs text-muted-foreground">Minimum tier</Label>
                  <TierBadge tier={form.browserMinTier} />
                </div>
                <Slider
                  value={[form.browserMinTier]}
                  onValueChange={([v]) => update('browserMinTier', v)}
                  min={1}
                  max={5}
                  step={1}
                  className="w-full"
                />
                <p className="text-[11px] text-muted-foreground">
                  Only show notifications at or above this tier
                </p>
              </div>
            )}
          </div>

          <Separator className="bg-muted" />

          {/* Email */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Mail className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-foreground text-sm font-medium">Email notifications</p>
                  <p className="text-xs text-muted-foreground">Send notification digests via email</p>
                </div>
              </div>
              <Switch
                checked={form.emailEnabled}
                onCheckedChange={(checked) => update('emailEnabled', checked)}
              />
            </div>
            {form.emailEnabled && (
              <div className="ml-6 space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-xs text-muted-foreground">Minimum tier</Label>
                  <TierBadge tier={form.emailMinTier} />
                </div>
                <Slider
                  value={[form.emailMinTier]}
                  onValueChange={([v]) => update('emailMinTier', v)}
                  min={1}
                  max={5}
                  step={1}
                  className="w-full"
                />
                <p className="text-[11px] text-muted-foreground">
                  Only email notifications at or above this tier
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Category Toggles */}
      <Card className="bg-card border-border">
        <CardHeader className="pb-4">
          <CardTitle className="text-foreground flex items-center gap-2 text-base">
            <Server className="h-4 w-4 text-primary" />
            Categories
          </CardTitle>
          <CardDescription className="text-muted-foreground text-xs">
            Choose which notification categories you want to receive
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2">
            <ToggleRow
              icon={<Cpu className="h-4 w-4" />}
              label="Node events"
              description="Node registration, offline, recovery"
              checked={form.nodeNotifications}
              onChange={(v) => update('nodeNotifications', v)}
            />
            <ToggleRow
              icon={<Server className="h-4 w-4" />}
              label="Service events"
              description="Service discovered, state changes"
              checked={form.serviceNotifications}
              onChange={(v) => update('serviceNotifications', v)}
            />
            <ToggleRow
              icon={<Network className="h-4 w-4" />}
              label="Profile updates"
              description="New profiles, major changes"
              checked={form.profileNotifications}
              onChange={(v) => update('profileNotifications', v)}
            />
            <ToggleRow
              icon={<Shield className="h-4 w-4" />}
              label="Security events"
              description="Auth, API keys, brute force"
              checked={form.securityNotifications}
              onChange={(v) => update('securityNotifications', v)}
            />
            <ToggleRow
              icon={<Bell className="h-4 w-4" />}
              label="System events"
              description="Settings, topology, general"
              checked={form.systemNotifications}
              onChange={(v) => update('systemNotifications', v)}
            />
            <ToggleRow
              icon={<Terminal className="h-4 w-4" />}
              label="Command events"
              description="Execution results and timeouts"
              checked={form.commandNotifications}
              onChange={(v) => update('commandNotifications', v)}
            />
          </div>
        </CardContent>
      </Card>

      {/* Quiet Hours */}
      <Card className="bg-card border-border">
        <CardHeader className="pb-4">
          <CardTitle className="text-foreground flex items-center gap-2 text-base">
            <Clock className="h-4 w-4 text-muted-foreground" />
            Quiet Hours
          </CardTitle>
          <CardDescription className="text-muted-foreground text-xs">
            Suppress non-critical notifications during specific hours
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-foreground text-sm font-medium">Enable quiet hours</p>
              <p className="text-xs text-muted-foreground">
                Only critical notifications will be delivered during this window
              </p>
            </div>
            <Switch
              checked={form.quietHoursEnabled}
              onCheckedChange={(v) => update('quietHoursEnabled', v)}
            />
          </div>
          {form.quietHoursEnabled && (
            <div className="space-y-4 rounded-lg border border-border bg-muted/30 p-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">Start time</Label>
                  <Input
                    type="time"
                    value={form.quietHoursStart}
                    onChange={(e) => update('quietHoursStart', e.target.value)}
                    className="bg-background"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-xs text-muted-foreground">End time</Label>
                  <Input
                    type="time"
                    value={form.quietHoursEnd}
                    onChange={(e) => update('quietHoursEnd', e.target.value)}
                    className="bg-background"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-xs text-muted-foreground">
                    Minimum tier during quiet hours
                  </Label>
                  <TierBadge tier={form.quietHoursMinTier} />
                </div>
                <Slider
                  value={[form.quietHoursMinTier]}
                  onValueChange={([v]) => update('quietHoursMinTier', v)}
                  min={1}
                  max={5}
                  step={1}
                  className="w-full"
                />
                <p className="text-[11px] text-muted-foreground">
                  Only notifications at or above this tier will be delivered during quiet hours
                </p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Save */}
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={updateUserSettings.isPending}>
          <Save className="mr-2 h-4 w-4" />
          Save Notification Settings
        </Button>
      </div>
    </div>
  );
}

function ToggleRow({
  icon,
  label,
  description,
  checked,
  onChange,
}: {
  icon: React.ReactNode;
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border p-3">
      <div className="flex items-center gap-3">
        <div className="text-muted-foreground">{icon}</div>
        <div>
          <p className="text-foreground text-sm font-medium">{label}</p>
          <p className="text-xs text-muted-foreground">{description}</p>
        </div>
      </div>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  );
}
