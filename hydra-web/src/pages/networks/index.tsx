import { useState } from 'react';
import { motion } from 'framer-motion';
import { Plus } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { NetworkList } from '@/components/networks/network-list';
import { NetworkFilters, NetworkFilterState } from '@/components/networks/network-filters';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { cn } from '@/lib/utils';

export default function NetworksPage() {
  const [filters, setFilters] = useState<NetworkFilterState>({
    search: '',
    type: null,
  });

  return (
    <div className="p-6">
      <PageHeader
        title="Networks"
        description="View and manage your network segments"
        actions={
          <button
            className={cn(
              'inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
              'hover:bg-primary/90 transition-colors'
            )}
          >
            <Plus className="h-4 w-4" />
            Add Network
          </button>
        }
      />

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        <motion.div variants={staggerItemVariants}>
          <NetworkFilters filters={filters} onFiltersChange={setFilters} />
        </motion.div>

        <motion.div variants={staggerItemVariants}>
          <NetworkList filters={filters} />
        </motion.div>
      </motion.div>
    </div>
  );
}
