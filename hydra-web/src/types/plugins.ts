// ── Plugin Enums ──────────────────────────────────────────────────

export type PluginStatus =
  | 'installed'
  | 'configured'
  | 'enabled'
  | 'active'
  | 'disabled'
  | 'error';

export type PluginClassification = 'core' | 'default' | 'community';

export type PluginCategory =
  | 'infrastructure'
  | 'monitoring'
  | 'version_control'
  | 'databases'
  | 'cloud'
  | 'development'
  | 'other';

// ── Embedded Types ────────────────────────────────────────────────

export interface PluginTouchpoints {
  profileEnrichment: boolean;
  discoveryProvider: boolean;
  commandProvider: boolean;
  executionHandler: boolean;
  topologyProvider: boolean;
  workflowBlockProvider: boolean;
}

export interface PluginHealthStatus {
  status: string;
  lastCheck: string | null;
  consecutiveFailures: number;
  lastError: string | null;
  responseTimeMs: number | null;
}

export interface NodeBinding {
  nodeId: string;
  enabled: boolean;
  allowedCommands: string[];
  boundAt: string;
}

export interface PluginManifest {
  pluginId: string;
  name: string;
  version: string;
  description: string;
  author: string;
  classification: PluginClassification;
  category: PluginCategory;
  touchpoints: PluginTouchpoints;
  supportedTiers: string[];
  healthCheckEndpoint: string | null;
  contributedCommands: string[];
}

// ── Response Types ────────────────────────────────────────────────

export interface PluginResponse {
  pluginId: string;
  manifest: PluginManifest;
  status: PluginStatus;
  config: Record<string, unknown>;
  nodeBindings: NodeBinding[];
  health: PluginHealthStatus;
  createdAt: string;
  updatedAt: string;
}

export interface PluginSummary {
  pluginId: string;
  name: string;
  status: PluginStatus;
  classification: PluginClassification;
  category: PluginCategory;
  healthStatus: string;
  nodeCount: number;
  createdAt: string;
}

// ── Request Types ─────────────────────────────────────────────────

export interface RegisterPluginRequest {
  manifest: PluginManifest;
  config?: Record<string, unknown>;
  credentials?: Record<string, string>;
}

export interface UpdatePluginConfigRequest {
  config?: Record<string, unknown>;
  credentials?: Record<string, string>;
}

export interface BindNodeRequest {
  allowedCommands?: string[];
}
