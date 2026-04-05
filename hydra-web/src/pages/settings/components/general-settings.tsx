import { useEffect, useState } from 'react';
import { Globe, Settings, Save } from 'lucide-react';
import { toast } from 'sonner';
import { useUpdateUserSettings, useUserSettings } from '@/api/settings';
import type { LayoutMode, ThemeMode } from '@/types/settings';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const layoutOptions: { value: LayoutMode; label: string }[] = [
  { value: 'list', label: 'List' },
  { value: 'grid', label: 'Grid' },
  { value: 'compact', label: 'Compact' },
];

export function GeneralSettings() {
  const { data: settings } = useUserSettings();
  const updateUserSettings = useUpdateUserSettings();

  const [uiForm, setUiForm] = useState({
    theme: 'system' as ThemeMode,
    sidebarCollapsed: false,
    animationsEnabled: true,
  });

  const [viewForm, setViewForm] = useState({
    nodesLayout: 'list' as LayoutMode,
    servicesLayout: 'list' as LayoutMode,
    networksLayout: 'list' as LayoutMode,
    groupsLayout: 'list' as LayoutMode,
    nodesPageSize: 20,
    servicesPageSize: 20,
  });

  useEffect(() => {
    if (!settings) return;
    setUiForm({
      theme: settings.ui.theme,
      sidebarCollapsed: settings.ui.sidebarCollapsed,
      animationsEnabled: settings.ui.animationsEnabled,
    });
    setViewForm({
      nodesLayout: settings.views.nodes.layout,
      servicesLayout: settings.views.services.layout,
      networksLayout: settings.views.networks.layout,
      groupsLayout: settings.views.groups.layout,
      nodesPageSize: settings.views.nodes.pageSize,
      servicesPageSize: settings.views.services.pageSize,
    });
  }, [settings]);

  const handleSaveUi = async () => {
    if (!settings) return;
    try {
      await updateUserSettings.mutateAsync({
        ui: {
          theme: uiForm.theme,
          sidebarCollapsed: uiForm.sidebarCollapsed,
          animationsEnabled: uiForm.animationsEnabled,
        },
      });
      toast.success('UI preferences updated');
    } catch {
      toast.error('Failed to update UI preferences');
    }
  };

  const handleSaveViews = async () => {
    if (!settings) return;
    try {
      await updateUserSettings.mutateAsync({
        views: {
          ...settings.views,
          nodes: {
            ...settings.views.nodes,
            layout: viewForm.nodesLayout,
            pageSize: viewForm.nodesPageSize,
          },
          services: {
            ...settings.views.services,
            layout: viewForm.servicesLayout,
            pageSize: viewForm.servicesPageSize,
          },
          networks: {
            ...settings.views.networks,
            layout: viewForm.networksLayout,
          },
          groups: {
            ...settings.views.groups,
            layout: viewForm.groupsLayout,
          },
        },
      });
      toast.success('View defaults updated');
    } catch {
      toast.error('Failed to update view defaults');
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card className="bg-card border-border">
        <CardHeader className="pb-4">
          <CardTitle className="text-foreground flex items-center gap-2 text-base">
            <Globe className="h-4 w-4 text-primary" />
            General
          </CardTitle>
          <CardDescription className="text-muted-foreground text-xs">
            UI preferences for your account
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label className="text-foreground text-sm">Theme</Label>
            <Select
              value={uiForm.theme}
              onValueChange={(value) => setUiForm((prev) => ({ ...prev, theme: value as ThemeMode }))}
            >
              <SelectTrigger className="bg-muted border-border text-foreground h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-popover border-border">
                <SelectItem value="system">System</SelectItem>
                <SelectItem value="light">Light</SelectItem>
                <SelectItem value="dark">Dark</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center justify-between py-1">
            <div>
              <p className="text-foreground text-sm font-medium">Collapse Sidebar</p>
              <p className="text-xs text-muted-foreground">Keep navigation minimized</p>
            </div>
            <Switch
              checked={uiForm.sidebarCollapsed}
              onCheckedChange={(checked) =>
                setUiForm((prev) => ({ ...prev, sidebarCollapsed: checked }))
              }
            />
          </div>
          <div className="flex items-center justify-between py-1">
            <div>
              <p className="text-foreground text-sm font-medium">Animations</p>
              <p className="text-xs text-muted-foreground">Enable motion effects</p>
            </div>
            <Switch
              checked={uiForm.animationsEnabled}
              onCheckedChange={(checked) =>
                setUiForm((prev) => ({ ...prev, animationsEnabled: checked }))
              }
            />
          </div>
          <Button className="w-full mt-4" onClick={handleSaveUi} disabled={updateUserSettings.isPending}>
            <Save className="mr-2 h-4 w-4" />
            Save Preferences
          </Button>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardHeader className="pb-4">
          <CardTitle className="text-foreground flex items-center gap-2 text-base">
            <Settings className="h-4 w-4 text-primary" />
            View Defaults
          </CardTitle>
          <CardDescription className="text-muted-foreground text-xs">
            Default layouts for list views
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 grid-cols-2">
            <div className="space-y-2">
              <Label className="text-foreground text-sm">Nodes Layout</Label>
              <Select
                value={viewForm.nodesLayout}
                onValueChange={(value) =>
                  setViewForm((prev) => ({ ...prev, nodesLayout: value as LayoutMode }))
                }
              >
                <SelectTrigger className="bg-muted border-border text-foreground h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-popover border-border">
                  {layoutOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="text-foreground text-sm">Services Layout</Label>
              <Select
                value={viewForm.servicesLayout}
                onValueChange={(value) =>
                  setViewForm((prev) => ({ ...prev, servicesLayout: value as LayoutMode }))
                }
              >
                <SelectTrigger className="bg-muted border-border text-foreground h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-popover border-border">
                  {layoutOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="text-foreground text-sm">Networks Layout</Label>
              <Select
                value={viewForm.networksLayout}
                onValueChange={(value) =>
                  setViewForm((prev) => ({ ...prev, networksLayout: value as LayoutMode }))
                }
              >
                <SelectTrigger className="bg-muted border-border text-foreground h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-popover border-border">
                  {layoutOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="text-foreground text-sm">Groups Layout</Label>
              <Select
                value={viewForm.groupsLayout}
                onValueChange={(value) =>
                  setViewForm((prev) => ({ ...prev, groupsLayout: value as LayoutMode }))
                }
              >
                <SelectTrigger className="bg-muted border-border text-foreground h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-popover border-border">
                  {layoutOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid gap-4 grid-cols-2">
            <div className="space-y-2">
              <Label className="text-foreground text-sm">Nodes Page Size</Label>
              <Input
                type="number"
                min={10}
                max={100}
                value={viewForm.nodesPageSize}
                onChange={(e) =>
                  setViewForm((prev) => ({
                    ...prev,
                    nodesPageSize: Number(e.target.value || 0),
                  }))
                }
                className="bg-muted border-border text-foreground h-9"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-foreground text-sm">Services Page Size</Label>
              <Input
                type="number"
                min={10}
                max={100}
                value={viewForm.servicesPageSize}
                onChange={(e) =>
                  setViewForm((prev) => ({
                    ...prev,
                    servicesPageSize: Number(e.target.value || 0),
                  }))
                }
                className="bg-muted border-border text-foreground h-9"
              />
            </div>
          </div>
          <Button className="w-full mt-4" onClick={handleSaveViews} disabled={updateUserSettings.isPending}>
            <Save className="mr-2 h-4 w-4" />
            Save View Defaults
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
