import { useRef, useEffect, useCallback } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

// Reasoning level type - exported for use in parent components
export type ReasoningLevel = 'none' | 'low' | 'medium' | 'high';

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  isStreaming: boolean;
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

  return (
    <div className="border-t border-border p-4 shrink-0">
      <div className="max-w-4xl mx-auto">
        <div className="flex gap-2 items-end">
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
