import { motion } from 'framer-motion';
import { PageHeader } from '@/components/layout/page-header';
import { StatsCards } from '@/components/dashboard/stats-cards';
import { CapacityOverview } from '@/components/dashboard/capacity-overview';
import { RecentActivity } from '@/components/dashboard/recent-activity';
import { ServiceSummary } from '@/components/dashboard/service-summary';
import { MiniTopology } from '@/components/dashboard/mini-topology';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

export default function DashboardPage() {
  return (
    <div className="p-6">
      <PageHeader
        title="Dashboard"
        description="Overview of your infrastructure"
      />

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        {/* Stats cards */}
        <motion.div variants={staggerItemVariants}>
          <StatsCards />
        </motion.div>

        {/* Main content grid */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Left column */}
          <motion.div variants={staggerItemVariants} className="space-y-6">
            <CapacityOverview />
            <ServiceSummary />
          </motion.div>

          {/* Right column */}
          <motion.div variants={staggerItemVariants} className="space-y-6">
            <MiniTopology />
            <RecentActivity />
          </motion.div>
        </div>
      </motion.div>
    </div>
  );
}
