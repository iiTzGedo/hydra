import { useEffect, useState } from 'react';
import { RefreshCw, Save } from 'lucide-react';
import { toast } from 'sonner';
import { useSystemSettings, useUpdateSystemSettings } from '@/api/settings';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';

export function AgentSettings() {
  const { data: settings } = useSystemSettings();
  const updateSystemSettings = useUpdateSystemSettings();

  const [form, setForm] = useState({
    enabled: false,
    endpoint: '',
    bucket: 'hydra-bucket',
    region: 'garage',
  });

  useEffect(() => {
    if (!settings) return;
    setForm({
      enabled: settings.objectStorage.enabled,
      endpoint: settings.objectStorage.endpoint || '',
      bucket: settings.objectStorage.bucket,
      region: settings.objectStorage.region,
    });
  }, [settings]);

  const handleSave = async () => {
    if (!settings) return;
    try {
      await updateSystemSettings.mutateAsync({
        objectStorage: {
          enabled: form.enabled,
          endpoint: form.endpoint || undefined,
          bucket: form.bucket,
          region: form.region,
        },
      });
      toast.success('Agent storage settings updated');
    } catch {
      toast.error('Failed to update agent storage settings');
    }
  };

  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-4">
        <CardTitle className="text-foreground flex items-center gap-2 text-base">
          <RefreshCw className="h-4 w-4 text-success" />
          Agent Storage
        </CardTitle>
        <CardDescription className="text-muted-foreground text-xs">
          Configure object storage for agent binaries
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between py-1">
          <div>
            <p className="text-foreground text-sm font-medium">Enable storage</p>
            <p className="text-xs text-muted-foreground">Use object storage for binaries</p>
          </div>
          <Switch
            checked={form.enabled}
            onCheckedChange={(checked) => setForm((prev) => ({ ...prev, enabled: checked }))}
          />
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label className="text-foreground text-sm">Endpoint</Label>
            <Input
              value={form.endpoint}
              onChange={(e) => setForm((prev) => ({ ...prev, endpoint: e.target.value }))}
              className="bg-muted border-border text-foreground h-9"
              placeholder="https://storage.example.com"
            />
          </div>
          <div className="space-y-2">
            <Label className="text-foreground text-sm">Region</Label>
            <Input
              value={form.region}
              onChange={(e) => setForm((prev) => ({ ...prev, region: e.target.value }))}
              className="bg-muted border-border text-foreground h-9"
              placeholder="garage"
            />
          </div>
          <div className="space-y-2">
            <Label className="text-foreground text-sm">Bucket</Label>
            <Input
              value={form.bucket}
              onChange={(e) => setForm((prev) => ({ ...prev, bucket: e.target.value }))}
              className="bg-muted border-border text-foreground h-9"
              placeholder="hydra-bucket"
            />
          </div>
        </div>
        <Separator className="bg-muted" />
        <Button className="" onClick={handleSave} disabled={updateSystemSettings.isPending}>
          <Save className="mr-2 h-4 w-4" />
          Save Agent Settings
        </Button>
      </CardContent>
    </Card>
  );
}
