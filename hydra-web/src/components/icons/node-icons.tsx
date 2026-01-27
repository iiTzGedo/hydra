import { SVGProps } from 'react';

type IconProps = SVGProps<SVGSVGElement> & {
  size?: number;
};

const defaultProps = {
  xmlns: 'http://www.w3.org/2000/svg',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

// Compute Icons
export function BareMetalIcon({ size = 24, ...props }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...defaultProps} {...props}>
      {/* Server rack chassis */}
      <rect x="4" y="4" width="16" height="16" rx="2" />
      {/* Drive bays */}
      <line x1="4" y1="8" x2="20" y2="8" />
      <line x1="4" y1="12" x2="20" y2="12" />
      <line x1="4" y1="16" x2="20" y2="16" />
      {/* Status LEDs */}
      <circle cx="7" cy="6" r="1" fill="currentColor" />
      <circle cx="7" cy="10" r="1" fill="currentColor" />
      <circle cx="7" cy="14" r="1" fill="currentColor" />
    </svg>
  );
}

export function VmIcon({ size = 24, ...props }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...defaultProps} {...props}>
      {/* Outer box - host */}
      <rect x="3" y="3" width="18" height="18" rx="2" />
      {/* Inner box - VM */}
      <rect x="7" y="7" width="10" height="10" rx="1" />
      {/* VM content */}
      <line x1="9" y1="10" x2="15" y2="10" />
      <line x1="9" y1="12" x2="15" y2="12" />
      <line x1="9" y1="14" x2="13" y2="14" />
    </svg>
  );
}

export function LxcIcon({ size = 24, ...props }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...defaultProps} {...props}>
      {/* Container box */}
      <rect x="4" y="6" width="16" height="12" rx="2" />
      {/* Container isolation layers */}
      <path d="M4 10h16" />
      <path d="M8 6v12" />
      {/* Penguin hint */}
      <circle cx="14" cy="13" r="2" />
    </svg>
  );
}

export function DockerIcon({ size = 24, ...props }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...defaultProps} {...props}>
      {/* Whale body */}
      <path d="M3 12c0 0 1-4 6-4h6c3 0 6 2 6 5s-2 5-6 5H9c-4 0-6-3-6-6z" />
      {/* Container stacks */}
      <rect x="5" y="9" width="3" height="2" rx="0.5" />
      <rect x="9" y="9" width="3" height="2" rx="0.5" />
      <rect x="13" y="9" width="3" height="2" rx="0.5" />
      <rect x="5" y="6" width="3" height="2" rx="0.5" />
      <rect x="9" y="6" width="3" height="2" rx="0.5" />
    </svg>
  );
}

export function KubernetesPodIcon({ size = 24, ...props }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...defaultProps} {...props}>
      {/* Hexagon pod shape */}
      <path d="M12 2L21 7v10l-9 5l-9-5V7l9-5z" />
      {/* Inner containers */}
      <circle cx="12" cy="9" r="2" />
      <circle cx="9" cy="14" r="2" />
      <circle cx="15" cy="14" r="2" />
    </svg>
  );
}

// Networking Icons
export function RouterIcon({ size = 24, ...props }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...defaultProps} {...props}>
      {/* Router body */}
      <rect x="3" y="8" width="18" height="10" rx="2" />
      {/* Antennas */}
      <line x1="7" y1="8" x2="7" y2="3" />
      <line x1="17" y1="8" x2="17" y2="3" />
      {/* Signal waves */}
      <path d="M5 5c1-1 3-1 4 0" />
      <path d="M15 5c1-1 3-1 4 0" />
      {/* Ports */}
      <rect x="6" y="13" width="2" height="2" rx="0.5" fill="currentColor" />
      <rect x="11" y="13" width="2" height="2" rx="0.5" fill="currentColor" />
      <rect x="16" y="13" width="2" height="2" rx="0.5" fill="currentColor" />
    </svg>
  );
}

export function SwitchIcon({ size = 24, ...props }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...defaultProps} {...props}>
      {/* Switch body */}
      <rect x="2" y="8" width="20" height="8" rx="1" />
      {/* Ports row */}
      <rect x="4" y="10" width="2" height="4" rx="0.5" />
      <rect x="7" y="10" width="2" height="4" rx="0.5" />
      <rect x="10" y="10" width="2" height="4" rx="0.5" />
      <rect x="13" y="10" width="2" height="4" rx="0.5" />
      <rect x="16" y="10" width="2" height="4" rx="0.5" />
      <rect x="19" y="10" width="2" height="4" rx="0.5" />
    </svg>
  );
}

export function AccessPointIcon({ size = 24, ...props }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...defaultProps} {...props}>
      {/* Base unit */}
      <ellipse cx="12" cy="18" rx="6" ry="2" />
      {/* Pole */}
      <line x1="12" y1="16" x2="12" y2="12" />
      {/* Signal waves */}
      <path d="M6 10c0-3.3 2.7-6 6-6s6 2.7 6 6" />
      <path d="M8 10c0-2.2 1.8-4 4-4s4 1.8 4 4" />
      <path d="M10 10c0-1.1 0.9-2 2-2s2 0.9 2 2" />
    </svg>
  );
}

export function FirewallIcon({ size = 24, ...props }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...defaultProps} {...props}>
      {/* Shield shape */}
      <path d="M12 2L4 6v6c0 5.5 3.4 10.6 8 12c4.6-1.4 8-6.5 8-12V6l-8-4z" />
      {/* Brick pattern */}
      <line x1="4" y1="10" x2="20" y2="10" />
      <line x1="4" y1="14" x2="20" y2="14" />
      <line x1="12" y1="6" x2="12" y2="10" />
      <line x1="8" y1="10" x2="8" y2="14" />
      <line x1="16" y1="10" x2="16" y2="14" />
      <line x1="12" y1="14" x2="12" y2="18" />
    </svg>
  );
}

