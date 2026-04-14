import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { PageHeaderLayout } from '@/components/layout/page-header-layout';
import { useSearchParams, useRouter } from 'next/navigation';
import {
  Globe,
  RefreshCw,
  Bell,
  Shield,
  Users,
  Lock,
  FileText,
  Bot,
  LayoutDashboard,
} from 'lucide-react';
import { useAuthStore } from '@/stores/auth-store';
import type { Role } from '@/types/user';
import { Badge } from '@/components/ui/badge';
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
  DashboardSettings,
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
    id: 'dashboards', 
    label: 'Dashboards', 
    icon: LayoutDashboard,
    description: 'Pinned dashboards and saved board preferences',
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

  const searchParams = useSearchParams();
  const router = useRouter();
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
    const topParam = searchParams?.get('top');
    if (topParam && visibleTopTabs.some((tab) => tab.id === topParam)) {
      setTopActiveTab(topParam);
    }
  }, [searchParams, visibleTopTabs]);

  useEffect(() => {
    const bottomParam = searchParams?.get('bottom');
    if (bottomParam && visibleBottomTabs.some((tab) => tab.id === bottomParam)) {
      setBottomActiveTab(bottomParam);
    }
  }, [searchParams, visibleBottomTabs]);

  const handleTopTabChange = (value: string) => {
    setTopActiveTab(value);
    const next = new URLSearchParams(searchParams?.toString() ?? '');
    next.set('top', value);
    router.replace(`?${next.toString()}`);
  };

  const handleBottomTabChange = (value: string) => {
    setBottomActiveTab(value);
    const next = new URLSearchParams(searchParams?.toString() ?? '');
    next.set('bottom', value);
    router.replace(`?${next.toString()}`);
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
        <PageHeaderLayout
          title="Settings"
          subtitle="Configure system settings and manage your account"
          showBackButton={false}
        />

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
            <AnimatePresence mode="wait">
              <motion.div
                key={topActiveTab}
                variants={tabVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
              >
                {topActiveTab === 'general' && <GeneralSettings />}
                {topActiveTab === 'ai' && <AISettings />}
                {topActiveTab === 'dashboards' && <DashboardSettings />}
                {topActiveTab === 'notifications' && <NotificationSettings />}
                {topActiveTab === 'security' && <SecuritySettings />}
                {topActiveTab === 'users' && <UserManagement />}
              </motion.div>
            </AnimatePresence>

            {visibleBottomTabs.length > 0 && <div className="mt-8" />}

            <AnimatePresence mode="wait">
              <motion.div
                key={bottomActiveTab}
                variants={tabVariants}
                initial="hidden"
                animate="visible"
                exit="exit"
              >
                {bottomActiveTab === 'agent' && <AgentSettings />}
                {bottomActiveTab === 'secrets' && <SecretsSection />}
                {bottomActiveTab === 'audit' && <AuditLogSection />}
              </motion.div>
            </AnimatePresence>
          </motion.div>
        </div>
      </div>
    </TooltipProvider>
  );
}
