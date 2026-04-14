import { useRouter } from 'next/navigation';
import {
  Server,
  Boxes,
  Network,
  Bell,
  CheckCircle2,
  XCircle,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  ArrowRight,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { useNodes } from '@/api/nodes';
import { useServices } from '@/api/services';
import { useNetworks } from '@/api/networks';
import { useNotificationStats } from '@/api/notifications';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton, SkeletonStats } from '@/components/ui/skeleton';
import { ROUTES } from '@/lib/constants';
import { cn } from '@/lib/utils';

// Color variants for stat cards
const colorVariants = {
  blue: {
    bg: 'bg-blue-500/10',
    text: 'text-blue-500',
    border: 'border-blue-500/20',
    gradient: 'from-blue-500/20 to-blue-500/5',
  },
  purple: {
    bg: 'bg-purple-500/10',
    text: 'text-purple-500',
    border: 'border-purple-500/20',
    gradient: 'from-purple-500/20 to-purple-500/5',
  },
  cyan: {
    bg: 'bg-cyan-500/10',
    text: 'text-cyan-500',
    border: 'border-cyan-500/20',
    gradient: 'from-cyan-500/20 to-cyan-500/5',
  },
  amber: {
    bg: 'bg-amber-500/10',
    text: 'text-amber-500',
    border: 'border-amber-500/20',
    gradient: 'from-amber-500/20 to-amber-500/5',
  },
};

interface DetailItem {
  label: string;
  value: number;
  href?: string;
  variant?: 'success' | 'destructive' | 'warning' | 'default';
}

interface StatCardProps {
  title: string;
  value: number | string;
  icon: React.ElementType;
  href: string;
  loading?: boolean;
  trend?: {
    value: number;
    direction: 'up' | 'down' | 'neutral';
    label: string;
  } | null;
  details?: DetailItem[];
  color: 'blue' | 'purple' | 'cyan' | 'amber';
}

/**
 * StatCard - Individual stat card with drill-down support
 *
 * IMPORTANT: Uses div with onClick instead of Link to avoid nesting issues
 * The card is clickable to navigate to the main href, and detail buttons
 * can navigate to specific filtered views.
 *
 * @example
 * <StatCard
 *   title="Total Nodes"
 *   value={12}
 *   icon={Server}
 *   href="/nodes"
 *   color="purple"
 *   details={[
 *     { label: 'online', value: 10, href: '/nodes?status=active', variant: 'success' },
 *   ]}
 * />
 */
