import { Send, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  isStreaming: boolean;
}

export function ChatInput({ value, onChange, onSend, isStreaming }: ChatInputProps) {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="border-t border-border p-4 shrink-0">
      <div className="max-w-4xl mx-auto">
        <div className="flex gap-2">
          <Textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your infrastructure..."
            className="min-h-[44px] max-h-32 resize-none bg-muted border-border text-foreground placeholder:text-muted-foreground"
            disabled={isStreaming}
            rows={1}
          />
          <Button
            onClick={onSend}
            disabled={!value.trim() || isStreaming}
            className="shrink-0 bg-blue-600 hover:bg-blue-700 text-white"
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
