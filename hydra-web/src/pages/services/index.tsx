import { useState } from 'react';
import { motion } from 'framer-motion';
import { PageHeader } from '@/components/layout/page-header';
import { ServiceList } from '@/components/services/service-list';
import { ServiceFilters, ServiceFilterState } from '@/components/services/service-filters';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

export default function ServicesPage() {
  const [filters, setFilters] = useState<ServiceFilterState>({
    search: '',
    runtime: null,
    status: null,
    nodeId: null,
  });

  return (
    <div className="p-6">
      <PageHeader
        title="Services"
        description="Monitor and manage your infrastructure services"
      />

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        <motion.div variants={staggerItemVariants}>
          <ServiceFilters filters={filters} onFiltersChange={setFilters} />
        </motion.div>

        <motion.div variants={staggerItemVariants}>
          <ServiceList filters={filters} />
        </motion.div>
      </motion.div>
    </div>
  );
}
