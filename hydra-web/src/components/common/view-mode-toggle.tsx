import { LayoutGrid, LayoutList } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

export type ViewMode = 'table' | 'grid';

export interface ViewModeToggleProps {
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
}

export function ViewModeToggle({ viewMode, onViewModeChange }: ViewModeToggleProps) {
  return (
    <div className="flex items-center border rounded-md">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant={viewMode === 'table' ? 'secondary' : 'ghost'}
            size="sm"
            className="rounded-r-none border-0"
            onClick={() => onViewModeChange('table')}
            aria-label="Table view"
            aria-pressed={viewMode === 'table'}
          >
            <LayoutList className="h-4 w-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>Table View</TooltipContent>
      </Tooltip>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
            size="sm"
            className="rounded-l-none border-l"
            onClick={() => onViewModeChange('grid')}
            aria-label="Grid view"
            aria-pressed={viewMode === 'grid'}
          >
            <LayoutGrid className="h-4 w-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>Grid View</TooltipContent>
      </Tooltip>
    </div>
  );
}
