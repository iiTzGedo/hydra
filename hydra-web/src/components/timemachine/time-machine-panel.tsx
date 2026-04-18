'use client';

import * as React from 'react';
import { Clock, History } from 'lucide-react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';
import { eventToken, severityToken } from '@/lib/design-tokens';
import type { TimelineEventType } from '@/types/timemachine';

/**
 * TimeMachinePanel — compound component family for the Time Machine feature.
 *
 * Pattern: each sub-component is a thin wrapper around a semantic region
 * (header, body, scrubber lane, event lane, snapshot, footer). Consumers
 * compose them the same way they would compose Card/CardHeader/CardContent
 * from `@/components/ui/card`, so the Time Machine page can be assembled
 * from reusable, token-compliant pieces instead of one monolithic view.
 *
 *   <TimeMachinePanel>
 *     <TimeMachinePanel.Header>
 *       <TimeMachinePanel.Title>Time Machine</TimeMachinePanel.Title>
 *       <TimeMachinePanel.Subtitle>Rewind infrastructure state</TimeMachinePanel.Subtitle>
 *     </TimeMachinePanel.Header>
 *     <TimeMachinePanel.Body>
 *       <TimeMachinePanel.ScrubberLane>…</TimeMachinePanel.ScrubberLane>
 *       <TimeMachinePanel.Split>
 *         <TimeMachinePanel.EventLane>…</TimeMachinePanel.EventLane>
 *         <TimeMachinePanel.Snapshot>…</TimeMachinePanel.Snapshot>
 *       </TimeMachinePanel.Split>
 *     </TimeMachinePanel.Body>
 *   </TimeMachinePanel>
 */

// ---------- Root ----------

const panelVariants = cva(
  'flex flex-col overflow-hidden rounded-xl border bg-card text-card-foreground shadow-sm',
  {
    variants: {
      density: {
        compact: 'gap-2',
        comfortable: 'gap-3',
        spacious: 'gap-4',
      },
    },
    defaultVariants: {
      density: 'comfortable',
    },
  }
);

export interface TimeMachinePanelProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof panelVariants> {}

const Root = React.forwardRef<HTMLDivElement, TimeMachinePanelProps>(
  ({ className, density, ...props }, ref) => (
    <section
      ref={ref}
      className={cn(panelVariants({ density }), className)}
      {...props}
    />
  )
);
Root.displayName = 'TimeMachinePanel';

// ---------- Header ----------

const Header = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <header
    ref={ref}
    className={cn(
      'flex flex-col gap-2 border-b border-border bg-surface-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between',
      className
    )}
    {...props}
  />
));
Header.displayName = 'TimeMachinePanel.Header';

const Title = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, children, ...props }, ref) => (
  <h2
    ref={ref}
    className={cn(
      'flex items-center gap-2 text-lg font-semibold tracking-tight',
      className
    )}
    {...props}
  >
    <History className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
    {children}
  </h2>
));
Title.displayName = 'TimeMachinePanel.Title';

const Subtitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn('text-sm text-muted-foreground', className)}
    {...props}
  />
));
Subtitle.displayName = 'TimeMachinePanel.Subtitle';

const Actions = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn('flex flex-wrap items-center gap-2', className)}
    {...props}
  />
));
Actions.displayName = 'TimeMachinePanel.Actions';

// ---------- Cursor (current-time badge) ----------

export interface CursorProps extends React.HTMLAttributes<HTMLDivElement> {
  timestamp: Date;
  compareTimestamp?: Date | null;
  formatter?: (date: Date) => string;
}

const Cursor = React.forwardRef<HTMLDivElement, CursorProps>(
  ({ className, timestamp, compareTimestamp, formatter, ...props }, ref) => {
    const format = formatter ?? ((d: Date) => d.toLocaleString());
    return (
      <div
        ref={ref}
        className={cn(
          'inline-flex items-center gap-2 rounded-md border border-border bg-surface-3 px-2.5 py-1 text-xs font-medium',
          className
        )}
        {...props}
      >
        <Clock className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
        <span className="font-mono tabular-nums text-foreground">
          {format(timestamp)}
        </span>
        {compareTimestamp && (
          <span className="flex items-center gap-1 border-l border-border pl-2 text-muted-foreground">
            <span className="text-warning" aria-hidden="true">
              ↔
            </span>
            <span className="font-mono tabular-nums">{format(compareTimestamp)}</span>
          </span>
        )}
      </div>
    );
  }
);
Cursor.displayName = 'TimeMachinePanel.Cursor';

// ---------- Body / layout primitives ----------

const Body = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn('flex-1 flex flex-col gap-3 p-4', className)} {...props} />
));
Body.displayName = 'TimeMachinePanel.Body';

const Split = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      'grid grid-cols-1 gap-3 md:grid-cols-[1fr_320px]',
      className
    )}
    {...props}
  />
));
Split.displayName = 'TimeMachinePanel.Split';

// ---------- Semantic lanes ----------

export interface ScrubberLaneProps extends React.HTMLAttributes<HTMLDivElement> {
  label?: string;
}

