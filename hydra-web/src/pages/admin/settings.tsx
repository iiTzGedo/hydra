import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Save, RefreshCw, Shield, Bell, Globe } from 'lucide-react';

export default function AdminSettingsPage() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-semibold text-foreground">Settings</h2>
          <p className="text-sm text-muted-foreground">Configure system settings and preferences</p>
        </div>
        <Button>
          <Save className="mr-2 h-4 w-4" />
          Save Changes
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* General Settings */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-4">
            <CardTitle className="text-foreground flex items-center gap-2 text-base">
              <Globe className="h-4 w-4 text-blue-500" />
              General
            </CardTitle>
            <CardDescription className="text-muted-foreground text-xs">
              Basic system configuration
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label className="text-foreground text-sm">Instance Name</Label>
              <Input
                defaultValue="Hydra Production"
                className="bg-muted border-border text-foreground h-9"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-foreground text-sm">Base URL</Label>
              <Input
                defaultValue="https://hydra.example.com"
                className="bg-muted border-border text-foreground h-9"
              />
            </div>
            <div className="grid gap-4 grid-cols-2">
              <div className="space-y-2">
                <Label className="text-foreground text-sm">Timezone</Label>
                <Select defaultValue="utc">
                  <SelectTrigger className="bg-muted border-border text-foreground h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-muted border-border">
                    <SelectItem value="utc">UTC</SelectItem>
                    <SelectItem value="est">Eastern Time</SelectItem>
                    <SelectItem value="pst">Pacific Time</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-foreground text-sm">Language</Label>
                <Select defaultValue="en">
                  <SelectTrigger className="bg-muted border-border text-foreground h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-muted border-border">
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="es">Spanish</SelectItem>
                    <SelectItem value="de">German</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Agent Configuration */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-4">
            <CardTitle className="text-foreground flex items-center gap-2 text-base">
              <RefreshCw className="h-4 w-4 text-emerald-500" />
              Agent Configuration
            </CardTitle>
            <CardDescription className="text-muted-foreground text-xs">
              Settings for Hydra agents
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 grid-cols-2">
              <div className="space-y-2">
                <Label className="text-foreground text-sm">Profile Capture</Label>
                <Select defaultValue="60">
                  <SelectTrigger className="bg-muted border-border text-foreground h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-muted border-border">
                    <SelectItem value="30">30 minutes</SelectItem>
                    <SelectItem value="60">1 hour</SelectItem>
                    <SelectItem value="360">6 hours</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-foreground text-sm">Heartbeat (sec)</Label>
                <Input
                  type="number"
                  defaultValue="30"
                  className="bg-muted border-border text-foreground h-9"
                />
              </div>
            </div>
            <div className="flex items-center justify-between py-1">
              <div>
                <p className="text-foreground text-sm font-medium">Auto-register agents</p>
                <p className="text-xs text-muted-foreground">Auto approve new registrations</p>
              </div>
              <Switch />
            </div>
            <div className="flex items-center justify-between py-1">
              <div>
                <p className="text-foreground text-sm font-medium">Collect packages</p>
                <p className="text-xs text-muted-foreground">Include in node profiles</p>
              </div>
              <Switch defaultChecked />
            </div>
          </CardContent>
        </Card>

        {/* Notifications */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-4">
            <CardTitle className="text-foreground flex items-center gap-2 text-base">
              <Bell className="h-4 w-4 text-amber-500" />
              Notifications
            </CardTitle>
            <CardDescription className="text-muted-foreground text-xs">
              Alert and notification preferences
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
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
            <Separator className="bg-muted" />
            <div className="space-y-3">
              <p className="text-xs text-muted-foreground">Alert thresholds</p>
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
          </CardContent>
        </Card>

        {/* Security */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-4">
            <CardTitle className="text-foreground flex items-center gap-2 text-base">
              <Shield className="h-4 w-4 text-red-500" />
              Security
            </CardTitle>
            <CardDescription className="text-muted-foreground text-xs">
              Authentication and access control
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between py-1">
              <div>
                <p className="text-foreground text-sm font-medium">Two-factor auth</p>
                <p className="text-xs text-muted-foreground">Require 2FA for all users</p>
              </div>
              <Switch />
            </div>
            <div className="flex items-center justify-between py-1">
              <div>
                <p className="text-foreground text-sm font-medium">Session timeout</p>
                <p className="text-xs text-muted-foreground">Auto logout after inactivity</p>
              </div>
              <Select defaultValue="60">
                <SelectTrigger className="w-[100px] bg-muted border-border text-foreground h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-muted border-border">
                  <SelectItem value="30">30 min</SelectItem>
                  <SelectItem value="60">1 hour</SelectItem>
                  <SelectItem value="480">8 hours</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between py-1">
              <div>
                <p className="text-foreground text-sm font-medium">API rate limiting</p>
                <p className="text-xs text-muted-foreground">Limit requests per minute</p>
              </div>
              <Switch defaultChecked />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