function StatCard({
  title,
  value,
  icon: Icon,
  href,
  loading,
  trend,
  details,
  color,
}: StatCardProps) {
  const router = useRouter();
  const colors = colorVariants[color];

  if (loading) {
    return (
      <Card className="bg-card border-border overflow-hidden">
        <CardContent className="p-6">
          <div className="flex items-start justify-between">
            <div className="space-y-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-8 w-16" />
            </div>
            <Skeleton className="h-10 w-10 rounded-lg" />
          </div>
        </CardContent>
      </Card>
    );
  }

  // Handle card click - navigate to main href
  const handleCardClick = () => {
    router.push(href);
  };

  // Handle detail button click - navigate to specific href
  const handleDetailClick = (e: React.MouseEvent, detailHref?: string) => {
    if (!detailHref) return;
    e.stopPropagation(); // Prevent card click
    router.push(detailHref);
  };

  return (
    <motion.div
      whileHover={{ y: -2, transition: { duration: 0.2 } }}
      whileTap={{ scale: 0.98 }}
      onClick={handleCardClick}
      className="cursor-pointer group"
      role="link"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleCardClick();
        }
      }}
      aria-label={`${title}: ${value}`}
    >
      <Card
        className={cn(
          'bg-card border-border overflow-hidden',
          'transition-all duration-200 hover:shadow-lg hover:border-foreground/10'
        )}
      >
        <CardContent className="p-6">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">{title}</p>
              <div className="flex items-baseline gap-2">
                <h3 className="text-3xl font-bold text-foreground tracking-tight">
                  {value}
                </h3>
                {trend && (
                  <div
                    className={cn(
                      'flex items-center text-xs font-medium',
                      trend.direction === 'up'
                        ? 'text-success'
                        : trend.direction === 'down'
                        ? 'text-destructive'
                        : 'text-muted-foreground'
                    )}
                  >
                    {trend.direction === 'up' ? (
                      <TrendingUp className="h-3 w-3 mr-0.5" />
                    ) : trend.direction === 'down' ? (
                      <TrendingDown className="h-3 w-3 mr-0.5" />
                    ) : null}
                    {trend.label}
                  </div>
                )}
              </div>
            </div>
            <div
              className={cn(
                'p-3 rounded-xl bg-gradient-to-br',
                colors.gradient,
                colors.border,
                'border group-hover:scale-110 transition-transform duration-200'
              )}
            >
              <Icon className={cn('h-5 w-5', colors.text)} />
            </div>
          </div>

          {/* Details row - use buttons instead of links to avoid nesting */}
          <div className="mt-4 pt-4 border-t border-border/50 min-h-[32px] flex items-center gap-3 flex-wrap">
            {details && details.length > 0 ? (
              <>
                {details.map((detail, index) => (
                  <button
                    key={index}
                    onClick={(e) => handleDetailClick(e, detail.href)}
                    className={cn(
                      'flex items-center text-xs font-medium transition-colors',
                      'rounded px-1.5 py-0.5 hover:bg-muted',
                      'focus:outline-none focus:ring-2 focus:ring-primary/20',
                      detail.variant === 'success' &&
                        'text-success hover:text-success/80',
                      detail.variant === 'destructive' &&
                        'text-destructive hover:text-destructive/80',
                      detail.variant === 'warning' &&
                        'text-warning hover:text-warning/80',
                      (!detail.variant || detail.variant === 'default') &&
                        'text-muted-foreground hover:text-foreground'
                    )}
                    disabled={!detail.href}
                  >
                    {detail.variant === 'success' && (
                      <CheckCircle2 className="mr-1 h-3 w-3" />
                    )}
                    {detail.variant === 'destructive' && (
                      <XCircle className="mr-1 h-3 w-3" />
                    )}
                    {detail.variant === 'warning' && (
                      <AlertCircle className="mr-1 h-3 w-3" />
                    )}
                    {detail.value} {detail.label}
                  </button>
                ))}
                <ArrowRight className="h-3 w-3 text-muted-foreground ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
              </>
            ) : (
              <span className="text-xs text-muted-foreground/50">—</span>
            )}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

/**
 * StatsCards - Dashboard statistics overview
 *
 * Displays key metrics for nodes, services, networks, and notifications
 * with drill-down navigation to filtered views.
 *
 * Note: Trend data is currently hardcoded. In production, this should
 * be calculated from historical data.
 */
