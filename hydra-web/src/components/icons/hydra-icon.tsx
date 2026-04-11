import { useState } from 'react';
import type { ComponentType, SVGProps } from 'react';
import {
  AppWindow,
  BookOpen,
  Bookmark,
  Boxes,
  Clock3,
  CloudSun,
  FileText,
  FolderTree,
  LayoutDashboard,
  Monitor,
  Network,
  PenSquare,
  Plug,
  Rss,
  Server,
  Shield,
  Square,
  Terminal,
} from 'lucide-react';
import { NODE_KIND_ICONS } from '@/components/icons/node-icons';
import { cn } from '@/lib/utils';
import type { IconDescriptor } from '@/types/icons';

type IconRenderer = ComponentType<SVGProps<SVGSVGElement>>;

const LUCIDE_FALLBACKS: Record<string, IconRenderer> = {
  'app-window': AppWindow,
  'book-open': BookOpen,
  bookmark: Bookmark,
  boxes: Boxes,
  'clock-3': Clock3,
  'cloud-sun': CloudSun,
  container: Boxes,
  'file-text': FileText,
  'folder-tree': FolderTree,
  'layout-dashboard': LayoutDashboard,
  monitor: Monitor,
  network: Network,
  networking: Network,
  plug: Plug,
  compute: Server,
  group: FolderTree,
  iot: Shield,
  rss: Rss,
  server: Server,
  shield: Shield,
  square: Square,
  'square-pen': PenSquare,
  terminal: Terminal,
  dashboard: LayoutDashboard,
  'stats-cards': LayoutDashboard,
  'capacity-overview': LayoutDashboard,
  'service-summary': Boxes,
  'recent-activity': Clock3,
  'mini-topology': Network,
  'node-status-grid': Server,
  docker: NODE_KIND_ICONS.docker,
  kubernetes: NODE_KIND_ICONS['kubernetes-pod'],
  lxc: NODE_KIND_ICONS.lxc,
  router: NODE_KIND_ICONS.router,
  switch: NODE_KIND_ICONS.switch,
  firewall: NODE_KIND_ICONS.firewall,
  vm: NODE_KIND_ICONS.vm,
  'bare-metal': NODE_KIND_ICONS['bare-metal'],
};

interface HydraIconProps {
  icon?: IconDescriptor | null;
  fallback?: string;
  className?: string;
  size?: number;
  title?: string;
}

function HydraRemoteIcon({
  src,
  alt,
  title,
  size,
  className,
  fallbackIcon: FallbackIcon,
  fallbackColor,
}: {
  src: string;
  alt: string;
  title: string;
  size: number;
  className?: string;
  fallbackIcon: IconRenderer;
  fallbackColor?: string | null;
}) {
  const [hasError, setHasError] = useState(false);

  if (hasError) {
    return (
      <FallbackIcon
        className={cn('shrink-0', className)}
        style={
          fallbackColor
            ? { color: fallbackColor, width: size, height: size }
            : { width: size, height: size }
        }
      />
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      title={title}
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      className={cn('shrink-0 object-contain', className)}
      onError={() => setHasError(true)}
    />
  );
}

export function HydraIcon({
  icon,
  fallback = 'square',
  className,
  size = 18,
  title,
}: HydraIconProps) {
  const slug = icon?.slug ?? fallback;
  const IconComponent = LUCIDE_FALLBACKS[slug] ?? LUCIDE_FALLBACKS[icon?.fallback ?? fallback] ?? Square;
  const iconLabel = title ?? icon?.label ?? slug;

  if (icon?.url) {
    return (
      <HydraRemoteIcon
        key={`${icon.url}:${slug}`}
        src={icon.url}
        alt={iconLabel}
        title={iconLabel}
        size={size}
        className={className}
        fallbackIcon={IconComponent}
        fallbackColor={icon?.color}
      />
    );
  }

  return (
    <IconComponent
      className={cn('shrink-0', className)}
      style={icon?.color ? { color: icon.color, width: size, height: size } : { width: size, height: size }}
    />
  );
}
