import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from './button';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}

interface ToastItemProps {
  toast: Toast;
  onDismiss: (id: string) => void;
}

const toastConfig: Record<ToastType, { icon: typeof CheckCircle; color: string; bg: string }> = {
  success: {
    icon: CheckCircle,
    color: 'text-success',
    bg: 'bg-success/10',
  },
  error: {
    icon: AlertCircle,
    color: 'text-destructive',
    bg: 'bg-destructive/10',
  },
  warning: {
    icon: AlertTriangle,
    color: 'text-warning',
    bg: 'bg-warning/10',
  },
  info: {
    icon: Info,
    color: 'text-info',
    bg: 'bg-info/10',
  },
};

function ToastItem({ toast, onDismiss }: ToastItemProps) {
  const config = toastConfig[toast.type];
  const Icon = config.icon;
  const duration = toast.duration ?? 5000;

  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(() => {
        onDismiss(toast.id);
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [duration, toast.id, onDismiss]);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 50, scale: 0.9 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 50, scale: 0.9 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
      className={cn(
        'relative w-full max-w-sm overflow-hidden rounded-xl border shadow-lg',
        'bg-card border-border'
      )}
    >
      {/* Progress bar */}
      {duration > 0 && (
        <motion.div
          initial={{ scaleX: 1 }}
          animate={{ scaleX: 0 }}
          transition={{ duration: duration / 1000, ease: 'linear' }}
          className={cn(
            'absolute bottom-0 left-0 right-0 h-1 origin-left',
            toast.type === 'success' && 'bg-success',
            toast.type === 'error' && 'bg-destructive',
            toast.type === 'warning' && 'bg-warning',
            toast.type === 'info' && 'bg-info'
          )}
        />
      )}

      <div className="p-4">
        <div className="flex gap-3">
          {/* Icon */}
          <div className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-xl', config.bg)}>
            <Icon className={cn('h-5 w-5', config.color)} />
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0 pt-0.5">
            {toast.title && (
              <h4 className="font-semibold text-foreground text-sm">{toast.title}</h4>
            )}
            <p className={cn('text-sm text-muted-foreground', toast.title && 'mt-0.5')}>
              {toast.message}
            </p>

            {/* Action */}
            {toast.action && (
              <Button
                variant="link"
                size="sm"
                className="h-auto p-0 mt-2 text-xs"
                onClick={() => {
                  toast.action?.onClick();
                  onDismiss(toast.id);
                }}
              >
                {toast.action.label}
              </Button>
            )}
          </div>

          {/* Dismiss */}
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 shrink-0 -mr-1 -mt-1 text-muted-foreground hover:text-foreground"
            onClick={() => onDismiss(toast.id)}
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </motion.div>
  );
}

interface ToastContainerProps {
  toasts: Toast[];
  onDismiss: (id: string) => void;
  position?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left' | 'top-center' | 'bottom-center';
}

export function ToastContainer({
  toasts,
  onDismiss,
  position = 'bottom-right',
}: ToastContainerProps) {
  const positionClasses = {
    'top-right': 'top-4 right-4',
    'top-left': 'top-4 left-4',
    'bottom-right': 'bottom-4 right-4',
    'bottom-left': 'bottom-4 left-4',
    'top-center': 'top-4 left-1/2 -translate-x-1/2',
    'bottom-center': 'bottom-4 left-1/2 -translate-x-1/2',
  };

  return (
    <div
      className={cn(
        'fixed z-50 flex flex-col gap-2 pointer-events-none',
        positionClasses[position]
      )}
    >
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <div key={toast.id} className="pointer-events-auto">
            <ToastItem toast={toast} onDismiss={onDismiss} />
          </div>
        ))}
      </AnimatePresence>
    </div>
  );
}

// Simple toast store for global usage
let toastListeners: Array<(toasts: Toast[]) => void> = [];
let toasts: Toast[] = [];

function notifyListeners() {
  toastListeners.forEach((listener) => listener([...toasts]))
;}

export function addToast(toast: Omit<Toast, 'id'>) {
  const id = Math.random().toString(36).substring(2, 9);
  toasts = [...toasts, { ...toast, id }];
  notifyListeners();
  return id;
}

export function removeToast(id: string) {
  toasts = toasts.filter((t) => t.id !== id);
  notifyListeners();
}

export function subscribeToToasts(listener: (toasts: Toast[]) => void) {
  toastListeners.push(listener);
  return () => {
    toastListeners = toastListeners.filter((l) => l !== listener);
  };
}

// Helper functions
export const toast = {
  success: (message: string, title?: string, duration?: number) =>
    addToast({ type: 'success', message, title, duration }),
  error: (message: string, title?: string, duration?: number) =>
    addToast({ type: 'error', message, title, duration }),
  warning: (message: string, title?: string, duration?: number) =>
    addToast({ type: 'warning', message, title, duration }),
  info: (message: string, title?: string, duration?: number) =>
    addToast({ type: 'info', message, title, duration }),
  custom: (toast: Omit<Toast, 'id'>) => addToast(toast),
  dismiss: removeToast,
};
