import { useState } from 'react';
import { motion } from 'framer-motion';
import { Plus } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { NodeList } from '@/components/nodes/node-list';
import { NodeFilters, NodeFilterState } from '@/components/nodes/node-filters';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { cn } from '@/lib/utils';

export default function NodesPage() {
  const [filters, setFilters] = useState<NodeFilterState>({
    search: '',
    class: null,
    type: null,
    kind: null,
    status: null,
  });

  return (
    <div className="p-6">
      <PageHeader
        title="Nodes"
        description="Manage your infrastructure nodes"
        actions={
          <button
            className={cn(
              'inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
              'hover:bg-primary/90 transition-colors'
            )}
          >
            <Plus className="h-4 w-4" />
            Add Node
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
          <NodeFilters filters={filters} onFiltersChange={setFilters} />
        </motion.div>

        <motion.div variants={staggerItemVariants}>
          <NodeList filters={filters} />
        </motion.div>
      </motion.div>
    </div>
  );
}
