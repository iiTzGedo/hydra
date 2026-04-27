/**
 * Integration tests for WidgetGrid configurator popover wiring.
 *
 * Verifies that clicking a widget in edit mode opens the
 * WidgetConfiguratorPopover, and that its callbacks propagate correctly.
 */

import type { ReactNode } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WidgetGrid } from '@/components/dashboard/widget-grid';
import type { DashboardWidgetInstance, DashboardBoardLayout, WidgetTypeDefinition } from '@/types/dashboard';
import type { WidgetConfiguratorCallbacks } from '@/components/dashboard/widget-grid';

// ── Mocks ──────────────────────────────────────────────────────────

// react-grid-layout depends on browser layout APIs unavailable in jsdom.
// Use a minimal columns layout to avoid ResponsiveGridLayout.
vi.mock('react-grid-layout', () => ({
  ResponsiveGridLayout: ({ children }: { children: ReactNode }) => (
    <div data-testid="rgl">{children}</div>
  ),
  useContainerWidth: () => ({ width: 1200, containerRef: { current: null }, mounted: true }),
}));

// EntityCombobox is used by FieldSchemaRenderer inside the popover
vi.mock('@/components/ui/entity-combobox', () => ({
  EntityCombobox: ({
    value,
    onValueChange,
  }: {
    value: string;
    onValueChange: (v: string) => void;
  }) => (
    <input
      data-testid="entity-combobox"
      value={value}
      onChange={(e) => onValueChange(e.target.value)}
    />
  ),
}));

// ── Fixtures ───────────────────────────────────────────────────────

const COLUMNS_LAYOUT: DashboardBoardLayout = {
  mode: 'columns',
  columnsLayout: {
    columns: [{ id: 'col-1', ratio: 1 }],
    gap: 16,
    padding: [0, 0],
  },
};

function makeWidget(overrides?: Partial<DashboardWidgetInstance>): DashboardWidgetInstance {
  return {
    instanceId: 'widget-abc',
    widgetType: 'hydra::metric-card',
    position: { x: 0, y: 0, w: 4, h: 3 },
    placements: { lg: { x: 0, y: 0, w: 4, h: 3 } },
    config: {},
    dataBinding: null,
    column: 'col-1',
    ...overrides,
  };
}

function makeTypeDef(): WidgetTypeDefinition {
  return {
    widgetType: 'hydra::metric-card',
    displayName: 'Metric Card',
    description: '',
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
  };
}

function makeConfigurator(overrides?: Partial<WidgetConfiguratorCallbacks>): WidgetConfiguratorCallbacks {
  return {
    widgetDefinitions: new Map([['hydra::metric-card', makeTypeDef()]]),
    onWidgetConfigChange: vi.fn(),
    onWidgetSizeChange: vi.fn(),
    onWidgetRefreshChange: vi.fn(),
    onWidgetDuplicate: vi.fn(),
    onWidgetOpenDataBinding: vi.fn(),
    ...overrides,
  };
}

// ── Helper ─────────────────────────────────────────────────────────

function renderGrid(
  {
    widgets = [makeWidget()],
    isEditMode = true,
    // Pass null to signal "explicitly no configurator"; undefined → use default
    configurator,
    onRemoveWidget = vi.fn(),
  }: {
    widgets?: DashboardWidgetInstance[];
    isEditMode?: boolean;
    /** undefined = use default makeConfigurator(), null = explicitly omit */
    configurator?: WidgetConfiguratorCallbacks | null;
    onRemoveWidget?: ReturnType<typeof vi.fn>;
  } = {},
) {
  const resolvedConfigurator =
    configurator === undefined ? makeConfigurator() : (configurator ?? undefined);
  return render(
    <WidgetGrid
      widgets={widgets}
      layout={COLUMNS_LAYOUT}
      isEditMode={isEditMode}
      onRemoveWidget={onRemoveWidget}
      configurator={resolvedConfigurator}
    >
      {widgets.map((w) => (
        <div key={w.instanceId} data-testid={`child-${w.instanceId}`}>
          Widget content
        </div>
      ))}
    </WidgetGrid>,
  );
}

// ── Tests ──────────────────────────────────────────────────────────