export function StatsCards() {
  const { data: nodesData, isLoading: nodesLoading } = useNodes({});
  const { data: servicesData, isLoading: servicesLoading } = useServices({});
  const { data: networksData, isLoading: networksLoading } = useNetworks({});
  const { data: notifStats, isLoading: notifLoading } = useNotificationStats();

  const totalNodes = nodesData?.total ?? 0;
  const onlineNodes =
    nodesData?.items?.filter((n) => n.status === 'active').length ?? 0;
  const offlineNodes =
    nodesData?.items?.filter(
      (n) => n.status === 'inactive' || n.status === 'archived'
    ).length ?? 0;
  const warningNodes =
    nodesData?.items?.filter((n) => n.status === 'pending').length ?? 0;

  const totalServices = servicesData?.total ?? 0;
  const runningServices =
    servicesData?.items?.filter((s) => s.status === 'running').length ?? 0;
  const stoppedServices =
    servicesData?.items?.filter((s) => s.status !== 'running').length ?? 0;

  const totalNetworks = networksData?.total ?? 0;
  const physicalNetworks =
    networksData?.items?.filter((n) => n.type === 'physical').length ?? 0;

  const criticalCount = notifStats?.byTier?.critical ?? 0;
  const highCount = notifStats?.byTier?.high ?? 0;
  const warningCount = notifStats?.byTier?.warning ?? 0;
  const needsAttention = notifStats?.needsAttention ?? 0;
  const acknowledgedPending = notifStats?.acknowledgedPending ?? 0;

  // Show skeleton loading state
  if (nodesLoading || servicesLoading || networksLoading || notifLoading) {
    return <SkeletonStats count={4} />;
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <StatCard
        title="Total Nodes"
        value={totalNodes}
        icon={Server}
        href={ROUTES.NODES}
        color="purple"
        trend={null} // Remove hardcoded trend - should be calculated from historical data
        details={[
          {
            label: 'online',
            value: onlineNodes,
            href: `${ROUTES.NODES}?status=active`,
            variant: 'success',
          },
          ...(offlineNodes > 0
            ? [
                {
                  label: 'offline',
                  value: offlineNodes,
                  href: `${ROUTES.NODES}?status=inactive`,
                  variant: 'destructive' as const,
                },
              ]
            : []),
          ...(warningNodes > 0
            ? [
                {
                  label: 'warning',
                  value: warningNodes,
                  href: `${ROUTES.NODES}?status=pending`,
                  variant: 'warning' as const,
                },
              ]
            : []),
        ]}
      />

      <StatCard
        title="Services"
        value={totalServices}
        icon={Boxes}
        href={ROUTES.SERVICES}
        color="blue"
        details={[
          {
            label: 'running',
            value: runningServices,
            href: `${ROUTES.SERVICES}?status=running`,
            variant: 'success',
          },
          ...(stoppedServices > 0
            ? [
                {
                  label: 'stopped',
                  value: stoppedServices,
                  href: `${ROUTES.SERVICES}?status=stopped`,
                  variant: 'default' as const,
                },
              ]
            : []),
        ]}
      />

      <StatCard
        title="Networks"
        value={totalNetworks}
        icon={Network}
        href={ROUTES.NETWORKS}
        color="cyan"
        details={[
          { label: 'physical', value: physicalNetworks },
          { label: 'virtual', value: totalNetworks - physicalNetworks },
        ]}
      />

      <StatCard
        title="Notifications"
        value={needsAttention}
        icon={Bell}
        href={ROUTES.NOTIFICATIONS}
        color="amber"
        trend={
          needsAttention > 0
            ? {
                value: notifStats?.unread ?? 0,
                direction: 'neutral',
                label: `${notifStats?.unread ?? 0} unread`,
              }
            : null
        }
        details={[
          ...(criticalCount > 0
            ? [
                {
                  label: 'critical',
                  value: criticalCount,
                  href: `${ROUTES.NOTIFICATIONS}?tier=5`,
                  variant: 'destructive' as const,
                },
              ]
            : []),
          ...(highCount > 0
            ? [
                {
                  label: 'high',
                  value: highCount,
                  href: `${ROUTES.NOTIFICATIONS}?tier=4`,
                  variant: 'warning' as const,
                },
              ]
            : []),
          ...(warningCount > 0
            ? [
                {
                  label: 'warning',
                  value: warningCount,
                  href: `${ROUTES.NOTIFICATIONS}?tier=3`,
                  variant: 'warning' as const,
                },
              ]
            : []),
          ...(acknowledgedPending > 0
            ? [
                {
                  label: 'in progress',
                  value: acknowledgedPending,
                  href: `${ROUTES.NOTIFICATIONS}?acknowledged=true`,
                  variant: 'success' as const,
                },
              ]
            : []),
          ...(needsAttention === 0
            ? [
                {
                  label: 'All clear',
                  value: 0,
                  variant: 'success' as const,
                },
              ]
            : []),
        ]}
      />
    </div>
  );
}
