import type { ListParams } from '@/types/api';

export type DashboardBoardType = 'home' | 'custom' | 'template';
export type DashboardVisibility = 'private' | 'shared' | 'public';
export type DashboardLayoutMode = 'grid' | 'columns';
export type DashboardGridCompaction = 'vertical' | 'horizontal' | 'none';

export interface DashboardLayoutBreakpoint {
  columns: number;
  width: number;
}

export interface DashboardGridLayoutConfig {
  columns: number;
  rowHeight: number;
  breakpoints: Record<string, DashboardLayoutBreakpoint>;
  compaction: DashboardGridCompaction;
  margin: [number, number];
  padding: [number, number];
}

export interface DashboardColumnDefinition {
  id: string;
  title?: string | null;
  ratio: number;
}

export interface DashboardColumnsLayoutConfig {
  columns: DashboardColumnDefinition[];
  gap: number;
  padding: [number, number];
}

export interface DashboardGridBoardLayout {
  mode: 'grid';
  grid: DashboardGridLayoutConfig;
  columnsLayout?: never;
}

export interface DashboardColumnsBoardLayout {
  mode: 'columns';
  grid?: never;
  columnsLayout: DashboardColumnsLayoutConfig;
}

export type DashboardBoardLayout = DashboardGridBoardLayout | DashboardColumnsBoardLayout;

export interface LegacyDashboardBoardLayout {
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
  position?: DashboardWidgetPosition | null;
  placements?: Record<string, DashboardWidgetPosition> | null;
  column?: string | null;
  order?: number | null;
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
  position?: DashboardWidgetPosition | null;
  placements?: Record<string, DashboardWidgetPosition> | null;
  column?: string | null;
  order?: number | null;
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

export function normalizeDashboardLayout(
  layout: DashboardBoardLayout | LegacyDashboardBoardLayout | null | undefined,
): DashboardBoardLayout {
  if (!layout) {
    return {
      mode: 'grid',
      grid: {
        columns: 12,
        rowHeight: 80,
        breakpoints: {
          lg: { columns: 12, width: 1200 },
          md: { columns: 8, width: 996 },
          sm: { columns: 4, width: 768 },
        },
        compaction: 'vertical',
        margin: [16, 16],
        padding: [0, 0],
      },
    };
  }

  if ('mode' in layout) {
    return layout;
  }

  return {
    mode: 'grid',
    grid: {
      columns: layout.columns,
      rowHeight: layout.rowHeight,
      breakpoints: layout.breakpoints,
      compaction: 'vertical',
      margin: [16, 16],
      padding: [0, 0],
    },
  };
}
