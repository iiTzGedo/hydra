import { LucideIcon, MoreHorizontal } from 'lucide-react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

export interface ActionMenuItem {
  label: string;
  icon?: LucideIcon;
  onClick?: () => void;
  href?: string;
  variant?: 'default' | 'destructive';
  disabled?: boolean;
}

export interface ActionMenuDivider {
  type: 'divider';
}

export type ActionMenuItemOrDivider = ActionMenuItem | ActionMenuDivider;

export interface ActionMenuProps {
  items: ActionMenuItemOrDivider[];
  align?: 'start' | 'end';
  triggerClassName?: string;
}

function isMenuItem(item: ActionMenuItemOrDivider): item is ActionMenuItem {
  return !('type' in item && item.type === 'divider');
}

export function ActionMenu({ items, align = 'end', triggerClassName }: ActionMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            'opacity-0 group-hover:opacity-100 transition-opacity',
            triggerClassName
          )}
          aria-label="Actions"
        >
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align={align}>
        {items.map((item, index) => {
          if (!isMenuItem(item)) {
            return <DropdownMenuSeparator key={`divider-${index}`} />;
          }

          const Icon = item.icon;
          const content = (
            <>
              {Icon && <Icon className="h-4 w-4 mr-2" />}
              {item.label}
            </>
          );

          if (item.href) {
            return (
              <DropdownMenuItem
                key={item.label}
                asChild
                disabled={item.disabled}
                className={cn(item.variant === 'destructive' && 'text-destructive')}
              >
                <Link href={item.href}>{content}</Link>
              </DropdownMenuItem>
            );
          }

          return (
            <DropdownMenuItem
              key={item.label}
              onClick={item.onClick}
              disabled={item.disabled}
              className={cn(item.variant === 'destructive' && 'text-destructive')}
            >
              {content}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
