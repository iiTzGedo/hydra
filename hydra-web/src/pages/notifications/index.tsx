import { useState, useMemo, useCallback } from 'react';
import { PageHeaderLayout } from '@/components/layout/page-header-layout';
import {
  CheckCheck,
  CheckCircle,
  Filter,
  Info,
  Loader2,
  RefreshCw,
  Trash2,
  X,
} from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { queryKeys } from '@/lib/query-client';
import {
  useNotifications,
  useNotificationStats,
  useMarkNotificationRead,
  useMarkAllRead,
  useAcknowledgeNotification,
  useAcknowledgeAllNotifications,
  useResolveNotification,
  useDeleteNotification,
  useDeleteNotifications,
} from '@/api/notifications';
import { useAuthStore } from '@/stores/auth-store';
import { NotificationItem } from '@/components/notifications/notification-item';
import { NotificationDetailsModal } from '@/components/notifications/notification-details-modal';
import type { Notification, NotificationListParams, NotificationTier, SourceComponent } from '@/types/notification';
import { ACKNOWLEDGE_MIN_TIER, INFO_MAX_TIER, RESOLVE_MIN_TIER, TIER_COLORS } from '@/types/notification';

type StatusTab = 'active' | 'acknowledged' | 'resolved' | 'info';

const TAB_EMPTY_MESSAGES: Record<StatusTab, string> = {
  active: 'No active notifications requiring attention',
  acknowledged: 'No acknowledged notifications pending resolution',
  resolved: 'No resolved notifications',
  info: 'No informational notifications',
};

