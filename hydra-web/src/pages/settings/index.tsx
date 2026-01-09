import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Globe,
  RefreshCw,
  Bell,
  Shield,
  Users,
  Key,
  FileText,
  Settings,
  Save,
  Search,
  Plus,
  Copy,
  Check,
  Trash2,
  Clock,
  Loader2,
  Server,
  MoreVertical,
  Archive,
  UserCog,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
  ShieldCheck,
  Fingerprint,
  User,
  Boxes,
  Network,
  FolderTree,
  LogIn,
  LogOut,
  UserPlus,
  Zap,
  Edit,
  Lock,
} from 'lucide-react';
import { useAuthStore } from '@/stores/auth-store';
import { useUsers, useArchiveUser, useElevateRole } from '@/api/users';
import { useCreateToken } from '@/api/auth';
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from '@/api/auth';
import { useAuditLog } from '@/api/query';
import type { UserSummary, Role } from '@/types/user';
import type { AuditAction, AuditEntry } from '@/types/query';
import { ROLE_LABELS } from '@/lib/constants';
import { formatDate, formatDateTime, formatRelativeTime, cn } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

// Role badge variants
const roleVariants: Record<Role, 'destructive' | 'warning' | 'default' | 'success' | 'secondary'> = {
  admin: 'destructive',
  operator: 'warning',
  viewer: 'default',
  family: 'success',
  agent: 'secondary',
};

const roleIcons: Record<Role, typeof Shield> = {
  admin: ShieldAlert,
  operator: ShieldCheck,
  viewer: Shield,
  family: Shield,
  agent: Shield,
};

// Audit log helpers
const resourceIcons: Record<string, typeof User> = {
  user: User,
  node: Server,
  service: Boxes,
  network: Network,
  group: FolderTree,
  topology: Settings,
  system: Settings,
};

const actionIcons: Record<AuditAction, typeof User> = {
  create: UserPlus,
  update: Edit,
  delete: Trash2,
  login: LogIn,
  logout: LogOut,
  register: UserPlus,
  execute: Zap,
};

const actionVariants: Record<AuditAction, 'success' | 'default' | 'destructive' | 'secondary' | 'warning'> = {
  create: 'success',
  update: 'default',
  delete: 'destructive',
  login: 'default',
  logout: 'secondary',
  register: 'success',
  execute: 'warning',
};

// Top section tabs - high access rate, less critical
type TopTab = {
  id: string;
  label: string;
  icon: typeof Settings;
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
  icon: typeof Settings;
  roles?: Role[];
};

const bottomTabs: BottomTab[] = [
  { id: 'agent', label: 'Agent Config', icon: RefreshCw, roles: ['admin', 'operator'] },
  { id: 'secrets', label: 'Secrets', icon: Lock, roles: ['admin', 'operator'] },
  { id: 'audit', label: 'Audit Log', icon: FileText, roles: ['admin'] },
];

