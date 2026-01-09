import { StatsCards } from '@/components/dashboard/stats-cards';
import { CapacityOverview } from '@/components/dashboard/capacity-overview';
import { RecentActivity } from '@/components/dashboard/recent-activity';
import { NodeStatusGrid } from '@/components/dashboard/node-status-grid';
import { ServiceSummary } from '@/components/dashboard/service-summary';
import { MiniTopology } from '@/components/dashboard/mini-topology';

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      {/* Stats cards */}
      <StatsCards />

      {/* Main content grid - Resource usage (2 cols) + Activity (1 col) */}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <CapacityOverview />
        </div>
        <RecentActivity />
      </div>

      {/* Services and Topology row */}
      <div className="grid gap-6 lg:grid-cols-2">
        <ServiceSummary />
        <MiniTopology />
      </div>

      {/* Node Status Grid */}
      <NodeStatusGrid />
    </div>
  );
}
