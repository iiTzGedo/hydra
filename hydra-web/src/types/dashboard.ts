import type { ListParams } from '@/types/api';

// ── Enums ─────────────────────────────────────────────────────────

export type DashboardBoardType = 'user' | 'template' | 'shared' | 'kiosk';
export type DashboardOwnerType = 'user' | 'system';
export type DashboardVisibilityScope = 'private' | 'shared' | 'public';
export type DashboardLayoutMode = 'grid' | 'columns' | 'freeform';
export type DashboardGridCompaction = 'vertical' | 'horizontal' | 'none';
export type DashboardBreakpointKey = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

// ── Structured visibility ────────────────────────────────────────

export interface DashboardSharedWith {
  roles: string[];
  users: string[];
}

export interface DashboardVisibility {
  scope: DashboardVisibilityScope;
  sharedWith: DashboardSharedWith;
}

// ── Layout ────────────────────────────────────────────────────────

export interface DashboardLayoutBreakpoint {
  columns: number;
  width: number;
}

export interface DashboardGridLayoutConfig {
  columns: number;
  rowHeight: number;
  breakpoints: Partial<Record<DashboardBreakpointKey, DashboardLayoutBreakpoint>>;
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
  breakpoints: Partial<Record<DashboardBreakpointKey, DashboardLayoutBreakpoint>>;
}

// ── Widget instance ───────────────────────────────────────────────

