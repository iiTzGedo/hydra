import { useEffect, useState } from 'react';
import { Shield, Save } from 'lucide-react';
import { toast } from 'sonner';
import { useSystemSettings, useUpdateSystemSettings } from '@/api/settings';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const nodeStatusOptions = ['active', 'inactive', 'pending'];

export function SecuritySettings() {
  const { data: settings } = useSystemSettings();
  const updateSystemSettings = useUpdateSystemSettings();

  const [form, setForm] = useState({
    sessionTimeoutMinutes: 60,
    profileRetentionDays: 90,
    nodeStatus: 'active',
  });

  useEffect(() => {
    if (!settings) return;
    setForm({
      sessionTimeoutMinutes: settings.defaults.sessionTimeoutMinutes,
      profileRetentionDays: settings.defaults.profileRetentionDays,
      nodeStatus: settings.defaults.nodeStatus,
    });
  }, [settings]);

  const handleSave = async () => {
    if (!settings) return;
    try {
      await updateSystemSettings.mutateAsync({
        defaults: {
          sessionTimeoutMinutes: form.sessionTimeoutMinutes,
          profileRetentionDays: form.profileRetentionDays,
          nodeStatus: form.nodeStatus,
        },
      });
      toast.success('Security defaults updated');
    } catch {
      toast.error('Failed to update security defaults');
    }
  };

  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-4">
        <CardTitle className="text-foreground flex items-center gap-2 text-base">
          <Shield className="h-4 w-4 text-destructive" />
          Security Defaults
        </CardTitle>
        <CardDescription className="text-muted-foreground text-xs">
          Default security settings for new sessions and nodes
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-foreground text-sm">Session timeout (minutes)</Label>
              <Select
                value={String(form.sessionTimeoutMinutes)}
                onValueChange={(value) =>
                  setForm((prev) => ({ ...prev, sessionTimeoutMinutes: Number(value) }))
                }
              >
                <SelectTrigger className="w-[140px] bg-muted border-border text-foreground h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-popover border-border">
                  <SelectItem value="30">30 min</SelectItem>
                  <SelectItem value="60">1 hour</SelectItem>
                  <SelectItem value="480">8 hours</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="text-foreground text-sm">Profile retention (days)</Label>
              <Input
                type="number"
                min={1}
                value={form.profileRetentionDays}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    profileRetentionDays: Number(e.target.value || 0),
                  }))
                }
                className="bg-muted border-border text-foreground h-9"
              />
            </div>
          </div>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-foreground text-sm">Default node status</Label>
              <Select
                value={form.nodeStatus}
                onValueChange={(value) =>
                  setForm((prev) => ({ ...prev, nodeStatus: value }))
                }
              >
                <SelectTrigger className="bg-muted border-border text-foreground h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-popover border-border">
                  {nodeStatusOptions.map((status) => (
                    <SelectItem key={status} value={status}>
                      {status}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>
        <Separator className="bg-muted" />
        <Button className="" onClick={handleSave} disabled={updateSystemSettings.isPending}>
          <Save className="mr-2 h-4 w-4" />
          Save Security Defaults
        </Button>
      </CardContent>
    </Card>
  );
}
