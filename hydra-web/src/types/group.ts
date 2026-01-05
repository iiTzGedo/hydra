import { ListParams } from './api';

// Entity types that can be grouped
export type GroupEntityType = 'nodes' | 'services' | 'both';

// Selector types
export type SelectorType = 'id' | 'network' | 'tag' | 'status' | 'class' | 'type' | 'kind' | 'runtime';

// Tag selector mode
export type TagSelectorMode = 'isAny' | 'isAll';

// Base selector
export interface BaseSelector {
  type: SelectorType;
}

// ID selector - select specific IDs
export interface IdSelector extends BaseSelector {
  type: 'id';
  ids: string[];
}

// Network selector - select by network membership
export interface NetworkSelector extends BaseSelector {
  type: 'network';
  networkIds: string[];
}

// Tag selector - select by tags
export interface TagSelector extends BaseSelector {
  type: 'tag';
  tags: string[];
  mode: TagSelectorMode;
}

// Status selector
export interface StatusSelector extends BaseSelector {
  type: 'status';
  statuses: string[];
}

// Class selector (nodes)
export interface ClassSelector extends BaseSelector {
  type: 'class';
  classes: string[];
}

// Type selector (nodes)
export interface TypeSelector extends BaseSelector {
  type: 'type';
  types: string[];
}

// Kind selector (nodes)
export interface KindSelector extends BaseSelector {
  type: 'kind';
  kinds: string[];
}

// Runtime selector (services)
export interface RuntimeSelector extends BaseSelector {
  type: 'runtime';
  runtimes: string[];
}

// Union of all selector types
export type Selector =
  | IdSelector
  | NetworkSelector
  | TagSelector
  | StatusSelector
  | ClassSelector
  | TypeSelector
  | KindSelector
  | RuntimeSelector;

// Member counts
export interface MemberCounts {
  nodes?: number;
  services?: number;
  total: number;
}

// Group summary (for list views)
export interface GroupSummary {
  groupId: string;
  name: string;
  entityTypes: GroupEntityType;
  memberCounts: MemberCounts;
  tags: string[];
  createdAt: string;
  updatedAt: string;
}

// Full group details
export interface Group extends GroupSummary {
  description?: string;
  selectors: Selector[];
  parentGroupId?: string;
}

// Group member
export interface GroupMember {
  id: string;
  type: 'node' | 'service';
  displayName: string;
  matchedBy: SelectorType[];
  class?: string; // Node class if type is 'node'
  kind?: string; // Node kind if type is 'node'
  status?: string; // Status of the entity
  runtime?: string; // Service runtime if type is 'service'
}

// Helper to get selector display value
export function getSelectorDisplayValue(selector: Selector): string {
  switch (selector.type) {
    case 'id':
      return selector.ids.join(', ');
    case 'network':
      return selector.networkIds.join(', ');
    case 'tag':
      return `${selector.mode}: ${selector.tags.join(', ')}`;
    case 'status':
      return selector.statuses.join(', ');
    case 'class':
      return selector.classes.join(', ');
    case 'type':
      return selector.types.join(', ');
    case 'kind':
      return selector.kinds.join(', ');
    case 'runtime':
      return selector.runtimes.join(', ');
    default:
      return '';
  }
}

// Group list params
export interface GroupListParams extends ListParams {
  types?: GroupEntityType;
  parentGroupId?: string;
  tags?: string[];
}

// Create group request
export interface CreateGroupRequest {
  groupId?: string;
  name: string;
  description?: string;
  entityTypes: GroupEntityType;
  selectors: Selector[];
  parentGroupId?: string;
  tags?: string[];
}

// Update group request
export interface UpdateGroupRequest {
  name?: string;
  description?: string;
  selectors?: Selector[];
  tags?: string[];
}
