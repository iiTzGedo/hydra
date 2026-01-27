import { Cpu, MemoryStick, HardDrive, Server, Layers } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useCapacity } from '@/api/query';
import { formatMemoryGB, formatStorageTB } from '@/lib/utils';

export function CapacityOverview() {
  const { data, isLoading } = useCapacity();

  const summary = data?.summary;
  const byClass = data?.byClass;

  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="text-foreground">Infrastructure Capacity</CardTitle>
        <CardDescription className="text-muted-foreground">
          Aggregated hardware resources from profiled nodes
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-20 rounded-lg" />
              ))}
            </div>
            <Skeleton className="h-32 rounded-lg" />
          </div>
        ) : !summary ? (
          <div className="flex h-32 items-center justify-center rounded-lg bg-muted/60">
            <p className="text-sm text-muted-foreground">No capacity data available</p>
          </div>
        ) : (
          <div className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="rounded-lg border bg-muted/30 p-4">
                <div className="flex items-center gap-2 text-muted-foreground mb-2">
                  <Server className="h-4 w-4" />
                  <span className="text-xs font-medium uppercase">Nodes</span>
                </div>
                <div className="text-2xl font-bold text-foreground">{summary.totalNodes}</div>
                <div className="text-xs text-muted-foreground mt-1">
                  {summary.physicalNodes} physical, {summary.logicalNodes} logical
                </div>
              </div>

              <div className="rounded-lg border bg-muted/30 p-4">
                <div className="flex items-center gap-2 text-muted-foreground mb-2">
                  <Cpu className="h-4 w-4 text-chart-1" />
                  <span className="text-xs font-medium uppercase">CPU Cores</span>
                </div>
                <div className="text-2xl font-bold text-foreground">{summary.totalCores}</div>
                <div className="text-xs text-muted-foreground mt-1">total cores</div>
              </div>

              <div className="rounded-lg border bg-muted/30 p-4">
                <div className="flex items-center gap-2 text-muted-foreground mb-2">
                  <MemoryStick className="h-4 w-4 text-chart-2" />
                  <span className="text-xs font-medium uppercase">Memory</span>
                </div>
                <div className="text-2xl font-bold text-foreground">
                  {formatMemoryGB(summary.totalMemoryGB)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">total RAM</div>
              </div>

              <div className="rounded-lg border bg-muted/30 p-4">
                <div className="flex items-center gap-2 text-muted-foreground mb-2">
                  <HardDrive className="h-4 w-4 text-chart-3" />
                  <span className="text-xs font-medium uppercase">Storage</span>
                </div>
                <div className="text-2xl font-bold text-foreground">
                  {formatStorageTB(summary.totalStorageTB)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">total capacity</div>
              </div>
            </div>

            {byClass && Object.keys(byClass).length > 0 && (
              <div className="rounded-lg border bg-muted/30 p-4">
                <div className="flex items-center gap-2 text-muted-foreground mb-3">
                  <Layers className="h-4 w-4" />
                  <span className="text-xs font-medium uppercase">By Node Class</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {Object.entries(byClass).map(([className, capacity]) => (
                    <div key={className} className="flex items-center justify-between">
                      <div>
                        <div className="font-medium capitalize text-foreground">{className}</div>
                        <div className="text-xs text-muted-foreground">
                          {capacity.nodes} node{capacity.nodes !== 1 ? 's' : ''}
                        </div>
                      </div>
                      <div className="text-right text-sm text-muted-foreground">
                        {capacity.cores && <div>{capacity.cores} cores</div>}
                        {capacity.memoryGB && <div>{formatMemoryGB(capacity.memoryGB)}</div>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
