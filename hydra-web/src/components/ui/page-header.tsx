import * as React from 'react';
import { cn } from '@/lib/utils';

interface PageHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

const PageHeader = React.forwardRef<HTMLDivElement, PageHeaderProps>(
  ({ className, title, subtitle, actions, children, ...props }, ref) => {
    return (
      <div ref={ref} className={cn('page-header mb-6', className)} {...props}>
        <div className="space-y-1">
          <h1 className="page-title">{title}</h1>
          {subtitle && <p className="page-subtitle">{subtitle}</p>}
        </div>
        {(actions || children) && (
          <div className="flex items-center gap-2 mt-4 sm:mt-0">
            {actions}
            {children}
          </div>
        )}
      </div>
    );
  }
);
PageHeader.displayName = 'PageHeader';

interface SectionProps extends React.HTMLAttributes<HTMLElement> {
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
}

const Section = React.forwardRef<HTMLElement, SectionProps>(
  ({ className, title, subtitle, actions, children, ...props }, ref) => {
    return (
      <section ref={ref} className={cn('space-y-4', className)} {...props}>
        {(title || subtitle || actions) && (
          <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <div>
              {title && (
                <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
              )}
              {subtitle && (
                <p className="text-sm text-muted-foreground">{subtitle}</p>
              )}
            </div>
            {actions && <div className="flex items-center gap-2">{actions}</div>}
          </div>
        )}
        {children}
      </section>
    );
  }
);
Section.displayName = 'Section';

export { PageHeader, Section };
