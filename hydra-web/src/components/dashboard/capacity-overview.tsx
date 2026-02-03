import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Cpu, MemoryStick, HardDrive, Server, Layers, ArrowRight } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useCapacity } from '@/api/query';
import { formatMemoryGB, formatStorageTB } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

// Colors mapped to node classes using the project's CSS variables
const CLASS_CHART_COLORS: Record<string, string> = {
  compute: 'hsl(var(--compute))',
  networking: 'hsl(var(--network))',
  iot: 'hsl(var(--iot))',
};

// Fallback colors for any unexpected classes
const FALLBACK_COLORS = [
  'hsl(var(--chart-1))',
  'hsl(var(--chart-3))',
  'hsl(var(--chart-4))',
];

function getClassColor(className: string, index: number): string {
  return CLASS_CHART_COLORS[className] ?? FALLBACK_COLORS[index % FALLBACK_COLORS.length];
}

const tooltipStyle = {
  backgroundColor: 'hsl(var(--popover))',
  border: '1px solid hsl(var(--border))',
  borderRadius: '8px',
  color: 'hsl(var(--popover-foreground))',
  fontSize: '12px',
};

export function CapacityOverview() {
  const { data, isLoading } = useCapacity();

  const summary = data?.summary;
  const byClass = data?.byClass;

  const pieData = useMemo(() => {
    if (!byClass) return [];
    return Object.entries(byClass).map(([className, capacity]) => ({
      name: className.charAt(0).toUpperCase() + className.slice(1),
      value: capacity.nodes,
      className,
    }));
  }, [byClass]);

  const barData = useMemo(() => {
    if (!byClass) return [];
    return Object.entries(byClass).map(([className, capacity]) => ({
      name: className.charAt(0).toUpperCase() + className.slice(1),
      className,
      cores: capacity.cores ?? 0,
      memoryGB: capacity.memoryGB ? Math.round(capacity.memoryGB * 10) / 10 : 0,
      storageTB: capacity.storageTB ? Math.round(capacity.storageTB * 100) / 100 : 0,
    }));
  }, [byClass]);

  const classNames = useMemo(() => {
    if (!byClass) return [];
    return Object.keys(byClass);
  }, [byClass]);

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
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Skeleton className="h-64 rounded-lg" />
              <Skeleton className="h-64 rounded-lg" />
            </div>
          </div>
        ) : !summary ? (
          <div className="flex h-32 items-center justify-center rounded-lg bg-muted/60">
            <p className="text-sm text-muted-foreground">No capacity data available</p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Summary metric cards with drill-down links */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Link
                to={ROUTES.NODES}
                className="rounded-lg border bg-muted/30 p-4 hover:border-foreground/20 transition-colors group"
              >
                <div className="flex items-center justify-between text-muted-foreground mb-2">
                  <div className="flex items-center gap-2">
                    <Server className="h-4 w-4" />
                    <span className="text-xs font-medium uppercase">Nodes</span>
                  </div>
                  <ArrowRight className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <div className="text-2xl font-bold text-foreground">{summary.totalNodes}</div>
                <div className="text-xs text-muted-foreground mt-1">
                  {summary.physicalNodes} physical, {summary.logicalNodes} logical
                </div>
              </Link>

              <Link
                to={`${ROUTES.NODES}?sort=cores`}
                className="rounded-lg border bg-muted/30 p-4 hover:border-foreground/20 transition-colors group"
              >
                <div className="flex items-center justify-between text-muted-foreground mb-2">
                  <div className="flex items-center gap-2">
                    <Cpu className="h-4 w-4 text-chart-1" />
                    <span className="text-xs font-medium uppercase">CPU Cores</span>
                  </div>
                  <ArrowRight className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <div className="text-2xl font-bold text-foreground">{summary.totalCores}</div>
                <div className="text-xs text-muted-foreground mt-1">total cores</div>
              </Link>

              <Link
                to={`${ROUTES.NODES}?sort=memory`}
                className="rounded-lg border bg-muted/30 p-4 hover:border-foreground/20 transition-colors group"
              >
                <div className="flex items-center justify-between text-muted-foreground mb-2">
                  <div className="flex items-center gap-2">
                    <MemoryStick className="h-4 w-4 text-chart-2" />
                    <span className="text-xs font-medium uppercase">Memory</span>
                  </div>
                  <ArrowRight className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <div className="text-2xl font-bold text-foreground">
                  {formatMemoryGB(summary.totalMemoryGB)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">total RAM</div>
              </Link>

              <Link
                to={`${ROUTES.NODES}?sort=storage`}
                className="rounded-lg border bg-muted/30 p-4 hover:border-foreground/20 transition-colors group"
              >
                <div className="flex items-center justify-between text-muted-foreground mb-2">
                  <div className="flex items-center gap-2">
                    <HardDrive className="h-4 w-4 text-chart-3" />
                    <span className="text-xs font-medium uppercase">Storage</span>
                  </div>
                  <ArrowRight className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <div className="text-2xl font-bold text-foreground">
                  {formatStorageTB(summary.totalStorageTB)}
                </div>
                <div className="text-xs text-muted-foreground mt-1">total capacity</div>
              </Link>
            </div>

            {/* Charts section */}
            {byClass && Object.keys(byClass).length > 0 && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {/* Donut chart: Node distribution by class */}
                <div className="rounded-lg border bg-muted/30 p-4">
                  <div className="flex items-center gap-2 text-muted-foreground mb-4">
                    <Layers className="h-4 w-4" />
                    <span className="text-xs font-medium uppercase">Nodes by Class</span>
                  </div>
                  <div className="h-[220px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={pieData}
                          cx="50%"
                          cy="50%"
                          innerRadius={55}
                          outerRadius={85}
                          paddingAngle={3}
                          dataKey="value"
                          stroke="none"
                        >
                          {pieData.map((entry, index) => (
                            <Cell
                              key={entry.className}
                              fill={getClassColor(entry.className, index)}
                            />
                          ))}
                        </Pie>
                        <Tooltip
                          contentStyle={tooltipStyle}
                          formatter={(value: number, name: string) => [
                            `${value} node${value !== 1 ? 's' : ''}`,
                            name,
                          ]}
                        />
                        <Legend
                          verticalAlign="bottom"
                          height={36}
                          formatter={(value: string) => (
                            <span style={{ color: 'hsl(var(--foreground))', fontSize: '12px' }}>
                              {value}
                            </span>
                          )}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  {/* Class drill-down links */}
                  <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-border">
                    {classNames.map((className) => (
                      <Link
                        key={className}
                        to={`${ROUTES.NODES}?class=${className}`}
                        className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground transition-colors"
                      >
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ backgroundColor: getClassColor(className, 0) }}
                        />
                        <span className="capitalize">{className}</span>
                        <span className="text-muted-foreground">
                          ({byClass[className].nodes})
                        </span>
                        <ArrowRight className="h-3 w-3 opacity-60" />
                      </Link>
                    ))}
                  </div>
                </div>

                {/* Stacked bar chart: Resource utilization by class */}
                <div className="rounded-lg border bg-muted/30 p-4">
                  <div className="flex items-center gap-2 text-muted-foreground mb-4">
                    <Cpu className="h-4 w-4" />
                    <span className="text-xs font-medium uppercase">Resources by Class</span>
                  </div>
                  <div className="h-[220px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={barData}
                        layout="vertical"
                        margin={{ top: 0, right: 16, left: 0, bottom: 0 }}
                      >
                        <XAxis
                          type="number"
                          stroke="hsl(var(--muted-foreground))"
                          fontSize={11}
                          tickLine={false}
                          axisLine={false}
                        />
                        <YAxis
                          type="category"
                          dataKey="name"
                          stroke="hsl(var(--muted-foreground))"
                          fontSize={11}
                          tickLine={false}
                          axisLine={false}
                          width={80}
                        />
                        <Tooltip
                          contentStyle={tooltipStyle}
                          formatter={(value: number, name: string) => {
                            const labels: Record<string, string> = {
                              cores: 'CPU Cores',
                              memoryGB: 'Memory (GB)',
                              storageTB: 'Storage (TB)',
                            };
                            const units: Record<string, string> = {
                              cores: '',
                              memoryGB: ' GB',
                              storageTB: ' TB',
                            };
                            return [
                              `${value}${units[name] ?? ''}`,
                              labels[name] ?? name,
                            ];
                          }}
                        />
                        <Legend
                          verticalAlign="bottom"
                          height={36}
                          formatter={(value: string) => {
                            const labels: Record<string, string> = {
                              cores: 'Cores',
                              memoryGB: 'Memory (GB)',
                              storageTB: 'Storage (TB)',
                            };
                            return (
                              <span style={{ color: 'hsl(var(--foreground))', fontSize: '12px' }}>
                                {labels[value] ?? value}
                              </span>
                            );
                          }}
                        />
                        <Bar
                          dataKey="cores"
                          fill="hsl(var(--chart-1))"
                          radius={[0, 4, 4, 0]}
                          barSize={14}
                        />
                        <Bar
                          dataKey="memoryGB"
                          fill="hsl(var(--chart-2))"
                          radius={[0, 4, 4, 0]}
                          barSize={14}
                        />
                        <Bar
                          dataKey="storageTB"
                          fill="hsl(var(--chart-3))"
                          radius={[0, 4, 4, 0]}
                          barSize={14}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            )}

            {/* By class detail cards with drill-down links */}
            {byClass && Object.keys(byClass).length > 0 && (
              <div className="rounded-lg border bg-muted/30 p-4">
                <div className="flex items-center gap-2 text-muted-foreground mb-3">
                  <Layers className="h-4 w-4" />
                  <span className="text-xs font-medium uppercase">By Node Class</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {Object.entries(byClass).map(([className, capacity]) => (
                    <Link
                      key={className}
                      to={`${ROUTES.NODES}?class=${className}`}
                      className="flex items-center justify-between rounded-lg border bg-card/50 p-3 hover:border-foreground/20 transition-colors group"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span
                            className="h-2.5 w-2.5 rounded-full"
                            style={{ backgroundColor: getClassColor(className, 0) }}
                          />
                          <span className="font-medium capitalize text-foreground">{className}</span>
                        </div>
                        <div className="text-xs text-muted-foreground mt-1 ml-[18px]">
                          {capacity.nodes} node{capacity.nodes !== 1 ? 's' : ''}
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="text-right text-sm text-muted-foreground">
                          {capacity.cores != null && <div>{capacity.cores} cores</div>}
                          {capacity.memoryGB != null && <div>{formatMemoryGB(capacity.memoryGB)}</div>}
                          {capacity.storageTB != null && <div>{formatStorageTB(capacity.storageTB)}</div>}
                        </div>
                        <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                    </Link>
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
