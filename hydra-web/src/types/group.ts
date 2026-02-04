import { ListParams } from './api';

export type GroupEntityType = 'node' | 'service';

export interface IdSelector {
  isAll?: string[];
}

export interface AnySelector {
  isAny?: string[];
}

export interface TagsSelector {
  isAny?: string[];
  isAll?: string[];
}

export interface GroupSelectors {
  id?: IdSelector;
  network?: AnySelector;
  status?: AnySelector;
  kind?: AnySelector;
  runtime?: AnySelector;
  tags?: TagsSelector;
}

export interface MemberCount {
  nodes: number;
  services: number;
  lastComputed?: string;
}

export interface GroupSummary {
  groupId: string;
  name: string;
  description?: string;
  types: GroupEntityType[];
  memberCount: MemberCount;
  tags: string[];
}

export interface Group extends GroupSummary {
  selectors: GroupSelectors;
  parentGroupIds: string[];
  members?: GroupMembersResponse;
  createdAt: string;
  updatedAt: string;
}

export interface GroupMemberNode {
  nodeId: string;
  displayName: string;
  matchedSelectors: string[];
}

export interface GroupMemberService {
  serviceId: string;
  name: string;
  nodeId: string;
  matchedSelectors: string[];
}

export interface GroupMembersResponse {
  nodes: GroupMemberNode[];
  services: GroupMemberService[];
}

export interface GroupMember {
  id: string;
  type: 'node' | 'service';
  displayName: string;
  matchedBy: string[];
  class?: string;
  kind?: string;
  status?: string;
  runtime?: string;
  nodeId?: string;
}

export interface SelectorEntry {
  type: string;
  values: string[];
  mode?: 'isAny' | 'isAll';
}

export function getSelectorEntries(selectors: GroupSelectors): SelectorEntry[] {
  const entries: SelectorEntry[] = [];

  if (selectors.id?.isAll?.length) {
    entries.push({ type: 'id', values: selectors.id.isAll, mode: 'isAll' });
  }
  if (selectors.network?.isAny?.length) {
    entries.push({ type: 'network', values: selectors.network.isAny });
  }
  if (selectors.status?.isAny?.length) {
    entries.push({ type: 'status', values: selectors.status.isAny });
  }
  if (selectors.kind?.isAny?.length) {
    entries.push({ type: 'kind', values: selectors.kind.isAny });
  }
  if (selectors.runtime?.isAny?.length) {
    entries.push({ type: 'runtime', values: selectors.runtime.isAny });
  }
  if (selectors.tags?.isAny?.length) {
    entries.push({ type: 'tags', values: selectors.tags.isAny, mode: 'isAny' });
  }
  if (selectors.tags?.isAll?.length) {
    entries.push({ type: 'tags', values: selectors.tags.isAll, mode: 'isAll' });
  }

  return entries;
}

export function getSelectorDisplayValue(entry: SelectorEntry): string {
  const values = entry.values.join(', ');
  if (entry.type === 'tags' && entry.mode) {
    return `${entry.mode}: ${values}`;
  }
  return values;
}

export interface GroupListParams extends ListParams {
  types?: GroupEntityType[];
  parentGroupId?: string;
  tags?: string[];
}

export interface CreateGroupRequest {
  groupId: string;
  name: string;
  description?: string;
  types: GroupEntityType[];
  selectors: GroupSelectors;
  parentGroupIds?: string[];
  tags?: string[];
}

export interface UpdateGroupRequest {
  name?: string;
  description?: string;
  selectors?: GroupSelectors;
  parentGroupIds?: string[];
  tags?: string[];
}