export function LoadBalancerIcon({ size = 24, ...props }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...defaultProps} {...props}>
      {/* Central node */}
      <circle cx="12" cy="5" r="3" />
      {/* Distribution arrows */}
      <line x1="12" y1="8" x2="6" y2="14" />
      <line x1="12" y1="8" x2="12" y2="14" />
      <line x1="12" y1="8" x2="18" y2="14" />
      {/* Target nodes */}
      <circle cx="6" cy="17" r="3" />
      <circle cx="12" cy="17" r="3" />
      <circle cx="18" cy="17" r="3" />
    </svg>
  );
}

// IoT Icons
export function SensorIcon({ size = 24, ...props }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...defaultProps} {...props}>
      {/* Sensor body */}
      <circle cx="12" cy="12" r="8" />
      {/* Inner sensing element */}
      <circle cx="12" cy="12" r="3" fill="currentColor" />
      {/* Detection waves */}
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
    </svg>
  );
}

export function ActuatorIcon({ size = 24, ...props }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...defaultProps} {...props}>
      {/* Motor/actuator body */}
      <rect x="6" y="6" width="12" height="12" rx="2" />
      {/* Shaft */}
      <line x1="12" y1="6" x2="12" y2="2" />
      {/* Gear indicator */}
      <circle cx="12" cy="12" r="4" />
      <path d="M12 8v8" />
      <path d="M8 12h8" />
    </svg>
  );
}

export function ControllerIcon({ size = 24, ...props }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...defaultProps} {...props}>
      {/* Controller board */}
      <rect x="3" y="5" width="18" height="14" rx="2" />
      {/* Chip */}
      <rect x="9" y="9" width="6" height="6" rx="1" />
      {/* Pins */}
      <line x1="6" y1="5" x2="6" y2="3" />
      <line x1="10" y1="5" x2="10" y2="3" />
      <line x1="14" y1="5" x2="14" y2="3" />
      <line x1="18" y1="5" x2="18" y2="3" />
      <line x1="6" y1="19" x2="6" y2="21" />
      <line x1="10" y1="19" x2="10" y2="21" />
      <line x1="14" y1="19" x2="14" y2="21" />
      <line x1="18" y1="19" x2="18" y2="21" />
    </svg>
  );
}

export function HubIcon({ size = 24, ...props }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...defaultProps} {...props}>
      {/* Central hub */}
      <circle cx="12" cy="12" r="4" />
      {/* Spokes */}
      <line x1="12" y1="8" x2="12" y2="3" />
      <line x1="12" y1="16" x2="12" y2="21" />
      <line x1="8" y1="12" x2="3" y2="12" />
      <line x1="16" y1="12" x2="21" y2="12" />
      <line x1="9" y1="9" x2="5" y2="5" />
      <line x1="15" y1="9" x2="19" y2="5" />
      <line x1="9" y1="15" x2="5" y2="19" />
      <line x1="15" y1="15" x2="19" y2="19" />
    </svg>
  );
}

export function BridgeIcon({ size = 24, ...props }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...defaultProps} {...props}>
      {/* Bridge arch */}
      <path d="M3 16c0-4 4-8 9-8s9 4 9 8" />
      {/* Bridge deck */}
      <line x1="3" y1="16" x2="21" y2="16" />
      {/* Pillars */}
      <line x1="6" y1="16" x2="6" y2="20" />
      <line x1="12" y1="16" x2="12" y2="20" />
      <line x1="18" y1="16" x2="18" y2="20" />
      {/* Connecting arrow */}
      <path d="M8 12l4-4 4 4" />
    </svg>
  );
}

export function ApplianceIcon({ size = 24, ...props }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...defaultProps} {...props}>
      {/* Appliance body */}
      <rect x="4" y="4" width="16" height="16" rx="3" />
      {/* Display/interface */}
      <rect x="7" y="7" width="10" height="6" rx="1" />
      {/* Control buttons */}
      <circle cx="9" cy="16" r="1.5" />
      <circle cx="15" cy="16" r="1.5" />
    </svg>
  );
}

export function OtherIcon({ size = 24, ...props }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" {...defaultProps} {...props}>
      {/* Generic device */}
      <rect x="4" y="4" width="16" height="16" rx="2" />
      {/* Question mark */}
      <path d="M9 9c0-1.7 1.3-3 3-3s3 1.3 3 3c0 1.5-1 2-2 2.5v1" />
      <circle cx="12" cy="16" r="1" fill="currentColor" />
    </svg>
  );
}

// Icon mapping by node kind
export const NODE_KIND_ICONS: Record<string, React.ComponentType<IconProps>> = {
  'bare-metal': BareMetalIcon,
  vm: VmIcon,
  lxc: LxcIcon,
  docker: DockerIcon,
  'kubernetes-pod': KubernetesPodIcon,
  router: RouterIcon,
  switch: SwitchIcon,
  'access-point': AccessPointIcon,
  firewall: FirewallIcon,
  'load-balancer': LoadBalancerIcon,
  sensor: SensorIcon,
  actuator: ActuatorIcon,
  controller: ControllerIcon,
  hub: HubIcon,
  bridge: BridgeIcon,
  appliance: ApplianceIcon,
  other: OtherIcon,
};

// Helper component that renders the appropriate icon based on kind
export function NodeKindIcon({
  kind,
  size = 24,
  ...props
}: IconProps & { kind: string }) {
  const IconComponent = NODE_KIND_ICONS[kind] || OtherIcon;
  return <IconComponent size={size} {...props} />;
}