export default function SettingsPage() {
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

// General Settings Component
function GeneralSettings() {
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

// Agent Settings Component
function AgentSettings() {
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

// Notification Settings Component
function NotificationSettings() {
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

// Security Settings Component
function SecuritySettings() {
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

// User Management Component
function UserManagement() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const limit = 10;

  const { data, isLoading, error } = useUsers({
    limit,
    offset: page * limit,
    search: search || undefined,
  });

  const totalPages = data ? Math.ceil(data.total / limit) : 0;

  if (error) {
    return (
      <Card className="bg-card border-border">
        <CardContent className="p-8 text-center">
          <p className="text-destructive">Failed to load users</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="relative max-w-md flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search users..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10 bg-muted border-border text-foreground"
          />
        </div>
      </div>

      {isLoading ? (
        <Card className="bg-card border-border">
          <div className="divide-y divide-border">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center gap-4 p-4">
                <Skeleton className="h-10 w-10 rounded-full bg-muted" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-32 bg-muted" />
                  <Skeleton className="h-3 w-48 bg-muted" />
                </div>
              </div>
            ))}
          </div>
        </Card>
      ) : !data?.items?.length ? (
        <Card className="bg-card border-border">
          <CardContent className="p-8 text-center">
            <UserCog className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold text-foreground">No users found</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              {search ? 'Try adjusting your search' : 'No users registered yet'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="text-sm text-muted-foreground">
            Showing {data.items.length} of {data.total} users
          </div>

          <motion.div
            variants={staggerContainerVariants}
            initial="hidden"
            animate="visible"
          >
            <Card className="bg-card border-border">
              <div className="divide-y divide-border">
                <AnimatePresence mode="popLayout">
                  {data.items.map((user: UserSummary) => (
                    <UserRow key={user.userId} user={user} />
                  ))}
                </AnimatePresence>
              </div>
            </Card>
          </motion.div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {page + 1} of {totalPages}
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="text-muted-foreground hover:text-foreground hover:bg-muted"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function UserRow({ user }: { user: UserSummary }) {
  const archiveMutation = useArchiveUser();
  const elevateMutation = useElevateRole();

  const RoleIcon = roleIcons[user.role] || Shield;
  const roleLabel = ROLE_LABELS[user.role] || user.role;

  const handleArchive = async () => {
    await archiveMutation.mutateAsync(user.userId);
  };

  const handleElevate = async (newRole: Role) => {
    await elevateMutation.mutateAsync({ userId: user.userId, data: { newRole } });
  };

  return (
    <motion.div
      variants={staggerItemVariants}
      layout
      className="group flex items-center gap-4 p-4 hover:bg-muted/60 transition-colors"
    >
      <Avatar>
        <AvatarFallback className="bg-primary text-primary-foreground">
          {user.username?.charAt(0).toUpperCase() || 'U'}
        </AvatarFallback>
      </Avatar>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-foreground truncate">{user.username}</span>
          <Badge variant={roleVariants[user.role]}>
            {roleLabel}
          </Badge>
          {user.status === 'archived' && (
            <Badge variant="secondary">Archived</Badge>
          )}
        </div>
        <div className="mt-1 text-sm text-muted-foreground truncate">
          {user.email}
        </div>
      </div>

      <div className="hidden md:block text-right text-sm text-muted-foreground">
        {formatDate(new Date(user.createdAt))}
      </div>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
          >
            <MoreVertical className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="bg-popover border-border">
          <DropdownMenuLabel className="text-foreground">Change Role</DropdownMenuLabel>
          {(['admin', 'operator', 'viewer', 'family'] as Role[]).map((role) => {
            const Icon = roleIcons[role];
            return (
              <DropdownMenuItem
                key={role}
                onClick={() => handleElevate(role)}
                disabled={user.role === role}
                className="text-foreground focus:text-foreground focus:bg-muted"
              >
                <Icon className="mr-2 h-4 w-4" />
                {ROLE_LABELS[role]}
              </DropdownMenuItem>
            );
          })}
          <DropdownMenuSeparator className="bg-border" />
          <DropdownMenuItem
            onClick={handleArchive}
            className="text-destructive focus:text-destructive focus:bg-destructive/10"
          >
            <Archive className="mr-2 h-4 w-4" />
            Archive User
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </motion.div>
  );
}

// Secrets Section - Merged API Keys and Registration Tokens
function SecretsSection() {
  const [secretsTab, setSecretsTab] = useState<'tokens' | 'apikeys'>('tokens');

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 border-b border-border">
        <button
          onClick={() => setSecretsTab('tokens')}
          className={cn(
            'pb-3 text-sm font-medium transition-colors border-b-2 -mb-px',
            secretsTab === 'tokens'
              ? 'border-primary text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          )}
        >
          <Key className="h-4 w-4 inline mr-2" />
          Registration Tokens
        </button>
        <button
          onClick={() => setSecretsTab('apikeys')}
          className={cn(
            'pb-3 text-sm font-medium transition-colors border-b-2 -mb-px',
            secretsTab === 'apikeys'
              ? 'border-primary text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          )}
        >
          <Fingerprint className="h-4 w-4 inline mr-2" />
          API Keys
        </button>
      </div>

      {secretsTab === 'tokens' && <RegistrationTokens />}
      {secretsTab === 'apikeys' && <ApiKeysSection />}
    </div>
  );
}

// Registration Tokens Component
function RegistrationTokens() {
  const createMutation = useCreateToken();

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newToken, setNewToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [scope, setScope] = useState<'user' | 'node'>('user');
  const [maxUses, setMaxUses] = useState('1');
  const [expiresInDays, setExpiresInDays] = useState('7');
  const [allowedRoles, setAllowedRoles] = useState<Role[]>(['viewer']);

  const handleCreate = async () => {
    const days = parseInt(expiresInDays) || 7;
    const expiresIn = days * 24 * 60 * 60;

    const result = await createMutation.mutateAsync({
      scope,
      maxUses: parseInt(maxUses) || 1,
      expiresIn,
      allowedRoles: scope === 'user' ? allowedRoles : undefined,
    });
    setNewToken(result.token);
  };

  const handleCopy = async () => {
    if (newToken) {
      await navigator.clipboard.writeText(newToken);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const toggleRole = (role: Role) => {
    setAllowedRoles((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]
    );
  };

  const handleCloseModal = () => {
    setShowCreateForm(false);
    setNewToken(null);
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-medium text-foreground">Registration Tokens</h3>
          <p className="text-sm text-muted-foreground">Create tokens for user and node registration</p>
        </div>
        <Button
          onClick={() => setShowCreateForm(true)}
          className=""
        >
          <Plus className="mr-2 h-4 w-4" />
          Create Token
        </Button>
      </div>

      <Dialog open={showCreateForm} onOpenChange={handleCloseModal}>
        <DialogContent className="sm:max-w-md bg-card border-border text-foreground">
          {newToken ? (
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
                <Check className="h-6 w-6 text-success" />
              </div>
              <DialogHeader className="mt-4">
                <DialogTitle className="text-foreground">Token Created</DialogTitle>
                <DialogDescription className="text-muted-foreground">
                  Copy this token now. It won't be shown again.
                </DialogDescription>
              </DialogHeader>
              <div className="mt-4 flex items-center gap-2 rounded-lg bg-muted p-3">
                <code className="flex-1 text-sm font-mono break-all text-left text-success">
                  {newToken}
                </code>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleCopy}
                  className="text-muted-foreground hover:text-foreground hover:bg-muted"
                >
                  {copied ? (
                    <Check className="h-4 w-4 text-success" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
              <Button
                onClick={handleCloseModal}
                className="mt-6 w-full "
              >
                Done
              </Button>
            </div>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle className="text-foreground">Create Registration Token</DialogTitle>
              </DialogHeader>

              <div className="space-y-4">
                <div className="space-y-2">
                  <Label className="text-foreground">Token Scope</Label>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant={scope === 'user' ? 'default' : 'outline'}
                      onClick={() => setScope('user')}
                      className={cn(
                        'flex-1',
                        scope === 'user'
                          ? ''
                          : 'border-border text-foreground hover:bg-muted bg-transparent'
                      )}
                    >
                      <Users className="mr-2 h-4 w-4" />
                      User
                    </Button>
                    <Button
                      type="button"
                      variant={scope === 'node' ? 'default' : 'outline'}
                      onClick={() => setScope('node')}
                      className={cn(
                        'flex-1',
                        scope === 'node'
                          ? ''
                          : 'border-border text-foreground hover:bg-muted bg-transparent'
                      )}
                    >
                      <Server className="mr-2 h-4 w-4" />
                      Node
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="maxUses" className="text-foreground">
                    Max Uses
                  </Label>
                  <Input
                    id="maxUses"
                    type="number"
                    value={maxUses}
                    onChange={(e) => setMaxUses(e.target.value)}
                    min="1"
                    className="bg-muted border-border text-foreground"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="expiresIn" className="text-foreground">
                    Expires in (days)
                  </Label>
                  <Input
                    id="expiresIn"
                    type="number"
                    value={expiresInDays}
                    onChange={(e) => setExpiresInDays(e.target.value)}
                    min="1"
                    className="bg-muted border-border text-foreground"
                  />
                </div>

                {scope === 'user' && (
                  <div className="space-y-2">
                    <Label className="text-foreground">Allowed Roles</Label>
                    <div className="flex flex-wrap gap-2">
                      {(['admin', 'operator', 'viewer', 'family'] as Role[]).map((role) => (
                        <Badge
                          key={role}
                          variant={allowedRoles.includes(role) ? 'default' : 'outline'}
                          className={cn(
                            'cursor-pointer transition-colors',
                            allowedRoles.includes(role)
                              ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                              : 'border-border text-muted-foreground hover:bg-muted'
                          )}
                          onClick={() => toggleRole(role)}
                        >
                          {ROLE_LABELS[role]}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="mt-6 flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleCloseModal}
                  className="flex-1 border-border text-foreground hover:bg-muted bg-transparent"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleCreate}
                  disabled={createMutation.isPending}
                  className="flex-1"
                >
                  {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Create
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="text-foreground flex items-center gap-2">
            <Key className="h-5 w-5 text-warning" />
            Token Information
          </CardTitle>
          <CardDescription className="text-muted-foreground">
            About registration tokens
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          <p>
            Registration tokens can be created here. Token listing and revocation are not available
            in API v0.3.0, so store tokens securely when created.
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="p-4 rounded-lg bg-muted/60 border border-border">
              <div className="flex items-center gap-2 text-foreground font-medium mb-2">
                <Users className="h-4 w-4 text-primary" />
                User Tokens
              </div>
              <p className="text-xs text-muted-foreground">
                Allow new users to register accounts with specified roles.
              </p>
            </div>
            <div className="p-4 rounded-lg bg-muted/60 border border-border">
              <div className="flex items-center gap-2 text-foreground font-medium mb-2">
                <Server className="h-4 w-4 text-success" />
                Node Tokens
              </div>
              <p className="text-xs text-muted-foreground">
                Allow Hydra agents to register new nodes to the system.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// API Keys Component
function ApiKeysSection() {
  const { data: apiKeys, isLoading, error, refetch } = useApiKeys();
  const createMutation = useCreateApiKey();
  const revokeMutation = useRevokeApiKey();

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newApiKey, setNewApiKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const [name, setName] = useState('');
  const [expiresInDays, setExpiresInDays] = useState('365');

  const handleCreate = async () => {
    const days = parseInt(expiresInDays) || 365;
    const expiresAt = new Date(Date.now() + days * 24 * 60 * 60 * 1000).toISOString();

    const result = await createMutation.mutateAsync({
      name,
      expiresAt,
    });
    setNewApiKey(result.key ?? null);
    setName('');
    refetch();
  };

  const handleCopy = async () => {
    if (newApiKey) {
      await navigator.clipboard.writeText(newApiKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleRevoke = async (keyId: string) => {
    await revokeMutation.mutateAsync(keyId);
    refetch();
  };

  const handleCloseModal = () => {
    setShowCreateForm(false);
    setNewApiKey(null);
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-medium text-foreground">API Keys</h3>
          <p className="text-sm text-muted-foreground">Manage API keys for programmatic access</p>
        </div>
        <Button
          onClick={() => setShowCreateForm(true)}
          className=""
        >
          <Plus className="mr-2 h-4 w-4" />
          Create API Key
        </Button>
      </div>

      <Dialog open={showCreateForm} onOpenChange={handleCloseModal}>
        <DialogContent className="sm:max-w-md bg-card border-border text-foreground">
          {newApiKey ? (
            <div className="text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
                <Check className="h-6 w-6 text-success" />
              </div>
              <DialogHeader className="mt-4">
                <DialogTitle className="text-foreground">API Key Created</DialogTitle>
                <DialogDescription className="text-muted-foreground">
                  Copy this key now. It won't be shown again.
                </DialogDescription>
              </DialogHeader>
              <div className="mt-4 flex items-center gap-2 rounded-lg bg-muted p-3">
                <code className="flex-1 text-sm font-mono break-all text-left text-success">
                  {newApiKey}
                </code>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleCopy}
                  className="text-muted-foreground hover:text-foreground hover:bg-muted"
                >
                  {copied ? (
                    <Check className="h-4 w-4 text-success" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
              <Button
                onClick={handleCloseModal}
                className="mt-6 w-full "
              >
                Done
              </Button>
            </div>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle className="text-foreground">Create API Key</DialogTitle>
              </DialogHeader>

              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="name" className="text-foreground">
                    Name <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., CI/CD Pipeline"
                    className="bg-muted border-border text-foreground"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="expiresIn" className="text-foreground">
                    Expires in (days)
                  </Label>
                  <Input
                    id="expiresIn"
                    type="number"
                    value={expiresInDays}
                    onChange={(e) => setExpiresInDays(e.target.value)}
                    min="1"
                    className="bg-muted border-border text-foreground"
                  />
                </div>
              </div>

              <div className="mt-6 flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleCloseModal}
                  className="flex-1 border-border text-foreground hover:bg-muted bg-transparent"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleCreate}
                  disabled={createMutation.isPending || !name.trim()}
                  className="flex-1 "
                >
                  {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Create
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {error ? (
        <Card className="bg-card border-border">
          <CardContent className="p-8 text-center">
            <p className="text-destructive">Failed to load API keys</p>
          </CardContent>
        </Card>
      ) : isLoading ? (
        <Card className="bg-card border-border">
          <CardContent className="p-6 space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="h-10 w-10 rounded-lg bg-muted" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-32 bg-muted" />
                  <Skeleton className="h-3 w-48 bg-muted" />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : !apiKeys?.length ? (
        <Card className="bg-card border-border">
          <CardContent className="p-8 text-center">
            <Fingerprint className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold text-foreground">No API keys</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Create an API key for programmatic access
            </p>
          </CardContent>
        </Card>
      ) : (
        <motion.div
          variants={staggerContainerVariants}
          initial="hidden"
          animate="visible"
        >
          <Card className="bg-card border-border">
            <div className="divide-y divide-border">
              {apiKeys.map((apiKey) => (
                <motion.div
                  key={apiKey.keyId}
                  variants={staggerItemVariants}
                  className="flex items-center gap-4 p-4 hover:bg-muted/60 transition-colors group"
                >
                  <div className="rounded-lg bg-green-500/20 p-2.5">
                    <Fingerprint className="h-5 w-5 text-green-400" />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-foreground">{apiKey.name}</div>
                    <div className="mt-1 flex items-center gap-3 text-sm text-muted-foreground">
                      <span className="font-mono">{apiKey.keyId.slice(0, 8)}...</span>
                      <span>-</span>
                      <span>Created {formatRelativeTime(new Date(apiKey.createdAt))}</span>
                    </div>
                  </div>

                  <div className="hidden md:flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock className="h-4 w-4" />
                    <span>
                      {apiKey.expiresAt
                        ? `Expires ${formatDateTime(apiKey.expiresAt)}`
                        : 'Never expires'}
                    </span>
                  </div>

                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleRevoke(apiKey.keyId)}
                        disabled={revokeMutation.isPending}
                        className="text-destructive hover:text-destructive hover:bg-destructive/10 opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent className="bg-muted border-border text-foreground">
                      Revoke API Key
                    </TooltipContent>
                  </Tooltip>
                </motion.div>
              ))}
            </div>
          </Card>
        </motion.div>
      )}
    </div>
  );
}

// Audit Log Component
function AuditLogSection() {
  const [search, setSearch] = useState('');
  const [filterAction, setFilterAction] = useState<string>('all');
  const [page, setPage] = useState(0);
  const limit = 10;

  useEffect(() => {
    setPage(0);
  }, [search, filterAction]);

  const { data, isLoading, error } = useAuditLog({
    limit,
    offset: page * limit,
    resourceType: filterAction !== 'all' ? filterAction : undefined,
  });

  const logs = data?.items ?? [];
  const normalizedSearch = search.trim().toLowerCase();
  const filteredLogs = normalizedSearch
    ? logs.filter((log) => {
        const resourceText = `${log.resource.type}:${log.resource.id}`.toLowerCase();
        const actorText = `${log.actor.type}:${log.actor.id}`.toLowerCase();
        return (
          log.action.toLowerCase().includes(normalizedSearch) ||
          resourceText.includes(normalizedSearch) ||
          actorText.includes(normalizedSearch)
        );
      })
    : logs;

  const totalPages = normalizedSearch ? 1 : Math.ceil((data?.total ?? 0) / limit);

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-medium text-foreground">Audit Log</h3>
        <p className="text-sm text-muted-foreground">View system activity and changes</p>
      </div>

      <div className="flex flex-col gap-4 md:flex-row md:items-center">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search logs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10 bg-muted border-border text-foreground"
          />
        </div>

        <Select value={filterAction} onValueChange={setFilterAction}>
          <SelectTrigger className="w-[180px] bg-muted border-border text-foreground">
            <SelectValue placeholder="All Actions" />
          </SelectTrigger>
          <SelectContent className="bg-popover border-border">
            <SelectItem value="all">All Actions</SelectItem>
            <SelectItem value="user">User</SelectItem>
            <SelectItem value="node">Node</SelectItem>
            <SelectItem value="service">Service</SelectItem>
            <SelectItem value="network">Network</SelectItem>
            <SelectItem value="group">Group</SelectItem>
            <SelectItem value="topology">Topology</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {error ? (
        <Card className="bg-card border-border">
          <CardContent className="p-8 text-center">
            <p className="text-destructive">Failed to load audit logs</p>
          </CardContent>
        </Card>
      ) : isLoading ? (
        <Card className="bg-card border-border">
          <CardContent className="p-6 space-y-4">
            {[...Array(5)].map((_, index) => (
              <Skeleton key={index} className="h-12 w-full rounded-lg bg-muted" />
            ))}
          </CardContent>
        </Card>
      ) : filteredLogs.length === 0 ? (
        <Card className="bg-card border-border">
          <CardContent className="p-8 text-center">
            <FileText className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold text-foreground">No audit entries</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              {normalizedSearch ? 'No entries match your search' : 'Audit log is empty'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <motion.div
          variants={staggerContainerVariants}
          initial="hidden"
          animate="visible"
        >
          <Card className="bg-card border-border">
            <div className="divide-y divide-border">
              {filteredLogs.map((log: AuditEntry) => {
                const Icon = resourceIcons[log.resource.type] || FileText;
                const ActionIcon = actionIcons[log.action] || Settings;
                const variant = actionVariants[log.action] || 'secondary';

                return (
                  <motion.div
                    key={log.entryId}
                    variants={staggerItemVariants}
                    className="flex items-start gap-4 p-4 hover:bg-muted/60 transition-colors"
                  >
                    <div
                      className={cn(
                        'rounded-lg p-2',
                        variant === 'success' && 'bg-success/10 text-success',
                        variant === 'default' && 'bg-primary/10 text-primary',
                        variant === 'destructive' && 'bg-destructive/10 text-destructive',
                        variant === 'secondary' && 'bg-muted text-muted-foreground',
                        variant === 'warning' && 'bg-warning/10 text-warning'
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <ActionIcon className="h-3 w-3 text-muted-foreground" />
                        <span className="font-medium text-foreground">{log.action}</span>
                        <Badge
                          variant={variant}
                          className={cn(
                            variant === 'success' && 'bg-success/20 text-success',
                            variant === 'default' && 'bg-primary/20 text-primary',
                            variant === 'destructive' && 'bg-destructive/20 text-destructive',
                            variant === 'secondary' && 'bg-muted text-foreground',
                            variant === 'warning' && 'bg-warning/20 text-warning'
                          )}
                        >
                          {log.resource.type}
                        </Badge>
                      </div>
                      <div className="mt-1 text-sm text-muted-foreground">
                        <span className="font-mono">
                          {log.resource.type}:{log.resource.id}
                        </span>
                        <span className="mx-2">by</span>
                        <span>
                          {log.actor.type}:{log.actor.id}
                        </span>
                        {log.actor.ip && <span className="ml-2">({log.actor.ip})</span>}
                      </div>
                      {log.details && Object.keys(log.details).length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {Object.entries(log.details).map(([key, value]) => (
                            <Badge
                              key={key}
                              variant="secondary"
                              className="text-xs bg-muted text-muted-foreground"
                            >
                              {key}: {String(value)}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="text-right">
                      <div className="text-sm text-muted-foreground" title={formatDate(log.timestamp)}>
                        {formatRelativeTime(log.timestamp)}
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </Card>
        </motion.div>
      )}

      {totalPages > 1 && !normalizedSearch && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="text-muted-foreground hover:text-foreground hover:bg-muted"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page + 1} of {totalPages}
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="text-muted-foreground hover:text-foreground hover:bg-muted"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
