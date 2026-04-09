import type { ListParams } from '@/types/api';

export type DashboardBoardType = 'home' | 'custom' | 'template';
export type DashboardVisibility = 'private' | 'shared' | 'public';

export interface DashboardLayoutBreakpoint {
  columns: number;
  width: number;
}

export interface DashboardBoardLayout {
  columns: number;
  rowHeight: number;
  breakpoints: Record<string, DashboardLayoutBreakpoint>;
}

export interface DashboardWidgetPosition {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface DashboardDataBinding {
  source: string;
  query: Record<string, unknown>;
  refreshInterval?: number | null;
}

export interface DashboardWidgetInstance {
  instanceId: string;
  widgetType: string;
  position: DashboardWidgetPosition;
  config: Record<string, unknown>;
  dataBinding?: DashboardDataBinding | null;
}

export interface DashboardBoardSettings {
  theme: string;
  autoRefresh: boolean;
  refreshInterval: number;
  showHeader: boolean;
  kioskMode: boolean;
}

export interface DashboardBoardSummary {
  boardId: string;
  name: string;
  description?: string | null;
  icon?: string | null;
  ownerId: string;
  boardType: DashboardBoardType;
  visibility: DashboardVisibility;
  widgetCount: number;
  tags: string[];
  isHome: boolean;
  version: number;
  createdAt: string;
  updatedAt: string;
}

export interface DashboardBoard extends DashboardBoardSummary {
  layout: DashboardBoardLayout;
  widgets: DashboardWidgetInstance[];
  settings: DashboardBoardSettings;
  clonedFrom?: string | null;
  archivedAt?: string | null;
}

export interface DashboardCreateWidgetRequest {
  widgetType: string;
  position: DashboardWidgetPosition;
  config?: Record<string, unknown>;
  dataBinding?: DashboardDataBinding | null;
}

export interface CreateDashboardRequest {
  name: string;
  description?: string | null;
  icon?: string | null;
  boardType?: DashboardBoardType;
  visibility?: DashboardVisibility;
  layout?: DashboardBoardLayout;
  widgets?: DashboardCreateWidgetRequest[];
  settings?: DashboardBoardSettings;
  tags?: string[];
  isHome?: boolean;
}

export interface UpdateDashboardRequest {
  name?: string;
  description?: string | null;
  icon?: string | null;
  boardType?: DashboardBoardType;
  visibility?: DashboardVisibility;
  layout?: DashboardBoardLayout;
  widgets?: DashboardWidgetInstance[];
  settings?: DashboardBoardSettings;
  tags?: string[];
  isHome?: boolean;
}

export interface DashboardListParams extends ListParams {
  boardType?: DashboardBoardType;
  visibility?: DashboardVisibility;
  tags?: string[];
}

export interface WidgetSize {
  w: number;
  h: number;
}

export interface WidgetConfigOption {
  label: string;
  value: string;
}

export interface WidgetConfigField {
  key: string;
  label: string;
  fieldType: 'text' | 'boolean' | 'number' | 'select';
  description?: string | null;
  placeholder?: string | null;
  minValue?: number | null;
  maxValue?: number | null;
  options: WidgetConfigOption[];
}

export interface WidgetCapabilities {
  configurable: boolean;
  supportsVisibilityToggle: boolean;
  repeatable: boolean;
}

export interface WidgetTypeDefinition {
  widgetType: string;
  displayName: string;
  description: string;
  category: string;
  icon: string;
  source: string;
  defaultSize: WidgetSize;
  minSize: WidgetSize;
  maxSize: WidgetSize;
  configSchema: WidgetConfigField[];
  capabilities: WidgetCapabilities;
}

export interface WidgetCategoryInfo {
  id: string;
  name: string;
  count: number;
}

export interface WidgetRegistryResponse {
  widgets: WidgetTypeDefinition[];
  categories: WidgetCategoryInfo[];
  total: number;
}

// ── Template & Sharing Types ────────────────────────────────────────

export interface ShareTarget {
  roles: string[];
  users: string[];
}

export interface ShareBoardRequest {
  sharedWith: ShareTarget;
}

export interface ShareInfo {
  sharedWith: ShareTarget;
  sharedAt: string;
  sharedBy: string;
}

export interface SaveAsTemplateRequest {
  name?: string;
  description?: string;
  tags?: string[];
}

export interface ExportedBoard {
  name: string;
  description?: string;
  icon?: string;
  boardType: DashboardBoardType;
  layout?: DashboardBoardLayout;
  widgets?: DashboardWidgetInstance[];
  settings?: DashboardBoardSettings;
  tags?: string[];
}

export interface ImportBoardRequest {
  board: ExportedBoard;
  name?: string;
}

export interface TemplateListParams {
  search?: string;
  tags?: string[];
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

export interface DashboardTemplateSummary {
  templateId: string;
  name: string;
  description?: string | null;
  boardType: DashboardBoardType;
  tags: string[];
  widgetCount: number;
  createdBy: string;
  createdAt: string;
}

export interface DashboardTemplate extends DashboardTemplateSummary {
  layout: DashboardBoardLayout;
  widgets: DashboardWidgetInstance[];
  settings: DashboardBoardSettings;
  updatedAt: string;
}
