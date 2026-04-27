/**
 * Tests for CloneWithVariablesDialog component.
 *
 * Covers:
 *  - Renders name field with default "(clone)" suffix
 *  - Renders no variable fields when sourceBoard.variables is undefined
 *  - Renders one FieldSchemaRenderer per declared variable
 *  - Required variables block submit until filled
 *  - Submit invokes onSubmit callback with { name, variables }
 *  - Cancel button closes the dialog (calls onOpenChange(false))
 *  - isSubmitting disables the submit button
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CloneWithVariablesDialog } from '@/components/dashboard/clone-with-variables-dialog';
import type { DashboardBoard, FieldSchema } from '@/types/dashboard';

// ── Mocks ──────────────────────────────────────────────────────────

// FieldSchemaRenderer uses EntityCombobox which requires TanStack Query.
// Mock it to a simple stub so we stay unit-focused.
vi.mock('@/components/ui/entity-combobox', () => ({
  EntityCombobox: ({
    value,
    onValueChange,
    placeholder,
  }: {
    value: string;
    onValueChange: (v: string) => void;
    placeholder?: string;
  }) => (
    <input
      data-testid="entity-combobox"
      value={value}
      placeholder={placeholder}
      onChange={(e) => onValueChange(e.target.value)}
    />
  ),
}));

// ── Helpers ────────────────────────────────────────────────────────

function makeBoard(
  overrides: Partial<DashboardBoard & { variables?: FieldSchema[] }> = {}
): DashboardBoard & { variables?: FieldSchema[] } {
  return {
    boardId: 'board-001',
    name: 'My Board',
    description: null,
    icon: null,
    ownerId: 'user-001',
    ownerType: 'user',
    boardType: 'user',
    visibility: { scope: 'private', sharedWith: { roles: [], users: [] } },
    widgetCount: 0,
    tags: [],
    isHome: false,
    version: 1,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    layoutMode: 'grid',
    scope: 'standalone',
    entityTypeFilter: null,
    isSystemDefault: false,
    layout: {
      mode: 'grid',
      grid: {
        columns: 12,
        rowHeight: 80,
        breakpoints: {},
        compaction: 'vertical',
        margin: [16, 16],
        padding: [0, 0],
      },
    },
    widgets: [],
    settings: {
      theme: 'inherit',
      autoRefresh: true,
      refreshInterval: 30,
      showHeader: true,
      kioskMode: false,
      kioskAutoScroll: false,
      kioskScrollSpeed: 30,
      backgroundImage: null,
      customCss: null,
    },
    ...overrides,
  };
}

function renderDialog(
  props: Partial<{
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSubmit: (payload: { name: string; variables: Record<string, unknown> }) => void;
    isSubmitting: boolean;
    board: DashboardBoard & { variables?: FieldSchema[] };
  }> = {}
) {
  const board = props.board ?? makeBoard();
  const onOpenChange = props.onOpenChange ?? vi.fn();
  const onSubmit = props.onSubmit ?? vi.fn();

  const { rerender, ...rest } = render(
    <CloneWithVariablesDialog
      sourceBoard={board}
      open={props.open ?? true}
      onOpenChange={onOpenChange}
      onSubmit={onSubmit}
      isSubmitting={props.isSubmitting ?? false}
    />
  );

  return { ...rest, rerender, onOpenChange, onSubmit };
}

// ── Tests ──────────────────────────────────────────────────────────

describe('CloneWithVariablesDialog — no variables', () => {
  it('renders the dialog with a name input defaulting to "My Board (clone)"', () => {
    renderDialog();
    const input = screen.getByLabelText(/name/i);
    expect(input).toBeInTheDocument();
    expect(input).toHaveValue('My Board (clone)');
  });

  it('renders the board name in the dialog title', () => {
    renderDialog();
    expect(screen.getByText(/clone.*my board/i)).toBeInTheDocument();
  });

  it('does not render variable fields when sourceBoard.variables is undefined', () => {
    renderDialog({ board: makeBoard({ variables: undefined }) });
    // The "variables" section header should be absent
    expect(screen.queryByText(/this board uses variables/i)).not.toBeInTheDocument();
  });

  it('does not render variable fields when sourceBoard.variables is an empty array', () => {
    renderDialog({ board: makeBoard({ variables: [] }) });
    expect(screen.queryByText(/this board uses variables/i)).not.toBeInTheDocument();
  });

  it('submit button is enabled with a non-empty name', () => {
    renderDialog();
    const cloneBtn = screen.getByRole('button', { name: /clone/i });
    expect(cloneBtn).not.toBeDisabled();
  });

  it('calls onSubmit with the entered name and empty variables on submit', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderDialog({ onSubmit });

    const input = screen.getByLabelText(/name/i);
    await user.clear(input);
    await user.type(input, 'New Copy');

    await user.click(screen.getByRole('button', { name: /clone/i }));

    expect(onSubmit).toHaveBeenCalledOnce();
    expect(onSubmit).toHaveBeenCalledWith({ name: 'New Copy', variables: {} });
  });

  it('submit is disabled when name is empty', async () => {
    const user = userEvent.setup();
    renderDialog();

    const input = screen.getByLabelText(/name/i);
    await user.clear(input);

    expect(screen.getByRole('button', { name: /clone/i })).toBeDisabled();
  });

  it('Cancel button calls onOpenChange(false)', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    renderDialog({ onOpenChange });

    await user.click(screen.getByRole('button', { name: /cancel/i }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('isSubmitting disables the submit (Clone) button', () => {
    renderDialog({ isSubmitting: true });
    const cloneBtn = screen.getByRole('button', { name: /cloning/i });
    expect(cloneBtn).toBeDisabled();
  });
});

// ── With variables ─────────────────────────────────────────────────

describe('CloneWithVariablesDialog — with variables', () => {
  const variables: FieldSchema[] = [
    { key: 'env', label: 'Environment', type: 'string', required: true },
    { key: 'region', label: 'Region', type: 'string', required: false, default: 'us-east-1' },
  ];

  it('renders one input per declared variable', () => {
    renderDialog({ board: makeBoard({ variables }) });
    // FieldSchemaRenderer renders a textbox for 'string' fields
    const inputs = screen.getAllByRole('textbox');
    // name input + 2 variable inputs = 3 total
    expect(inputs.length).toBeGreaterThanOrEqual(3);
  });

  it('renders the informational "this board uses variables" message', () => {
    renderDialog({ board: makeBoard({ variables }) });
    expect(screen.getByText(/this board uses variables/i)).toBeInTheDocument();
  });

  it('submit is disabled when a required variable is empty', async () => {
    const user = userEvent.setup();
    renderDialog({ board: makeBoard({ variables }) });

    // 'env' is required and starts empty; submit should be disabled
    const cloneBtn = screen.getByRole('button', { name: /clone/i });
    expect(cloneBtn).toBeDisabled();

    // Fill in the required field
    const varInputs = screen.getAllByRole('textbox');
    // varInputs[0] = name, varInputs[1] = env, varInputs[2] = region
    await user.type(varInputs[1], 'production');
    expect(cloneBtn).not.toBeDisabled();
  });

  it('submit is enabled once all required variables are filled', async () => {
    const user = userEvent.setup();
    renderDialog({ board: makeBoard({ variables }) });

    const varInputs = screen.getAllByRole('textbox');
    await user.type(varInputs[1], 'staging');

    const cloneBtn = screen.getByRole('button', { name: /clone/i });
    expect(cloneBtn).not.toBeDisabled();
  });

  it('calls onSubmit with name and variable values on confirm', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderDialog({ board: makeBoard({ variables }), onSubmit });

    const varInputs = screen.getAllByRole('textbox');
    // varInputs[0] = name, varInputs[1] = env, varInputs[2] = region
    await user.clear(varInputs[0]);
    await user.type(varInputs[0], 'Clone Board');
    await user.type(varInputs[1], 'production');

    fireEvent.click(screen.getByRole('button', { name: /clone/i }));

    expect(onSubmit).toHaveBeenCalledOnce();
    const payload = onSubmit.mock.calls[0][0] as { name: string; variables: Record<string, unknown> };
    expect(payload.name).toBe('Clone Board');
    expect(payload.variables['env']).toBe('production');
  });

  it('non-required variables with defaults do not block submit', () => {
    // Only 'env' (required) blocks; region has a default and is not required
    const onlyRequiredBlocking: FieldSchema[] = [
      { key: 'region', label: 'Region', type: 'string', required: false, default: 'eu-west-1' },
    ];
    renderDialog({ board: makeBoard({ variables: onlyRequiredBlocking }) });
    // No required fields → submit should be enabled
    expect(screen.getByRole('button', { name: /clone/i })).not.toBeDisabled();
  });
});
