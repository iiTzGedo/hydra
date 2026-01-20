import { Link } from 'react-router-dom';
import { Plus, Network, MessageSquare, History } from 'lucide-react';
import { StatsCards } from '@/components/dashboard/stats-cards';
import { CapacityOverview } from '@/components/dashboard/capacity-overview';
import { RecentActivity } from '@/components/dashboard/recent-activity';
import { NodeStatusGrid } from '@/components/dashboard/node-status-grid';
import { ServiceSummary } from '@/components/dashboard/service-summary';
import { MiniTopology } from '@/components/dashboard/mini-topology';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { Button } from '@/components/ui/button';
import { ROUTES } from '@/lib/constants';

export default function DashboardPage() {
  useDocumentTitle('Dashboard');

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Dashboard</h1>
          <p className="text-muted-foreground">Overview of your infrastructure</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link to={ROUTES.TOPOLOGY}>
            <Button variant="outline" size="sm">
              <Network className="mr-2 h-4 w-4" />
              Topology
            </Button>
          </Link>
          <Link to={ROUTES.TIME_MACHINE}>
            <Button variant="outline" size="sm">
              <History className="mr-2 h-4 w-4" />
              Time Machine
            </Button>
          </Link>
          <Link to={ROUTES.CHAT}>
            <Button variant="outline" size="sm">
              <MessageSquare className="mr-2 h-4 w-4" />
              AI Chat
            </Button>
          </Link>
          <Link to={ROUTES.GROUPS + '/new'}>
            <Button size="sm">
              <Plus className="mr-2 h-4 w-4" />
              New Group
            </Button>
          </Link>
        </div>
      </div>

      <StatsCards />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <CapacityOverview />
        </div>
        <RecentActivity />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ServiceSummary />
        <MiniTopology />
      </div>

      <NodeStatusGrid />
    </div>
  );
}
