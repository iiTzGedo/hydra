import { useState, useEffect } from 'react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import {
  Globe,
  RefreshCw,
  Bell,
  Shield,
  Users,
  Lock,
  FileText,
} from 'lucide-react';
import { useAuthStore } from '@/stores/auth-store';
import type { Role } from '@/types/user';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { TooltipProvider } from '@/components/ui/tooltip';
import {
  GeneralSettings,
  AgentSettings,
  NotificationSettings,
  SecuritySettings,
  UserManagement,
  SecretsSection,
  AuditLogSection,
} from './components';

// Top section tabs - high access rate, less critical
type TopTab = {
  id: string;
  label: string;
  icon: typeof Globe;
  roles?: Role[];
};

const topTabs: TopTab[] = [
  { id: 'general', label: 'General', icon: Globe },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'security', label: 'Security', icon: Shield, roles: ['admin'] },
  { id: 'users', label: 'Users', icon: Users, roles: ['admin'] },
];

// Bottom section tabs - admin/critical functions
type BottomTab = {
  id: string;
  label: string;
  icon: typeof Globe;
  roles?: Role[];
};

const bottomTabs: BottomTab[] = [
  { id: 'agent', label: 'Agent Config', icon: RefreshCw, roles: ['admin', 'operator'] },
  { id: 'secrets', label: 'Secrets', icon: Lock, roles: ['admin', 'operator'] },
  { id: 'audit', label: 'Audit Log', icon: FileText, roles: ['admin'] },
];

export default function SettingsPage() {
  useDocumentTitle('Settings');

  const { hasAnyRole } = useAuthStore();
  const [topActiveTab, setTopActiveTab] = useState('general');
  const [bottomActiveTab, setBottomActiveTab] = useState('agent');

  // Filter tabs based on user role
  const visibleTopTabs = topTabs.filter((tab) => {
    if (!tab.roles) return true;
    return hasAnyRole(tab.roles);
  });

  const visibleBottomTabs = bottomTabs.filter((tab) => {
    if (!tab.roles) return true;
    return hasAnyRole(tab.roles);
  });

  // Make sure active tabs are visible
  useEffect(() => {
    if (!visibleTopTabs.find((t) => t.id === topActiveTab)) {
      setTopActiveTab(visibleTopTabs[0]?.id || 'general');
    }
  }, [visibleTopTabs, topActiveTab]);

  useEffect(() => {
    if (!visibleBottomTabs.find((t) => t.id === bottomActiveTab)) {
      setBottomActiveTab(visibleBottomTabs[0]?.id || 'agent');
    }
  }, [visibleBottomTabs, bottomActiveTab]);

  return (
    <TooltipProvider>
      <div className="space-y-8">
        {/* Page Header */}
        <div>
          <h2 className="text-2xl font-semibold text-foreground">Settings</h2>
          <p className="text-sm text-muted-foreground">
            Configure system settings and manage your account
          </p>
        </div>

        {/* Top Section - General Settings */}
        <div className="space-y-4">
          <Tabs value={topActiveTab} onValueChange={setTopActiveTab}>
            <TabsList className="bg-card border border-border p-1 h-auto">
              {visibleTopTabs.map((tab) => {
                const Icon = tab.icon;
                return (
                  <TabsTrigger
                    key={tab.id}
                    value={tab.id}
                    className="data-[state=active]:bg-muted data-[state=active]:text-foreground text-muted-foreground px-4 py-2 text-sm"
                  >
                    <Icon className="h-4 w-4 mr-2" />
                    {tab.label}
                  </TabsTrigger>
                );
              })}
            </TabsList>

            <TabsContent value="general" className="mt-4">
              <GeneralSettings />
            </TabsContent>

            <TabsContent value="notifications" className="mt-4">
              <NotificationSettings />
            </TabsContent>

            <TabsContent value="security" className="mt-4">
              <SecuritySettings />
            </TabsContent>

            <TabsContent value="users" className="mt-4">
              <UserManagement />
            </TabsContent>
          </Tabs>
        </div>

        {/* Divider */}
        {visibleBottomTabs.length > 0 && (
          <div className="relative">
            <Separator className="bg-muted" />
            <span className="absolute left-1/2 -translate-x-1/2 -translate-y-1/2 bg-background px-4 text-xs text-muted-foreground uppercase tracking-wider">
              Administration
            </span>
          </div>
        )}

        {/* Bottom Section - Admin Settings */}
        {visibleBottomTabs.length > 0 && (
          <div className="space-y-4">
            <Tabs value={bottomActiveTab} onValueChange={setBottomActiveTab}>
              <TabsList className="bg-card border border-border p-1 h-auto">
                {visibleBottomTabs.map((tab) => {
                  const Icon = tab.icon;
                  return (
                    <TabsTrigger
                      key={tab.id}
                      value={tab.id}
                      className="data-[state=active]:bg-muted data-[state=active]:text-foreground text-muted-foreground px-4 py-2 text-sm"
                    >
                      <Icon className="h-4 w-4 mr-2" />
                      {tab.label}
                      {tab.roles && (
                        <Badge
                          variant="secondary"
                          className="ml-2 text-[10px] px-1 py-0 h-4 bg-muted text-muted-foreground"
                        >
                          {tab.roles.includes('admin') && !tab.roles.includes('operator')
                            ? 'Admin'
                            : 'Admin/Op'}
                        </Badge>
                      )}
                    </TabsTrigger>
                  );
                })}
              </TabsList>

              <TabsContent value="agent" className="mt-4">
                <AgentSettings />
              </TabsContent>

              <TabsContent value="secrets" className="mt-4">
                <SecretsSection />
              </TabsContent>

              <TabsContent value="audit" className="mt-4">
                <AuditLogSection />
              </TabsContent>
            </Tabs>
          </div>
        )}
      </div>
    </TooltipProvider>
  );
}
