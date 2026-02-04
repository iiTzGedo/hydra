import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home, Bug } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { cn } from '@/lib/utils';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onReset?: () => void;
  className?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

/**
 * ErrorBoundary - Catches JavaScript errors in child components and displays a fallback UI
 * 
 * @example
 * // Basic usage
 * <ErrorBoundary>
 *   <MyComponent />
 * </ErrorBoundary>
 * 
 * @example
 * // With custom fallback
 * <ErrorBoundary fallback={<CustomErrorView />}>
 *   <MyComponent />
 * </ErrorBoundary>
 * 
 * @example
 * // With reset handler
 * <ErrorBoundary onReset={() => console.log('Reset!')}>
 *   <MyComponent />
 * </ErrorBoundary>
 */
export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.setState({ error, errorInfo });
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    this.props.onReset?.();
  };

  private handleReload = () => {
    window.location.reload();
  };

  private handleGoHome = () => {
    window.location.href = '/';
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <ErrorFallback
          error={this.state.error}
          errorInfo={this.state.errorInfo}
          onReset={this.handleReset}
          onReload={this.handleReload}
          onGoHome={this.handleGoHome}
          className={this.props.className}
        />
      );
    }

    return this.props.children;
  }
}

/**
 * ErrorFallback - Default error fallback UI
 */
interface ErrorFallbackProps {
  error: Error | null;
  errorInfo: ErrorInfo | null;
  onReset: () => void;
  onReload: () => void;
  onGoHome: () => void;
  className?: string;
}

function ErrorFallback({
  error,
  errorInfo,
  onReset,
  onReload,
  onGoHome,
  className,
}: ErrorFallbackProps) {
  const [showDetails, setShowDetails] = useState(false);

  return (
    <div
      className={cn(
        'flex min-h-[400px] items-center justify-center p-4 animate-in fade-in',
        className
      )}
    >
      <Card className="w-full max-w-lg border-destructive/20">
        <CardHeader className="text-center pb-2">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10 mb-4">
            <AlertTriangle className="h-8 w-8 text-destructive" />
          </div>
          <CardTitle className="text-xl">Something went wrong</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-center">
          <p className="text-muted-foreground">
            An error occurred while rendering this component. You can try to reset
            the component or reload the page.
          </p>

          {error && (
            <div className="rounded-md bg-muted p-3 text-left">
              <p className="text-sm font-medium text-destructive mb-1">
                {error.name}: {error.message}
              </p>
              {showDetails && errorInfo && (
                <pre className="mt-2 text-xs text-muted-foreground overflow-auto max-h-40 p-2 bg-background rounded">
                  {errorInfo.componentStack}
                </pre>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowDetails(!showDetails)}
                className="mt-2 h-auto py-1 text-xs"
              >
                <Bug className="h-3 w-3 mr-1" />
                {showDetails ? 'Hide details' : 'Show details'}
              </Button>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
            <Button onClick={onReset} variant="default">
              <RefreshCw className="h-4 w-4 mr-2" />
              Try Again
            </Button>
            <Button onClick={onReload} variant="outline">
              <RefreshCw className="h-4 w-4 mr-2" />
              Reload Page
            </Button>
            <Button onClick={onGoHome} variant="ghost">
              <Home className="h-4 w-4 mr-2" />
              Go Home
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// Import useState for the ErrorFallback component
import { useState } from 'react';

/**
 * withErrorBoundary - HOC to wrap components with ErrorBoundary
 */
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<Props, 'children'>
) {
  return function WithErrorBoundary(props: P) {
    return (
      <ErrorBoundary {...errorBoundaryProps}>
        <Component {...props} />
      </ErrorBoundary>
    );
  };
}

/**
 * AsyncErrorBoundary - Error boundary specifically for async errors
 * This component can also handle errors thrown from async operations
 */
export class AsyncErrorBoundary extends ErrorBoundary {
  public static getDerivedStateFromProps(
    props: Props,
    state: State
  ): State | null {
    // Reset error state if children change
    if (state.hasError && props.children) {
      return { hasError: false, error: null, errorInfo: null };
    }
    return null;
  }
}
