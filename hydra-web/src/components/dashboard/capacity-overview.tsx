import { useMemo } from 'react';
import { Cpu, MemoryStick, HardDrive } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip } from 'recharts';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { useCapacity } from '@/api/query';

// Generate mock metrics data for 24h chart
const generateMetricsData = () => {
  const data = [];
  const now = Date.now();
  for (let i = 23; i >= 0; i--) {
    data.push({
      time: new Date(now - i * 3600000).toLocaleTimeString([], { hour: '2-digit' }),
      cpu: Math.floor(Math.random() * 30) + 40,
      memory: Math.floor(Math.random() * 20) + 55,
    });
  }
  return data;
};

export function CapacityOverview() {
  const { data, isLoading } = useCapacity();
  const metricsData = useMemo(() => generateMetricsData(), []);

  // Mock average values (in real app, calculate from actual data)
  const avgCpu = 58;
  const avgMemory = 67;
  const avgStorage = 42;

  return (
    <Card className="bg-card border-border">
      <CardHeader>
        <CardTitle className="text-foreground">Capacity Snapshot</CardTitle>
        <CardDescription className="text-muted-foreground">
          Last captured utilization across all nodes with recent snapshots below
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* Chart */}
        <div className="h-[250px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={metricsData}>
              <defs>
                <linearGradient id="cpuGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--chart-1))" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(var(--chart-1))" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="memoryGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--chart-2))" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(var(--chart-2))" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="time"
                stroke="hsl(var(--muted-foreground))"
                fontSize={12}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                stroke="hsl(var(--muted-foreground))"
                fontSize={12}
                tickLine={false}
                axisLine={false}
                domain={[0, 100]}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--popover))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: 'hsl(var(--muted-foreground))' }}
              />
              <Area
                type="monotone"
                dataKey="cpu"
                stroke="hsl(var(--chart-1))"
                fill="url(#cpuGradient)"
                name="CPU %"
              />
              <Area
                type="monotone"
                dataKey="memory"
                stroke="hsl(var(--chart-2))"
                fill="url(#memoryGradient)"
                name="Memory %"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Resource Gauges */}
        <div className="grid grid-cols-3 gap-4 mt-6">
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center text-muted-foreground">
                <Cpu className="mr-2 h-4 w-4 text-chart-1" />
                CPU
              </span>
              <span className="text-foreground font-medium">{avgCpu}%</span>
            </div>
            <Progress value={avgCpu} className="h-2 bg-muted" indicatorClassName="bg-chart-1" />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center text-muted-foreground">
                <MemoryStick className="mr-2 h-4 w-4 text-chart-2" />
                Memory
              </span>
              <span className="text-foreground font-medium">{avgMemory}%</span>
            </div>
            <Progress value={avgMemory} className="h-2 bg-muted" indicatorClassName="bg-chart-2" />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center text-muted-foreground">
                <HardDrive className="mr-2 h-4 w-4 text-chart-3" />
                Storage
              </span>
              <span className="text-foreground font-medium">{avgStorage}%</span>
            </div>
            <Progress value={avgStorage} className="h-2 bg-muted" indicatorClassName="bg-chart-3" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
