import { Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface NewProjectModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectName: string;
  onProjectNameChange: (name: string) => void;
  onCreateProject: () => void;
}

export function NewProjectModal({
  open,
  onOpenChange,
  projectName,
  onProjectNameChange,
  onCreateProject,
}: NewProjectModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-card border-border text-foreground max-w-md">
        <DialogHeader>
          <DialogTitle>Create New Project</DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Projects help you organize your chat conversations by topic or purpose.
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <Label htmlFor="projectName" className="text-foreground">
            Project Name
          </Label>
          <Input
            id="projectName"
            value={projectName}
            onChange={(e) => onProjectNameChange(e.target.value)}
            placeholder="e.g., Production Monitoring"
            className="mt-2 bg-muted border-border text-foreground"
            onKeyDown={(e) => e.key === 'Enter' && onCreateProject()}
          />
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="border-border text-foreground hover:bg-muted bg-transparent"
          >
            Cancel
          </Button>
          <Button
            onClick={onCreateProject}
            disabled={!projectName.trim()}
            className="bg-blue-600 hover:bg-blue-700 text-white"
          >
            <Check className="h-4 w-4 mr-2" />
            Create Project
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
