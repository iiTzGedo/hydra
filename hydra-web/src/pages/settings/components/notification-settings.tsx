import { Bell, Save } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';

export function NotificationSettings() {
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
              <Switch defaultChecked />
            </div>
            <div className="flex items-center justify-between py-1">
              <div>
                <p className="text-foreground text-sm font-medium">Slack integration</p>
                <p className="text-xs text-muted-foreground">Send alerts to Slack</p>
              </div>
              <Switch />
            </div>
            <div className="flex items-center justify-between py-1">
              <div>
                <p className="text-foreground text-sm font-medium">Webhook notifications</p>
                <p className="text-xs text-muted-foreground">POST alerts to custom URL</p>
              </div>
              <Switch />
            </div>
          </div>
          <div className="space-y-4">
            <p className="text-xs text-muted-foreground font-medium">Alert Thresholds</p>
            <div className="grid gap-3 grid-cols-3">
              <div className="space-y-1">
                <Label className="text-foreground text-xs">CPU %</Label>
                <Input
                  type="number"
                  defaultValue="80"
                  className="bg-muted border-border text-foreground h-8"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-foreground text-xs">Memory %</Label>
                <Input
                  type="number"
                  defaultValue="85"
                  className="bg-muted border-border text-foreground h-8"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-foreground text-xs">Disk %</Label>
                <Input
                  type="number"
                  defaultValue="90"
                  className="bg-muted border-border text-foreground h-8"
                />
              </div>
            </div>
          </div>
        </div>
        <Separator className="bg-muted" />
        <Button className="">
          <Save className="mr-2 h-4 w-4" />
          Save Notification Settings
        </Button>
      </CardContent>
    </Card>
  );
}
