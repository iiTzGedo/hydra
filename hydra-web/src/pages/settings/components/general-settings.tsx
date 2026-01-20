import { Globe, Settings, Save } from 'lucide-react';
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

export function GeneralSettings() {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card className="bg-card border-border">
        <CardHeader className="pb-4">
          <CardTitle className="text-foreground flex items-center gap-2 text-base">
            <Globe className="h-4 w-4 text-primary" />
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
                <SelectContent className="bg-popover border-border">
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
                <SelectContent className="bg-popover border-border">
                  <SelectItem value="en">English</SelectItem>
                  <SelectItem value="es">Spanish</SelectItem>
                  <SelectItem value="de">German</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <Button className="w-full mt-4">
            <Save className="mr-2 h-4 w-4" />
            Save Changes
          </Button>
        </CardContent>
      </Card>

      {/* Theme Settings */}
      <Card className="bg-card border-border">
        <CardHeader className="pb-4">
          <CardTitle className="text-foreground flex items-center gap-2 text-base">
            <Settings className="h-4 w-4 text-purple-500" />
            Appearance
          </CardTitle>
          <CardDescription className="text-muted-foreground text-xs">
            Customize the look and feel
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between py-1">
            <div>
              <p className="text-foreground text-sm font-medium">Dark Mode</p>
              <p className="text-xs text-muted-foreground">Use dark theme</p>
            </div>
            <Switch defaultChecked />
          </div>
          <div className="flex items-center justify-between py-1">
            <div>
              <p className="text-foreground text-sm font-medium">Compact View</p>
              <p className="text-xs text-muted-foreground">Reduce spacing in lists</p>
            </div>
            <Switch />
          </div>
          <div className="flex items-center justify-between py-1">
            <div>
              <p className="text-foreground text-sm font-medium">Show Animations</p>
              <p className="text-xs text-muted-foreground">Enable page transitions</p>
            </div>
            <Switch defaultChecked />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
