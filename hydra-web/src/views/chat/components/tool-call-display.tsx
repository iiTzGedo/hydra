import { useState } from 'react';
import { ChevronDown, Wrench } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChatToolCall } from '@/api/chat';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';

interface ToolCallDisplayProps {
  toolCall: ChatToolCall;
}

export function ToolCallDisplay({ toolCall }: ToolCallDisplayProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Collapsible open={expanded} onOpenChange={setExpanded}>
      <CollapsibleTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-between h-auto py-2 px-3 bg-card/60 hover:bg-card text-muted-foreground"
        >
          <div className="flex items-center gap-2">
            <Wrench className="h-3 w-3" />
            <span className="text-xs font-mono">{toolCall.name}</span>
          </div>
          <ChevronDown
            className={cn('h-3 w-3 transition-transform', expanded && 'rotate-180')}
          />
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="mt-2 p-3 rounded bg-card text-xs font-mono overflow-auto max-h-48">
          <p className="text-muted-foreground mb-1">Arguments:</p>
          <pre className="text-foreground">{JSON.stringify(toolCall.arguments, null, 2)}</pre>
          {!!toolCall.result && (
            <>
              <p className="text-muted-foreground mt-2 mb-1">Result:</p>
              <pre className="text-emerald-400">
                {JSON.stringify(toolCall.result, null, 2).slice(0, 500)}
              </pre>
            </>
          )}
          {toolCall.error && <p className="mt-1 text-red-400">{String(toolCall.error)}</p>}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
