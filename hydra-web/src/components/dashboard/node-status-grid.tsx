import { Link } from 'react-router-dom';
import { ArrowRight, Server, Wifi, Cpu, HardDrive } from 'lucide-react';
import { useNodes } from '@/api/nodes';
import { ROUTES } from '@/lib/constants';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { NodeClass } from '@/types/node';

const nodeClassIcons: Record<NodeClass, typeof Server> = {
  compute: Cpu,
  networking: Wifi,
  iot: HardDrive,
};

const nodeClassColors: Record<NodeClass, string> = {
  compute: 'text-compute',
  networking: 'text-network',
  iot: 'text-iot',
};

export function NodeStatusGrid() {
  const { data, isLoading } = useNodes({ limit: 8 });
  const nodes = data?.items ?? [];

  return (
    <Card className="bg-card border-border">
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle className="text-foreground">Node Status</CardTitle>
          <CardDescription className="text-muted-foreground">
            Quick overview of all infrastructure nodes
          </CardDescription>
        </div>
        <Link to={ROUTES.NODES}>
          <Button variant="outline" size="sm">
            View All Nodes
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </Link>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {[...Array(8)].map((_, index) => (
              <div
                key={index}
                className="h-16 rounded-lg bg-muted animate-pulse"
              />
            ))}
          </div>
        ) : nodes.length === 0 ? (
          <div className="flex h-32 items-center justify-center rounded-lg bg-muted/60">
            <p className="text-sm text-muted-foreground">No nodes available</p>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {nodes.map((node) => {
              const Icon = nodeClassIcons[node.class] || Server;
              const iconColor = nodeClassColors[node.class] || 'text-muted-foreground';
              const statusColor =
                node.status === 'active'
                  ? 'bg-success'
                  : node.status === 'inactive' || node.status === 'archived'
                    ? 'bg-destructive'
                    : node.status === 'pending'
                      ? 'bg-warning'
                      : 'bg-muted-foreground';

              return (
                <Link key={node.nodeId} to={`${ROUTES.NODES}/${node.nodeId}`}>
                  <div className="flex items-center gap-3 rounded-lg border border-border bg-card/60 p-3 transition-colors hover:bg-muted">
                    <div className={cn('rounded-lg p-2 bg-muted', iconColor)}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">
                        {node.displayName || node.nodeId}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">{node.nodeId}</p>
                    </div>
                    <div className={cn('h-2.5 w-2.5 rounded-full shrink-0', statusColor)} />
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
