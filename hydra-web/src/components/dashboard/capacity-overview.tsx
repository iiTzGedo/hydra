import { motion } from 'framer-motion';
import { Cpu, MemoryStick, HardDrive } from 'lucide-react';
import { cn } from '@/lib/utils';

interface CapacityBarProps {
  label: string;
  used: number;
  total: number;
  unit: string;
  icon: React.ReactNode;
  color: string;
}

function CapacityBar({ label, used, total, unit, icon, color }: CapacityBarProps) {
  const percentage = total > 0 ? Math.round((used / total) * 100) : 0;
  const isHigh = percentage > 80;
  const isMedium = percentage > 60;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={cn('rounded-lg p-2', color)}>
            {icon}
          </div>
          <span className="font-medium">{label}</span>
        </div>
        <span className="text-sm text-muted-foreground">
          {used.toLocaleString()} / {total.toLocaleString()} {unit}
        </span>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-muted">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className={cn(
            'h-full rounded-full',
            isHigh ? 'bg-error' : isMedium ? 'bg-warning' : 'bg-success'
          )}
        />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{percentage}% used</span>
        <span>{total - used} {unit} available</span>
      </div>
    </div>
  );
}

export function CapacityOverview() {
  // Mock data - in a real app, this would aggregate from node profiles
  const capacityData = {
    cpu: { used: 42, total: 64, unit: 'cores' },
    memory: { used: 86, total: 128, unit: 'GB' },
    storage: { used: 1.8, total: 4, unit: 'TB' },
  };

  return (
    <div className="rounded-xl border bg-card p-6 shadow-sm">
      <h3 className="mb-6 text-lg font-semibold">Capacity Overview</h3>
      <div className="space-y-6">
        <CapacityBar
          label="CPU"
          used={capacityData.cpu.used}
          total={capacityData.cpu.total}
          unit={capacityData.cpu.unit}
          icon={<Cpu className="h-4 w-4 text-white" />}
          color="bg-compute"
        />
        <CapacityBar
          label="Memory"
          used={capacityData.memory.used}
          total={capacityData.memory.total}
          unit={capacityData.memory.unit}
          icon={<MemoryStick className="h-4 w-4 text-white" />}
          color="bg-hydra-blue"
        />
        <CapacityBar
          label="Storage"
          used={capacityData.storage.used}
          total={capacityData.storage.total}
          unit={capacityData.storage.unit}
          icon={<HardDrive className="h-4 w-4 text-white" />}
          color="bg-networking"
        />
      </div>
    </div>
  );
}
