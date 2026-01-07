import { Cpu, MemoryStick, HardDrive } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useCapacity } from '@/api/query';

interface CapacityStatProps {
  label: string;
  total: number;
  unit: string;
  icon: React.ReactNode;
  color: string;
  isLoading?: boolean;
}

function CapacityStat({ label, total, unit, icon, color, isLoading }: CapacityStatProps) {
  const formattedTotal = total.toLocaleString(undefined, {
    maximumFractionDigits: unit === 'TB' ? 2 : 0,
  });

  return (
    <div className="space-y-2 rounded-lg border p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={cn('rounded-lg p-2', color)}>
            {icon}
          </div>
          <span className="font-medium">{label}</span>
        </div>
        {isLoading ? (
          <div className="h-6 w-20 animate-pulse rounded bg-muted" />
        ) : (
          <span className="text-sm text-muted-foreground">
            {formattedTotal} {unit}
          </span>
        )}
      </div>
    </div>
  );
}

export function CapacityOverview() {
  const { data, isLoading } = useCapacity();
  const summary = data?.summary;

  return (
    <div className="rounded-xl border bg-card p-6 shadow-sm">
      <h3 className="mb-6 text-lg font-semibold">Capacity Overview</h3>
      {summary ? (
        <div className="space-y-4">
          <CapacityStat
            label="CPU Cores"
            total={summary.totalCores ?? 0}
            unit="cores"
            icon={<Cpu className="h-4 w-4 text-white" />}
            color="bg-compute"
            isLoading={isLoading}
          />
          <CapacityStat
            label="Memory"
            total={summary.totalMemoryGB ?? 0}
            unit="GB"
            icon={<MemoryStick className="h-4 w-4 text-white" />}
            color="bg-hydra-blue"
            isLoading={isLoading}
          />
          <CapacityStat
            label="Storage"
            total={summary.totalStorageTB ?? 0}
            unit="TB"
            icon={<HardDrive className="h-4 w-4 text-white" />}
            color="bg-networking"
            isLoading={isLoading}
          />
          <p className="text-xs text-muted-foreground">
            Totals reflect reported capacity. Utilization data is not provided by the API.
          </p>
        </div>
      ) : isLoading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, index) => (
            <div key={index} className="h-16 rounded-lg bg-muted animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="flex h-32 items-center justify-center rounded-lg bg-muted/50">
          <p className="text-sm text-muted-foreground">No capacity data available</p>
        </div>
      )}
    </div>
  );
}
