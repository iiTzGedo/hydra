export type ThemeMode = 'light' | 'dark' | 'system';
export type LayoutMode = 'list' | 'grid' | 'compact';
export type SortOrder = 'asc' | 'desc';

export interface UISettings {
  theme: ThemeMode;
  sidebarCollapsed: boolean;
  animationsEnabled: boolean;
}

export interface EntityViewSettings {
  layout: LayoutMode;
  sortField: string;
  sortOrder: SortOrder;
  pageSize: number;
  filters: Record<string, unknown>;
}

export interface ViewSettings {
  nodes: EntityViewSettings;
  services: EntityViewSettings;
  networks: EntityViewSettings;
  groups: EntityViewSettings;
  topology: EntityViewSettings;
}

export interface NotificationSettings {
  emailEnabled: boolean;
  browserEnabled: boolean;
  nodeAlerts: boolean;
  serviceAlerts: boolean;
  profileUpdates: boolean;
}

export interface UserSettingsResponse {
  userId: string;
  ui: UISettings;
  views: ViewSettings;
  notifications: NotificationSettings;
  updatedAt: string;
}

export interface UserSettingsUpdate {
  ui?: Partial<UISettings>;
  views?: Partial<ViewSettings>;
  notifications?: Partial<NotificationSettings>;
}

export interface SmtpSettings {
  enabled: boolean;
  host?: string | null;
  port: number;
  username?: string | null;
  fromAddress?: string | null;
  fromName: string;
  useTls: boolean;
}

export interface ObjectStorageSettings {
  enabled: boolean;
  endpoint?: string | null;
  bucket: string;
  region: string;
}

export interface DefaultSettings {
  nodeStatus: string;
  profileRetentionDays: number;
  sessionTimeoutMinutes: number;
}

export interface SystemSettingsResponse {
  smtp: SmtpSettings;
  objectStorage: ObjectStorageSettings;
  defaults: DefaultSettings;
  updatedAt: string;
  updatedBy?: string | null;
}

export interface SystemSettingsUpdate {
  smtp?: Partial<SmtpSettings>;
  objectStorage?: Partial<ObjectStorageSettings>;
  defaults?: Partial<DefaultSettings>;
}
