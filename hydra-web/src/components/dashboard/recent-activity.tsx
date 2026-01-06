import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import {
  Server,
  Boxes,
  Network,
  RefreshCw,
  Plus,
  Trash2,
  Edit,
  ArrowRight,
} from 'lucide-react';
import { cn, formatRelativeTime } from '@/lib/utils';
import { ROUTES } from '@/lib/constants';
import { staggerContainerVariants, staggerItemVariants } from '@/lib/animations';

interface ActivityItem {
  id: string;
  type: 'node' | 'service' | 'network' | 'profile';
  action: 'created' | 'updated' | 'deleted' | 'profiled';
  entityName: string;
  entityId: string;
  timestamp: Date;
}

// Mock activity data - in a real app, this would come from an API
const mockActivity: ActivityItem[] = [
  {
    id: '1',
    type: 'node',
    action: 'profiled',
    entityName: 'proxmox-01',
    entityId: 'proxmox-01',
    timestamp: new Date(Date.now() - 5 * 60 * 1000),
  },
  {
    id: '2',
    type: 'service',
    action: 'created',
    entityName: 'nginx-proxy',
    entityId: 'svc-nginx-proxy-c3d4',
    timestamp: new Date(Date.now() - 15 * 60 * 1000),
  },
  {
    id: '3',
    type: 'network',
    action: 'updated',
    entityName: '192.168.1.0/24',
    entityId: 'net-1',
    timestamp: new Date(Date.now() - 30 * 60 * 1000),
  },
  {
    id: '4',
    type: 'node',
    action: 'created',
    entityName: 'docker-host-02',
    entityId: 'docker-host-02',
    timestamp: new Date(Date.now() - 45 * 60 * 1000),
  },
  {
    id: '5',
    type: 'profile',
    action: 'profiled',
    entityName: 'opnsense.gw',
    entityId: 'opnsense.gw',
    timestamp: new Date(Date.now() - 60 * 60 * 1000),
  },
];

const typeIcons = {
  node: Server,
  service: Boxes,
  network: Network,
  profile: RefreshCw,
};

const actionIcons = {
  created: Plus,
  updated: Edit,
  deleted: Trash2,
  profiled: RefreshCw,
};

const typeColors = {
  node: 'text-compute bg-compute/10',
  service: 'text-hydra-blue bg-hydra-blue/10',
  network: 'text-networking bg-networking/10',
  profile: 'text-success bg-success/10',
};

export function RecentActivity() {
  return (
    <div className="rounded-xl border bg-card p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold">Recent Activity</h3>
        <Link
          to={ROUTES.ADMIN + '/audit'}
          className="flex items-center gap-1 text-sm text-primary hover:underline"
        >
          View all
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>

      <motion.div
        variants={staggerContainerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-3"
      >
        {mockActivity.map((item) => {
          const TypeIcon = typeIcons[item.type];
          const ActionIcon = actionIcons[item.action];

          return (
            <motion.div
              key={item.id}
              variants={staggerItemVariants}
              className="flex items-center gap-3 rounded-lg p-2 hover:bg-muted/50 transition-colors"
            >
              <div className={cn('rounded-lg p-2', typeColors[item.type])}>
                <TypeIcon className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <ActionIcon className="h-3 w-3 text-muted-foreground" />
                  <span className="font-medium truncate">{item.entityName}</span>
                </div>
                <p className="text-xs text-muted-foreground capitalize">
                  {item.type} {item.action}
                </p>
              </div>
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {formatRelativeTime(item.timestamp)}
              </span>
            </motion.div>
          );
        })}
      </motion.div>
    </div>
  );
}
