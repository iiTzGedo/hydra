/**
 * HtmlBlockWidget -- config-only widget that renders arbitrary HTML content
 * in a sandboxed iframe via srcdoc.
 *
 * Config: { html: string }
 *
 * No data binding required. HTML content is provided purely through config.
 * The iframe is sandboxed with allow-same-origin only.
 */

import { Code } from 'lucide-react';
import type { WidgetComponentProps } from '@/types/dashboard';
import { WidgetLoadingState } from '../shared/widget-loading-state';
import { WidgetErrorState } from '../shared/widget-error-state';

interface HtmlBlockConfig extends Record<string, unknown> {
  html?: string;
}

export function HtmlBlockWidget({
  config,
  isLoading,
  error,
  dimensions,
}: WidgetComponentProps<unknown, HtmlBlockConfig>) {
  if (isLoading) return <WidgetLoadingState />;
  if (error) return <WidgetErrorState error={error} />;

  const html = typeof config.html === 'string' ? config.html.trim() : '';

  if (!html) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
        <Code className="h-5 w-5" />
        <div className="text-sm">Add HTML content in widget settings</div>
      </div>
    );
  }

  return (
    <div className="h-full w-full overflow-hidden rounded-lg border border-border/40">
      <iframe
        srcDoc={html}
        sandbox="allow-same-origin"
        title="HTML block content"
        className="h-full w-full border-0"
        style={{
          maxHeight: dimensions.height > 0 ? `${dimensions.height}px` : undefined,
        }}
      />
    </div>
  );
}
