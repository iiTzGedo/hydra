import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { useSearchParams } from 'react-router-dom';
import {
  Globe,
  RefreshCw,
  Bell,
  Shield,
  Users,
  Lock,
  FileText,
  Bot,
  Settings,
} from 'lucide-react';
import { useAuthStore } from '@/stores/auth-store';
import type { Role } from '@/types/user';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { TooltipProvider } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import {
  GeneralSettings,
  AgentSettings,
  NotificationSettings,
  SecuritySettings,
  UserManagement,
  SecretsSection,
  AuditLogSection,
  AISettings,
} from './components';

type TopTab = {
  id: string;
  label: string;
  icon: typeof Globe;
  description: string;
  roles?: Role[];
};

const topTabs: TopTab[] = [
  { 
    id: 'general', 
    label: 'General', 
    icon: Globe,
    description: 'System-wide preferences and defaults',
  },
  { 
    id: 'ai', 
    label: 'AI', 
    icon: Bot,
    description: 'Configure AI and chat settings',
  },
  { 
    id: 'notifications', 
    label: 'Notifications', 
    icon: Bell,
    description: 'Manage notification preferences',
  },
  { 
    id: 'security', 
    label: 'Security', 
    icon: Shield, 
    roles: ['admin'],
    description: 'Security policies and authentication',
  },
  { 
    id: 'users', 
    label: 'Users', 
    icon: Users, 
    roles: ['admin'],
    description: 'Manage users and permissions',
  },
];

type BottomTab = {
  id: string;
  label: string;
  icon: typeof Globe;
  description: string;
  roles?: Role[];
};

const bottomTabs: BottomTab[] = [
  { 
    id: 'agent', 
    label: 'Agent Config', 
    icon: RefreshCw, 
    roles: ['admin', 'operator'],
    description: 'Configure Hydra agent settings',
  },
  { 
    id: 'secrets', 
    label: 'Secrets', 
    icon: Lock, 
    roles: ['admin', 'operator'],
    description: 'Manage secrets and credentials',
  },
  { 
    id: 'audit', 
    label: 'Audit Log', 
    icon: FileText, 
    roles: ['admin'],
    description: 'View system audit logs',
  },
];

const tabVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: { 
    opacity: 1, 
    y: 0,
    transition: { duration: 0.2, ease: [0.16, 1, 0.3, 1] }
  },
  exit: { 
    opacity: 0, 
    y: -10,
    transition: { duration: 0.15 }
  }
};

