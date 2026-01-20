import { RefreshCw, Save } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

export function AgentSettings() {
  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-4">
        <CardTitle className="text-foreground flex items-center gap-2 text-base">
          <RefreshCw className="h-4 w-4 text-success" />
          Agent Configuration
        </CardTitle>
        <CardDescription className="text-muted-foreground text-xs">
          Settings for Hydra agents
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-4">
            <div className="grid gap-4 grid-cols-2">
              <div className="space-y-2">
                <Label className="text-foreground text-sm">Profile Capture</Label>
                <Select defaultValue="60">
                  <SelectTrigger className="bg-muted border-border text-foreground h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-popover border-border">
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
          </div>
          <div className="space-y-4">
            <div className="flex items-center justify-between py-1">
              <div>
                <p className="text-foreground text-sm font-medium">Service discovery</p>
                <p className="text-xs text-muted-foreground">Auto-detect running services</p>
              </div>
              <Switch defaultChecked />
            </div>
            <div className="flex items-center justify-between py-1">
              <div>
                <p className="text-foreground text-sm font-medium">Network scanning</p>
                <p className="text-xs text-muted-foreground">Discover network topology</p>
              </div>
              <Switch defaultChecked />
            </div>
            <div className="flex items-center justify-between py-1">
              <div>
                <p className="text-foreground text-sm font-medium">Debug mode</p>
                <p className="text-xs text-muted-foreground">Verbose logging for agents</p>
              </div>
              <Switch />
            </div>
          </div>
        </div>
        <Separator className="bg-muted" />
        <Button className="">
          <Save className="mr-2 h-4 w-4" />
          Save Agent Settings
        </Button>
      </CardContent>
    </Card>
  );
}
