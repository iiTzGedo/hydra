export const STORAGE_KEYS = {
  theme: 'hydra-theme',
} as const;

export const ROUTES = {
  LOGIN: '/login',
  REGISTER: '/register',
  FORGOT_PASSWORD: '/forgot-password',
  RESET_PASSWORD: '/reset-password',

  DASHBOARD: '/dashboard',
  NODES: '/nodes',
  NODE_DETAIL: '/nodes/:nodeId',
  NODE_PROFILES: '/nodes/:nodeId/profiles',
  NODE_PROFILES_COMPARE: '/nodes/:nodeId/profiles/compare',
  NODE_PROFILE: '/nodes/:nodeId/profile/:profileId',
  SERVICES: '/services',
  SERVICE_DETAIL: '/services/:serviceId',
  NETWORKS: '/networks',
  NETWORK_DETAIL: '/networks/:networkId',
  DISCOVERY: '/discovery',
  GROUPS: '/groups',
  GROUP_NEW: '/groups/new',
  GROUP_DETAIL: '/groups/:groupId',
  TOPOLOGY: '/topology',
  TIME_MACHINE: '/timemachine',
  CHAT: '/chat',
  COMMANDS: '/commands',
  COMMAND_DETAIL: '/commands/:commandId',
  MCP_MARKETPLACE: '/mcp-marketplace',
  NOTIFICATIONS: '/notifications',
  PROFILE: '/profile',

  SETTINGS: '/settings',

  ADMIN: '/settings',
  ADMIN_USERS: '/settings',
  ADMIN_APPROVALS: '/settings',
  ADMIN_TOKENS: '/settings',
  ADMIN_APIKEYS: '/settings',
  ADMIN_AUDIT: '/settings',
  ADMIN_SETTINGS: '/settings',
} as const;

export const NODE_CLASS_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  compute: {
    bg: 'bg-compute',
    text: 'text-compute',
    border: 'border-compute',
  },
  networking: {
    bg: 'bg-network',
    text: 'text-network',
    border: 'border-network',
  },
  iot: {
    bg: 'bg-iot',
    text: 'text-iot',
    border: 'border-iot',
  },
};

export const NODE_KIND_LABELS: Record<string, string> = {
  'bare-metal': 'Bare Metal',
  vm: 'Virtual Machine',
  lxc: 'LXC Container',
  docker: 'Docker Container',
  'kubernetes-pod': 'Kubernetes Pod',
  router: 'Router',
  switch: 'Switch',
  'access-point': 'Access Point',
  firewall: 'Firewall',
  'load-balancer': 'Load Balancer',
  sensor: 'Sensor',
  actuator: 'Actuator',
  controller: 'Controller',
  hub: 'Hub',
  bridge: 'Bridge',
  appliance: 'Appliance',
  other: 'Other',
};

export const STATUS_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  // Positive states - use semantic success token
  active: {
    bg: 'bg-success/10',
    text: 'text-success',
    dot: 'bg-success',
  },
  running: {
    bg: 'bg-success/10',
    text: 'text-success',
    dot: 'bg-success',
  },
  // Neutral/inactive states - use semantic muted token
  inactive: {
    bg: 'bg-muted',
    text: 'text-muted-foreground',
    dot: 'bg-muted-foreground',
  },
  stopped: {
    bg: 'bg-muted',
    text: 'text-muted-foreground',
    dot: 'bg-muted-foreground',
  },
  exited: {
    bg: 'bg-muted',
    text: 'text-muted-foreground',
    dot: 'bg-muted-foreground',
  },
  unknown: {
    bg: 'bg-muted',
    text: 'text-muted-foreground',
    dot: 'bg-muted-foreground',
  },
  // Warning states - use semantic warning token
  pending: {
    bg: 'bg-warning/10',
    text: 'text-warning',
    dot: 'bg-warning',
  },
  paused: {
    bg: 'bg-warning/10',
    text: 'text-warning',
    dot: 'bg-warning',
  },
  restarting: {
    bg: 'bg-warning/10',
    text: 'text-warning',
    dot: 'bg-warning',
  },
  // Error/destructive states - use semantic destructive token
  archived: {
    bg: 'bg-destructive/10',
    text: 'text-destructive',
    dot: 'bg-destructive',
  },
  failed: {
    bg: 'bg-destructive/10',
    text: 'text-destructive',
    dot: 'bg-destructive',
  },
};

export const SERVICE_RUNTIME_LABELS: Record<string, string> = {
  systemd: 'systemd',
  docker: 'Docker',
  podman: 'Podman',
  kubernetes: 'Kubernetes',
  lxc: 'LXC',
  supervisord: 'Supervisord',
  pm2: 'PM2',
  rc: 'RC',
  openrc: 'OpenRC',
  winservice: 'Windows Service',
  launchd: 'launchd',
  containerd: 'containerd',
  unknown: 'Unknown',
};

export const SERVICE_RUNTIME_COLORS: Record<string, { text: string; bg: string }> = {
  systemd: { text: 'text-success', bg: 'bg-success/10' },
  docker: { text: 'text-info', bg: 'bg-info/10' },
  podman: { text: 'text-warning', bg: 'bg-warning/10' },
  kubernetes: { text: 'text-info', bg: 'bg-info/10' },
  lxc: { text: 'text-success', bg: 'bg-success/10' },
  supervisord: { text: 'text-destructive', bg: 'bg-destructive/10' },
  pm2: { text: 'text-primary', bg: 'bg-primary/10' },
  rc: { text: 'text-warning', bg: 'bg-warning/10' },
  openrc: { text: 'text-warning', bg: 'bg-warning/10' },
  winservice: { text: 'text-info', bg: 'bg-info/10' },
  launchd: { text: 'text-muted-foreground', bg: 'bg-muted' },
  containerd: { text: 'text-primary', bg: 'bg-primary/10' },
  unknown: { text: 'text-muted-foreground', bg: 'bg-muted' },
};

export const NETWORK_TYPE_LABELS: Record<string, string> = {
  physical: 'Physical',
  virtual: 'Virtual',
  overlay: 'Overlay',
  vlan: 'VLAN',
  vxlan: 'VXLAN',
  bridge: 'Bridge',
  tunnel: 'Tunnel',
};

export const ROLE_LABELS: Record<string, string> = {
  admin: 'Administrator',
  operator: 'Operator',
  viewer: 'Viewer',
  family: 'Family',
  agent: 'Agent',
};

export const ROLE_COLORS: Record<string, { bg: string; text: string }> = {
  admin: { bg: 'bg-destructive/10', text: 'text-destructive' },
  operator: { bg: 'bg-info/10', text: 'text-info' },
  viewer: { bg: 'bg-muted', text: 'text-muted-foreground' },
  family: { bg: 'bg-success/10', text: 'text-success' },
  agent: { bg: 'bg-primary/10', text: 'text-primary' },
};