const ScrubberLane = React.forwardRef<HTMLDivElement, ScrubberLaneProps>(
  ({ className, label = 'Timeline scrubber', children, ...props }, ref) => (
    <div
      ref={ref}
      role="group"
      aria-label={label}
      className={cn(
        'rounded-lg border border-border bg-surface-2 p-3',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
);
ScrubberLane.displayName = 'TimeMachinePanel.ScrubberLane';

export interface EventLaneProps extends React.HTMLAttributes<HTMLDivElement> {
  label?: string;
}

const EventLane = React.forwardRef<HTMLDivElement, EventLaneProps>(
  ({ className, label = 'Event stream', children, ...props }, ref) => (
    <div
      ref={ref}
      role="region"
      aria-label={label}
      className={cn(
        'flex flex-col gap-3 rounded-lg border border-border bg-surface-2 p-3',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
);
EventLane.displayName = 'TimeMachinePanel.EventLane';

export interface SnapshotProps extends React.HTMLAttributes<HTMLDivElement> {
  label?: string;
}

const Snapshot = React.forwardRef<HTMLDivElement, SnapshotProps>(
  ({ className, label = 'Historical snapshot', children, ...props }, ref) => (
    <aside
      ref={ref}
      aria-label={label}
      className={cn(
        'flex flex-col gap-3 rounded-lg border border-border bg-surface-2 p-3',
        className
      )}
      {...props}
    >
      {children}
    </aside>
  )
);
Snapshot.displayName = 'TimeMachinePanel.Snapshot';

const Footer = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <footer
    ref={ref}
    className={cn(
      'flex flex-wrap items-center justify-between gap-2 border-t border-border bg-surface-2 px-4 py-2 text-xs text-muted-foreground',
      className
    )}
    {...props}
  />
));
Footer.displayName = 'TimeMachinePanel.Footer';

// ---------- Event chip (uses eventToken) ----------

export interface EventChipProps extends React.HTMLAttributes<HTMLSpanElement> {
  event: TimelineEventType;
  surface?: 'solid' | 'soft' | 'dot';
  label?: string;
}

const EventChip = React.forwardRef<HTMLSpanElement, EventChipProps>(
  ({ className, event, surface = 'soft', label, children, ...props }, ref) => {
    if (surface === 'dot') {
      return (
        <span
          ref={ref}
          className={cn(
            'inline-block h-2 w-2 rounded-full',
            eventToken({ event, surface: 'dot' }),
            className
          )}
          aria-label={label}
          {...props}
        />
      );
    }
    return (
      <span
        ref={ref}
        className={cn(
          'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium',
          eventToken({ event, surface }),
          className
        )}
        {...props}
      >
        {label ?? children}
      </span>
    );
  }
);
EventChip.displayName = 'TimeMachinePanel.EventChip';

// ---------- Severity chip (notification tiers) ----------

export interface SeverityChipProps extends React.HTMLAttributes<HTMLSpanElement> {
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  surface?: 'solid' | 'soft' | 'dot';
}

const SeverityChip = React.forwardRef<HTMLSpanElement, SeverityChipProps>(
  ({ className, severity, surface = 'soft', children, ...props }, ref) => {
    if (surface === 'dot') {
      return (
        <span
          ref={ref}
          className={cn(
            'inline-block h-2 w-2 rounded-full',
            severityToken({ severity, surface: 'dot' }),
            className
          )}
          {...props}
        />
      );
    }
    return (
      <span
        ref={ref}
        className={cn(
          'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium capitalize',
          severityToken({ severity, surface }),
          className
        )}
        {...props}
      >
        {children ?? severity}
      </span>
    );
  }
);
SeverityChip.displayName = 'TimeMachinePanel.SeverityChip';

// ---------- Public compound API ----------

type TimeMachinePanelComponent = React.ForwardRefExoticComponent<
  TimeMachinePanelProps & React.RefAttributes<HTMLDivElement>
> & {
  Header: typeof Header;
  Title: typeof Title;
  Subtitle: typeof Subtitle;
  Actions: typeof Actions;
  Cursor: typeof Cursor;
  Body: typeof Body;
  Split: typeof Split;
  ScrubberLane: typeof ScrubberLane;
  EventLane: typeof EventLane;
  Snapshot: typeof Snapshot;
  Footer: typeof Footer;
  EventChip: typeof EventChip;
  SeverityChip: typeof SeverityChip;
};

export const TimeMachinePanel = Object.assign(Root, {
  Header,
  Title,
  Subtitle,
  Actions,
  Cursor,
  Body,
  Split,
  ScrubberLane,
  EventLane,
  Snapshot,
  Footer,
  EventChip,
  SeverityChip,
}) as TimeMachinePanelComponent;

export {
  Root as TimeMachinePanelRoot,
  Header as TimeMachinePanelHeader,
  Title as TimeMachinePanelTitle,
  Subtitle as TimeMachinePanelSubtitle,
  Actions as TimeMachinePanelActions,
  Cursor as TimeMachinePanelCursor,
  Body as TimeMachinePanelBody,
  Split as TimeMachinePanelSplit,
  ScrubberLane as TimeMachinePanelScrubberLane,
  EventLane as TimeMachinePanelEventLane,
  Snapshot as TimeMachinePanelSnapshot,
  Footer as TimeMachinePanelFooter,
  EventChip as TimeMachinePanelEventChip,
  SeverityChip as TimeMachinePanelSeverityChip,
};
