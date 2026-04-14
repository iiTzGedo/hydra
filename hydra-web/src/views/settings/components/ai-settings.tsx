import { useState } from 'react';
import {
  Bot,
  Check,
  Eye,
  EyeOff,
  Key,
  Loader2,
  Settings,
  Trash2,
  AlertCircle,
  Wrench,
  Brain,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  useLLMProviders,
  useGlobalKeys,
  useSetGlobalKey,
  useDeleteGlobalKey,
  useValidateGlobalKey,
  useDeleteLLMProvider,
  type LLMProviderType,
  type GlobalKeyScope,
} from '@/api/ai';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

const PROVIDER_LABELS: Record<LLMProviderType, { name: string; description: string }> = {
  anthropic: { name: 'Anthropic', description: 'Claude models' },
  openai: { name: 'OpenAI', description: 'GPT models' },
  openrouter: { name: 'OpenRouter', description: 'Multi-provider gateway' },
  ollama: { name: 'Ollama', description: 'Local models (no API key required)' },
};

const SCOPE_LABELS: Record<GlobalKeyScope, { name: string; description: string }> = {
  chat: { name: 'Chat', description: 'Use for chat conversations' },
  meta: { name: 'Meta', description: 'Fetch model lists and capabilities' },
  title_gen: { name: 'Title Gen', description: 'Auto-generate session titles' },
};

const ALL_PROVIDERS: LLMProviderType[] = ['anthropic', 'openai', 'openrouter', 'ollama'];

