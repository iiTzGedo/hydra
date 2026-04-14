import { useParams } from 'next/navigation';
import { toast } from 'sonner';
import {
  Terminal,
  Clock,
  Server,
  Boxes,
  AlertTriangle,
  XCircle,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { useState } from 'react';
import { useDocumentTitle } from '@/hooks/use-document-title';
import { useCommand, useCancelCommand, useConfirmCommand } from '@/api/commands';
import type { DangerLevel } from '@/api/commands';
import { getErrorMessage } from '@/lib/api-client';
import { ControlConfirmationDialog } from '@/components/commands/control-confirmation-dialog';
import { PageHeaderLayout } from '@/components/layout/page-header-layout';
import { CommandStatusBadge } from '@/components/commands/command-status-badge';
import { CommandOutput } from '@/components/commands/command-output';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';

export default function CommandDetailPage() {
  const { commandId } = useParams<{ commandId: string }>()!
  const { data: command, isLoading, error } = useCommand(commandId);
  const cancelCommand = useCancelCommand();
  const confirmCommand = useConfirmCommand();
  const [paramsExpanded, setParamsExpanded] = useState(false);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);

  useDocumentTitle(command ? `Command: ${command.action}` : 'Command Details');

  const handleCancel = async () => {
    if (!commandId) return;
    try {
      await cancelCommand.mutateAsync(commandId);
      toast.success('Command cancelled');
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, 'Failed to cancel command'));
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeaderLayout isLoading />
        <div className="space-y-4">
          <Skeleton className="h-32 rounded-lg" />
          <Skeleton className="h-64 rounded-lg" />
        </div>
      </div>
    );
  }

  if (error || !command) {
    return (
      <div className="space-y-6">
        <PageHeaderLayout
          title="Command Not Found"
          subtitle={`Command "${commandId}" could not be found`}
        />
        <Card>
          <CardContent className="p-8 text-center">
            <Terminal className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">Command not found</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              The requested command could not be loaded
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const canCancel = ['queued', 'pending', 'pending_confirmation'].includes(command.status);
  const isPendingConfirmation = command.status === 'pending_confirmation';
  const hasParams = command.parameters && Object.keys(command.parameters).length > 0;
  const hasResult = command.result?.output || command.result?.error;
  const hasError = command.error;

  const handleConfirm = async () => {
    if (!commandId) return;
    try {
      await confirmCommand.mutateAsync(commandId);
      toast.success('Command confirmed and queued');
      setShowConfirmDialog(false);
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, 'Failed to confirm command'));
    }
  };

  return (
    <div className="space-y-6">
      <PageHeaderLayout
        title={command.action}
        subtitle={`Command ${command.commandId}`}
        actions={
          (canCancel || isPendingConfirmation) ? (
            <div className="flex items-center gap-2">
              {isPendingConfirmation && (
                <Button
                  size="sm"
                  onClick={() => setShowConfirmDialog(true)}
                  disabled={confirmCommand.isPending}
                >
                  {confirmCommand.isPending ? 'Confirming...' : 'Confirm'}
                </Button>
              )}
              {canCancel && (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleCancel}
                  disabled={cancelCommand.isPending}
                >
                  <XCircle className="h-4 w-4 mr-1.5" />
                  {cancelCommand.isPending ? 'Cancelling...' : 'Cancel'}
                </Button>
              )}
            </div>
          ) : undefined
        }
      />

      {/* Status badge - large */}
      <div className="flex items-center gap-3">
        <CommandStatusBadge status={command.status} className="text-sm px-3 py-1" />
        {['queued', 'executing', 'pending_confirmation'].includes(command.status) && (
          <span className="text-xs text-muted-foreground animate-pulse">Auto-refreshing...</span>
        )}
      </div>

      {/* Pending confirmation banner */}
      {isPendingConfirmation && (
        <Card className="border-warning/40 bg-warning/5">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-warning mt-0.5 shrink-0" />
              <div className="flex-1 space-y-1">
                <p className="text-sm font-medium">Awaiting confirmation</p>
                {command.confirmationMessage && (
                  <p className="text-sm text-muted-foreground">{command.confirmationMessage}</p>
                )}
                {command.confirmationExpiresAt && (
                  <p className="text-xs text-muted-foreground">
                    Expires: {new Date(command.confirmationExpiresAt).toLocaleString()}
                  </p>
                )}
              </div>
              <Button size="sm" onClick={() => setShowConfirmDialog(true)}>
                Confirm
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Confirmation dialog */}
      {isPendingConfirmation && (
        <ControlConfirmationDialog
          open={showConfirmDialog}
          onOpenChange={setShowConfirmDialog}
          dangerLevel={(command.dangerLevel as DangerLevel) ?? 'medium'}
          resourceName={command.target.nodeId}
          actionLabel={command.action}
          confirmationMessage={command.confirmationMessage}
          onConfirm={handleConfirm}
          isPending={confirmCommand.isPending}
        />
      )}

      {/* Info grid */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Details</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <InfoItem label="Command ID" value={command.commandId} mono />
            <InfoItem
              label="Registry ID"
              value={command.registryId ?? '-'}
              mono
            />
            <InfoItem
              label="Target Node"
              value={command.target.nodeId}
              icon={<Server className="h-4 w-4 text-muted-foreground" />}
              mono
            />
            {command.target.serviceId && (
              <InfoItem
                label="Target Service"
                value={command.target.serviceId}
                icon={<Boxes className="h-4 w-4 text-muted-foreground" />}
                mono
              />
            )}
            <InfoItem label="Type" value={command.type} />
            <InfoItem
              label="Execution Method"
              value={command.executionMethod ?? '-'}
            />
            <InfoItem
              label="Timeout"
              value={`${command.timeoutSeconds}s`}
            />
            <InfoItem
              label="Retry Count"
              value={String(command.retryCount)}
            />
            {command.queuePosition != null && (
              <InfoItem
                label="Queue Position"
                value={String(command.queuePosition)}
              />
            )}

            <Separator className="sm:col-span-2 lg:col-span-3" />

            <InfoItem
              label="Created"
              value={new Date(command.createdAt).toLocaleString()}
              icon={<Clock className="h-4 w-4 text-muted-foreground" />}
            />
            {command.queuedAt && (
              <InfoItem
                label="Queued"
                value={new Date(command.queuedAt).toLocaleString()}
              />
            )}
            {command.startedAt && (
              <InfoItem
                label="Started"
                value={new Date(command.startedAt).toLocaleString()}
              />
            )}
            {command.completedAt && (
              <InfoItem
                label="Completed"
                value={new Date(command.completedAt).toLocaleString()}
              />
            )}
            {command.cancelledAt && (
              <InfoItem
                label="Cancelled"
                value={new Date(command.cancelledAt).toLocaleString()}
              />
            )}
            {command.cancelledBy && (
              <InfoItem label="Cancelled By" value={command.cancelledBy} />
            )}
            {command.requestedBy && (
              <InfoItem
                label="Requested By"
                value={
                  command.requestedBy.userId
                    ? `${command.requestedBy.userId} (${command.requestedBy.source})`
                    : command.requestedBy.source
                }
              />
            )}
          </div>
        </CardContent>
      </Card>

      {/* Parameters */}
      {hasParams && (
        <Card>
          <CardHeader
            className="cursor-pointer"
            onClick={() => setParamsExpanded(!paramsExpanded)}
          >
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Parameters</CardTitle>
              {paramsExpanded ? (
                <ChevronUp className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              )}
            </div>
          </CardHeader>
          {paramsExpanded && (
            <CardContent>
              <pre className="bg-zinc-950 text-zinc-100 rounded-lg p-4 font-mono text-sm overflow-auto max-h-64">
                {JSON.stringify(command.parameters, null, 2)}
              </pre>
            </CardContent>
          )}
        </Card>
      )}

      {/* Result */}
      {hasResult && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Result</CardTitle>
              {command.result?.success !== undefined && (
                <CommandStatusBadge
                  status={command.result.success ? 'completed' : 'failed'}
                />
              )}
            </div>
            {command.result?.exitCode != null && (
              <p className="text-sm text-muted-foreground">
                Exit code: {command.result.exitCode}
              </p>
            )}
          </CardHeader>
          <CardContent>
            <CommandOutput
              output={command.result?.output}
              error={command.result?.error}
            />
          </CardContent>
        </Card>
      )}

      {/* Error */}
      {hasError && (
        <Card className="border-destructive/40">
          <CardHeader>
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              <CardTitle className="text-base text-destructive">Error</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-sm font-medium">{command.error!.message}</p>
            {command.error!.code && (
              <p className="text-xs text-muted-foreground font-mono">
                Code: {command.error!.code}
              </p>
            )}
            {command.error!.details && (
              <pre className="bg-zinc-950 text-red-400 rounded-lg p-4 font-mono text-sm overflow-auto max-h-48">
                {JSON.stringify(command.error!.details, null, 2)}
              </pre>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── Info Item helper ──────────────────────────────────────────────────────
function InfoItem({
  label,
  value,
  icon,
  mono,
}: {
  label: string;
  value: string;
  icon?: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="space-y-1">
      <p className="text-xs text-muted-foreground">{label}</p>
      <div className="flex items-center gap-1.5">
        {icon}
        <p className={`text-sm ${mono ? 'font-mono' : ''} break-all`}>{value}</p>
      </div>
    </div>
  );
}
