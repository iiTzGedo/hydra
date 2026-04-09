import { useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  Loader2,
  XCircle,
} from 'lucide-react';
import { useCancelInstallation, useInstallation } from '@/api/discovery';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import type { InstallationStatus } from '@/types/discovery';

interface InstallProgressProps {
  installationId: string;
}

const PHASE_STEPS: Array<{
  phase: InstallationStatus;
  label: string;
}> = [
  { phase: 'connecting', label: 'Connecting' },
  { phase: 'transferring', label: 'Transferring' },
  { phase: 'configuring', label: 'Configuring' },
  { phase: 'registering', label: 'Registering' },
  { phase: 'running', label: 'Running' },
  { phase: 'completed', label: 'Completed' },
];

const ACTIVE_STATUSES = new Set<string>([
  'pending',
  'connecting',
  'transferring',
  'configuring',
  'registering',
  'running',
]);

function phaseIndex(phase: InstallationStatus): number {
  const idx = PHASE_STEPS.findIndex((step) => step.phase === phase);
  return idx >= 0 ? idx : -1;
}

function StepIcon({ step, currentPhase, isFailed }: {
  step: { phase: InstallationStatus; label: string };
  currentPhase: InstallationStatus;
  isFailed: boolean;
}) {
  const stepIdx = phaseIndex(step.phase);
  const currentIdx = phaseIndex(currentPhase);

  if (isFailed && step.phase === currentPhase) {
    return <XCircle className="h-5 w-5 text-destructive" />;
  }
  if (stepIdx < currentIdx || currentPhase === 'completed') {
    return <CheckCircle2 className="h-5 w-5 text-success" />;
  }
  if (stepIdx === currentIdx) {
    return <Loader2 className="h-5 w-5 animate-spin text-primary" />;
  }
  return <Circle className="h-5 w-5 text-muted-foreground/40" />;
}

export function InstallProgress({ installationId }: InstallProgressProps) {
  const { data: installation, isLoading } = useInstallation(installationId);
  const cancelInstallation = useCancelInstallation();
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    if (!installation) return;
    if (!ACTIVE_STATUSES.has(installation.status)) return;

    const startedAt = new Date(installation.createdAt).getTime();
    const interval = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);

    return () => clearInterval(interval);
  }, [installation]);

  if (isLoading || !installation) {
    return (
      <Card>
        <CardContent className="flex min-h-[200px] items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  const isActive = ACTIVE_STATUSES.has(installation.status);
  const isFailed = installation.status === 'failed';
  const isCancelled = installation.status === 'cancelled';
  const isCompleted = installation.status === 'completed';

  const formatElapsed = () => {
    const minutes = Math.floor(elapsedSeconds / 60);
    const seconds = elapsedSeconds % 60;
    return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">
              {installation.targetHostname || installation.targetIp}
            </CardTitle>
            <CardDescription>
              {installation.installationId}
              {installation.discoveryId ? ` from ${installation.discoveryId}` : ''}
            </CardDescription>
          </div>
          <Badge
            variant="outline"
            className={
              isCompleted
                ? 'border-transparent bg-success/10 text-success'
                : isFailed
                  ? 'border-transparent bg-destructive/10 text-destructive'
                  : isCancelled
                    ? 'border-transparent bg-muted text-muted-foreground'
                    : 'border-transparent bg-primary/10 text-primary'
            }
          >
            {installation.status}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Progress bar */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">
              {installation.progress.message || installation.progress.phase}
            </span>
            <span className="font-medium">
              {installation.progress.percentComplete}%
            </span>
          </div>
          <Progress value={installation.progress.percentComplete} />
        </div>

        {/* Phase stepper */}
        <div className="grid grid-cols-6 gap-1">
          {PHASE_STEPS.map((step) => (
            <div key={step.phase} className="flex flex-col items-center gap-1">
              <StepIcon
                step={step}
                currentPhase={installation.progress.phase}
                isFailed={isFailed}
              />
              <span className="text-[10px] text-muted-foreground text-center leading-tight">
                {step.label}
              </span>
            </div>
          ))}
        </div>

        {/* Elapsed time */}
        {isActive && (
          <div className="text-sm text-muted-foreground">
            Elapsed: {formatElapsed()}
          </div>
        )}

        {/* Error display */}
        {isFailed && installation.error && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
              <p className="text-sm text-destructive">{installation.error}</p>
            </div>
          </div>
        )}

        {/* Completed */}
        {isCompleted && (
          <div className="rounded-lg border border-success/40 bg-success/5 p-3 text-sm text-success">
            Agent installation completed successfully.
            {installation.nodeId && (
              <span className="ml-1 font-medium">Node: {installation.nodeId}</span>
            )}
          </div>
        )}

        {/* Cancel button for active installations */}
        {isActive && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => cancelInstallation.mutate(installationId)}
            disabled={cancelInstallation.isPending}
          >
            {cancelInstallation.isPending && (
              <Loader2 className="mr-2 h-3 w-3 animate-spin" />
            )}
            Cancel Installation
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
