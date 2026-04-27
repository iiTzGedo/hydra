/**
 * Tests for WidgetConfiguratorPopover component.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WidgetConfiguratorPopover } from '@/components/dashboard/widget-configurator-popover';
import type { DashboardWidgetInstance, WidgetTypeDefinition } from '@/types/dashboard';

// ── Mocks ──────────────────────────────────────────────────────────

// Mock EntityCombobox used inside FieldSchemaRenderer
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

// ── Fixtures ───────────────────────────────────────────────────────

function makeTypeDef(overrides?: Partial<WidgetTypeDefinition>): WidgetTypeDefinition {
  return {
    widgetType: 'hydra::metric-card',
    displayName: 'Metric Card',
    description: 'Displays a single metric',
    category: 'data-display',
    icon: 'metric-card',
    source: 'hydra',
    version: '1.0.0',
    supportedDataShapes: [],
    tags: [],
    permissions: { view: [], interact: [] },
    defaultSize: { w: 4, h: 3 },
    minSize: { w: 2, h: 2 },
    maxSize: { w: 12, h: 12 },
    capabilities: {
      configurable: true,
      supportsVisibilityToggle: true,
      repeatable: true,
    },
    kioskMode: 'render',
    isAvailable: true,
    configSchema: [],
    ...overrides,
  };
}

function makeInstance(overrides?: Partial<DashboardWidgetInstance>): DashboardWidgetInstance {
  return {
    instanceId: 'inst-001',
    widgetType: 'hydra::metric-card',
    position: { x: 0, y: 0, w: 4, h: 3 },
    placements: { lg: { x: 0, y: 0, w: 4, h: 3 } },
    config: {},
    dataBinding: null,
    ...overrides,
  };
}

// ── Default props ──────────────────────────────────────────────────

interface PopoverRenderProps {
  typeDef?: WidgetTypeDefinition;
  instance?: DashboardWidgetInstance;
  open?: boolean;
  onConfigChange?: ReturnType<typeof vi.fn>;
  onSizeChange?: ReturnType<typeof vi.fn>;
  onRefreshChange?: ReturnType<typeof vi.fn>;
  onDelete?: ReturnType<typeof vi.fn>;
  onDuplicate?: ReturnType<typeof vi.fn>;
  onOpenDataBinding?: ReturnType<typeof vi.fn>;
}

function renderPopover(props: PopoverRenderProps = {}) {
  const {
    typeDef = makeTypeDef(),
    instance = makeInstance(),
    open = true,
    onConfigChange = vi.fn(),
    onSizeChange = vi.fn(),
    onRefreshChange = vi.fn(),
    onDelete = vi.fn(),
    onDuplicate = vi.fn(),
    onOpenDataBinding = vi.fn(),
  } = props;

  return render(
    <WidgetConfiguratorPopover
      typeDef={typeDef}
      instance={instance}
      open={open}
      trigger={<button type="button">Open</button>}
      onConfigChange={onConfigChange}
      onSizeChange={onSizeChange}
      onRefreshChange={onRefreshChange}
      onDelete={onDelete}
      onDuplicate={onDuplicate}
      onOpenDataBinding={onOpenDataBinding}
    />,
  );
}

// ── Tests ──────────────────────────────────────────────────────────

describe('WidgetConfiguratorPopover', () => {
  describe('rendering', () => {
    it('renders widget display name in header', () => {
      renderPopover();
      expect(screen.getByText('Metric Card')).toBeInTheDocument();
    });

    it('renders instance ID in header', () => {
      renderPopover({ instance: makeInstance({ instanceId: 'inst-123' }) });
      expect(screen.getByText('inst-123')).toBeInTheDocument();
    });

    it('renders title input', () => {
      renderPopover({ instance: makeInstance({ config: { title: 'My Widget' } }) });
      expect(screen.getByLabelText('Title')).toHaveValue('My Widget');
    });

    it('renders size preset buttons S, M, L, XL', () => {
      renderPopover();
      expect(screen.getByTitle('2 × 2')).toBeInTheDocument(); // S
      expect(screen.getByTitle('4 × 3')).toBeInTheDocument(); // M
      expect(screen.getByTitle('6 × 4')).toBeInTheDocument(); // L
      expect(screen.getByTitle('12 × 6')).toBeInTheDocument(); // XL
    });

    it('renders refresh interval select when onRefreshChange is provided', () => {
      renderPopover();
      expect(screen.getByLabelText('Refresh')).toBeInTheDocument();
    });

    it('does not render refresh section when onRefreshChange is omitted', () => {
      render(
        <WidgetConfiguratorPopover
          typeDef={makeTypeDef()}
          instance={makeInstance()}
          open={true}
          trigger={<button type="button">Open</button>}
          onConfigChange={vi.fn()}
          onSizeChange={vi.fn()}
          onDelete={vi.fn()}
          onDuplicate={vi.fn()}
          onOpenDataBinding={vi.fn()}
        />,
      );
      expect(screen.queryByLabelText('Refresh')).not.toBeInTheDocument();
    });

    it('renders Duplicate and Remove action buttons', () => {
      renderPopover();
      expect(screen.getByRole('button', { name: /duplicate/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /remove/i })).toBeInTheDocument();
    });

    it('renders "Edit data binding…" footer button', () => {
      renderPopover();
      expect(screen.getByRole('button', { name: /edit data binding/i })).toBeInTheDocument();
    });

    it('renders configSchema fields when schema is non-empty', () => {
      const typeDef = makeTypeDef({
        configSchema: [
          { key: 'label', label: 'Label Text', type: 'string' },
          { key: 'showBorder', label: 'Show Border', type: 'boolean' },
        ],
      });
      renderPopover({ typeDef });
      expect(screen.getByLabelText('Label Text')).toBeInTheDocument();
      expect(screen.getByRole('switch', { name: 'Show Border' })).toBeInTheDocument();
    });

    it('does not render "Widget Settings" section when configSchema is empty', () => {
      renderPopover({ typeDef: makeTypeDef({ configSchema: [] }) });
      expect(screen.queryByText('Widget Settings')).not.toBeInTheDocument();
    });
  });

  describe('size presets', () => {
    it('clicking S calls onSizeChange with { w: 2, h: 2 }', async () => {
      const user = userEvent.setup();
      const onSizeChange = vi.fn();
      renderPopover({ onSizeChange });

      await user.click(screen.getByTitle('2 × 2'));
      expect(onSizeChange).toHaveBeenCalledWith({ w: 2, h: 2 });
    });

    it('clicking M calls onSizeChange with { w: 4, h: 3 }', async () => {
      const user = userEvent.setup();
      const onSizeChange = vi.fn();
      renderPopover({ onSizeChange });

      await user.click(screen.getByTitle('4 × 3'));
      expect(onSizeChange).toHaveBeenCalledWith({ w: 4, h: 3 });
    });

    it('clicking L calls onSizeChange with { w: 6, h: 4 }', async () => {
      const user = userEvent.setup();
      const onSizeChange = vi.fn();
      renderPopover({ onSizeChange });

      await user.click(screen.getByTitle('6 × 4'));
      expect(onSizeChange).toHaveBeenCalledWith({ w: 6, h: 4 });
    });

    it('clicking XL calls onSizeChange with { w: 12, h: 6 }', async () => {
      const user = userEvent.setup();
      const onSizeChange = vi.fn();
      renderPopover({ onSizeChange });

      await user.click(screen.getByTitle('12 × 6'));
      expect(onSizeChange).toHaveBeenCalledWith({ w: 12, h: 6 });
    });

    it('active size preset button has primary styling when matching current placement', () => {
      // M is 4×3 which matches the default placement
      renderPopover({
        instance: makeInstance({ placements: { lg: { x: 0, y: 0, w: 4, h: 3 } } }),
      });
      const mBtn = screen.getByTitle('4 × 3');
      expect(mBtn.className).toContain('border-primary');
    });
  });

  describe('refresh interval', () => {
    it('calls onRefreshChange with numeric seconds when changed', async () => {
      const user = userEvent.setup();
      const onRefreshChange = vi.fn();
      renderPopover({ onRefreshChange });

      await user.click(screen.getByLabelText('Refresh'));
      const option = screen.getByRole('option', { name: '30s' });
      await user.click(option);
      expect(onRefreshChange).toHaveBeenCalledWith(30);
    });

    it('calls onRefreshChange with 0 when "Off" is selected', async () => {
      const user = userEvent.setup();
      const onRefreshChange = vi.fn();
      renderPopover({
        onRefreshChange,
        instance: makeInstance({ config: { refreshInterval: 30 } }),
      });

      await user.click(screen.getByLabelText('Refresh'));
      const option = screen.getByRole('option', { name: 'Off' });
      await user.click(option);
      expect(onRefreshChange).toHaveBeenCalledWith(0);
    });
  });

  describe('title field', () => {
    it('changing title input calls onConfigChange with "title" key', async () => {
      const user = userEvent.setup();
      const onConfigChange = vi.fn();
      renderPopover({ onConfigChange, instance: makeInstance({ config: { title: '' } }) });

      await user.type(screen.getByLabelText('Title'), 'My Title');
      expect(onConfigChange).toHaveBeenCalledWith('title', expect.stringContaining('M'));
    });
  });

  describe('actions', () => {
    it('clicking Duplicate calls onDuplicate', async () => {
      const user = userEvent.setup();
      const onDuplicate = vi.fn();
      renderPopover({ onDuplicate });

      await user.click(screen.getByRole('button', { name: /duplicate/i }));
      expect(onDuplicate).toHaveBeenCalledOnce();
    });

    it('clicking Remove calls onDelete', async () => {
      const user = userEvent.setup();
      const onDelete = vi.fn();
      renderPopover({ onDelete });

      await user.click(screen.getByRole('button', { name: /remove/i }));
      expect(onDelete).toHaveBeenCalledOnce();
    });

    it('clicking "Edit data binding…" calls onOpenDataBinding', async () => {
      const user = userEvent.setup();
      const onOpenDataBinding = vi.fn();
      renderPopover({ onOpenDataBinding });

      await user.click(screen.getByRole('button', { name: /edit data binding/i }));
      expect(onOpenDataBinding).toHaveBeenCalledOnce();
    });
  });

  describe('configSchema field changes', () => {
    it('changing a string schema field calls onConfigChange with field key', async () => {
      const user = userEvent.setup();
      const onConfigChange = vi.fn();
      const typeDef = makeTypeDef({
        configSchema: [{ key: 'unit', label: 'Unit', type: 'string' }],
      });
      renderPopover({ typeDef, onConfigChange });

      await user.type(screen.getByLabelText('Unit'), 'GB');
      expect(onConfigChange).toHaveBeenCalledWith('unit', expect.stringContaining('G'));
    });

    it('toggling a boolean schema field calls onConfigChange', async () => {
      const user = userEvent.setup();
      const onConfigChange = vi.fn();
      const typeDef = makeTypeDef({
        configSchema: [{ key: 'showIcon', label: 'Show Icon', type: 'boolean' }],
      });
      renderPopover({ typeDef, onConfigChange });

      await user.click(screen.getByRole('switch', { name: 'Show Icon' }));
      expect(onConfigChange).toHaveBeenCalledWith('showIcon', true);
    });
  });
});
