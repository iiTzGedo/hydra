import { useState } from 'react';
import type { ComponentType, SVGProps } from 'react';
import {
  Activity,
  AppWindow,
  Bot,
  BookOpen,
  Bookmark,
  Boxes,
  Clock3,
  CloudSun,
  Cog,
  Cpu,
  Database,
  FileCog,
  FileText,
  FolderTree,
  Github,
  GitBranch,
  GitFork,
  HardDrive,
  Home,
  Key,
  Layers,
  LayoutDashboard,
  Monitor,
  Network,
  Package,
  PenSquare,
  Play,
  Plug,
  Rss,
  Server,
  Settings,
  Shield,
  Square,
  Terminal,
  Upload,
  Zap,
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
  'kubernetes-pod': NODE_KIND_ICONS['kubernetes-pod'],
  k8s: NODE_KIND_ICONS['kubernetes-pod'],
  lxc: NODE_KIND_ICONS.lxc,
  router: NODE_KIND_ICONS.router,
  switch: NODE_KIND_ICONS.switch,
  firewall: NODE_KIND_ICONS.firewall,
  vm: NODE_KIND_ICONS.vm,
  'bare-metal': NODE_KIND_ICONS['bare-metal'],
  // Integration / plugin brand slugs — mapped to the closest lucide primitive
  // so every plugin has an icon even without a bundled SVG. Plugins that
  // supply their own icon via the `icon` descriptor URL take precedence.
  ansible: Play,
  proxmox: HardDrive,
  'home-assistant': Home,
  homeassistant: Home,
  ha: Home,
  prometheus: Activity,
  grafana: Activity,
  terraform: Layers,
  ssh: Key,
  github: Github,
  gitlab: GitBranch,
  git: GitBranch,
  gitea: GitFork,
  systemd: Cog,
  podman: Boxes,
  containerd: Boxes,
  postgres: Database,
  postgresql: Database,
  mysql: Database,
  mongodb: Database,
  redis: Database,
  sqlite: Database,
  nginx: Server,
  apache: Server,
  caddy: Server,
  traefik: Network,
  // Command-category / agent icons
  agent: Bot,
  bot: Bot,
  package: Package,
  packages: Package,
  metadata: FileCog,
  config: Settings,
  configuration: Settings,
  system: Cpu,
  custom: Zap,
  workflow: GitBranch,
  'workflow-step': GitBranch,
  deploy: Upload,
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