export default function NotificationsPage() {
  const queryClient = useQueryClient();
  const { hasPermission } = useAuthStore();
  const canWrite = hasPermission('notifications:write');

  // Filters
  const [statusTab, setStatusTab] = useState<StatusTab>('active');
  const [tierFilter, setTierFilter] = useState<string>('all');
  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [page, setPage] = useState(0);
  const pageSize = 20;

  // Details modal state
  const [detailsNotification, setDetailsNotification] = useState<Notification | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);

  // Selection state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // Build query params based on active tab
  const params = useMemo<NotificationListParams>(() => {
    const p: NotificationListParams = {
      limit: pageSize,
      offset: page * pageSize,
    };

    // Tab-specific query logic
    switch (statusTab) {
      case 'active':
        // Tier 3+ unacknowledged active notifications
        p.status = 'active';
        p.tierMin = ACKNOWLEDGE_MIN_TIER;
        p.acknowledged = false;
        break;
      case 'acknowledged':
        // Tier 3+ acknowledged but still active (not resolved)
        p.status = 'active';
        p.tierMin = ACKNOWLEDGE_MIN_TIER;
        p.acknowledged = true;
        break;
      case 'resolved':
        // Tier 3+ resolved notifications
        p.status = 'resolved';
        p.tierMin = RESOLVE_MIN_TIER;
        break;
      case 'info':
        // Tier 1-2 (blue/green) informational — any status
        p.tierMax = INFO_MAX_TIER;
        break;
    }

    // Apply user filters on top
    if (tierFilter !== 'all') {
      p.tier = parseInt(tierFilter) as NotificationTier;
    }
    if (sourceFilter !== 'all') {
      p.source = sourceFilter as SourceComponent;
    }
    return p;
  }, [statusTab, tierFilter, sourceFilter, page]);

  const { data, isLoading, isFetching } = useNotifications(params);
  const { data: stats } = useNotificationStats();

  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllRead();
  const acknowledge = useAcknowledgeNotification();
  const acknowledgeAll = useAcknowledgeAllNotifications();
  const resolve = useResolveNotification();
  const deleteSingle = useDeleteNotification();
  const deleteMany = useDeleteNotifications();

  const notifications = useMemo(() => data?.items ?? [], [data?.items]);
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / pageSize);

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all });
  };

  const handleViewDetails = useCallback((notification: Notification) => {
    setDetailsNotification(notification);
    setDetailsOpen(true);
  }, []);

  // Selection handlers
  const toggleSelect = useCallback((id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    if (selectedIds.size === notifications.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(notifications.map(n => n.notificationId)));
    }
  }, [selectedIds.size, notifications]);

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  // Clear selection when tab or filters change
  const handleTabChange = useCallback((v: string) => {
    setStatusTab(v as StatusTab);
    setTierFilter('all');
    setPage(0);
    setSelectedIds(new Set());
  }, []);

  // Delete handlers
  const handleDeleteSingle = useCallback((id: string) => {
    deleteSingle.mutate(id);
  }, [deleteSingle]);

  const handleDeleteSelected = useCallback(() => {
    setDeleteDialogOpen(true);
  }, []);

  const confirmDeleteSelected = useCallback(() => {
    if (selectedIds.size > 0) {
      deleteMany.mutate({ notificationIds: Array.from(selectedIds) });
      setSelectedIds(new Set());
    }
    setDeleteDialogOpen(false);
  }, [selectedIds, deleteMany]);

  const tierCounts = stats?.byTier ?? {};

  // Determine which level filter options to show based on tab
  const levelOptions = useMemo(() => {
    if (statusTab === 'info') {
      return [
        { value: 'all', label: 'All levels' },
        { value: '2', label: 'System' },
        { value: '1', label: 'Info' },
      ];
    }
    if (statusTab === 'resolved') {
      return [
        { value: 'all', label: 'All levels' },
        { value: '5', label: 'Critical' },
        { value: '4', label: 'High' },
        { value: '3', label: 'Warning' },
      ];
    }
    // active / acknowledged: tier 3+
    return [
      { value: 'all', label: 'All levels' },
      { value: '5', label: 'Critical' },
      { value: '4', label: 'High' },
      { value: '3', label: 'Warning' },
    ];
  }, [statusTab]);

  // Tab-specific bulk action button
  const renderBulkAction = () => {
    switch (statusTab) {
      case 'active':
        return canWrite ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => acknowledgeAll.mutate({ tierMin: ACKNOWLEDGE_MIN_TIER as NotificationTier })}
            disabled={acknowledgeAll.isPending || notifications.length === 0}
          >
            <CheckCircle className="mr-1.5 h-4 w-4" />
            Acknowledge all
          </Button>
        ) : null;
      case 'info':
        return (
          <Button
            variant="outline"
            size="sm"
            onClick={() => markAllRead.mutate({ tierMin: 1 as NotificationTier })}
            disabled={markAllRead.isPending || (stats?.unread ?? 0) === 0}
          >
            <CheckCheck className="mr-1.5 h-4 w-4" />
            Mark all read
          </Button>
        );
      case 'resolved':
        return (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              deleteMany.mutate({ status: 'resolved' });
            }}
            disabled={deleteMany.isPending || notifications.length === 0}
          >
            <Trash2 className="mr-1.5 h-4 w-4" />
            Clear all resolved
          </Button>
        );
      default:
        return null;
    }
  };

  const allSelected = notifications.length > 0 && selectedIds.size === notifications.length;
  const someSelected = selectedIds.size > 0 && selectedIds.size < notifications.length;

  return (
    <div className="space-y-6">
      <PageHeaderLayout
        title="Notifications"
        subtitle={stats ? `${stats.total} active, ${stats.unread} unread` : 'Loading...'}
        showBackButton={false}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={isFetching}
            >
              <RefreshCw className={`mr-1.5 h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            {renderBulkAction()}
          </div>
        }
      />

      {/* Level summary badges */}
      <div className="flex flex-wrap gap-2">
        {([5, 4, 3, 2, 1] as NotificationTier[]).map((tier) => {
          const count = tierCounts[TIER_COLORS[tier].label.toLowerCase()] ?? 0;
          if (count === 0) return null;
          const colors = TIER_COLORS[tier];
          return (
            <Badge
              key={tier}
              variant="outline"
              className={`cursor-pointer ${colors.bg} ${colors.text} ${colors.border}`}
              onClick={() => setTierFilter(String(tier))}
            >
              <span className={`mr-1.5 h-2 w-2 rounded-full ${colors.dot}`} />
              {colors.label}: {count}
            </Badge>
          );
        })}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <Tabs value={statusTab} onValueChange={handleTabChange}>
          <TabsList>
            <TabsTrigger value="active">Active</TabsTrigger>
            <TabsTrigger value="acknowledged">Acknowledged</TabsTrigger>
            <TabsTrigger value="resolved">Resolved</TabsTrigger>
            <TabsTrigger value="info" className="gap-1.5">
              <Info className="h-3.5 w-3.5" />
              Info
            </TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="flex items-center gap-2 ml-auto">
          <Filter className="h-4 w-4 text-muted-foreground" />

          <Select value={tierFilter} onValueChange={(v) => { setTierFilter(v); setPage(0); }}>
            <SelectTrigger className="w-[140px] h-9 text-xs">
              <SelectValue placeholder="All levels" />
            </SelectTrigger>
            <SelectContent>
              {levelOptions.map(opt => (
                <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={sourceFilter} onValueChange={(v) => { setSourceFilter(v); setPage(0); }}>
            <SelectTrigger className="w-[150px] h-9 text-xs">
              <SelectValue placeholder="All sources" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All sources</SelectItem>
              <SelectItem value="hydra-api">hydra-api</SelectItem>
              <SelectItem value="hydra-agent">hydra-agent</SelectItem>
              <SelectItem value="hydra-mcp">hydra-mcp</SelectItem>
              <SelectItem value="system">system</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Selection toolbar */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg border bg-muted/50 px-4 py-2">
          <span className="text-sm font-medium">
            {selectedIds.size} selected
          </span>
          <Button
            variant="destructive"
            size="sm"
            onClick={handleDeleteSelected}
            disabled={deleteMany.isPending}
          >
            <Trash2 className="mr-1.5 h-3.5 w-3.5" />
            Delete selected
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={clearSelection}
          >
            <X className="mr-1.5 h-3.5 w-3.5" />
            Clear
          </Button>
        </div>
      )}

      {/* Notification list */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : notifications.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-16 text-center">
              <CheckCircle className="h-10 w-10 text-green-500/40" />
              <div>
                <p className="text-sm font-medium">All clear</p>
                <p className="text-xs text-muted-foreground">
                  {TAB_EMPTY_MESSAGES[statusTab]}
                  {tierFilter !== 'all' && ' matching your filters'}
                </p>
              </div>
            </div>
          ) : (
            <>
              {/* Select all header */}
              <div className="flex items-center gap-3 border-b px-4 py-2 bg-muted/20">
                <Checkbox
                  checked={allSelected ? true : someSelected ? 'indeterminate' : false}
                  onCheckedChange={toggleSelectAll}
                  aria-label="Select all notifications"
                />
                <span className="text-xs text-muted-foreground">
                  {allSelected ? 'All selected' : `${notifications.length} notification${notifications.length !== 1 ? 's' : ''}`}
                </span>
              </div>

              <div className="divide-y">
                {notifications.map((notification) => (
                  <div key={notification.notificationId} className="flex items-start gap-3 p-3">
                    <Checkbox
                      checked={selectedIds.has(notification.notificationId)}
                      onCheckedChange={() => toggleSelect(notification.notificationId)}
                      className="mt-2"
                      aria-label={`Select ${notification.title}`}
                    />
                    <div className="flex-1 min-w-0">
                      <NotificationItem
                        notification={notification}
                        onMarkRead={(id) => markRead.mutate(id)}
                        onAcknowledge={(id) => acknowledge.mutate(id)}
                        onResolve={(id) => resolve.mutate(id)}
                        onDelete={handleDeleteSingle}
                        onViewDetails={handleViewDetails}
                        canWrite={canWrite}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Showing {page * pageSize + 1}-{Math.min((page + 1) * pageSize, total)} of {total}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= totalPages - 1}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Details modal for tier 4-5 notifications */}
      <NotificationDetailsModal
        notification={detailsNotification}
        open={detailsOpen}
        onOpenChange={setDetailsOpen}
        onAcknowledge={(id) => acknowledge.mutate(id)}
        onResolve={(id) => resolve.mutate(id)}
        onDelete={handleDeleteSingle}
        canWrite={canWrite}
      />

      {/* Delete confirmation dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete notifications</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete {selectedIds.size} notification{selectedIds.size !== 1 ? 's' : ''}? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDeleteSelected}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
