export type DocType =
  | 'guide'
  | 'architecture'
  | 'runbook'
  | 'troubleshooting'
  | 'reference'
  | 'changelog'
  | 'other';

export type DocStatus = 'draft' | 'published' | 'archived';
export type DocFormat = 'markdown' | 'plain' | 'html';
export type EntityType = 'node' | 'service' | 'network' | 'group';

export interface LinkedEntity {
  entityType: EntityType;
  entityId: string;
}

export interface DocumentSection {
  sectionId: string;
  title: string;
  content: string;
  source: 'generated' | 'manual' | 'manual-override';
  templateRef?: string | null;
  dataFingerprint?: string | null;
  lastGeneratedAt?: string | null;
  lastEditedAt?: string | null;
  editedBy?: string | null;
  order: number;
}

export interface DocSummary {
  docId: string;
  title: string;
  type: DocType;
  category?: string | null;
  status: DocStatus;
  linkedEntities?: LinkedEntity[] | null;
  version: number;
  lastGeneratedAt?: string | null;
  staleAfterHours?: number | null;
  updatedAt: string;
}

export interface DocResponse {
  docId: string;
  title: string;
  description?: string | null;
  type: DocType;
  format: DocFormat;
  content: string;
  sections: DocumentSection[];
  linkedEntities?: LinkedEntity[] | null;
  category?: string | null;
  tags?: string[] | null;
  version: number;
  author?: string | null;
  status: DocStatus;
  templateId?: string | null;
  lastGeneratedAt?: string | null;
  staleAfterHours?: number | null;
  createdAt: string;
  updatedAt: string;
}

export interface DocTreeNode {
  nodeId: string;
  title: string;
  path: string;
  kind: 'category' | 'document';
  category?: string | null;
  docId?: string | null;
  docType?: DocType | null;
  status?: DocStatus | null;
  updatedAt?: string | null;
  children: DocTreeNode[];
}

export interface DocSearchResult {
  docId: string;
  title: string;
  type: DocType;
  status: DocStatus;
  category?: string | null;
  excerpt?: string | null;
  linkedEntities?: LinkedEntity[] | null;
  updatedAt: string;
}

export interface DocsListParams {
  type?: DocType;
  status?: DocStatus;
  category?: string;
  entityType?: EntityType;
  entityId?: string;
  tags?: string[];
  search?: string;
  limit?: number;
  offset?: number;
}
