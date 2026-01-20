import { Bot, Plus } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { LLMProvider } from '@/types/mcp';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface LLMConfigModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  llmProviders: LLMProvider[];
  activeLLMProviderId: string | null;
  onSetActiveProvider: (providerId: string) => void;
  onUpdateProvider: (providerId: string, updates: { apiKey?: string }) => void;
}

export function LLMConfigModal({
  open,
  onOpenChange,
  llmProviders,
  activeLLMProviderId,
  onSetActiveProvider,
  onUpdateProvider,
}: LLMConfigModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-card border-border text-foreground max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>LLM Providers</DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Configure language models for the chat interface.
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="flex-1 -mx-6 px-6">
          <div className="space-y-4 py-4">
            {llmProviders.map((llm) => (
              <Card key={llm.id} className="bg-muted/60 border-border">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-card">
                        <Bot className="h-5 w-5 text-amber-500" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="font-medium text-foreground">{llm.name}</h4>
                          {activeLLMProviderId === llm.id && (
                            <Badge className="bg-blue-500/10 text-blue-400 border-blue-500/20">
                              Active
                            </Badge>
                          )}
                          <Badge
                            variant="outline"
                            className={cn(
                              llm.isConfigured
                                ? 'border-emerald-500/30 text-emerald-400'
                                : 'border-border text-muted-foreground'
                            )}
                          >
                            {llm.isConfigured ? 'Configured' : 'Not configured'}
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {llm.type} / {llm.model}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {!llm.isConfigured && llm.type !== 'ollama' && (
                        <Input
                          type="password"
                          placeholder="API Key"
                          className="h-8 w-32 text-xs bg-card border-border text-foreground"
                          onChange={(e) =>
                            onUpdateProvider(llm.id, { apiKey: e.target.value })
                          }
                        />
                      )}
                      {llm.isConfigured && activeLLMProviderId !== llm.id && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => onSetActiveProvider(llm.id)}
                          className="border-border text-foreground hover:bg-muted bg-transparent"
                        >
                          Set Active
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </ScrollArea>
        <DialogFooter className="border-t border-border pt-4">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="border-border text-foreground hover:bg-muted bg-transparent"
          >
            Close
          </Button>
          <Button className="bg-blue-600 hover:bg-blue-700 text-white">
            <Plus className="h-4 w-4 mr-2" />
            Add Provider
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
