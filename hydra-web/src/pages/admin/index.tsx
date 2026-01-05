import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Users,
  UserCheck,
  Key,
  Fingerprint,
  FileText,
  Settings,
  Shield,
  ArrowRight,
} from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { useUsers } from '@/api/users';
import { useTokens, useApiKeys, useApprovals } from '@/api/auth';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';
import { staggerContainerVariants, staggerItemVariants, scaleVariants } from '@/lib/animations';

interface AdminCardProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  href: string;
  count?: number;
  countLabel?: string;
  color: string;
}

function AdminCard({ title, description, icon, href, count, countLabel, color }: AdminCardProps) {
  return (
    <motion.div variants={staggerItemVariants}>
      <Link
        to={href}
        className="group block rounded-xl border bg-card p-6 shadow-sm hover:border-primary/50 transition-all hover:shadow-md"
      >
        <div className="flex items-start justify-between">
          <motion.div
            variants={scaleVariants}
            whileHover={{ scale: 1.1 }}
            className={cn('rounded-xl p-3', color)}
          >
            {icon}
          </motion.div>
          <ArrowRight className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors" />
        </div>

        <h3 className="mt-4 font-semibold">{title}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>

        {count !== undefined && (
          <div className="mt-4 pt-4 border-t">
            <span className="text-2xl font-bold">{count}</span>
            {countLabel && (
              <span className="ml-2 text-sm text-muted-foreground">{countLabel}</span>
            )}
          </div>
        )}
      </Link>
    </motion.div>
  );
}

export default function AdminPage() {
  const { data: users } = useUsers({ limit: 1 });
  const { data: approvals } = useApprovals();
  const { data: tokens } = useTokens();
  const { data: apiKeys } = useApiKeys();

  const adminCards = [
    {
      title: 'Users',
      description: 'Manage user accounts and roles',
      icon: <Users className="h-6 w-6 text-white" />,
      href: ROUTES.ADMIN_USERS,
      count: users?.total ?? 0,
      countLabel: 'registered users',
      color: 'bg-compute',
    },
    {
      title: 'Pending Approvals',
      description: 'Review and approve new registrations',
      icon: <UserCheck className="h-6 w-6 text-white" />,
      href: ROUTES.ADMIN_APPROVALS,
      count: approvals?.pendingUsers?.length ?? 0,
      countLabel: 'pending',
      color: 'bg-warning',
    },
    {
      title: 'Registration Tokens',
      description: 'Create and manage registration tokens',
      icon: <Key className="h-6 w-6 text-white" />,
      href: ROUTES.ADMIN_TOKENS,
      count: tokens?.length ?? 0,
      countLabel: 'active tokens',
      color: 'bg-networking',
    },
    {
      title: 'API Keys',
      description: 'Manage API access keys',
      icon: <Fingerprint className="h-6 w-6 text-white" />,
      href: ROUTES.ADMIN_APIKEYS,
      count: apiKeys?.length ?? 0,
      countLabel: 'API keys',
      color: 'bg-iot',
    },
    {
      title: 'Audit Log',
      description: 'View system activity and changes',
      icon: <FileText className="h-6 w-6 text-white" />,
      href: ROUTES.ADMIN_AUDIT,
      color: 'bg-hydra-blue',
    },
  ];

  return (
    <div className="p-6">
      <PageHeader
        title="Administration"
        description="Manage users, tokens, and system settings"
        actions={
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-3 py-1 text-sm font-medium text-primary">
              <Shield className="h-4 w-4" />
              Admin Access
            </span>
          </div>
        }
      />

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="grid gap-6 md:grid-cols-2 lg:grid-cols-3"
      >
        {adminCards.map((card) => (
          <AdminCard key={card.title} {...card} />
        ))}
      </motion.div>
    </div>
  );
}
