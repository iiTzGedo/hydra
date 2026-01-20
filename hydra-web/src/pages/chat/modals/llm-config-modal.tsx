import { useState } from 'react';
import { Bot, Plus, Trash2, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { LLMProviderCreate, LLMProviderResponse, LLMProviderType } from '@/api/ai';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
  llmProviders: LLMProviderResponse[];
  activeLLMProviderId: string | null;
  onSetActiveProvider: (providerId: string) => void;
  onUpdateProvider: (providerId: string, updates: { apiKey?: string }) => void;
  onCreateProvider: (data: LLMProviderCreate) => void;
  onDeleteProvider: (providerId: string) => void;
  onValidateProvider: (providerId: string) => void;
}

export function LLMConfigModal({
  open,
  onOpenChange,
  llmProviders,
  activeLLMProviderId,
  onSetActiveProvider,
  onUpdateProvider,
  onCreateProvider,
  onDeleteProvider,
  onValidateProvider,
}: LLMConfigModalProps) {
  const [showCreate, setShowCreate] = useState(false);
  const [draftKeys, setDraftKeys] = useState<Record<string, string>>({});
  const [newProvider, setNewProvider] = useState<LLMProviderCreate>({
    name: '',
    type: 'anthropic',
    model: '',
    apiKey: '',
    baseUrl: '',
    isDefault: false,
  });

  const handleSaveApiKey = (providerId: string) => {
    const key = draftKeys[providerId];
    if (!key) return;
    onUpdateProvider(providerId, { apiKey: key });
    setDraftKeys((prev) => ({ ...prev, [providerId]: '' }));
  };

  const handleCreateProvider = () => {
    if (!newProvider.name.trim() || !newProvider.model.trim()) {
      return;
    }

    onCreateProvider({
      ...newProvider,
      name: newProvider.name.trim(),
      model: newProvider.model.trim(),
      apiKey: newProvider.apiKey?.trim() || undefined,
      baseUrl: newProvider.baseUrl?.trim() || undefined,
    });

    setNewProvider({
      name: '',
      type: 'anthropic',
      model: '',
      apiKey: '',
      baseUrl: '',
      isDefault: false,
    });
    setShowCreate(false);
  };

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
              <Card key={llm.providerId} className="bg-muted/60 border-border">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-card">
                        <Bot className="h-5 w-5 text-amber-500" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="font-medium text-foreground">{llm.name}</h4>
                          {activeLLMProviderId === llm.providerId && (
                            <Badge className="bg-blue-500/10 text-blue-400 border-blue-500/20">
                              Active
                            </Badge>
                          )}
                          <Badge
                            variant="outline"
                            className={cn(
                              llm.apiKeySet || llm.type === 'ollama'
                                ? 'border-emerald-500/30 text-emerald-400'
                                : 'border-border text-muted-foreground'
                            )}
                          >
                            {llm.apiKeySet || llm.type === 'ollama' ? 'Configured' : 'Not configured'}
                          </Badge>
                          {llm.isValid === false && (
                            <Badge variant="outline" className="border-red-500/30 text-red-400">
                              Invalid
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {llm.type} / {llm.model}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {!llm.apiKeySet && llm.type !== 'ollama' && (
                        <div className="flex items-center gap-2">
                          <Input
                            type="password"
                            placeholder="API Key"
                            className="h-8 w-32 text-xs bg-card border-border text-foreground"
                            value={draftKeys[llm.providerId] || ''}
                            onChange={(e) =>
                              setDraftKeys((prev) => ({
                                ...prev,
                                [llm.providerId]: e.target.value,
                              }))
                            }
                            onKeyDown={(e) =>
                              e.key === 'Enter' && handleSaveApiKey(llm.providerId)
                            }
                          />
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleSaveApiKey(llm.providerId)}
                            className="border-border text-foreground hover:bg-muted bg-transparent"
                          >
                            Save
                          </Button>
                        </div>
                      )}
                      {(llm.apiKeySet || llm.type === 'ollama') &&
                        activeLLMProviderId !== llm.providerId && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => onSetActiveProvider(llm.providerId)}
                          className="border-border text-foreground hover:bg-muted bg-transparent"
                        >
                          Set Active
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onValidateProvider(llm.providerId)}
                        className="h-8 w-8 text-muted-foreground hover:text-foreground"
                        title="Validate provider"
                      >
                        <Check className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onDeleteProvider(llm.providerId)}
                        className="h-8 w-8 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                        title="Remove provider"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </ScrollArea>
        {showCreate && (
          <div className="border-t border-border px-6 py-4 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Name</Label>
                <Input
                  value={newProvider.name}
                  onChange={(e) => setNewProvider({ ...newProvider, name: e.target.value })}
                  placeholder="Provider name"
                  className="h-8 text-xs bg-card border-border text-foreground"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Type</Label>
                <Select
                  value={newProvider.type}
                  onValueChange={(value) =>
                    setNewProvider({ ...newProvider, type: value as LLMProviderType })
                  }
                >
                  <SelectTrigger className="h-8 text-xs bg-card border-border text-foreground">
                    <SelectValue placeholder="Select type" />
                  </SelectTrigger>
                  <SelectContent className="bg-card border-border">
                    <SelectItem value="anthropic">Anthropic</SelectItem>
                    <SelectItem value="openai">OpenAI</SelectItem>
                    <SelectItem value="ollama">Ollama</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Model</Label>
                <Input
                  value={newProvider.model}
                  onChange={(e) => setNewProvider({ ...newProvider, model: e.target.value })}
                  placeholder="Model name"
                  className="h-8 text-xs bg-card border-border text-foreground"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">API Key</Label>
                <Input
                  type="password"
                  value={newProvider.apiKey}
                  onChange={(e) => setNewProvider({ ...newProvider, apiKey: e.target.value })}
                  placeholder="Optional"
                  className="h-8 text-xs bg-card border-border text-foreground"
                />
              </div>
              <div className="col-span-2 space-y-1">
                <Label className="text-xs text-muted-foreground">Base URL</Label>
                <Input
                  value={newProvider.baseUrl}
                  onChange={(e) => setNewProvider({ ...newProvider, baseUrl: e.target.value })}
                  placeholder="Optional for custom/ollama"
                  className="h-8 text-xs bg-card border-border text-foreground"
                />
              </div>
            </div>
          </div>
        )}
        <DialogFooter className="border-t border-border pt-4">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            className="border-border text-foreground hover:bg-muted bg-transparent"
          >
            Close
          </Button>
          {showCreate ? (
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                onClick={() => setShowCreate(false)}
                className="border-border text-foreground hover:bg-muted bg-transparent"
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreateProvider}
                className="bg-blue-600 hover:bg-blue-700 text-white"
              >
                <Plus className="h-4 w-4 mr-2" />
                Save Provider
              </Button>
            </div>
          ) : (
            <Button
              className="bg-blue-600 hover:bg-blue-700 text-white"
              onClick={() => setShowCreate(true)}
            >
              <Plus className="h-4 w-4 mr-2" />
              Add Provider
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
