import type { ColumnConfig } from '@/components/common/entity-list-page';
import type { FilterConfig } from '@/components/common/filter-bar';

export type GroupColumnKey = 'group' | 'types' | 'nodes' | 'services' | 'tags' | 'actions';

export const GROUP_FILTER_CONFIG: FilterConfig[] = [
  {
    type: 'search',
    key: 'search',
    placeholder: 'Search groups by name...',
    className: 'flex-1 max-w-md',
  },
];

export const GROUP_COLUMNS: ColumnConfig[] = [
  { key: 'group', label: 'Group' },
  { key: 'types', label: 'Types' },
  { key: 'nodes', label: 'Nodes' },
  { key: 'services', label: 'Services' },
  { key: 'tags', label: 'Tags' },
  { key: 'actions', label: 'Actions' },
];
