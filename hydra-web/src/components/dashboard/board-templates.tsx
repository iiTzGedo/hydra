/**
 * Board Templates dialog for browsing and instantiating dashboard templates.
 *
 * Displays a searchable gallery of template cards with name, description,
 * widget count, and tags. Users can clone a template into a new personal board.
 */

import { useMemo, useState } from 'react';
import { LayoutTemplate, Search } from 'lucide-react';
import { toast } from 'sonner';
import { useDashboardTemplates } from '@/api/dashboards';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { ScrollArea } from '@/components/ui/scroll-area';
import { apiClient, getErrorMessage } from '@/lib/api-client';

interface BoardTemplatesProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onTemplateUsed?: (boardId: string) => void;
}

export function BoardTemplates({ open, onOpenChange, onTemplateUsed }: BoardTemplatesProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [instantiatingId, setInstantiatingId] = useState<string | null>(null);

  const templatesQuery = useDashboardTemplates({ limit: 50 });
  const templateItems = templatesQuery.data?.items;

  const filteredTemplates = useMemo(() => {
    const templates = templateItems ?? [];
    if (!searchQuery.trim()) return templates;
    const q = searchQuery.toLowerCase();
    return templates.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        (t.description ?? '').toLowerCase().includes(q) ||
        t.tags.some((tag) => tag.toLowerCase().includes(q))
    );
  }, [templateItems, searchQuery]);

  const handleUseTemplate = async (templateId: string) => {
    setInstantiatingId(templateId);
    try {
      const response = await apiClient.post(
        `/dashboards/templates/${templateId}/instantiate`,
        {}
      );
      const newBoardId = response.data?.data?.boardId;
      toast.success('Dashboard created from template');
      onOpenChange(false);
      if (newBoardId && onTemplateUsed) {
        onTemplateUsed(newBoardId);
      }
    } catch (error) {
      toast.error(getErrorMessage(error, 'Failed to create dashboard from template'));
    } finally {
      setInstantiatingId(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[700px] max-h-[80vh] flex flex-col bg-card border-border">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-foreground">
            <LayoutTemplate className="h-5 w-5 text-primary" />
            Dashboard Templates
          </DialogTitle>
          <DialogDescription>
            Choose a template to create a new dashboard board with pre-configured widgets.
          </DialogDescription>
        </DialogHeader>

        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search templates..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 bg-muted/50 border-border"
          />
        </div>

        {templatesQuery.isLoading ? (
          <div className="flex items-center justify-center py-12">
            <LoadingSpinner />
          </div>
        ) : templatesQuery.isError ? (
          <div className="text-center py-12 text-sm text-muted-foreground">
            Failed to load templates.
          </div>
        ) : filteredTemplates.length === 0 ? (
          <div className="text-center py-12 text-sm text-muted-foreground">
            {searchQuery.trim() ? 'No templates match your search.' : 'No templates available.'}
          </div>
        ) : (
          <ScrollArea className="flex-1 -mx-1 max-h-[500px]">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 px-1 pb-1">
              {filteredTemplates.map((template) => (
                <div
                  key={template.templateId}
                  className="flex flex-col gap-2 rounded-lg border border-border p-4 hover:border-primary/50 hover:bg-muted/30 transition-colors"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <h4 className="text-sm font-medium text-foreground truncate">
                        {template.name}
                      </h4>
                      {template.description && (
                        <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
                          {template.description}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant="secondary" className="text-[10px]">
                      {template.widgetCount} widget{template.widgetCount !== 1 ? 's' : ''}
                    </Badge>
                    {template.tags.slice(0, 3).map((tag) => (
                      <Badge key={tag} variant="outline" className="text-[10px]">
                        {tag}
                      </Badge>
                    ))}
                  </div>

                  <Button
                    size="sm"
                    variant="outline"
                    className="mt-1 w-full"
                    disabled={instantiatingId === template.templateId}
                    onClick={() => void handleUseTemplate(template.templateId)}
                  >
                    {instantiatingId === template.templateId ? (
                      <LoadingSpinner size="sm" className="mr-2 text-current" />
                    ) : null}
                    Use Template
                  </Button>
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  );
}
