import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ChevronRight, Home } from 'lucide-react';
import { motion } from 'framer-motion';
import { ROUTES } from '@/lib/constants';
import { getRouteBreadcrumbs } from '@/router/routes';
import { cn } from '@/lib/utils';

interface PageBreadcrumbsProps {
  className?: string;
}

export function PageBreadcrumbs({ className }: PageBreadcrumbsProps) {
  const pathname = usePathname() ?? '/';
  const crumbs = getRouteBreadcrumbs(pathname);

  return (
    <nav aria-label="Breadcrumb" className={cn('flex items-center', className)}>
      <motion.ol
        className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground"
        initial={{ opacity: 0, y: -4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      >
        <li>
          <Link
            href={ROUTES.DASHBOARD}
            className="flex items-center gap-1 rounded px-1 py-0.5 transition-colors hover:bg-muted hover:text-foreground"
          >
            <Home className="h-3 w-3" />
            <span>Home</span>
          </Link>
        </li>

        {crumbs.map((crumb, index) => {
          const isCurrent = index === crumbs.length - 1;
          const resolvedPath = crumb.path.includes(':') ? '#' : crumb.path;

          return (
            <li key={`${crumb.path}-${crumb.title}`} className="flex items-center gap-1">
              <ChevronRight className="h-3 w-3 text-muted-foreground/50" />
              {isCurrent ? (
                <span className="text-foreground/80" aria-current="page">
                  {crumb.title}
                </span>
              ) : (
                <Link
                  href={resolvedPath}
                  className="rounded px-1 py-0.5 transition-colors hover:bg-muted hover:text-foreground"
                >
                  {crumb.title}
                </Link>
              )}
            </li>
          );
        })}
      </motion.ol>
    </nav>
  );
}

export function BreadcrumbsSkeleton() {
  return (
    <div className="flex items-center gap-1.5 text-sm">
      <div className="h-4 w-12 animate-pulse rounded bg-muted" />
      <div className="h-3.5 w-3.5 animate-pulse rounded bg-muted" />
      <div className="h-4 w-24 animate-pulse rounded bg-muted" />
    </div>
  );
}
