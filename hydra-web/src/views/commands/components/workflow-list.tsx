import { useMemo, useState } from 'react';
import { toast } from 'sonner';
import {
  AlertTriangle,
  GitBranch,
  Loader2,
  Pencil,
  Play,
  Plus,
  Search,
} from 'lucide-react';
import {
  useWorkflows,
  useWorkflow,
  useExecuteWorkflow,
  useCreateWorkflow,
  useUpdateWorkflow,
} from '@/api/workflows';
import type { CreateWorkflowRequest } from '@/types/workflows';
import { getErrorMessage } from '@/lib/api-client';
import { formatRelativeTime } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { WorkflowBuilder } from './workflow-builder/workflow-builder';

// ── Builder mode state ────────────────────────────────────────────────

type BuilderMode =
  | { kind: 'list' }
  | { kind: 'create' }
  | { kind: 'edit'; chainId: string };

// ── Edit wrapper ──────────────────────────────────────────────────────

function EditWorkflowBuilder({
  chainId,
  onSave,
  onCancel,
}: {
  chainId: string;
  onSave: (chainId: string, data: CreateWorkflowRequest) => void;
  onCancel: () => void;
}) {
  const { data: workflow, isLoading, error } = useWorkflow(chainId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !workflow) {
    return (
      <Card className="border-destructive/40">
        <CardContent className="p-8 text-center">
          <AlertTriangle className="mx-auto h-12 w-12 text-destructive" />
          <h3 className="mt-4 text-lg font-semibold">Failed to load workflow</h3>
          <p className="mt-2 text-sm text-muted-foreground">Please try again later</p>
          <Button variant="outline" className="mt-4" onClick={onCancel}>
            Go Back
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <WorkflowBuilder
      initialWorkflow={workflow}
      onSave={(data) => onSave(chainId, data)}
      onCancel={onCancel}
    />
  );
}

// ── Main component ────────────────────────────────────────────────────

export function WorkflowList() {
  const [builderMode, setBuilderMode] = useState<BuilderMode>({ kind: 'list' });
  const [searchQuery, setSearchQuery] = useState('');
  const { data, isLoading, error } = useWorkflows();
  const executeWorkflow = useExecuteWorkflow();
  const createWorkflow = useCreateWorkflow();
  const updateWorkflow = useUpdateWorkflow();

  const filteredWorkflows = useMemo(() => {
    const items = data?.items ?? [];
    if (!searchQuery.trim()) return items;
    const query = searchQuery.toLowerCase();
    return items.filter(
      (w) =>
        w.name.toLowerCase().includes(query) ||
        w.description?.toLowerCase().includes(query)
    );
  }, [data?.items, searchQuery]);

  const handleExecute = async (chainId: string, name: string) => {
    try {
      await executeWorkflow.mutateAsync({ chainId });
      toast.success(`Workflow "${name}" started`);
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, 'Failed to execute workflow'));
    }
  };

  const handleCreate = async (data: CreateWorkflowRequest) => {
    try {
      await createWorkflow.mutateAsync(data);
      toast.success(`Workflow "${data.name}" created`);
      setBuilderMode({ kind: 'list' });
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, 'Failed to create workflow'));
    }
  };

  const handleUpdate = async (chainId: string, data: CreateWorkflowRequest) => {
    try {
      await updateWorkflow.mutateAsync({ chainId, data });
      toast.success(`Workflow "${data.name}" updated`);
      setBuilderMode({ kind: 'list' });
    } catch (err: unknown) {
      toast.error(getErrorMessage(err, 'Failed to update workflow'));
    }
  };

  // ── Builder views ───────────────────────────────────────────────────

  if (builderMode.kind === 'create') {
    return (
      <WorkflowBuilder
        onSave={handleCreate}
        onCancel={() => setBuilderMode({ kind: 'list' })}
      />
    );
  }

  if (builderMode.kind === 'edit') {
    return (
      <EditWorkflowBuilder
        chainId={builderMode.chainId}
        onSave={handleUpdate}
        onCancel={() => setBuilderMode({ kind: 'list' })}
      />
    );
  }

  // ── List view ───────────────────────────────────────────────────────

  if (error) {
    return (
      <Card className="border-destructive/40">
        <CardContent className="p-8 text-center">
          <AlertTriangle className="mx-auto h-12 w-12 text-destructive" />
          <h3 className="mt-4 text-lg font-semibold">Failed to load workflows</h3>
          <p className="mt-2 text-sm text-muted-foreground">Please try again later</p>
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Skeleton className="h-10 w-full max-w-sm" />
          <Skeleton className="h-9 w-32" />
        </div>
        <Card>
          <Table>
            <TableHeader>
              <TableRow className="border-border hover:bg-transparent">
                <TableHead className="text-muted-foreground">Name</TableHead>
                <TableHead className="text-muted-foreground">Description</TableHead>
                <TableHead className="text-muted-foreground">Steps</TableHead>
                <TableHead className="text-muted-foreground">Last Updated</TableHead>
                <TableHead className="w-[140px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {[1, 2, 3, 4, 5].map((i) => (
                <TableRow key={i} className="border-border">
                  <TableCell><Skeleton className="h-4 w-32" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-48" /></TableCell>
                  <TableCell><Skeleton className="h-6 w-10 rounded-md" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-24" /></TableCell>
                  <TableCell><Skeleton className="h-8 w-24 rounded-md" /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Toolbar: search + new button */}
      <div className="flex items-center justify-between gap-4">
        <div className="relative max-w-sm flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search workflows..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Button
          size="sm"
          className="gap-1.5"
          onClick={() => setBuilderMode({ kind: 'create' })}
        >
          <Plus className="h-4 w-4" />
          New Workflow
        </Button>
      </div>

      {/* Table */}
      {filteredWorkflows.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center">
            <GitBranch className="mx-auto h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">
              {searchQuery ? 'No matching workflows' : 'No workflows defined yet'}
            </h3>
            <p className="mt-2 text-sm text-muted-foreground">
              {searchQuery
                ? 'Try adjusting your search query'
                : 'Create a workflow to orchestrate multi-step command sequences.'}
            </p>
            {!searchQuery && (
              <Button
                className="mt-4 gap-1.5"
                onClick={() => setBuilderMode({ kind: 'create' })}
              >
                <Plus className="h-4 w-4" />
                Create Workflow
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow className="border-border hover:bg-transparent">
                <TableHead className="text-muted-foreground">Name</TableHead>
                <TableHead className="text-muted-foreground">Description</TableHead>
                <TableHead className="text-muted-foreground">Steps</TableHead>
                <TableHead className="text-muted-foreground">Last Updated</TableHead>
                <TableHead className="w-[140px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredWorkflows.map((workflow) => (
                <TableRow key={workflow.chainId} className="border-border">
                  <TableCell className="font-medium">{workflow.name}</TableCell>
                  <TableCell className="text-sm text-muted-foreground max-w-xs truncate">
                    {workflow.description ?? '--'}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{workflow.stepCount}</Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {workflow.updatedAt
                      ? formatRelativeTime(workflow.updatedAt)
                      : formatRelativeTime(workflow.createdAt)}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          setBuilderMode({
                            kind: 'edit',
                            chainId: workflow.chainId,
                          })
                        }
                      >
                        <Pencil className="h-4 w-4" />
                        <span className="ml-1.5">Edit</span>
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          handleExecute(workflow.chainId, workflow.name)
                        }
                        disabled={executeWorkflow.isPending}
                      >
                        {executeWorkflow.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Play className="h-4 w-4" />
                        )}
                        <span className="ml-1.5">Run</span>
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}
