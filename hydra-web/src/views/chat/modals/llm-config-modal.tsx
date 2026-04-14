import { useState, useEffect } from 'react';
import { Bot, Plus, Trash2, Check, Loader2, Eye, Wrench, Brain, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { LLMProviderCreate, LLMProviderResponse, LLMProviderType, LLMModel } from '@/api/ai';
import { useProviderModels, useGlobalKeys } from '@/api/ai';
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

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

const PROVIDER_OPTIONS: { value: LLMProviderType; label: string; requiresApiKey: boolean }[] = [
  { value: 'anthropic', label: 'Anthropic', requiresApiKey: true },
  { value: 'openai', label: 'OpenAI', requiresApiKey: true },
  { value: 'openrouter', label: 'OpenRouter', requiresApiKey: true },
  { value: 'ollama', label: 'Ollama', requiresApiKey: false },
];

// Name validation: letters only at start, max 2 hyphen-separated segments
// Valid examples: my-config, anthropic-claude-1
// Invalid: my-config-test-here (too many segments)
const NAME_PATTERN = /^[a-zA-Z]+(-[a-zA-Z0-9]+){0,2}$/;

function ModelCapabilityBadges({ model }: { model: LLMModel }) {
  return (
    <div className="flex gap-1">
      {model.supportsTools && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger>
              <Badge variant="outline" className="h-5 px-1.5 border-blue-500/30 text-blue-400">
                <Wrench className="h-3 w-3" />
              </Badge>
            </TooltipTrigger>
            <TooltipContent>Supports tool/function calling</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
      {model.supportsVision && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger>
              <Badge variant="outline" className="h-5 px-1.5 border-purple-500/30 text-purple-400">
                <Eye className="h-3 w-3" />
              </Badge>
            </TooltipTrigger>
            <TooltipContent>Supports vision/image input</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
      {model.supportsReasoning && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger>
              <Badge variant="outline" className="h-5 px-1.5 border-amber-500/30 text-amber-400">
                <Brain className="h-3 w-3" />
              </Badge>
            </TooltipTrigger>
            <TooltipContent>Supports extended reasoning</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </div>
  );
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
  const [nameError, setNameError] = useState<string | null>(null);

  // Fetch global keys to check if we have API keys for providers
  const { data: globalKeysData } = useGlobalKeys();

  // Check if there's a global key for the selected provider type
  const hasGlobalKey = globalKeysData?.keys?.some(
    (k) => k.providerType === newProvider.type && k.apiKeySet
  );

  // Fetch available models for the selected provider
  const {
    data: modelsData,
    isLoading: modelsLoading,
    error: modelsError,
  } = useProviderModels(newProvider.type, {
    enabled: showCreate && (!!newProvider.apiKey || hasGlobalKey || newProvider.type === 'ollama'),
  });

  // Selected model details
  const selectedModel = modelsData?.models?.find((m) => m.id === newProvider.model);

  // Reset model when provider type changes
  useEffect(() => {
    setNewProvider((prev) => ({ ...prev, model: '' }));
  }, [newProvider.type]);

  // Validate name
  const validateName = (name: string): boolean => {
    if (!name) {
      setNameError('Name is required');
      return false;
    }
    if (name.length < 2) {
      setNameError('Name must be at least 2 characters');
      return false;
    }
    if (!NAME_PATTERN.test(name)) {
      setNameError('Name must start with a letter and contain only letters, numbers, and hyphens');
      return false;
    }
    setNameError(null);
    return true;
  };

  const handleSaveApiKey = (providerId: string) => {
    const key = draftKeys[providerId];
    if (!key) return;
    onUpdateProvider(providerId, { apiKey: key });
    setDraftKeys((prev) => ({ ...prev, [providerId]: '' }));
  };

  const handleCreateProvider = () => {
    if (!validateName(newProvider.name)) {
      return;
    }
    if (!newProvider.model.trim()) {
      return;
    }

    const providerOption = PROVIDER_OPTIONS.find((p) => p.value === newProvider.type);
    if (providerOption?.requiresApiKey && !newProvider.apiKey?.trim() && !hasGlobalKey) {
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
    setNameError(null);
    setShowCreate(false);
  };

  const selectedProviderOption = PROVIDER_OPTIONS.find((p) => p.value === newProvider.type);
  const needsApiKey = selectedProviderOption?.requiresApiKey && !hasGlobalKey;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-card border-border text-foreground max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>LLM Configurations</DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Configure language model providers for the chat interface.
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="flex-1 -mx-6 px-6">
          <div className="space-y-4 py-4">
            {llmProviders.map((llm) => (
              <Card key={llm.configId} className="bg-muted/60 border-border">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-card">
                        <Bot className="h-5 w-5 text-amber-500" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="font-medium text-foreground">{llm.name}</h4>
                          {activeLLMProviderId === llm.configId && (
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
                            autoComplete="off"
                            placeholder="API Key"
                            className="h-8 w-32 text-xs bg-card border-border text-foreground"
                            value={draftKeys[llm.configId] || ''}
                            onChange={(e) =>
                              setDraftKeys((prev) => ({
                                ...prev,
                                [llm.configId]: e.target.value,
                              }))
                            }
                            onKeyDown={(e) =>
                              e.key === 'Enter' && handleSaveApiKey(llm.configId)
                            }
                          />
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleSaveApiKey(llm.configId)}
                            className="border-border text-foreground hover:bg-muted bg-transparent"
                          >
                            Save
                          </Button>
                        </div>
                      )}
                      {(llm.apiKeySet || llm.type === 'ollama') &&
                        activeLLMProviderId !== llm.configId && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => onSetActiveProvider(llm.configId)}
                          className="border-border text-foreground hover:bg-muted bg-transparent"
                        >
                          Set Active
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onValidateProvider(llm.configId)}
                        className="h-8 w-8 text-muted-foreground hover:text-foreground"
                        title="Validate provider"
                      >
                        <Check className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onDeleteProvider(llm.configId)}
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
                  onChange={(e) => {
                    setNewProvider({ ...newProvider, name: e.target.value });
                    if (e.target.value) validateName(e.target.value);
                  }}
                  placeholder="my-claude-config"
                  className={cn(
                    'h-8 text-xs bg-card border-border text-foreground',
                    nameError && 'border-red-500'
                  )}
                />
                {nameError && (
                  <p className="text-xs text-red-400 flex items-center gap-1">
                    <AlertCircle className="h-3 w-3" />
                    {nameError}
                  </p>
                )}
              </div>
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">Provider</Label>
                <Select
                  value={newProvider.type}
                  onValueChange={(value) =>
                    setNewProvider({ ...newProvider, type: value as LLMProviderType })
                  }
                >
                  <SelectTrigger className="h-8 text-xs bg-card border-border text-foreground">
                    <SelectValue placeholder="Select provider" />
                  </SelectTrigger>
                  <SelectContent className="bg-card border-border">
                    {PROVIDER_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {needsApiKey && (
                <div className="col-span-2 space-y-1">
                  <Label className="text-xs text-muted-foreground">
                    API Key {hasGlobalKey && '(using global key)'}
                  </Label>
                  <Input
                    type="password"
                    autoComplete="off"
                    value={newProvider.apiKey}
                    onChange={(e) => setNewProvider({ ...newProvider, apiKey: e.target.value })}
                    placeholder={hasGlobalKey ? 'Optional (global key available)' : 'Required'}
                    className="h-8 text-xs bg-card border-border text-foreground"
                  />
                </div>
              )}
              {newProvider.type === 'ollama' && (
                <div className="col-span-2 space-y-1">
                  <Label className="text-xs text-muted-foreground">Base URL</Label>
                  <Input
                    value={newProvider.baseUrl}
                    onChange={(e) => setNewProvider({ ...newProvider, baseUrl: e.target.value })}
                    placeholder="http://localhost:11434"
                    className="h-8 text-xs bg-card border-border text-foreground"
                  />
                  <p className="text-xs text-muted-foreground">
                    For MCP tool support, use ollama-mcp-bridge URL instead
                  </p>
                </div>
              )}
              <div className="col-span-2 space-y-1">
                <Label className="text-xs text-muted-foreground">Model</Label>
                {modelsLoading ? (
                  <div className="flex items-center gap-2 h-8 px-3 text-xs text-muted-foreground">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Loading models...
                  </div>
                ) : modelsError || !modelsData?.models?.length ? (
                  <Input
                    value={newProvider.model}
                    onChange={(e) => setNewProvider({ ...newProvider, model: e.target.value })}
                    placeholder={
                      needsApiKey && !newProvider.apiKey
                        ? 'Enter API key to load models'
                        : 'Enter model name (e.g., claude-3-5-sonnet-20241022)'
                    }
                    className="h-8 text-xs bg-card border-border text-foreground"
                  />
                ) : (
                  <Select
                    value={newProvider.model}
                    onValueChange={(value) => setNewProvider({ ...newProvider, model: value })}
                  >
                    <SelectTrigger className="h-8 text-xs bg-card border-border text-foreground">
                      <SelectValue placeholder="Select model" />
                    </SelectTrigger>
                    <SelectContent className="bg-card border-border max-h-60">
                      {modelsData.models.map((model) => (
                        <SelectItem key={model.id} value={model.id}>
                          <div className="flex items-center gap-2">
                            <span>{model.name}</span>
                            <ModelCapabilityBadges model={model} />
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>
              {selectedModel && (
                <div className="col-span-2 p-2 rounded bg-muted/60 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">
                      Context: {selectedModel.contextWindow.toLocaleString()} tokens
                    </span>
                    {selectedModel.costPer1kInput && selectedModel.costPer1kOutput && (
                      <span className="text-xs text-muted-foreground">
                        ${selectedModel.costPer1kInput.toFixed(4)}/1K in, $
                        {selectedModel.costPer1kOutput.toFixed(4)}/1K out
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <ModelCapabilityBadges model={selectedModel} />
                    <span className="text-xs text-muted-foreground">
                      {[
                        selectedModel.supportsTools && 'Tools',
                        selectedModel.supportsVision && 'Vision',
                        selectedModel.supportsReasoning && 'Reasoning',
                      ]
                        .filter(Boolean)
                        .join(' • ') || 'Basic completion'}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
        <DialogFooter className="border-t border-border pt-4">
          {showCreate ? (
            <>
              <Button
                variant="outline"
                onClick={() => {
                  setShowCreate(false);
                  setNameError(null);
                }}
                className="border-border text-foreground hover:bg-muted bg-transparent"
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreateProvider}
                disabled={!newProvider.name || !newProvider.model || !!nameError}
                className="bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
              >
                <Plus className="h-4 w-4 mr-2" />
                Save Configuration
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                onClick={() => onOpenChange(false)}
                className="border-border text-foreground hover:bg-muted bg-transparent"
              >
                Close
              </Button>
              <Button
                className="bg-blue-600 hover:bg-blue-700 text-white"
                onClick={() => setShowCreate(true)}
              >
                <Plus className="h-4 w-4 mr-2" />
                Add Configuration
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
