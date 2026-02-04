/**
 * Tests for EmptyState and EmptyStateCompact components.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Server, Inbox } from 'lucide-react';
import { EmptyState, EmptyStateCompact } from '@/components/ui/empty-state';

describe('EmptyState', () => {
  it('renders title', () => {
    render(<EmptyState title="No nodes found" />);
    expect(screen.getByText('No nodes found')).toBeInTheDocument();
  });

  it('renders description when provided', () => {
    render(
      <EmptyState
        title="No nodes found"
        description="Get started by adding your first node"
      />
    );
    expect(screen.getByText('Get started by adding your first node')).toBeInTheDocument();
  });

  it('does not render description when omitted', () => {
    const { container } = render(<EmptyState title="Empty" />);
    expect(container.querySelector('p')).toBeNull();
  });

  it('renders icon when provided', () => {
    const { container } = render(<EmptyState icon={Server} title="No nodes" />);
    // Lucide icons render as SVGs
    expect(container.querySelector('svg')).toBeInTheDocument();
  });

  it('does not render icon container when icon is omitted', () => {
    const { container } = render(<EmptyState title="No nodes" />);
    expect(container.querySelector('svg')).toBeNull();
  });

  it('renders primary action button and handles click', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();

    render(
      <EmptyState
        title="No nodes"
        action={{ label: 'Add Node', onClick }}
      />
    );

    const button = screen.getByRole('button', { name: 'Add Node' });
    expect(button).toBeInTheDocument();

    await user.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('renders secondary action button and handles click', async () => {
    const user = userEvent.setup();
    const primaryClick = vi.fn();
    const secondaryClick = vi.fn();

    render(
      <EmptyState
        title="No nodes"
        action={{ label: 'Add Node', onClick: primaryClick }}
        secondaryAction={{ label: 'View Docs', onClick: secondaryClick }}
      />
    );

    expect(screen.getByRole('button', { name: 'Add Node' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'View Docs' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'View Docs' }));
    expect(secondaryClick).toHaveBeenCalledOnce();
    expect(primaryClick).not.toHaveBeenCalled();
  });

  it('does not render action buttons when omitted', () => {
    render(<EmptyState title="Empty" />);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('applies custom className', () => {
    const { container } = render(
      <EmptyState title="Empty" className="custom-class" />
    );
    expect(container.firstChild).toHaveClass('custom-class');
  });
});

describe('EmptyStateCompact', () => {
  it('renders message', () => {
    render(<EmptyStateCompact message="No items" />);
    expect(screen.getByText('No items')).toBeInTheDocument();
  });

  it('renders icon when provided', () => {
    const { container } = render(
      <EmptyStateCompact icon={Inbox} message="No items" />
    );
    expect(container.querySelector('svg')).toBeInTheDocument();
  });

  it('does not render icon when omitted', () => {
    const { container } = render(<EmptyStateCompact message="No items" />);
    expect(container.querySelector('svg')).toBeNull();
  });

  it('applies custom className', () => {
    const { container } = render(
      <EmptyStateCompact message="No items" className="my-class" />
    );
    expect(container.firstChild).toHaveClass('my-class');
  });
});
