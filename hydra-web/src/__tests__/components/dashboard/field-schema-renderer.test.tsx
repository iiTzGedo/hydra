/**
 * Tests for FieldSchemaRenderer component.
 * Verifies each FieldSchema type renders the correct input control.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FieldSchemaRenderer } from '@/components/dashboard/field-schema-renderer';
import type { FieldSchema } from '@/types/dashboard';

// Mock EntityCombobox — it fires real API calls via TanStack Query,
// which is out of scope for these unit tests.
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

function makeSchema(overrides: Partial<FieldSchema>): FieldSchema {
  return {
    key: 'testKey',
    label: 'Test Label',
    type: 'string',
    ...overrides,
  };
}

// ── string ─────────────────────────────────────────────────────────

describe('FieldSchemaRenderer — string', () => {
  it('renders a text input', () => {
    const onChange = vi.fn();
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'string', label: 'Name' })}
        value="hello"
        onChange={onChange}
      />,
    );

    const input = screen.getByRole('textbox');
    expect(input).toBeInTheDocument();
    expect(input).toHaveValue('hello');
  });

  it('calls onChange with new string value on input', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'string' })}
        value=""
        onChange={onChange}
      />,
    );

    await user.type(screen.getByRole('textbox'), 'abc');
    expect(onChange).toHaveBeenCalledWith(expect.stringContaining('a'));
  });

  it('renders required asterisk when required=true', () => {
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'string', required: true })}
        value=""
        onChange={vi.fn()}
      />,
    );
    // aria-hidden asterisk
    expect(screen.getByText('*')).toBeInTheDocument();
  });

  it('renders description when provided', () => {
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'string', description: 'A helpful tip.' })}
        value=""
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByText('A helpful tip.')).toBeInTheDocument();
  });

  it('uses schema default when value is undefined', () => {
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'string', default: 'default-val' })}
        value={undefined}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByRole('textbox')).toHaveValue('default-val');
  });
});

// ── number ─────────────────────────────────────────────────────────

describe('FieldSchemaRenderer — number', () => {
  it('renders a number input', () => {
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'number', label: 'Count' })}
        value={42}
        onChange={vi.fn()}
      />,
    );
    const input = screen.getByRole('spinbutton');
    expect(input).toBeInTheDocument();
    expect(input).toHaveValue(42);
  });

  it('renders with min and max attributes', () => {
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'number', min: 0, max: 100 })}
        value={50}
        onChange={vi.fn()}
      />,
    );
    const input = screen.getByRole('spinbutton');
    expect(input).toHaveAttribute('min', '0');
    expect(input).toHaveAttribute('max', '100');
  });

  it('renders with step attribute', () => {
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'number', step: 5 })}
        value={10}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByRole('spinbutton')).toHaveAttribute('step', '5');
  });

  it('calls onChange with numeric value', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'number' })}
        value={0}
        onChange={onChange}
      />,
    );
    const input = screen.getByRole('spinbutton');
    await user.clear(input);
    await user.type(input, '7');
    expect(onChange).toHaveBeenCalledWith(7);
  });

  it('clamps number to min/max in onChange', () => {
    const onChange = vi.fn();
    const schema: FieldSchema = {
      key: 'n', label: 'N', type: 'number', min: 0, max: 100, default: 50,
    };
    render(<FieldSchemaRenderer schema={schema} value={50} onChange={onChange} />);
    const input = screen.getByRole('spinbutton');
    fireEvent.change(input, { target: { value: '9999' } });
    expect(onChange).toHaveBeenCalledWith(100);
    fireEvent.change(input, { target: { value: '-50' } });
    expect(onChange).toHaveBeenCalledWith(0);
  });
});

// ── boolean ────────────────────────────────────────────────────────

describe('FieldSchemaRenderer — boolean', () => {
  it('renders a switch (checkbox role)', () => {
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'boolean', label: 'Enabled' })}
        value={false}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByRole('switch')).toBeInTheDocument();
  });

  it('switch is checked when value is true', () => {
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'boolean' })}
        value={true}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByRole('switch')).toBeChecked();
  });

  it('switch is unchecked when value is false', () => {
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'boolean' })}
        value={false}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByRole('switch')).not.toBeChecked();
  });

  it('calls onChange when switch is toggled', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'boolean' })}
        value={false}
        onChange={onChange}
      />,
    );
    await user.click(screen.getByRole('switch'));
    expect(onChange).toHaveBeenCalledWith(true);
  });
});

// ── enum ───────────────────────────────────────────────────────────

describe('FieldSchemaRenderer — enum', () => {
  const schema = makeSchema({
    type: 'enum',
    label: 'Theme',
    options: [
      { value: 'light', label: 'Light' },
      { value: 'dark', label: 'Dark' },
    ],
  });

  it('renders a combobox (select)', () => {
    render(
      <FieldSchemaRenderer schema={schema} value="light" onChange={vi.fn()} />,
    );
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('shows options when opened', async () => {
    const user = userEvent.setup();
    render(
      <FieldSchemaRenderer schema={schema} value="" onChange={vi.fn()} />,
    );
    await user.click(screen.getByRole('combobox'));
    expect(screen.getByText('Light')).toBeInTheDocument();
    expect(screen.getByText('Dark')).toBeInTheDocument();
  });

  it('calls onChange with selected option value', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <FieldSchemaRenderer schema={schema} value="" onChange={onChange} />,
    );
    await user.click(screen.getByRole('combobox'));
    await user.click(screen.getByText('Dark'));
    expect(onChange).toHaveBeenCalledWith('dark');
  });
});

// ── color ──────────────────────────────────────────────────────────

describe('FieldSchemaRenderer — color', () => {
  it('renders a color input', () => {
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'color', label: 'Background' })}
        value="#ff0000"
        onChange={vi.fn()}
      />,
    );
    const input = document.querySelector('input[type="color"]');
    expect(input).toBeInTheDocument();
    expect(input).toHaveValue('#ff0000');
  });

  it('defaults to black when no value provided', () => {
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'color' })}
        value={undefined}
        onChange={vi.fn()}
      />,
    );
    const input = document.querySelector('input[type="color"]');
    expect(input).toHaveValue('#000000');
  });

  it('calls onChange with hex color string', () => {
    const onChange = vi.fn();
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'color' })}
        value="#000000"
        onChange={onChange}
      />,
    );
    const input = document.querySelector('input[type="color"]') as HTMLInputElement;
    // fireEvent.change is required for color inputs in jsdom
    // (userEvent.type does not trigger onChange on color inputs)
    fireEvent.change(input, { target: { value: '#abcdef' } });
    expect(onChange).toHaveBeenCalledWith('#abcdef');
  });
});

// ── entity-ref ─────────────────────────────────────────────────────

describe('FieldSchemaRenderer — entity-ref', () => {
  it('renders EntityCombobox (not a plain text input)', () => {
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'entity-ref', entityType: 'node', label: 'Node' })}
        value=""
        onChange={vi.fn()}
      />,
    );
    // Our mock renders data-testid="entity-combobox"
    expect(screen.getByTestId('entity-combobox')).toBeInTheDocument();
  });

  it('passes current value to EntityCombobox', () => {
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'entity-ref', entityType: 'node' })}
        value="my-node-id"
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId('entity-combobox')).toHaveValue('my-node-id');
  });

  it('calls onChange when EntityCombobox selection changes', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'entity-ref', entityType: 'node' })}
        value=""
        onChange={onChange}
      />,
    );
    // The mock renders a plain input; simulate value change
    await user.type(screen.getByTestId('entity-combobox'), 'n');
    expect(onChange).toHaveBeenCalledWith(expect.stringContaining('n'));
  });

  it('renders for service entity type', () => {
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'entity-ref', entityType: 'service' })}
        value=""
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId('entity-combobox')).toBeInTheDocument();
  });

  it('renders EntityCombobox for network entity type', () => {
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'entity-ref', entityType: 'network' })}
        value=""
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId('entity-combobox')).toBeInTheDocument();
  });

  it('renders EntityCombobox for group entity type', () => {
    render(
      <FieldSchemaRenderer
        schema={makeSchema({ type: 'entity-ref', entityType: 'group' })}
        value=""
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId('entity-combobox')).toBeInTheDocument();
  });

  it('renders error message when entity-ref schema lacks entityType', () => {
    const schema: FieldSchema = { key: 'x', label: 'X', type: 'entity-ref' };
    render(<FieldSchemaRenderer schema={schema} value="" onChange={() => {}} />);
    expect(screen.getByText(/missing entityType/i)).toBeInTheDocument();
  });
});
