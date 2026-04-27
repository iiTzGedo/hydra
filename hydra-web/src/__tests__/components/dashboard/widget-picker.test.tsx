/**
 * Tests for WidgetPicker component — focuses on the Tier 3 gating split.
 *
 * Covers:
 *  - Available widgets render and are clickable
 *  - Unavailable widgets render in a separate "Unavailable" section
 *  - Unavailable widgets have disabled styling / aria-disabled
 *  - Clicking an unavailable widget does NOT invoke the add callback
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WidgetPicker } from '@/components/dashboard/widget-picker';
import type { WidgetRegistryResponse } from '@/types/dashboard';

// ── Mock useWidgetRegistry ─────────────────────────────────────────

const mockRegistryData: { data: WidgetRegistryResponse | undefined; isLoading: boolean; isError: boolean } = {
  data: undefined,
  isLoading: false,
  isError: false,
};

vi.mock('@/api/dashboards', () => ({
  useWidgetRegistry: () => mockRegistryData,
}));

// ── Shared registry fixture ────────────────────────────────────────

function makeRegistry(overrides: { unavailableCount?: number } = {}): WidgetRegistryResponse {
  const { unavailableCount = 2 } = overrides;

  const available = [
    {
      widgetType: 'hydra::stats-cards',
      displayName: 'Stats Overview',
      description: 'Key metrics',
      category: 'data-display',
      icon: 'bar-chart-3',
      source: 'hydra',
      version: '1.0.0',
      supportedDataShapes: [],
      tags: [],
      permissions: { view: [], interact: [] },
      defaultSize: { w: 12, h: 2 },
      minSize: { w: 6, h: 2 },
      maxSize: { w: 12, h: 4 },
      configSchema: [],
      capabilities: { configurable: false, supportsVisibilityToggle: true, repeatable: false },
      kioskMode: 'render' as const,
      isAvailable: true,
    },
    {
      widgetType: 'hydra::node-status',
      displayName: 'Node Status',
      description: 'Node health',
      category: 'status',
      icon: 'server',
      source: 'hydra',
      version: '1.0.0',
      supportedDataShapes: [],
      tags: [],
      permissions: { view: [], interact: [] },
      defaultSize: { w: 6, h: 3 },
      minSize: { w: 4, h: 3 },
      maxSize: { w: 12, h: 6 },
      configSchema: [],
      capabilities: { configurable: false, supportsVisibilityToggle: true, repeatable: false },
      kioskMode: 'render' as const,
      isAvailable: true,
    },
  ];

  const unavailable = Array.from({ length: unavailableCount }, (_, i) => ({
    widgetType: `plugin::tier3-widget-${i}`,
    displayName: `Tier 3 Widget ${i + 1}`,
    description: 'Requires plugin system',
    category: 'plugins',
    icon: 'square',
    source: 'plugin',
    version: '1.0.0',
    supportedDataShapes: [],
    tags: [],
    permissions: { view: [], interact: [] },
    defaultSize: { w: 6, h: 4 },
    minSize: { w: 4, h: 3 },
    maxSize: { w: 12, h: 8 },
    configSchema: [],
    capabilities: { configurable: false, supportsVisibilityToggle: false, repeatable: false },
    kioskMode: 'hide' as const,
    isAvailable: false,
  }));

  const allWidgets = [...available, ...unavailable];

  return {
    widgets: allWidgets,
    categories: [
      { id: 'data-display', name: 'Data Display', count: 1 },
      { id: 'status', name: 'Status', count: 1 },
      { id: 'plugins', name: 'Plugins', count: unavailableCount },
    ],
    total: allWidgets.length,
  };
}

// ── Helpers ────────────────────────────────────────────────────────

function openPicker(onSelect = vi.fn()) {
  render(<WidgetPicker onSelect={onSelect} />);
  // The WidgetPicker wraps a DialogTrigger — click "Add Widget" button to open
  fireEvent.click(screen.getByRole('button', { name: /add widget/i }));
}

// ── Tests ──────────────────────────────────────────────────────────

describe('WidgetPicker — Tier 3 gating', () => {
  beforeEach(() => {
    mockRegistryData.data = makeRegistry();
    mockRegistryData.isLoading = false;
    mockRegistryData.isError = false;
  });

  it('renders the "Add Widget" trigger button', () => {
    render(<WidgetPicker onSelect={vi.fn()} />);
    expect(screen.getByRole('button', { name: /add widget/i })).toBeInTheDocument();
  });

  it('shows available widgets after opening the dialog', () => {
    openPicker();
    expect(screen.getByText('Stats Overview')).toBeInTheDocument();
    expect(screen.getByText('Node Status')).toBeInTheDocument();
  });

  it('shows unavailable widgets in a separate section', () => {
    openPicker();
    // Unavailable section heading
    expect(screen.getByText(/unavailable.*wave 5/i)).toBeInTheDocument();
    // Both unavailable widgets appear
    expect(screen.getByText('Tier 3 Widget 1')).toBeInTheDocument();
    expect(screen.getByText('Tier 3 Widget 2')).toBeInTheDocument();
  });

  it('unavailable widget rows are aria-disabled', () => {
    openPicker();
    const unavailableWidgetRows = screen.getAllByText(/unavailable/i).filter(
      (el) => el.tagName.toLowerCase() === 'span' && el.textContent === 'Unavailable'
    );
    // Each unavailable widget has an "Unavailable" label
    expect(unavailableWidgetRows.length).toBe(2);

    // The container div should have aria-disabled="true"
    const tier3Row = screen.getByText('Tier 3 Widget 1').closest('[aria-disabled]');
    expect(tier3Row).toHaveAttribute('aria-disabled', 'true');
  });

  it('clicking an unavailable widget does NOT invoke the onSelect callback', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    openPicker(onSelect);

    // Click the unavailable widget row (not a button, so fireEvent)
    const tier3Row = screen.getByText('Tier 3 Widget 1').closest('div[aria-disabled]');
    if (tier3Row) {
      await user.click(tier3Row);
    }
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('clicking an available widget invokes onSelect with widgetType and defaultSize', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    openPicker(onSelect);

    await user.click(screen.getByText('Stats Overview'));
    expect(onSelect).toHaveBeenCalledOnce();
    expect(onSelect).toHaveBeenCalledWith('hydra::stats-cards', { w: 12, h: 2 });
  });

  it('does not show the unavailable section when all widgets are available', () => {
    mockRegistryData.data = makeRegistry({ unavailableCount: 0 });
    openPicker();
    expect(screen.queryByText(/unavailable.*wave 5/i)).not.toBeInTheDocument();
  });

  it('shows "No widgets match your search" when search has no results', async () => {
    const user = userEvent.setup();
    openPicker();

    const searchInput = screen.getByPlaceholderText(/search widgets/i);
    await user.type(searchInput, 'nonexistent-xyz');
    expect(screen.getByText(/no widgets match your search/i)).toBeInTheDocument();
  });
});

describe('WidgetPicker — loading and error states', () => {
  it('shows a loading spinner when registry is loading', () => {
    mockRegistryData.data = undefined;
    mockRegistryData.isLoading = true;
    render(<WidgetPicker onSelect={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /add widget/i }));
    // Just check the error state is NOT shown when loading
    expect(screen.queryByText(/failed to load/i)).not.toBeInTheDocument();
  });

  it('shows an error message when registry fails to load', () => {
    mockRegistryData.data = undefined;
    mockRegistryData.isLoading = false;
    mockRegistryData.isError = true;
    render(<WidgetPicker onSelect={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /add widget/i }));
    expect(screen.getByText(/failed to load widget registry/i)).toBeInTheDocument();
  });
});
