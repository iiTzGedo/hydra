import { Link, useNavigate } from 'react-router-dom';
import { Server, Boxes, Network, Bell, CheckCircle2, XCircle, AlertCircle, Activity } from 'lucide-react';
import { useNodes } from '@/api/nodes';
import { useServices } from '@/api/services';
import { useNetworks } from '@/api/networks';
import { useAlertStats } from '@/api/alerts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ROUTES } from '@/lib/constants';

// Clickable stat link that stops propagation to parent Link
function DrillDownLink({
  to,
  children,
  className = '',
}: {
  to: string;
  children: React.ReactNode;
  className?: string;
}) {
  const navigate = useNavigate();

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    navigate(to);
  };

  return (
    <button
      onClick={handleClick}
      className={`hover:underline cursor-pointer ${className}`}
    >
      {children}
    </button>
  );
}

export function StatsCards() {
  const { data: nodesData, isLoading: nodesLoading } = useNodes({});
  const { data: servicesData, isLoading: servicesLoading } = useServices({});
  const { data: networksData, isLoading: networksLoading } = useNetworks({});
  const { data: alertStats, isLoading: alertsLoading } = useAlertStats();

  const totalNodes = nodesData?.total ?? 0;
  const onlineNodes = nodesData?.items?.filter((n) => n.status === 'active').length ?? 0;
  const offlineNodes = nodesData?.items?.filter((n) => n.status === 'inactive' || n.status === 'archived').length ?? 0;
  const warningNodes = nodesData?.items?.filter((n) => n.status === 'pending').length ?? 0;

  const totalServices = servicesData?.total ?? 0;
  const runningServices = servicesData?.items?.filter((s) => s.status === 'running').length ?? 0;
  const stoppedServices = servicesData?.items?.filter((s) => s.status !== 'running').length ?? 0;

  const totalNetworks = networksData?.total ?? 0;
  const physicalNetworks = networksData?.items?.filter((n) => n.type === 'physical').length ?? 0;

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <Link to={ROUTES.NODES}>
        <Card className="bg-card border-border hover:border-foreground/20 transition-colors cursor-pointer">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Nodes</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {nodesLoading ? (
              <Skeleton className="h-8 w-16 bg-muted" />
            ) : (
              <>
                <div className="text-2xl font-bold text-foreground">{totalNodes}</div>
                <div className="flex items-center gap-2 mt-1">
                  <DrillDownLink
                    to={`${ROUTES.NODES}?status=active`}
                    className="flex items-center text-xs text-success"
                  >
                    <CheckCircle2 className="mr-1 h-3 w-3 text-success" />
                    {onlineNodes} online
                  </DrillDownLink>
                  {offlineNodes > 0 && (
                    <DrillDownLink
                      to={`${ROUTES.NODES}?status=inactive`}
                      className="flex items-center text-xs text-destructive"
                    >
                      <XCircle className="mr-1 h-3 w-3 text-destructive" />
                      {offlineNodes} offline
                    </DrillDownLink>
                  )}
                  {warningNodes > 0 && (
                    <DrillDownLink
                      to={`${ROUTES.NODES}?status=pending`}
                      className="flex items-center text-xs text-warning"
                    >
                      <AlertCircle className="mr-1 h-3 w-3 text-warning" />
                      {warningNodes} warning
                    </DrillDownLink>
                  )}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </Link>

      <Link to={ROUTES.SERVICES}>
        <Card className="bg-card border-border hover:border-foreground/20 transition-colors cursor-pointer">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Services</CardTitle>
            <Boxes className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {servicesLoading ? (
              <Skeleton className="h-8 w-16 bg-muted" />
            ) : (
              <>
                <div className="text-2xl font-bold text-foreground">{totalServices}</div>
                <div className="flex items-center gap-2 mt-1">
                  <DrillDownLink
                    to={`${ROUTES.SERVICES}?status=running`}
                    className="flex items-center text-xs text-success"
                  >
                    <Activity className="mr-1 h-3 w-3 text-success" />
                    {runningServices} running
                  </DrillDownLink>
                  {stoppedServices > 0 && (
                    <DrillDownLink
                      to={`${ROUTES.SERVICES}?status=stopped`}
                      className="text-xs text-muted-foreground"
                    >
                      {stoppedServices} stopped
                    </DrillDownLink>
                  )}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </Link>

      <Link to={ROUTES.NETWORKS}>
        <Card className="bg-card border-border hover:border-foreground/20 transition-colors cursor-pointer">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Networks</CardTitle>
            <Network className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {networksLoading ? (
              <Skeleton className="h-8 w-16 bg-muted" />
            ) : (
              <>
                <div className="text-2xl font-bold text-foreground">{totalNetworks}</div>
                <div className="flex items-center gap-2 mt-1">
                  <DrillDownLink
                    to={`${ROUTES.NETWORKS}?type=physical`}
                    className="text-xs text-muted-foreground"
                  >
                    {physicalNetworks} physical
                  </DrillDownLink>
                  <span className="text-xs text-muted-foreground">,</span>
                  <DrillDownLink
                    to={`${ROUTES.NETWORKS}?type=virtual`}
                    className="text-xs text-muted-foreground"
                  >
                    {totalNetworks - physicalNetworks} virtual
                  </DrillDownLink>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </Link>

      <Link to="/alerts">
        <Card className="bg-card border-border hover:border-foreground/20 transition-colors cursor-pointer">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Alerts</CardTitle>
            <Bell className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {alertsLoading ? (
              <Skeleton className="h-8 w-16 bg-muted" />
            ) : (
              <>
                <div className="text-2xl font-bold text-foreground">
                  {alertStats?.unacknowledged ?? 0}
                </div>
                <div className="flex items-center gap-2 mt-1">
                  {(alertStats?.critical ?? 0) > 0 && (
                    <DrillDownLink
                      to="/alerts?severity=critical"
                      className="flex items-center text-xs text-destructive"
                    >
                      <XCircle className="mr-1 h-3 w-3" />
                      {alertStats?.critical} critical
                    </DrillDownLink>
                  )}
                  {(alertStats?.warning ?? 0) > 0 && (
                    <DrillDownLink
                      to="/alerts?severity=warning"
                      className="flex items-center text-xs text-warning"
                    >
                      <AlertCircle className="mr-1 h-3 w-3" />
                      {alertStats?.warning} warning
                    </DrillDownLink>
                  )}
                  {(alertStats?.unacknowledged ?? 0) === 0 && (
                    <span className="text-xs text-muted-foreground">
                      No active alerts
                    </span>
                  )}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </Link>
    </div>
  );
}
