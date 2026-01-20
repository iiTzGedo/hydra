import { Shield, Save } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

export function SecuritySettings() {
  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-4">
        <CardTitle className="text-foreground flex items-center gap-2 text-base">
          <Shield className="h-4 w-4 text-destructive" />
          Security
        </CardTitle>
        <CardDescription className="text-muted-foreground text-xs">
          Authentication and access control
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-4">
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
                <SelectContent className="bg-popover border-border">
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
          </div>
          <div className="space-y-4">
            <div className="flex items-center justify-between py-1">
              <div>
                <p className="text-foreground text-sm font-medium">Password requirements</p>
                <p className="text-xs text-muted-foreground">Enforce strong passwords</p>
              </div>
              <Switch defaultChecked />
            </div>
            <div className="flex items-center justify-between py-1">
              <div>
                <p className="text-foreground text-sm font-medium">Login attempt limit</p>
                <p className="text-xs text-muted-foreground">Lock after failed attempts</p>
              </div>
              <Select defaultValue="5">
                <SelectTrigger className="w-[100px] bg-muted border-border text-foreground h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-popover border-border">
                  <SelectItem value="3">3 attempts</SelectItem>
                  <SelectItem value="5">5 attempts</SelectItem>
                  <SelectItem value="10">10 attempts</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between py-1">
              <div>
                <p className="text-foreground text-sm font-medium">IP whitelisting</p>
                <p className="text-xs text-muted-foreground">Restrict access by IP</p>
              </div>
              <Switch />
            </div>
          </div>
        </div>
        <Separator className="bg-muted" />
        <Button className="">
          <Save className="mr-2 h-4 w-4" />
          Save Security Settings
        </Button>
      </CardContent>
    </Card>
  );
}
