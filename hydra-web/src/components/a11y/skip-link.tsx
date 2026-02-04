import { cn } from '@/lib/utils';

interface SkipLinkProps {
  href: string;
  children: React.ReactNode;
  className?: string;
}

/**
 * SkipLink - Accessibility component for keyboard navigation
 * 
 * Allows keyboard users to skip repetitive navigation and jump to main content.
 * Hidden visually but visible on focus.
 * 
 * Usage:
 * <SkipLink href="#main-content">Skip to main content</SkipLink>
 * <main id="main-content">...</main>
 */
export function SkipLink({ href, children, className }: SkipLinkProps) {
  return (
    <a
      href={href}
      className={cn(
        'sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4',
        'focus:z-50 focus:px-4 focus:py-2 focus:bg-primary focus:text-primary-foreground',
        'focus:rounded-md focus:font-medium focus:text-sm focus:outline-none',
        'focus:ring-2 focus:ring-offset-2 focus:ring-primary',
        className
      )}
    >
      {children}
    </a>
  );
}

/**
 * SkipLinks - Container for multiple skip links
 */
interface SkipLinksProps {
  links: Array<{ href: string; label: string }>;
  className?: string;
}

export function SkipLinks({ links, className }: SkipLinksProps) {
  return (
    <nav aria-label="Skip links" className={className}>
      {links.map((link) => (
        <SkipLink key={link.href} href={link.href}>
          {link.label}
        </SkipLink>
      ))}
    </nav>
  );
}
