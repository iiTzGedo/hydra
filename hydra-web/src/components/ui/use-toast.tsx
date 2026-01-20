/**
 * Toast hook wrapper for sonner
 * Provides shadcn/ui-style API compatibility with sonner
 */

import { toast as sonnerToast } from 'sonner';

interface ToastOptions {
  title: string;
  description?: string;
  variant?: 'default' | 'destructive';
}

function toast({ title, description, variant }: ToastOptions) {
  if (variant === 'destructive') {
    sonnerToast.error(title, {
      description,
    });
  } else {
    sonnerToast.success(title, {
      description,
    });
  }
}

export function useToast() {
  return { toast };
}