export function AISettings() {
  const { data: llmProviders, isLoading: providersLoading } = useLLMProviders();
  const { data: globalKeysData, isLoading: keysLoading } = useGlobalKeys();
  const setGlobalKey = useSetGlobalKey();
  const deleteGlobalKey = useDeleteGlobalKey();
  const validateGlobalKey = useValidateGlobalKey();
  const deleteLLMProvider = useDeleteLLMProvider();

  const [apiKeyInputs, setApiKeyInputs] = useState<Record<string, string>>({});
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [scopes, setScopes] = useState<Record<string, GlobalKeyScope[]>>({
    anthropic: ['chat', 'meta', 'title_gen'],
    openai: ['chat', 'meta', 'title_gen'],
    openrouter: ['chat', 'meta', 'title_gen'],
  });
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [providerToDelete, setProviderToDelete] = useState<string | null>(null);

  const globalKeys = globalKeysData?.keys || [];

  const handleSaveGlobalKey = async (providerType: LLMProviderType) => {
    const apiKey = apiKeyInputs[providerType];
    if (!apiKey) return;

    await setGlobalKey.mutateAsync({
      providerType,
      data: {
        apiKey,
        scopes: scopes[providerType] || ['chat', 'meta', 'title_gen'],
      },
    });

    setApiKeyInputs((prev) => ({ ...prev, [providerType]: '' }));
  };

  const handleDeleteGlobalKey = async (providerType: LLMProviderType) => {
    await deleteGlobalKey.mutateAsync(providerType);
  };

  const handleValidateGlobalKey = async (providerType: LLMProviderType) => {
    await validateGlobalKey.mutateAsync(providerType);
  };

  const handleScopeChange = (providerType: LLMProviderType, scope: GlobalKeyScope, checked: boolean) => {
    setScopes((prev) => {
      const current = prev[providerType] || ['chat', 'meta', 'title_gen'];
      if (checked) {
        return { ...prev, [providerType]: [...current, scope] };
      } else {
        return { ...prev, [providerType]: current.filter((s) => s !== scope) };
      }
    });
  };

  const getGlobalKeyForProvider = (providerType: LLMProviderType) => {
    return globalKeys.find((k) => k.providerType === providerType);
  };

  const handleDeleteLLMConfig = async () => {
    if (!providerToDelete) return;
    await deleteLLMProvider.mutateAsync(providerToDelete);
    setDeleteDialogOpen(false);
    setProviderToDelete(null);
  };

  const isLoading = providersLoading || keysLoading;

  return (
    <div className="space-y-6">
      {/* Global API Keys Section */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-foreground">
            <Key className="h-5 w-5" />
            Global API Keys
          </CardTitle>
          <CardDescription className="text-muted-foreground">
            Configure global API keys for LLM providers. These keys are used when a specific
            configuration doesn&apos;t have its own key.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {ALL_PROVIDERS.filter((p) => p !== 'ollama').map((providerType) => {
            const provider = PROVIDER_LABELS[providerType];
            const globalKey = getGlobalKeyForProvider(providerType);
            const isValidating = validateGlobalKey.isPending && validateGlobalKey.variables === providerType;
            const isSaving = setGlobalKey.isPending && setGlobalKey.variables?.providerType === providerType;

            return (
              <div
                key={providerType}
                className="p-4 rounded-lg bg-muted/50 border border-border space-y-3"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-card">
                      <Bot className="h-5 w-5 text-amber-500" />
                    </div>
                    <div>
                      <h4 className="font-medium text-foreground">{provider.name}</h4>
                      <p className="text-xs text-muted-foreground">{provider.description}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {globalKey && (
                      <>
                        <Badge
                          variant="outline"
                          className={cn(
                            globalKey.isValid === true
                              ? 'border-emerald-500/30 text-emerald-400'
                              : globalKey.isValid === false
                                ? 'border-red-500/30 text-red-400'
                                : 'border-border text-muted-foreground'
                          )}
                        >
                          {globalKey.isValid === true
                            ? 'Valid'
                            : globalKey.isValid === false
                              ? 'Invalid'
                              : 'Unvalidated'}
                        </Badge>
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-muted-foreground hover:text-foreground"
                                onClick={() => handleValidateGlobalKey(providerType)}
                                disabled={isValidating}
                              >
                                {isValidating ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <Check className="h-4 w-4" />
                                )}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Validate API key</TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                                onClick={() => handleDeleteGlobalKey(providerType)}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>Remove API key</TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      </>
                    )}
                  </div>
                </div>

                {globalKey ? (
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-muted-foreground">Key:</span>
                    <code className="px-2 py-0.5 bg-card rounded text-foreground">
                      ••••••••{globalKey.apiKeyLast4}
                    </code>
                    <span className="text-muted-foreground ml-2">Scopes:</span>
                    {globalKey.scopes.map((scope) => (
                      <Badge key={scope} variant="secondary" className="text-xs">
                        {SCOPE_LABELS[scope]?.name || scope}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <div className="relative flex-1">
                        <Input
                          type={showKeys[providerType] ? 'text' : 'password'}
                          autoComplete="off"
                          placeholder="Enter API key"
                          value={apiKeyInputs[providerType] || ''}
                          onChange={(e) =>
                            setApiKeyInputs((prev) => ({
                              ...prev,
                              [providerType]: e.target.value,
                            }))
                          }
                          className="pr-10 bg-card border-border text-foreground"
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 text-muted-foreground hover:text-foreground"
                          onClick={() =>
                            setShowKeys((prev) => ({
                              ...prev,
                              [providerType]: !prev[providerType],
                            }))
                          }
                        >
                          {showKeys[providerType] ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                      <Button
                        onClick={() => handleSaveGlobalKey(providerType)}
                        disabled={!apiKeyInputs[providerType] || isSaving}
                        className="bg-blue-600 hover:bg-blue-700 text-white"
                      >
                        {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Save'}
                      </Button>
                    </div>
                    <div className="flex items-center gap-4">
                      <Label className="text-xs text-muted-foreground">Scopes:</Label>
                      {(Object.keys(SCOPE_LABELS) as GlobalKeyScope[]).map((scope) => (
                        <div key={scope} className="flex items-center gap-1.5">
                          <Checkbox
                            id={`${providerType}-${scope}`}
                            checked={(scopes[providerType] || []).includes(scope)}
                            onCheckedChange={(checked) =>
                              handleScopeChange(providerType, scope, !!checked)
                            }
                            className="h-3.5 w-3.5"
                          />
                          <Label
                            htmlFor={`${providerType}-${scope}`}
                            className="text-xs text-muted-foreground cursor-pointer"
                          >
                            {SCOPE_LABELS[scope].name}
                          </Label>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {/* Ollama note */}
          <div className="p-3 rounded-lg bg-muted/30 border border-border">
            <div className="flex items-start gap-2">
              <AlertCircle className="h-4 w-4 text-muted-foreground mt-0.5" />
              <div className="text-xs text-muted-foreground">
                <strong>Ollama</strong> runs locally and doesn&apos;t require an API key. Configure
                the base URL when creating an LLM configuration.
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Configured LLMs Section */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-foreground">
            <Settings className="h-5 w-5" />
            Configured LLMs
          </CardTitle>
          <CardDescription className="text-muted-foreground">
            Your saved LLM configurations. Manage these in the Chat interface.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : !llmProviders?.configs?.length ? (
            <div className="text-center py-8 text-muted-foreground">
              <Bot className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p>No LLM configurations yet.</p>
              <p className="text-xs mt-1">
                Create configurations in the Chat interface.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-border hover:bg-transparent">
                  <TableHead className="text-muted-foreground">Name</TableHead>
                  <TableHead className="text-muted-foreground">Provider</TableHead>
                  <TableHead className="text-muted-foreground">Model</TableHead>
                  <TableHead className="text-muted-foreground">Status</TableHead>
                  <TableHead className="text-muted-foreground w-[100px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {llmProviders.configs.map((provider) => (
                  <TableRow key={provider.configId} className="border-border">
                    <TableCell className="font-medium text-foreground">
                      <div className="flex items-center gap-2">
                        {provider.name}
                        {provider.isDefault && (
                          <Badge variant="secondary" className="text-xs">
                            Default
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground capitalize">
                      {provider.type}
                    </TableCell>
                    <TableCell>
                      <code className="text-xs px-1.5 py-0.5 bg-muted rounded text-foreground">
                        {provider.model}
                      </code>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant="outline"
                          className={cn(
                            provider.apiKeySet || provider.type === 'ollama'
                              ? 'border-emerald-500/30 text-emerald-400'
                              : 'border-amber-500/30 text-amber-400'
                          )}
                        >
                          {provider.apiKeySet || provider.type === 'ollama'
                            ? 'Configured'
                            : 'No Key'}
                        </Badge>
                        {provider.isValid === false && (
                          <Badge variant="outline" className="border-red-500/30 text-red-400">
                            Invalid
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                        onClick={() => {
                          setProviderToDelete(provider.configId);
                          setDeleteDialogOpen(true);
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Model Capabilities Legend */}
      <Card className="bg-card border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-foreground text-base">
            Model Capabilities
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="h-6 px-2 border-blue-500/30 text-blue-400">
                <Wrench className="h-3.5 w-3.5" />
              </Badge>
              <span className="text-muted-foreground">
                Tool/function calling support
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="h-6 px-2 border-purple-500/30 text-purple-400">
                <Eye className="h-3.5 w-3.5" />
              </Badge>
              <span className="text-muted-foreground">
                Vision/image input support
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="h-6 px-2 border-amber-500/30 text-amber-400">
                <Brain className="h-3.5 w-3.5" />
              </Badge>
              <span className="text-muted-foreground">
                Extended reasoning support
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent className="bg-card border-border">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-foreground">Delete LLM Configuration</AlertDialogTitle>
            <AlertDialogDescription className="text-muted-foreground">
              Are you sure you want to delete this LLM configuration? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="border-border text-foreground hover:bg-muted">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteLLMConfig}
              className="bg-red-600 hover:bg-red-700 text-white"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