export default function SettingsPage() {
  useDocumentTitle('Settings');

  const [searchParams, setSearchParams] = useSearchParams();
  const { hasAnyRole } = useAuthStore();
  const [topActiveTab, setTopActiveTab] = useState('general');
  const [bottomActiveTab, setBottomActiveTab] = useState('agent');

  const visibleTopTabs = topTabs.filter((tab) => {
    if (!tab.roles) return true;
    return hasAnyRole(tab.roles);
  });

  const visibleBottomTabs = bottomTabs.filter((tab) => {
    if (!tab.roles) return true;
    return hasAnyRole(tab.roles);
  });

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

  useEffect(() => {
    const topParam = searchParams.get('top');
    if (topParam && visibleTopTabs.some((tab) => tab.id === topParam)) {
      setTopActiveTab(topParam);
    }
  }, [searchParams, visibleTopTabs]);

  useEffect(() => {
    const bottomParam = searchParams.get('bottom');
    if (bottomParam && visibleBottomTabs.some((tab) => tab.id === bottomParam)) {
      setBottomActiveTab(bottomParam);
    }
  }, [searchParams, visibleBottomTabs]);

  const handleTopTabChange = (value: string) => {
    setTopActiveTab(value);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('top', value);
      return next;
    });
  };

  const handleBottomTabChange = (value: string) => {
    setBottomActiveTab(value);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('bottom', value);
      return next;
    });
  };

  const TabButton = ({ 
    tab, 
    isActive, 
    onClick 
  }: { 
    tab: TopTab | BottomTab; 
    isActive: boolean;
    onClick: () => void;
  }) => {
    const Icon = tab.icon;
    return (
      <button
        onClick={onClick}
        className={cn(
          'flex items-center gap-3 w-full p-3 rounded-xl text-left transition-all duration-200',
          'hover:bg-muted focus:outline-none focus:ring-2 focus:ring-primary/50',
          isActive && 'bg-primary/10 hover:bg-primary/15'
        )}
      >
        <div className={cn(
          'p-2 rounded-lg transition-colors',
          isActive ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
        )}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={cn(
              'font-medium text-sm',
              isActive ? 'text-foreground' : 'text-muted-foreground'
            )}>
              {tab.label}
            </span>
            {'roles' in tab && tab.roles && (
              <Badge
                variant="secondary"
                className="text-[10px] px-1.5 py-0 h-4 bg-muted text-muted-foreground shrink-0"
              >
                {tab.roles.includes('admin') && !tab.roles.includes('operator')
                  ? 'Admin'
                  : 'Admin/Op'}
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground truncate">{tab.description}</p>
        </div>
      </button>
    );
  };

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-3"
        >
          <div className="p-3 rounded-xl bg-primary/10">
            <Settings className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h2 className="text-2xl font-semibold text-foreground">Settings</h2>
            <p className="text-sm text-muted-foreground">
              Configure system settings and manage your account
            </p>
          </div>
        </motion.div>

        {/* Main Content */}
        <div className="grid gap-6 lg:grid-cols-[280px,1fr]">
          {/* Sidebar Navigation */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
            className="space-y-4"
          >
            {/* Top Tabs */}
            <div className="space-y-1">
              <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-3 mb-2">
                Configuration
              </h3>
              {visibleTopTabs.map((tab) => (
                <TabButton
                  key={tab.id}
                  tab={tab}
                  isActive={topActiveTab === tab.id}
                  onClick={() => handleTopTabChange(tab.id)}
                />
              ))}
            </div>

            {/* Bottom Tabs */}
            {visibleBottomTabs.length > 0 && (
              <>
                <Separator className="bg-border" />
                <div className="space-y-1">
                  <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-3 mb-2">
                    Administration
                  </h3>
                  {visibleBottomTabs.map((tab) => (
                    <TabButton
                      key={tab.id}
                      tab={tab}
                      isActive={bottomActiveTab === tab.id}
                      onClick={() => handleBottomTabChange(tab.id)}
                    />
                  ))}
                </div>
              </>
            )}
          </motion.div>

          {/* Tab Content */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.15 }}
          >
            <Tabs value={topActiveTab} onValueChange={handleTopTabChange}>
              <AnimatePresence mode="wait">
                <TabsContent value="general" className="mt-0">
                  <motion.div
                    key="general"
                    variants={tabVariants}
                    initial="hidden"
                    animate="visible"
                    exit="exit"
                  >
                    <GeneralSettings />
                  </motion.div>
                </TabsContent>

                <TabsContent value="ai" className="mt-0">
                  <motion.div
                    key="ai"
                    variants={tabVariants}
                    initial="hidden"
                    animate="visible"
                    exit="exit"
                  >
                    <AISettings />
                  </motion.div>
                </TabsContent>

                <TabsContent value="notifications" className="mt-0">
                  <motion.div
                    key="notifications"
                    variants={tabVariants}
                    initial="hidden"
                    animate="visible"
                    exit="exit"
                  >
                    <NotificationSettings />
                  </motion.div>
                </TabsContent>

                <TabsContent value="security" className="mt-0">
                  <motion.div
                    key="security"
                    variants={tabVariants}
                    initial="hidden"
                    animate="visible"
                    exit="exit"
                  >
                    <SecuritySettings />
                  </motion.div>
                </TabsContent>

                <TabsContent value="users" className="mt-0">
                  <motion.div
                    key="users"
                    variants={tabVariants}
                    initial="hidden"
                    animate="visible"
                    exit="exit"
                  >
                    <UserManagement />
                  </motion.div>
                </TabsContent>
              </AnimatePresence>
            </Tabs>

            <Tabs value={bottomActiveTab} onValueChange={handleBottomTabChange}>
              <AnimatePresence mode="wait">
                <TabsContent value="agent" className="mt-0">
                  <motion.div
                    key="agent"
                    variants={tabVariants}
                    initial="hidden"
                    animate="visible"
                    exit="exit"
                  >
                    <AgentSettings />
                  </motion.div>
                </TabsContent>

                <TabsContent value="secrets" className="mt-0">
                  <motion.div
                    key="secrets"
                    variants={tabVariants}
                    initial="hidden"
                    animate="visible"
                    exit="exit"
                  >
                    <SecretsSection />
                  </motion.div>
                </TabsContent>

                <TabsContent value="audit" className="mt-0">
                  <motion.div
                    key="audit"
                    variants={tabVariants}
                    initial="hidden"
                    animate="visible"
                    exit="exit"
                  >
                    <AuditLogSection />
                  </motion.div>
                </TabsContent>
              </AnimatePresence>
            </Tabs>
          </motion.div>
        </div>
      </div>
    </TooltipProvider>
  );
}
