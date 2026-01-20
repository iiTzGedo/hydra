import { useEffect, useState } from 'react';
import { Bell, Save } from 'lucide-react';
import { toast } from 'sonner';
import { useUpdateUserSettings, useUserSettings } from '@/api/settings';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';

export function NotificationSettings() {
  const { data: settings } = useUserSettings();
  const updateUserSettings = useUpdateUserSettings();

  const [form, setForm] = useState({
    emailEnabled: true,
    browserEnabled: true,
    nodeAlerts: true,
    serviceAlerts: true,
    profileUpdates: false,
  });

  useEffect(() => {
    if (!settings) return;
    setForm({
      emailEnabled: settings.notifications.emailEnabled,
      browserEnabled: settings.notifications.browserEnabled,
      nodeAlerts: settings.notifications.nodeAlerts,
      serviceAlerts: settings.notifications.serviceAlerts,
      profileUpdates: settings.notifications.profileUpdates,
    });
  }, [settings]);

  const handleSave = async () => {
    if (!settings) return;
    try {
      await updateUserSettings.mutateAsync({
        notifications: {
          emailEnabled: form.emailEnabled,
          browserEnabled: form.browserEnabled,
          nodeAlerts: form.nodeAlerts,
          serviceAlerts: form.serviceAlerts,
          profileUpdates: form.profileUpdates,
        },
      });
      toast.success('Notification settings updated');
    } catch (error) {
      toast.error('Failed to update notification settings');
    }
  };

  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-4">
        <CardTitle className="text-foreground flex items-center gap-2 text-base">
          <Bell className="h-4 w-4 text-warning" />
          Notifications
        </CardTitle>
        <CardDescription className="text-muted-foreground text-xs">
          Alert and notification preferences
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-4">
            <div className="flex items-center justify-between py-1">
              <div>
                <p className="text-foreground text-sm font-medium">Email notifications</p>
                <p className="text-xs text-muted-foreground">Send alerts via email</p>
              </div>
              <Switch
                checked={form.emailEnabled}
                onCheckedChange={(checked) =>
                  setForm((prev) => ({ ...prev, emailEnabled: checked }))
                }
              />
            </div>
            <div className="flex items-center justify-between py-1">
              <div>
                <p className="text-foreground text-sm font-medium">Browser notifications</p>
                <p className="text-xs text-muted-foreground">Show in-app alerts</p>
              </div>
              <Switch
                checked={form.browserEnabled}
                onCheckedChange={(checked) =>
                  setForm((prev) => ({ ...prev, browserEnabled: checked }))
                }
              />
            </div>
            <div className="flex items-center justify-between py-1">
              <div>
                <p className="text-foreground text-sm font-medium">Node alerts</p>
                <p className="text-xs text-muted-foreground">Changes in node status</p>
              </div>
              <Switch
                checked={form.nodeAlerts}
                onCheckedChange={(checked) =>
                  setForm((prev) => ({ ...prev, nodeAlerts: checked }))
                }
              />
            </div>
          </div>
          <div className="space-y-4">
            <div className="flex items-center justify-between py-1">
              <div>
                <p className="text-foreground text-sm font-medium">Service alerts</p>
                <p className="text-xs text-muted-foreground">Service status updates</p>
              </div>
              <Switch
                checked={form.serviceAlerts}
                onCheckedChange={(checked) =>
                  setForm((prev) => ({ ...prev, serviceAlerts: checked }))
                }
              />
            </div>
            <div className="flex items-center justify-between py-1">
              <div>
                <p className="text-foreground text-sm font-medium">Profile updates</p>
                <p className="text-xs text-muted-foreground">New profile submissions</p>
              </div>
              <Switch
                checked={form.profileUpdates}
                onCheckedChange={(checked) =>
                  setForm((prev) => ({ ...prev, profileUpdates: checked }))
                }
              />
            </div>
          </div>
        </div>
        <Separator className="bg-muted" />
        <Button className="" onClick={handleSave} disabled={updateUserSettings.isPending}>
          <Save className="mr-2 h-4 w-4" />
          Save Notification Settings
        </Button>
      </CardContent>
    </Card>
  );
}
