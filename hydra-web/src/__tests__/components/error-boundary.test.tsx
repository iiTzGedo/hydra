/**
 * Tests for ErrorBoundary component.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ErrorBoundary, AsyncErrorBoundary } from '@/components/error-boundary';

// Suppress console.error from ErrorBoundary's componentDidCatch
beforeEach(() => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

function ThrowingComponent({ message = 'Test error' }: { message?: string }): React.JSX.Element {
  throw new Error(message);
}

function GoodComponent() {
  return <div>Working component</div>;
}

describe('ErrorBoundary', () => {
  it('renders children when no error occurs', () => {
    render(
      <ErrorBoundary>
        <GoodComponent />
      </ErrorBoundary>
    );
    expect(screen.getByText('Working component')).toBeInTheDocument();
  });

  it('renders default fallback UI when child throws', () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText(/An error occurred while rendering/)).toBeInTheDocument();
  });

  it('displays error name and message in fallback', () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent message="broken widget" />
      </ErrorBoundary>
    );

    expect(screen.getByText(/Error: broken widget/)).toBeInTheDocument();
  });

  it('renders custom fallback when provided', () => {
    render(
      <ErrorBoundary fallback={<div>Custom error view</div>}>
        <ThrowingComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText('Custom error view')).toBeInTheDocument();
    expect(screen.queryByText('Something went wrong')).toBeNull();
  });

  it('calls onReset when Try Again is clicked', async () => {
    const user = userEvent.setup();
    const onReset = vi.fn();

    render(
      <ErrorBoundary onReset={onReset}>
        <ThrowingComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Try Again/i }));

    expect(onReset).toHaveBeenCalledOnce();
  });

  it('shows Reload Page and Go Home buttons', () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>
    );

    expect(screen.getByRole('button', { name: /Reload Page/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Go Home/i })).toBeInTheDocument();
  });

  it('toggles error details on Show details click', async () => {
    const user = userEvent.setup();

    render(
      <ErrorBoundary>
        <ThrowingComponent />
      </ErrorBoundary>
    );

    const toggleButton = screen.getByRole('button', { name: /Show details/i });
    expect(toggleButton).toBeInTheDocument();

    await user.click(toggleButton);
    expect(screen.getByRole('button', { name: /Hide details/i })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Hide details/i }));
    expect(screen.getByRole('button', { name: /Show details/i })).toBeInTheDocument();
  });

  it('logs error to console', () => {
    render(
      <ErrorBoundary>
        <ThrowingComponent message="console test" />
      </ErrorBoundary>
    );

    expect(console.error).toHaveBeenCalledWith(
      'ErrorBoundary caught an error:',
      expect.any(Error),
      expect.objectContaining({ componentStack: expect.any(String) })
    );
  });
});

describe('AsyncErrorBoundary', () => {
  it('renders children when no error occurs', () => {
    render(
      <AsyncErrorBoundary>
        <GoodComponent />
      </AsyncErrorBoundary>
    );
    expect(screen.getByText('Working component')).toBeInTheDocument();
  });

  it('extends ErrorBoundary', () => {
    // AsyncErrorBoundary extends ErrorBoundary with getDerivedStateFromProps
    // that resets error state when children change (for async error recovery)
    expect(AsyncErrorBoundary.prototype).toBeInstanceOf(ErrorBoundary);
  });
});