export interface DashboardWidgetPosition {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface DashboardDataBindingFallback {
  type: 'cached' | 'empty' | 'error';
  maxAge?: number | null;
}

export interface DashboardDataBindingQuery {
  /** API endpoint path (e.g., "/nodes", "/nodes/{nodeId}/profiles/latest") */
  endpoint?: string;
  /** Query parameters passed to the endpoint */
  params?: Record<string, unknown>;
  /** Transform to apply after fetch (e.g., "count", "sum(cores)", { chain: [...] }) */
  transform?: string | Record<string, unknown>;
  /** Inline data for static:: sources */
  data?: unknown;
}

export interface DashboardDataBinding {
  source: string;
  query: DashboardDataBindingQuery;
  refreshInterval?: number | null;
  realtimeChannel?: string | null;
  fallback?: DashboardDataBindingFallback | null;
}

// ── Multi-source bindings (spec §6.5) ─────────────────────────────

export interface DashboardMultiSourceEntry {
  source: string;
  query: DashboardDataBindingQuery;
}

export interface DashboardMultiSourceBinding {
  sources: Record<string, DashboardMultiSourceEntry>;
  /** Shared parameters for {placeholder} substitution across all sources */
  params?: Record<string, unknown>;
  refreshInterval?: number | null;
}

// ── Transform operations (spec §6.4) ──────────────────────────────

/**
 * Transform operations applied client-side to fetched data.
 * Can be a simple string name ("count", "none") or an object with args.
 */
export type TransformSpec =
  | string
  | { chain: TransformSpec[] }
  | { sum: string }
  | { avg: string }
  | { min: string }
  | { max: string }
  | { group_by: string }
  | { count_by: string }
  | { pluck: string }
  | { sort: { field: string; direction?: 'asc' | 'desc' } }
  | { first: number }
  | { last: number }
  | { map: string }
  | { filter: { field: string; op: string; value: unknown } };

export interface DashboardWidgetInstance {
  instanceId: string;
  widgetType: string;
  position?: DashboardWidgetPosition | null;
  placements?: Partial<Record<DashboardBreakpointKey, DashboardWidgetPosition>> | null;
  column?: string | null;
  order?: number | null;
  config: Record<string, unknown>;
  /** Single-source data binding */
  dataBinding?: DashboardDataBinding | null;
  /** Multi-source data binding (spec §6.5) — alternative to dataBinding */
  multiBinding?: DashboardMultiSourceBinding | null;
}

// ── Board settings ────────────────────────────────────────────────

export interface DashboardBoardSettings {
  theme: string;
  autoRefresh: boolean;
  refreshInterval: number;
  showHeader: boolean;
  kioskMode: boolean;
  kioskAutoScroll: boolean;
  kioskScrollSpeed: number;
  backgroundImage: string | null;
  customCss: string | null;
}

// ── Board summary / detail ───────────────────────────────────────

export interface DashboardBoardSummary {
  boardId: string;
  name: string;
  description?: string | null;
  icon?: string | null;
  ownerId: string;
  ownerType: DashboardOwnerType;
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

// ── Requests ──────────────────────────────────────────────────────

export interface DashboardCreateWidgetRequest {
  widgetType: string;
  position?: DashboardWidgetPosition | null;
  placements?: Partial<Record<DashboardBreakpointKey, DashboardWidgetPosition>> | null;
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
  ownerId?: string;
  visibility?: DashboardVisibilityScope;
  tags?: string[];
}

// ── PATCH operations ──────────────────────────────────────────────

export type PatchDashboardOperation =
  | { op: 'update-settings'; settings: DashboardBoardSettings }
  | { op: 'update-layout'; layout: DashboardBoardLayout }
  | { op: 'add-widget'; widget: DashboardCreateWidgetRequest }
  | {
      op: 'update-widget';
      instanceId: string;
      changes: Partial<DashboardWidgetInstance>;
    }
  | { op: 'remove-widget'; instanceId: string }
  | { op: 'reorder-widgets'; order: string[] };

export interface PatchDashboardRequest {
  operations: PatchDashboardOperation[];
}

// ── Widget registry ──────────────────────────────────────────────

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
  fieldType: 'text' | 'boolean' | 'number' | 'select' | 'entity';
  /** Entity type for fieldType === 'entity' */
  entityType?: 'node' | 'service' | 'network' | 'group';
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

export interface WidgetPermissions {
  view: string[];
  interact: string[];
}

export interface WidgetTypeDefinition {
  widgetType: string;
  displayName: string;
  description: string;
  category: string;
  icon: string;
  source: string;
  version: string;
  supportedDataShapes: string[];
  tags: string[];
  permissions: WidgetPermissions;
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

// ── Full widget component props contract (spec §14.3) ───────────

export interface WidgetComponentDimensions {
  width: number;
  height: number;
}

export interface WidgetComponentProps<
  TData = unknown,
  TConfig extends Record<string, unknown> = Record<string, unknown>,
> {
  /** Resolved data from the data binding layer (Wave 2). Null until resolved. */
  data?: TData | null;
  /** Widget-specific configuration persisted on the board. */
  config: TConfig;
  /** True while the board is in edit mode (drag/drop/resize). */
  isEditing: boolean;
  /** Rendered widget dimensions in pixels (resolved from grid). */
  dimensions: WidgetComponentDimensions;
  /** True while the data binding layer is loading the initial value. */
  isLoading: boolean;
  /** Error from the data binding layer, if any. */
  error: Error | null;
  /** Callback for control widgets to execute commands via RBAC. */
  onExecuteCommand?: (
    commandId: string,
    target: Record<string, unknown>,
    params: Record<string, unknown>,
  ) => Promise<void>;
  /** Callback for click-through navigation. */
  onNavigate?: (path: string) => void;
}

// ── Template & Sharing Types ────────────────────────────────────────

export interface ShareTarget {
  roles: string[];
  users: string[];
}

export interface ShareBoardRequest {
  scope: DashboardVisibilityScope;
  sharedWith: ShareTarget;
}

export interface ShareBoardResponse {
  boardId: string;
  scope: DashboardVisibilityScope;
  sharedWith: ShareTarget;
}

export interface ShareInfo {
  sharedWith: ShareTarget;
  sharedAt: string;
  sharedBy: string;
}

export type DashboardTemplateCategory =
  | 'infrastructure'
  | 'monitoring'
  | 'iot'
  | 'networking'
  | 'security'
  | 'capacity'
  | 'operations'
  | 'general';

export type DashboardTemplateSource = 'system' | 'user';

export interface TemplateVariableDefinition {
  type: string;
  label: string;
  description?: string | null;
  default?: unknown;
  required?: boolean;
  options?: string[] | null;
}

export interface SaveAsTemplateRequest {
  name?: string;
  description?: string;
  category?: DashboardTemplateCategory;
  targetRoles?: string[];
  requiredPlugins?: string[];
  optionalPlugins?: string[];
  variables?: Record<string, TemplateVariableDefinition> | null;
  tags?: string[];
}

export interface InstantiateTemplateRequest {
  name?: string;
  variables?: Record<string, unknown> | null;
}

export interface ExportedBoard {
  exportVersion?: number;
  name: string;
  description?: string | null;
  icon?: string | null;
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

export interface ImportValidationIssue {
  level: 'warning' | 'error';
  code: string;
  message: string;
  widgetIndex?: number | null;
}

export interface ImportBoardResponse {
  board: DashboardBoard;
  warnings: ImportValidationIssue[];
}

export interface TemplateListParams {
  category?: DashboardTemplateCategory;
  source?: DashboardTemplateSource;
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
  category: DashboardTemplateCategory;
  targetRoles: string[];
  requiredPlugins: string[];
  optionalPlugins: string[];
  preview?: string | null;
  source: DashboardTemplateSource;
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
  variables?: Record<string, TemplateVariableDefinition> | null;
  updatedAt: string;
}

// ── Version History Types ─────────────────────────────────────────

export interface DashboardVersionSummary {
  boardId: string;
  version: number;
  savedBy: string;
  savedAt: string;
  changeDescription?: string | null;
  widgetCount: number;
}

export interface DashboardVersionSnapshot extends DashboardVersionSummary {
  snapshot: Record<string, unknown>;
}

// ── Defaults & helpers ───────────────────────────────────────────

export const DEFAULT_BREAKPOINTS: Record<DashboardBreakpointKey, DashboardLayoutBreakpoint> = {
  xl: { columns: 12, width: 1536 },
  lg: { columns: 12, width: 1200 },
  md: { columns: 8, width: 996 },
  sm: { columns: 4, width: 480 },
  xs: { columns: 2, width: 0 },
};

export const DEFAULT_BOARD_SETTINGS: DashboardBoardSettings = {
  theme: 'inherit',
  autoRefresh: true,
  refreshInterval: 30,
  showHeader: true,
  kioskMode: false,
  kioskAutoScroll: false,
  kioskScrollSpeed: 30,
  backgroundImage: null,
  customCss: null,
};

export const DEFAULT_VISIBILITY: DashboardVisibility = {
  scope: 'private',
  sharedWith: { roles: [], users: [] },
};

export function normalizeDashboardLayout(
  layout: DashboardBoardLayout | LegacyDashboardBoardLayout | null | undefined,
): DashboardBoardLayout {
  if (!layout) {
    return {
      mode: 'grid',
      grid: {
        columns: 12,
        rowHeight: 80,
        breakpoints: { ...DEFAULT_BREAKPOINTS },
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
