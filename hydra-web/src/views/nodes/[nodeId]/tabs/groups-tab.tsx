import Link from 'next/link';
import { FolderTree, Loader2 } from 'lucide-react';
import { useNodeGroups } from '@/api/groups';
import type { Node } from '@/types/node';
import { ROUTES } from '@/lib/constants';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/common/empty-state';
import { Badge } from '@/components/ui/badge';

interface GroupsTabProps {
  node: Node;
}

export function GroupsTab({ node }: GroupsTabProps) {
  const { data: nodeGroups, isLoading, error, isFetching } = useNodeGroups(node.id || node.nodeId);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Checking group memberships...
        </div>
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <EmptyState
        icon={FolderTree}
        title="Failed to load groups"
        description="There was an error checking group memberships"
      />
    );
  }

  const groups = nodeGroups?.items ?? [];

  if (groups.length === 0) {
    return (
      <EmptyState
        icon={FolderTree}
        title="No group membership"
        description="This node is not a member of any groups"
        action={{
          label: 'View All Groups',
          href: ROUTES.GROUPS,
        }}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <p className="text-sm text-muted-foreground">
            Member of {groups.length} group{groups.length !== 1 ? 's' : ''}
          </p>
          {isFetching && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
        </div>
        <Link
          href={ROUTES.GROUPS}
          className="text-sm text-primary hover:underline"
        >
          View all groups
        </Link>
      </div>

      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {groups.map((group) => (
          <Link
            key={group.id}
            href={ROUTES.GROUPS + '/' + group.id}
            className="flex items-start gap-3 rounded-lg border bg-card p-4 hover:bg-muted/50 transition-colors group"
          >
            <div className="rounded-lg bg-muted p-2">
              <FolderTree className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-medium truncate group-hover:text-primary transition-colors">
                {group.name}
              </div>
              {group.description && (
                <div className="mt-0.5 text-xs text-muted-foreground truncate">
                  {group.description}
                </div>
              )}
              <div className="mt-1 flex items-center gap-2 flex-wrap">
                {group.types?.map(type => (
                  <Badge key={type} variant="secondary" className="text-xs capitalize">
                    {type}
                  </Badge>
                ))}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {(group.memberCount?.nodes ?? 0) + (group.memberCount?.services ?? 0)} total members
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
