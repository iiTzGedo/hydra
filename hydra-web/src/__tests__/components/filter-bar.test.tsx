/**
 * Tests for FilterBar component and related utilities.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderHook, act } from '@testing-library/react';
import { TooltipProvider } from '@/components/ui/tooltip';
import {
  FilterBar,
  getDefaultFilters,
  useFilterState,
  type FilterConfig,
} from '@/components/common/filter-bar';

// FilterBar uses Tooltip which needs a provider
function renderWithProviders(ui: React.ReactElement) {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
}

const searchConfig: FilterConfig = {
  type: 'search',
  key: 'search',
  placeholder: 'Search nodes...',
};

const selectConfig: FilterConfig = {
  type: 'select',
  key: 'status',
  label: 'Status',
  options: [
    { value: 'active', label: 'Active' },
    { value: 'inactive', label: 'Inactive' },
  ],
};

const defaultConfig: FilterConfig[] = [searchConfig, selectConfig];

describe('FilterBar', () => {
  it('renders search input with placeholder', () => {
    renderWithProviders(
      <FilterBar
        filters={{ search: '', status: 'all' }}
        onFilterChange={vi.fn()}
        config={defaultConfig}
      />
    );

    expect(screen.getByPlaceholderText('Search nodes...')).toBeInTheDocument();
  });

  it('renders select filter with all option', () => {
    renderWithProviders(
      <FilterBar
        filters={{ search: '', status: 'all' }}
        onFilterChange={vi.fn()}
        config={defaultConfig}
      />
    );

    // Select trigger should be visible
    expect(screen.getByText('All Status')).toBeInTheDocument();
  });

  it('calls onFilterChange when search input changes', async () => {
    const user = userEvent.setup();
    const onFilterChange = vi.fn();

    renderWithProviders(
      <FilterBar
        filters={{ search: '', status: 'all' }}
        onFilterChange={onFilterChange}
        config={defaultConfig}
      />
    );

    const input = screen.getByPlaceholderText('Search nodes...');
    await user.type(input, 'proxy');

    // Each character triggers a change
    expect(onFilterChange).toHaveBeenCalledWith('search', 'p');
  });

  it('does not show clear button when no active filters', () => {
    renderWithProviders(
      <FilterBar
        filters={{ search: '', status: 'all' }}
        onFilterChange={vi.fn()}
        onClearAll={vi.fn()}
        config={defaultConfig}
      />
    );

    expect(screen.queryByText('Clear')).toBeNull();
  });

  it('shows clear button when search has a value', () => {
    renderWithProviders(
      <FilterBar
        filters={{ search: 'test', status: 'all' }}
        onFilterChange={vi.fn()}
        onClearAll={vi.fn()}
        config={defaultConfig}
      />
    );

    expect(screen.getByText('Clear')).toBeInTheDocument();
  });

  it('shows clear button when select is not "all"', () => {
    renderWithProviders(
      <FilterBar
        filters={{ search: '', status: 'active' }}
        onFilterChange={vi.fn()}
        onClearAll={vi.fn()}
        config={defaultConfig}
      />
    );

    expect(screen.getByText('Clear')).toBeInTheDocument();
  });

  it('calls onClearAll when clear button is clicked', async () => {
    const user = userEvent.setup();
    const onClearAll = vi.fn();

    renderWithProviders(
      <FilterBar
        filters={{ search: 'test', status: 'all' }}
        onFilterChange={vi.fn()}
        onClearAll={onClearAll}
        config={defaultConfig}
      />
    );

    await user.click(screen.getByText('Clear'));
    expect(onClearAll).toHaveBeenCalledOnce();
  });

  it('renders children (extra actions)', () => {
    renderWithProviders(
      <FilterBar
        filters={{ search: '', status: 'all' }}
        onFilterChange={vi.fn()}
        config={defaultConfig}
      >
        <button>Export</button>
      </FilterBar>
    );

    expect(screen.getByText('Export')).toBeInTheDocument();
  });

  it('uses default placeholder when search config has no placeholder', () => {
    const config: FilterConfig[] = [
      { type: 'search', key: 'q' },
    ];

    renderWithProviders(
      <FilterBar
        filters={{ q: '' }}
        onFilterChange={vi.fn()}
        config={config}
      />
    );

    expect(screen.getByPlaceholderText('Search...')).toBeInTheDocument();
  });

  it('uses custom allLabel for select filter', () => {
    const config: FilterConfig[] = [
      {
        type: 'select',
        key: 'type',
        label: 'Type',
        allLabel: 'Any type',
        options: [{ value: 'compute', label: 'Compute' }],
      },
    ];

    renderWithProviders(
      <FilterBar
        filters={{ type: 'all' }}
        onFilterChange={vi.fn()}
        config={config}
      />
    );

    expect(screen.getByText('Any type')).toBeInTheDocument();
  });
});

describe('getDefaultFilters', () => {
  it('returns empty string for search filters', () => {
    const defaults = getDefaultFilters([searchConfig]);
    expect(defaults).toEqual({ search: '' });
  });

  it('returns "all" for select filters', () => {
    const defaults = getDefaultFilters([selectConfig]);
    expect(defaults).toEqual({ status: 'all' });
  });

  it('handles mixed config', () => {
    const defaults = getDefaultFilters(defaultConfig);
    expect(defaults).toEqual({ search: '', status: 'all' });
  });
});

describe('useFilterState', () => {
  it('initializes with provided state', () => {
    const { result } = renderHook(() =>
      useFilterState({ search: '', status: 'all' })
    );

    const [filters] = result.current;
    expect(filters).toEqual({ search: '', status: 'all' });
  });

  it('updates a single filter', () => {
    const { result } = renderHook(() =>
      useFilterState({ search: '', status: 'all' })
    );

    act(() => {
      const [, updateFilter] = result.current;
      updateFilter('search', 'test');
    });

    const [filters] = result.current;
    expect(filters.search).toBe('test');
    expect(filters.status).toBe('all');
  });

  it('clears filters to defaults', () => {
    const { result } = renderHook(() =>
      useFilterState({ search: '', status: 'all' })
    );

    act(() => {
      const [, updateFilter] = result.current;
      updateFilter('search', 'test');
      updateFilter('status', 'active');
    });

    act(() => {
      const [, , clearFilters] = result.current;
      clearFilters();
    });

    const [filters] = result.current;
    // clearFilters: non-empty initial → '', empty initial → 'all'
    // search was '' (empty) → becomes 'all'
    expect(filters.search).toBe('all');
    // status was 'all' (non-empty) → becomes ''
    expect(filters.status).toBe('');
  });
});
