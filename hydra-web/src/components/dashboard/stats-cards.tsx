import { motion } from 'framer-motion';
import { Server, Boxes, Network, FolderTree, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { useNodes } from '@/api/nodes';
import { useServices } from '@/api/services';
import { useNetworks } from '@/api/networks';
import { useGroups } from '@/api/groups';
import { cn } from '@/lib/utils';
import { scaleVariants } from '@/lib/animations';

interface StatCardProps {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  trend?: { value: number; label: string };
  color: string;
  isLoading?: boolean;
}

function StatCard({ title, value, icon, trend, color, isLoading }: StatCardProps) {
  return (
    <motion.div
      variants={scaleVariants}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      className="rounded-xl border bg-card p-6 shadow-sm"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          {isLoading ? (
            <div className="mt-2 h-8 w-16 animate-pulse rounded bg-muted" />
          ) : (
            <p className="mt-2 text-3xl font-bold">{value}</p>
          )}
          {trend && !isLoading && (
            <div className="mt-2 flex items-center gap-1 text-sm">
              {trend.value > 0 ? (
                <TrendingUp className="h-4 w-4 text-success" />
              ) : trend.value < 0 ? (
                <TrendingDown className="h-4 w-4 text-error" />
              ) : (
                <Minus className="h-4 w-4 text-muted-foreground" />
              )}
              <span
                className={cn(
                  trend.value > 0
                    ? 'text-success'
                    : trend.value < 0
                    ? 'text-error'
                    : 'text-muted-foreground'
                )}
              >
                {trend.value > 0 ? '+' : ''}{trend.value}%
              </span>
              <span className="text-muted-foreground">{trend.label}</span>
            </div>
          )}
        </div>
        <div className={cn('rounded-lg p-3', color)}>
          {icon}
        </div>
      </div>
    </motion.div>
  );
}

export function StatsCards() {
  const { data: nodesData, isLoading: nodesLoading } = useNodes({ limit: 1 });
  const { data: servicesData, isLoading: servicesLoading } = useServices({ limit: 1 });
  const { data: networksData, isLoading: networksLoading } = useNetworks({ limit: 1 });
  const { data: groupsData, isLoading: groupsLoading } = useGroups({ limit: 1 });

  const stats = [
    {
      title: 'Total Nodes',
      value: nodesData?.total ?? 0,
      icon: <Server className="h-6 w-6 text-white" />,
      color: 'bg-compute',
      isLoading: nodesLoading,
    },
    {
      title: 'Services',
      value: servicesData?.total ?? 0,
      icon: <Boxes className="h-6 w-6 text-white" />,
      color: 'bg-hydra-blue',
      isLoading: servicesLoading,
    },
    {
      title: 'Networks',
      value: networksData?.total ?? 0,
      icon: <Network className="h-6 w-6 text-white" />,
      color: 'bg-networking',
      isLoading: networksLoading,
    },
    {
      title: 'Groups',
      value: groupsData?.total ?? 0,
      icon: <FolderTree className="h-6 w-6 text-white" />,
      color: 'bg-iot',
      isLoading: groupsLoading,
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat) => (
        <StatCard key={stat.title} {...stat} />
      ))}
    </div>
  );
}
