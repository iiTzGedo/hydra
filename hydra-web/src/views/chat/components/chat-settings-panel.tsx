import {
  Settings,
  Thermometer,
  Brain,
  Globe,
  Gauge,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ModelConfig, SessionUsage } from '@/hooks/use-mcp-chat';
import type { ReasoningLevel } from './chat-input';
import type { SessionContext } from '@/api/chat';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';

const getEstimatedContextWindow = (model: string | undefined): number => {
  if (!model) return 128000; // Default fallback
  const m = model.toLowerCase();

  // Anthropic models
  if (m.includes('claude-3') || m.includes('claude-4')) return 200000;
  if (m.includes('claude-2')) return 100000;

  // OpenAI models
  if (m.includes('gpt-4o')) return 128000;
  if (m.includes('gpt-4-turbo') || m.includes('gpt-4-1106')) return 128000;
  if (m.includes('gpt-4-32k')) return 32768;
  if (m.includes('gpt-4')) return 8192;
  if (m.includes('gpt-3.5-turbo-16k')) return 16384;
  if (m.includes('gpt-3.5')) return 4096;
  if (m.includes('o1') || m.includes('o3')) return 128000;

  // Ollama/Local models
  if (m.includes('llama3') || m.includes('llama-3')) return 128000;
  if (m.includes('llama2') || m.includes('llama-2')) return 4096;
  if (m.includes('mistral')) return 32768;
  if (m.includes('mixtral')) return 32768;

  return 128000; // Default for unknown models
};

interface ChatSettingsPanelProps {
  modelConfig: ModelConfig;
  onModelConfigChange: (config: ModelConfig) => void;
  reasoningLevel: ReasoningLevel;
  onReasoningLevelChange: (level: ReasoningLevel) => void;
  webSearchEnabled: boolean;
  onWebSearchEnabledChange: (enabled: boolean) => void;
  supportsReasoning: boolean;
  supportsWebSearch: boolean;
  isStreaming: boolean;

  // Context/usage display
  sessionUsage: SessionUsage | null;
  sessionContext: SessionContext | null;
  activeLLMProvider: { name?: string; model?: string; type?: string } | null;
  onOpenLLMConfig: () => void;
}

