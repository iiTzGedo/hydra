import { Link } from 'react-router-dom';
import { Server, Boxes, Network, AlertTriangle, CheckCircle2, XCircle, AlertCircle, Activity } from 'lucide-react';
import { useNodes } from '@/api/nodes';
import { useServices } from '@/api/services';
import { useNetworks } from '@/api/networks';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ROUTES } from '@/lib/constants';

export function StatsCards() {
  const { data: nodesData, isLoading: nodesLoading } = useNodes({});
  const { data: servicesData, isLoading: servicesLoading } = useServices({});
  const { data: networksData, isLoading: networksLoading } = useNetworks({});

  const totalNodes = nodesData?.total ?? 0;
  const onlineNodes = nodesData?.items?.filter((n) => n.status === 'active').length ?? 0;
  const offlineNodes = nodesData?.items?.filter((n) => n.status === 'inactive' || n.status === 'archived').length ?? 0;
  const warningNodes = nodesData?.items?.filter((n) => n.status === 'pending').length ?? 0;

  const totalServices = servicesData?.total ?? 0;
  const runningServices = servicesData?.items?.filter((s) => s.status === 'running').length ?? 0;
  const stoppedServices = servicesData?.items?.filter((s) => s.status !== 'running').length ?? 0;

  const totalNetworks = networksData?.total ?? 0;
  const physicalNetworks = networksData?.items?.filter((n) => n.type === 'physical').length ?? 0;

  const criticalAlerts = 2;
  const warningAlerts = 3;

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
                  <span className="flex items-center text-xs text-success">
                    <CheckCircle2 className="mr-1 h-3 w-3 text-success" />
                    {onlineNodes} online
                  </span>
                  {offlineNodes > 0 && (
                    <span className="flex items-center text-xs text-destructive">
                      <XCircle className="mr-1 h-3 w-3 text-destructive" />
                      {offlineNodes} offline
                    </span>
                  )}
                  {warningNodes > 0 && (
                    <span className="flex items-center text-xs text-warning">
                      <AlertCircle className="mr-1 h-3 w-3 text-warning" />
                      {warningNodes} warning
                    </span>
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
                  <span className="flex items-center text-xs text-success">
                    <Activity className="mr-1 h-3 w-3 text-success" />
                    {runningServices} running
                  </span>
                  {stoppedServices > 0 && (
                    <span className="text-xs text-muted-foreground">
                      {stoppedServices} stopped
                    </span>
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
                <p className="text-xs text-muted-foreground mt-1">
                  {physicalNetworks} physical, {totalNetworks - physicalNetworks} virtual
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </Link>

      <Link to="/alerts">
        <Card className="bg-card border-border hover:border-foreground/20 transition-colors cursor-pointer">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Active Alerts</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">{criticalAlerts + warningAlerts}</div>
            <div className="flex items-center gap-2 mt-1">
              {criticalAlerts > 0 && (
                <Badge variant="destructive" className="text-[10px]">
                  {criticalAlerts} critical
                </Badge>
              )}
              {warningAlerts > 0 && (
                <Badge variant="warning" className="text-[10px]">
                  {warningAlerts} warning
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
      </Link>
    </div>
  );
}
