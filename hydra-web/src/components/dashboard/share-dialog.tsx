/**
 * Share Dialog for managing dashboard board sharing settings.
 *
 * Shows current shares, allows selecting roles and entering user IDs
 * to share with, and provides a revoke-all action.
 */

import { useCallback, useState } from 'react';
import { Share2, ShieldAlert, UserPlus, X } from 'lucide-react';
import { toast } from 'sonner';
import {
  useDashboardShares,
  useRevokeDashboardShares,
  useShareDashboard,
} from '@/api/dashboards';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { getErrorMessage } from '@/lib/api-client';

const AVAILABLE_ROLES = ['admin', 'operator', 'viewer', 'family'] as const;

interface ShareDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  boardId: string;
  boardName: string;
}

export function ShareDialog({ open, onOpenChange, boardId, boardName }: ShareDialogProps) {
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const [userInput, setUserInput] = useState('');
  const [userIds, setUserIds] = useState<string[]>([]);

  const sharesQuery = useDashboardShares(boardId);
  const shareMutation = useShareDashboard(boardId);
  const revokeMutation = useRevokeDashboardShares(boardId);

  const currentShares = sharesQuery.data;
  const isLoading = sharesQuery.isLoading;
  const isMutating = shareMutation.isPending || revokeMutation.isPending;

  const handleToggleRole = useCallback((role: string) => {
    setSelectedRoles((prev) =>
      prev.includes(role)
        ? prev.filter((r) => r !== role)
        : [...prev, role]
    );
  }, []);

  const handleAddUser = useCallback(() => {
    const trimmed = userInput.trim();
    if (trimmed && !userIds.includes(trimmed)) {
      setUserIds((prev) => [...prev, trimmed]);
      setUserInput('');
    }
  }, [userInput, userIds]);

  const handleRemoveUser = useCallback((userId: string) => {
    setUserIds((prev) => prev.filter((id) => id !== userId));
  }, []);

  const handleShare = useCallback(async () => {
    try {
      // Use the existing share endpoint with visibility + allowedUsers
      await shareMutation.mutateAsync({
        visibility: 'shared',
        allowedUsers: userIds,
      });
      toast.success('Dashboard shared successfully');
      sharesQuery.refetch();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to share dashboard'));
    }
  }, [shareMutation, userIds, sharesQuery]);

  const handleRevokeAll = useCallback(async () => {
    try {
      await revokeMutation.mutateAsync();
      setSelectedRoles([]);
      setUserIds([]);
      toast.success('All shares revoked');
      sharesQuery.refetch();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to revoke shares'));
    }
  }, [revokeMutation, sharesQuery]);

  const hasCurrentShares =
    (currentShares?.roles?.length ?? 0) > 0 || (currentShares?.users?.length ?? 0) > 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px] bg-card border-border">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-foreground">
            <Share2 className="h-5 w-5 text-primary" />
            Share Dashboard
          </DialogTitle>
          <DialogDescription>
            Manage sharing settings for "{boardName}".
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner />
          </div>
        ) : (
          <div className="space-y-5">
            {/* Current shares */}
            {hasCurrentShares && (
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground uppercase tracking-wide">
                  Current shares
                </Label>
                <div className="rounded-lg border border-border p-3 space-y-2">
                  {(currentShares?.roles?.length ?? 0) > 0 && (
                    <div className="flex items-center gap-2 flex-wrap">
                      <ShieldAlert className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">Roles:</span>
                      {currentShares?.roles.map((role) => (
                        <Badge key={role} variant="secondary" className="text-[10px]">
                          {role}
                        </Badge>
                      ))}
                    </div>
                  )}
                  {(currentShares?.users?.length ?? 0) > 0 && (
                    <div className="flex items-center gap-2 flex-wrap">
                      <UserPlus className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">Users:</span>
                      {currentShares?.users.map((userId) => (
                        <Badge key={userId} variant="secondary" className="text-[10px]">
                          {userId}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Role selection */}
            <div className="space-y-2">
              <Label>Share with roles</Label>
              <div className="flex flex-wrap gap-2">
                {AVAILABLE_ROLES.map((role) => (
                  <Button
                    key={role}
                    variant={selectedRoles.includes(role) ? 'default' : 'outline'}
                    size="sm"
                    className="h-7 text-xs capitalize"
                    onClick={() => handleToggleRole(role)}
                    disabled={isMutating}
                  >
                    {role}
                  </Button>
                ))}
              </div>
            </div>

            {/* User IDs */}
            <div className="space-y-2">
              <Label>Share with specific users</Label>
              <div className="flex gap-2">
                <Input
                  placeholder="Enter user ID..."
                  value={userInput}
                  onChange={(e) => setUserInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleAddUser();
                    }
                  }}
                  disabled={isMutating}
                  className="bg-muted/50 border-border"
                />
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleAddUser}
                  disabled={isMutating || !userInput.trim()}
                >
                  Add
                </Button>
              </div>
              {userIds.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {userIds.map((userId) => (
                    <Badge
                      key={userId}
                      variant="secondary"
                      className="text-xs gap-1 pr-1"
                    >
                      {userId}
                      <button
                        type="button"
                        onClick={() => handleRemoveUser(userId)}
                        className="hover:text-destructive transition-colors"
                        disabled={isMutating}
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        <DialogFooter className="flex-col sm:flex-row gap-2">
          {hasCurrentShares && (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => void handleRevokeAll()}
              disabled={isMutating}
            >
              {revokeMutation.isPending ? (
                <LoadingSpinner size="sm" className="mr-2 text-current" />
              ) : null}
              Revoke All
            </Button>
          )}
          <div className="flex-1" />
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isMutating}
          >
            Cancel
          </Button>
          <Button
            onClick={() => void handleShare()}
            disabled={isMutating || (selectedRoles.length === 0 && userIds.length === 0)}
          >
            {shareMutation.isPending ? (
              <LoadingSpinner size="sm" className="mr-2 text-current" />
            ) : null}
            Share
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
