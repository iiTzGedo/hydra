import { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Plus } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { GroupList } from '@/components/groups/group-list';
import { GroupFilters, GroupFilterState } from '@/components/groups/group-filters';
import { ROUTES } from '@/lib/constants';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { cn } from '@/lib/utils';

export default function GroupsPage() {
  const [filters, setFilters] = useState<GroupFilterState>({
    search: '',
  });

  return (
    <div className="p-6">
      <PageHeader
        title="Groups"
        description="Organize infrastructure with dynamic selectors"
        actions={
          <Link
            to={ROUTES.GROUP_NEW}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground',
              'hover:bg-primary/90 transition-colors'
            )}
          >
            <Plus className="h-4 w-4" />
            Create Group
          </Link>
        }
      />

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-6"
      >
        <motion.div variants={staggerItemVariants}>
          <GroupFilters filters={filters} onFiltersChange={setFilters} />
        </motion.div>

        <motion.div variants={staggerItemVariants}>
          <GroupList filters={filters} />
        </motion.div>
      </motion.div>
    </div>
  );
}
