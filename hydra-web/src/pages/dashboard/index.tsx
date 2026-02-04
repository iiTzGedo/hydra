import { Link } from 'react-router-dom';
import { Plus, Network, MessageSquare, History, LayoutGrid, ArrowRight, Maximize2, Boxes } from 'lucide-react';
import { motion } from 'framer-motion';
import { StatsCards } from '@/components/dashboard/stats-cards';
import { CapacityOverview } from '@/components/dashboard/capacity-overview';
import { RecentActivity } from '@/components/dashboard/recent-activity';
import { NodeStatusGrid } from '@/components/dashboard/node-status-grid';
import { ServiceSummary } from '@/components/dashboard/service-summary';
import { MiniTopology } from '@/components/dashboard/mini-topology';
import { TimeRangeSelector } from '@/components/dashboard/time-range-selector';
import { WidgetGrid, Widget, WidgetCustomizer } from '@/components/dashboard/widget-grid';
import { PageHeaderLayout } from '@/components/layout/page-header-layout';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { Button } from '@/components/ui/button';
import { ROUTES } from '@/lib/constants';

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.3,
      ease: [0.16, 1, 0.3, 1],
    },
  },
};

/**
 * DashboardPage - Main dashboard view
 *
 * Features:
 * - Stats overview cards
 * - Customizable widget grid
 * - Service status summary
 * - Recent activity feed
 * - Capacity overview charts
 * - Mini topology visualization
 * - Node status grid
 */
export default function DashboardPage() {
  useDocumentTitle('Dashboard');

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="space-y-6"
    >
      {/* Header with new PageHeaderLayout */}
      <motion.div variants={itemVariants}>
        <PageHeaderLayout
          title="Dashboard"
          subtitle="Overview of your infrastructure"
          showBreadcrumbs={false}
          showBackButton={false}
          actions={
            <>
              <TimeRangeSelector />
              <WidgetCustomizer />
              <Link to={ROUTES.GROUPS + '/new'}>
                <Button size="sm">
                  <Plus className="mr-2 h-4 w-4" />
                  New Group
                </Button>
              </Link>
            </>
          }
        />
      </motion.div>

      {/* Quick Actions Bar */}
      <motion.div variants={itemVariants} className="flex flex-wrap gap-2">
        <Link to={ROUTES.TOPOLOGY}>
          <Button variant="outline" size="sm" className="group">
            <Network className="mr-2 h-4 w-4 text-primary transition-transform group-hover:scale-110" />
            Topology
          </Button>
        </Link>
        <Link to={ROUTES.TIME_MACHINE}>
          <Button variant="outline" size="sm" className="group">
            <History className="mr-2 h-4 w-4 text-info transition-transform group-hover:scale-110" />
            Time Machine
          </Button>
        </Link>
        <Link to={ROUTES.CHAT}>
          <Button variant="outline" size="sm" className="group">
            <MessageSquare className="mr-2 h-4 w-4 text-compute transition-transform group-hover:scale-110" />
            AI Chat
          </Button>
        </Link>
      </motion.div>

      {/* Stats Overview */}
      <motion.div variants={itemVariants}>
        <StatsCards />
      </motion.div>

      {/* Main Content Grid */}
      <WidgetGrid>
        {/* Capacity Overview - Full width */}
        <motion.div variants={itemVariants}>
          <Widget
            id="capacity"
            title="Infrastructure Capacity"
            description="Aggregated hardware resources from profiled nodes"
            icon={LayoutGrid}
          >
            <CapacityOverview />
          </Widget>
        </motion.div>

        {/* Service Status + Recent Activity - side by side */}
        <motion.div variants={itemVariants} className="grid gap-6 lg:grid-cols-2">
          <Widget
            id="services"
            title="Service Status"
            icon={Boxes}
            actions={
              <Link to={ROUTES.SERVICES}>
                <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground">
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
            }
          >
            <ServiceSummary />
          </Widget>
          <Widget
            id="notifications"
            title="Recent Activity"
            description="Latest events and changes"
            actions={
              <Link to={`${ROUTES.SETTINGS}?bottom=audit`}>
                <Button variant="ghost" size="sm" className="group/btn text-muted-foreground">
                  View all
                  <ArrowRight className="ml-1 h-4 w-4 transition-transform group-hover/btn:translate-x-0.5" />
                </Button>
              </Link>
            }
          >
            <RecentActivity />
          </Widget>
        </motion.div>

        {/* Mini Topology */}
        <motion.div variants={itemVariants}>
          <Widget
            id="topology-mini"
            title="Infrastructure Topology"
            actions={
              <Link to={ROUTES.TOPOLOGY}>
                <Button variant="outline" size="sm">
                  <Maximize2 className="mr-2 h-4 w-4" />
                  Full view
                </Button>
              </Link>
            }
          >
            <MiniTopology />
          </Widget>
        </motion.div>

        {/* Node Status Grid */}
        <motion.div variants={itemVariants}>
          <Widget
            id="activity"
            title="Node Status"
            actions={
              <Link to={ROUTES.NODES}>
                <Button variant="outline" size="sm" className="group/btn">
                  View All
                  <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover/btn:translate-x-0.5" />
                </Button>
              </Link>
            }
          >
            <NodeStatusGrid />
          </Widget>
        </motion.div>
      </WidgetGrid>
    </motion.div>
  );
}
