import { useRef, useEffect, useCallback } from 'react';
import { Send, Loader2, Brain, Globe, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

// Reasoning level type - 'none' is default, levels increase reasoning effort
export type ReasoningLevel = 'none' | 'low' | 'medium' | 'high';

export const REASONING_LEVELS: { value: ReasoningLevel; label: string; description: string }[] = [
  { value: 'none', label: 'Off', description: 'No extended reasoning' },
  { value: 'low', label: 'Low', description: 'Brief reasoning for simple tasks' },
  { value: 'medium', label: 'Medium', description: 'Moderate reasoning for complex tasks' },
  { value: 'high', label: 'High', description: 'Extensive reasoning for difficult tasks' },
];

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  isStreaming: boolean;
  // Feature controls
  reasoningLevel?: ReasoningLevel;
  webSearchEnabled?: boolean;
  supportsReasoning?: boolean;
  supportsWebSearch?: boolean;
  onReasoningLevelChange?: (level: ReasoningLevel) => void;
  onWebSearchToggle?: (enabled: boolean) => void;
}

// Maximum height as percentage of viewport height
const MAX_HEIGHT_VH = 30; // 30% of viewport height
const MIN_HEIGHT_PX = 44;
const LINE_HEIGHT_PX = 24; // Approximate line height

export function ChatInput({
  value,
  onChange,
  onSend,
  isStreaming,
  reasoningLevel = 'none',
  webSearchEnabled = false,
  supportsReasoning = false,
  supportsWebSearch = false,
  onReasoningLevelChange,
  onWebSearchToggle,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    // Reset height to auto to get accurate scrollHeight
    textarea.style.height = 'auto';

    // Calculate max height based on viewport
    const maxHeight = Math.max(
      MIN_HEIGHT_PX + LINE_HEIGHT_PX * 2, // Minimum 3 lines
      Math.min(
        window.innerHeight * (MAX_HEIGHT_VH / 100),
        LINE_HEIGHT_PX * 12 // Cap at 12 lines regardless of viewport
      )
    );

    // Set height to scrollHeight, capped at maxHeight
    const newHeight = Math.min(textarea.scrollHeight, maxHeight);
    textarea.style.height = `${Math.max(newHeight, MIN_HEIGHT_PX)}px`;
  }, []);

  // Adjust height when value changes
  useEffect(() => {
    adjustHeight();
  }, [value, adjustHeight]);

  // Adjust on window resize
  useEffect(() => {
    window.addEventListener('resize', adjustHeight);
    return () => window.removeEventListener('resize', adjustHeight);
  }, [adjustHeight]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  const currentReasoningConfig = REASONING_LEVELS.find((l) => l.value === reasoningLevel) || REASONING_LEVELS[0];
  const isReasoningActive = reasoningLevel !== 'none';

  return (
    <div className="border-t border-border p-4 shrink-0">
      <div className="max-w-4xl mx-auto">
        <div className="flex gap-2 items-end">
          {/* Feature controls - left of textbox, always visible */}
          <div className="flex items-center gap-1 shrink-0">
            {/* Reasoning Level Selector - always shown, disabled if not supported */}
            <TooltipProvider>
              <Tooltip>
                {supportsReasoning ? (
                  <DropdownMenu>
                    <TooltipTrigger asChild>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          className={cn(
                            'h-[44px] px-2 gap-1',
                            isReasoningActive
                              ? 'text-amber-400 hover:text-amber-300 hover:bg-amber-500/10'
                              : 'text-muted-foreground hover:text-foreground'
                          )}
                          disabled={isStreaming}
                        >
                          <Brain className="h-4 w-4" />
                          {isReasoningActive && (
                            <span className="text-xs">{currentReasoningConfig.label}</span>
                          )}
                          <ChevronDown className="h-3 w-3" />
                        </Button>
                      </DropdownMenuTrigger>
                    </TooltipTrigger>
                    <DropdownMenuContent align="start" className="w-48">
                      {REASONING_LEVELS.map((level) => (
                        <DropdownMenuItem
                          key={level.value}
                          onClick={() => onReasoningLevelChange?.(level.value)}
                          className={cn(
                            'flex flex-col items-start gap-0.5',
                            reasoningLevel === level.value && 'bg-accent'
                          )}
                        >
                          <span className="font-medium">{level.label}</span>
                          <span className="text-xs text-muted-foreground">{level.description}</span>
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                ) : (
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-[44px] px-2 gap-1 text-muted-foreground/50 cursor-not-allowed"
                      disabled
                    >
                      <Brain className="h-4 w-4" />
                      <ChevronDown className="h-3 w-3" />
                    </Button>
                  </TooltipTrigger>
                )}
                <TooltipContent side="top">
                  {supportsReasoning
                    ? `Extended reasoning - ${currentReasoningConfig.description}`
                    : 'Reasoning option not available for this model'}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            {/* Web Search Toggle - always shown, disabled if not supported */}
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className={cn(
                      'h-[44px] px-2',
                      !supportsWebSearch
                        ? 'text-muted-foreground/50 cursor-not-allowed'
                        : webSearchEnabled
                          ? 'text-blue-400 hover:text-blue-300 hover:bg-blue-500/10'
                          : 'text-muted-foreground hover:text-foreground'
                    )}
                    onClick={() => supportsWebSearch && onWebSearchToggle?.(!webSearchEnabled)}
                    disabled={isStreaming || !supportsWebSearch}
                  >
                    <Globe className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top">
                  {!supportsWebSearch
                    ? 'Web search option not available for this model'
                    : webSearchEnabled
                      ? 'Web search enabled'
                      : 'Enable web search'}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>

          <Textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your infrastructure..."
            className="min-h-[44px] resize-none bg-muted border-border text-foreground placeholder:text-muted-foreground overflow-y-auto"
            disabled={isStreaming}
            rows={1}
          />

          {/* Send Button - doubled width */}
          <Button
            onClick={onSend}
            disabled={!value.trim() || isStreaming}
            className="shrink-0 bg-blue-600 hover:bg-blue-700 text-white h-[44px] w-20"
          >
            {isStreaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </div>
        <p className="text-[10px] text-muted-foreground mt-2 text-center">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