export function ChatSettingsPanel({
  modelConfig,
  onModelConfigChange,
  reasoningLevel,
  onReasoningLevelChange,
  webSearchEnabled,
  onWebSearchEnabledChange,
  supportsReasoning,
  supportsWebSearch,
  isStreaming,
  sessionUsage,
  sessionContext,
  activeLLMProvider,
  onOpenLLMConfig,
}: ChatSettingsPanelProps) {
  return (
    <>
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="p-3 space-y-4">
          {/* Model Configuration */}
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
              <Settings className="h-3.5 w-3.5 text-violet-500" />
              Model Configuration
            </h4>
            <div className="rounded-lg p-3 bg-muted/30 border border-border space-y-4">
              {/* Max Tokens */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label htmlFor="maxTokens" className="text-[10px] text-muted-foreground">
                    Max Output Tokens
                  </Label>
                  <span className="text-[10px] font-mono text-foreground">
                    {modelConfig.maxTokens || 'Default'}
                  </span>
                </div>
                <Input
                  id="maxTokens"
                  type="number"
                  placeholder="Default (4096)"
                  min={1}
                  max={100000}
                  value={modelConfig.maxTokens || ''}
                  onChange={(e) => onModelConfigChange({
                    ...modelConfig,
                    maxTokens: e.target.value ? parseInt(e.target.value, 10) : undefined,
                  })}
                  className="h-7 text-[11px] bg-background"
                />
              </div>

              {/* Temperature */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label className="text-[10px] text-muted-foreground flex items-center gap-1">
                    <Thermometer className="h-3 w-3" />
                    Temperature
                  </Label>
                  <span className="text-[10px] font-mono text-foreground">
                    {modelConfig.temperature?.toFixed(1) ?? 'Default'}
                  </span>
                </div>
                <Slider
                  value={modelConfig.temperature !== undefined ? [modelConfig.temperature] : [0.7]}
                  min={0}
                  max={2}
                  step={0.1}
                  onValueChange={(values) => onModelConfigChange({
                    ...modelConfig,
                    temperature: values[0],
                  })}
                  className="w-full"
                />
                <div className="flex justify-between text-[8px] text-muted-foreground">
                  <span>Precise (0)</span>
                  <span>Creative (2)</span>
                </div>
              </div>

              {/* Top P */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label className="text-[10px] text-muted-foreground">Top P</Label>
                  <span className="text-[10px] font-mono text-foreground">
                    {modelConfig.topP?.toFixed(2) ?? 'Default'}
                  </span>
                </div>
                <Slider
                  value={modelConfig.topP !== undefined ? [modelConfig.topP] : [1.0]}
                  min={0}
                  max={1}
                  step={0.05}
                  onValueChange={(values) => onModelConfigChange({
                    ...modelConfig,
                    topP: values[0],
                  })}
                  className="w-full"
                />
              </div>

              {/* Reset Button */}
              <Button
                variant="ghost"
                size="sm"
                className="w-full h-7 text-[10px] text-muted-foreground hover:text-foreground"
                onClick={() => onModelConfigChange({})}
              >
                Reset to Defaults
              </Button>
            </div>
          </div>

          {/* Reasoning & Search */}
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
              <Brain className="h-3.5 w-3.5 text-amber-500" />
              Reasoning & Search
            </h4>
            <div className="rounded-lg p-3 bg-muted/30 border border-border space-y-4">
              {/* Reasoning Level */}
              <div className="space-y-2">
                <Label className="text-[10px] text-muted-foreground">Reasoning Level</Label>
                <div className="grid grid-cols-4 gap-1">
                  {[
                    { value: 'none', label: 'Off' },
                    { value: 'low', label: 'Low' },
                    { value: 'medium', label: 'Med' },
                    { value: 'high', label: 'High' },
                  ].map((level) => (
                    <button
                      key={level.value}
                      onClick={() => supportsReasoning && onReasoningLevelChange(level.value as ReasoningLevel)}
                      disabled={!supportsReasoning || isStreaming}
                      className={cn(
                        'py-1.5 px-2 rounded text-[10px] transition-colors border',
                        reasoningLevel === level.value
                          ? 'bg-amber-500/20 border-amber-500/40 text-amber-400'
                          : 'border-border text-muted-foreground hover:bg-muted hover:text-foreground',
                        (!supportsReasoning || isStreaming) && 'opacity-50 cursor-not-allowed'
                      )}
                    >
                      {level.label}
                    </button>
                  ))}
                </div>
                {!supportsReasoning && (
                  <p className="text-[9px] text-muted-foreground">
                    Reasoning not available for this model
                  </p>
                )}
              </div>

              {/* Web Search */}
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label className="text-[10px] text-muted-foreground flex items-center gap-1">
                    <Globe className="h-3 w-3" />
                    Web Search
                  </Label>
                  {!supportsWebSearch && (
                    <p className="text-[9px] text-muted-foreground">
                      Not available for this model
                    </p>
                  )}
                </div>
                <Switch
                  checked={webSearchEnabled}
                  onCheckedChange={onWebSearchEnabledChange}
                  disabled={!supportsWebSearch || isStreaming}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom fixed section - Context details */}
      <div className="border-t border-border p-3 space-y-3 shrink-0">
        {/* Session Token Usage */}
        <div>
          <h4 className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Gauge className="h-3 w-3 text-cyan-500" />
            Context
          </h4>
          {(() => {
            // Use WebSocket session usage if available (real-time), otherwise fall back to persisted sessionContext
            const inputTokens = sessionUsage?.inputTokens ?? sessionContext?.inputTokens ?? 0;
            const outputTokens = sessionUsage?.outputTokens ?? sessionContext?.outputTokens ?? 0;
            const contextWindow = sessionUsage?.contextWindow || getEstimatedContextWindow(activeLLMProvider?.model);
            const usagePercent = contextWindow > 0 ? (inputTokens / contextWindow) * 100 : 0;

            return (
              <div className="space-y-2">
                <div className="space-y-1">
                  <div className="flex justify-between text-[10px]">
                    <span className="text-muted-foreground">Tokens</span>
                    <span className="text-foreground font-mono">
                      {inputTokens.toLocaleString()} / {contextWindow.toLocaleString()}
                    </span>
                  </div>
                  <Progress value={usagePercent} className="h-1.5" />
                </div>
                <div className="grid grid-cols-2 gap-1">
                  <div className="p-1.5 rounded bg-muted/60 text-center">
                    <div className="text-xs font-bold text-foreground">{inputTokens.toLocaleString()}</div>
                    <div className="text-[8px] text-muted-foreground">Input</div>
                  </div>
                  <div className="p-1.5 rounded bg-muted/60 text-center">
                    <div className="text-xs font-bold text-foreground">{outputTokens.toLocaleString()}</div>
                    <div className="text-[8px] text-muted-foreground">Output</div>
                  </div>
                </div>
              </div>
            );
          })()}
        </div>

        {/* Active Model Info */}
        <div className="flex items-center gap-2 p-2 rounded-md bg-violet-500/5 border border-violet-500/20">
          <Sparkles className="h-4 w-4 text-violet-500 shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-xs font-medium text-foreground truncate">
              {activeLLMProvider?.name || 'No Model Selected'}
            </div>
            <div className="text-[10px] text-muted-foreground">
              {activeLLMProvider?.model || 'Configure in settings'}
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-[10px] px-2 shrink-0 text-muted-foreground hover:text-foreground"
            onClick={onOpenLLMConfig}
          >
            Change
          </Button>
        </div>
      </div>
    </>
  );
}