describe('WidgetGrid configurator integration', () => {
  it('renders children without configurator when not in edit mode', () => {
    renderGrid({ isEditMode: false, configurator: null });
    expect(screen.getByTestId('child-widget-abc')).toBeInTheDocument();
    // Popover content should not be present (no configurator + not in edit mode)
    expect(screen.queryByText('Metric Card')).not.toBeInTheDocument();
  });

  it('renders children in edit mode without crashing', () => {
    renderGrid();
    expect(screen.getByTestId('child-widget-abc')).toBeInTheDocument();
  });

  it('widget wrapper has role="button" in edit mode with configurator', () => {
    renderGrid();
    expect(screen.getByRole('button', { name: /configure metric card/i })).toBeInTheDocument();
  });

  it('clicking a widget in edit mode opens the configurator popover', async () => {
    const user = userEvent.setup();
    renderGrid();

    await user.click(screen.getByRole('button', { name: /configure metric card/i }));
    // Popover content should now be visible
    expect(screen.getByText('Metric Card')).toBeInTheDocument();
    expect(screen.getByText('widget-abc')).toBeInTheDocument();
  });

  it('clicking a size preset in popover calls onWidgetSizeChange', async () => {
    const user = userEvent.setup();
    const configurator = makeConfigurator();
    renderGrid({ configurator });

    // Open popover
    await user.click(screen.getByRole('button', { name: /configure metric card/i }));
    // Click "L" preset (6 × 4)
    await user.click(screen.getByTitle('6 × 4'));
    expect(configurator.onWidgetSizeChange).toHaveBeenCalledWith('widget-abc', 6, 4);
  });

  it('clicking Duplicate in popover calls onWidgetDuplicate', async () => {
    const user = userEvent.setup();
    const configurator = makeConfigurator();
    renderGrid({ configurator });

    await user.click(screen.getByRole('button', { name: /configure metric card/i }));
    await user.click(screen.getByRole('button', { name: /duplicate/i }));
    expect(configurator.onWidgetDuplicate).toHaveBeenCalledWith('widget-abc');
  });

  it('clicking Remove in popover calls onRemoveWidget', async () => {
    const user = userEvent.setup();
    const onRemoveWidget = vi.fn();
    renderGrid({ onRemoveWidget });

    await user.click(screen.getByRole('button', { name: /configure metric card/i }));
    await user.click(screen.getByRole('button', { name: /^remove$/i }));
    expect(onRemoveWidget).toHaveBeenCalledWith('widget-abc');
  });

  it('clicking "Edit data binding…" calls onWidgetOpenDataBinding', async () => {
    const user = userEvent.setup();
    const configurator = makeConfigurator();
    renderGrid({ configurator });

    await user.click(screen.getByRole('button', { name: /configure metric card/i }));
    await user.click(screen.getByRole('button', { name: /edit data binding/i }));
    expect(configurator.onWidgetOpenDataBinding).toHaveBeenCalledWith('widget-abc');
  });

  it('no configurator popover when configurator prop is not provided', () => {
    renderGrid({ configurator: null });
    expect(screen.queryByRole('button', { name: /configure metric card/i })).not.toBeInTheDocument();
  });

  it('remove button in edit mode calls onRemoveWidget directly (outside popover)', async () => {
    const user = userEvent.setup();
    const onRemoveWidget = vi.fn();
    renderGrid({ onRemoveWidget });

    // The remove button is the dedicated red circle button
    const removeBtn = screen.getByRole('button', { name: /^remove metric card$/i });
    await user.click(removeBtn);
    expect(onRemoveWidget).toHaveBeenCalledWith('widget-abc');
  });

  it('selectedWidgetId is cleared when isEditMode transitions to false', async () => {
    const user = userEvent.setup();
    const widgets = [makeWidget()];
    const configurator = makeConfigurator();

    const { rerender } = render(
      <WidgetGrid
        widgets={widgets}
        layout={COLUMNS_LAYOUT}
        isEditMode={true}
        onRemoveWidget={vi.fn()}
        configurator={configurator}
      >
        <div data-testid="child-widget-abc">Widget content</div>
      </WidgetGrid>,
    );

    // Open popover by clicking the widget
    await user.click(screen.getByRole('button', { name: /configure metric card/i }));
    // Verify popover is open (widget instanceId visible in header)
    expect(screen.getByText('widget-abc')).toBeInTheDocument();

    // Transition to non-edit mode
    act(() => {
      rerender(
        <WidgetGrid
          widgets={widgets}
          layout={COLUMNS_LAYOUT}
          isEditMode={false}
          onRemoveWidget={vi.fn()}
          configurator={configurator}
        >
          <div data-testid="child-widget-abc">Widget content</div>
        </WidgetGrid>,
      );
    });

    // Popover content should no longer be visible
    expect(screen.queryByText('widget-abc')).not.toBeInTheDocument();
  });
});
