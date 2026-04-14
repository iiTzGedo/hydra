/**
 * Data Binding Editor — visual configuration UI for widget data bindings.
 *
 * Per Dashboard Technical Specification §6 and §14 (P2DASH-T034):
 * - Source selector (hydra::, static::, computed::, external::)
 * - Endpoint picker for hydra:: sources
 * - Query parameter builder (key-value pairs)
 * - Transform chain selector
 * - Refresh interval and fallback strategy
 */

import { useState, useCallback } from 'react';
import {
  Database,
  FileJson,
  Calculator,
  Globe,
  Plus,
  Trash2,
  RefreshCcw,
  AlertTriangle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { DashboardDataBinding, DashboardDataBindingQuery } from '@/types/dashboard';

// ── Constants ──────────────────────────────────────────────────────

const SOURCE_PREFIXES = [
  { value: 'hydra::', label: 'Hydra API', icon: Database, description: 'Query Hydra API endpoints' },
  { value: 'static::', label: 'Static Data', icon: FileJson, description: 'Inline static data' },
  { value: 'computed::', label: 'Computed', icon: Calculator, description: 'Client-side computation' },
  { value: 'external::', label: 'External URL', icon: Globe, description: 'HTTP fetch from external URL' },
] as const;

const HYDRA_ENDPOINTS = [
  { value: '/nodes', label: 'Nodes', description: 'All infrastructure nodes' },
  { value: '/nodes/stats', label: 'Node Stats', description: 'Aggregated node statistics' },
  { value: '/services', label: 'Services', description: 'All tracked services' },
  { value: '/services/stats', label: 'Service Stats', description: 'Aggregated service statistics' },
  { value: '/profiles', label: 'Profiles', description: 'Profile snapshots' },
  { value: '/networks', label: 'Networks', description: 'Network spaces' },
  { value: '/groups', label: 'Groups', description: 'Logical groupings' },
  { value: '/topologies', label: 'Topologies', description: 'Topology graphs' },
  { value: '/health', label: 'Health', description: 'System health status' },
] as const;

const TRANSFORM_OPS = [
  { value: 'count', label: 'Count', description: 'Count items in array' },
  { value: 'sum', label: 'Sum', description: 'Sum numeric field' },
  { value: 'avg', label: 'Average', description: 'Average numeric field' },
  { value: 'min', label: 'Min', description: 'Minimum value' },
  { value: 'max', label: 'Max', description: 'Maximum value' },
  { value: 'group_by', label: 'Group By', description: 'Group by field' },
  { value: 'filter', label: 'Filter', description: 'Filter by condition' },
  { value: 'sort', label: 'Sort', description: 'Sort by field' },
  { value: 'unique', label: 'Unique', description: 'Deduplicate values' },
  { value: 'first', label: 'First', description: 'First item' },
  { value: 'last', label: 'Last', description: 'Last item' },
  { value: 'rate', label: 'Rate', description: 'Rate of change' },
  { value: 'map', label: 'Map', description: 'Reshape fields' },
] as const;

const FALLBACK_STRATEGIES = [
  { value: 'cached', label: 'Use Cached', description: 'Show last known data' },
  { value: 'empty', label: 'Show Empty', description: 'Display empty state' },
  { value: 'error', label: 'Show Error', description: 'Display error message' },
] as const;

// ── Props ──────────────────────────────────────────────────────────

interface DataBindingEditorProps {
  value: DashboardDataBinding | null;
  onChange: (binding: DashboardDataBinding | null) => void;
  className?: string;
}

// ── Component ──────────────────────────────────────────────────────

export function DataBindingEditor({ value, onChange, className }: DataBindingEditorProps) {
  const [activeTab, setActiveTab] = useState<'source' | 'query' | 'transform' | 'options'>('source');

  const sourcePrefix = value?.source ? getSourcePrefix(value.source) : '';
  const sourceSuffix = value?.source ? value.source.slice(sourcePrefix.length) : '';

  const handleSourcePrefixChange = useCallback((prefix: string) => {
    onChange({
      source: prefix,
      query: {},
      refreshInterval: value?.refreshInterval ?? null,
      realtimeChannel: value?.realtimeChannel ?? null,
      fallback: value?.fallback ?? null,
    });
  }, [onChange, value]);

  const handleEndpointChange = useCallback((endpoint: string) => {
    onChange({
      ...value!,
      source: `hydra::${endpoint}`,
      query: { ...value?.query, endpoint },
    });
  }, [onChange, value]);

  const handleQueryChange = useCallback((query: DashboardDataBindingQuery) => {
    if (!value) return;
    onChange({ ...value, query });
  }, [onChange, value]);

  const handleTransformChange = useCallback((transform: string | Record<string, unknown> | undefined) => {
    if (!value) return;
    onChange({
      ...value,
      query: { ...value.query, transform },
    });
  }, [onChange, value]);

  const handleRefreshChange = useCallback((seconds: number | null) => {
    if (!value) return;
    onChange({ ...value, refreshInterval: seconds });
  }, [onChange, value]);

  const handleFallbackChange = useCallback((type: 'cached' | 'empty' | 'error') => {
    if (!value) return;
    onChange({
      ...value,
      fallback: { type, maxAge: type === 'cached' ? 300 : null },
    });
  }, [onChange, value]);

  const handleClear = useCallback(() => {
    onChange(null);
  }, [onChange]);

  return (
    <div className={cn('rounded-lg border bg-card', className)}>
      {/* Tab Bar */}
      <div className="flex border-b">
        {(['source', 'query', 'transform', 'options'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              'flex-1 px-3 py-2 text-xs font-medium capitalize transition-colors',
              activeTab === tab
                ? 'border-b-2 border-primary text-primary'
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="p-3 space-y-3">
        {/* Source Tab */}
        {activeTab === 'source' && (
          <div className="space-y-3">
            <div className="text-xs font-medium text-muted-foreground">Data Source</div>
            <div className="grid grid-cols-2 gap-2">
              {SOURCE_PREFIXES.map((src) => (
                <button
                  key={src.value}
                  onClick={() => handleSourcePrefixChange(src.value)}
                  className={cn(
                    'flex items-center gap-2 rounded-lg border p-2 text-left transition-colors',
                    sourcePrefix === src.value
                      ? 'border-primary bg-primary/5'
                      : 'hover:bg-muted'
                  )}
                >
                  <src.icon className="h-4 w-4 shrink-0" />
                  <div>
                    <div className="text-xs font-medium">{src.label}</div>
                    <div className="text-[10px] text-muted-foreground">{src.description}</div>
                  </div>
                </button>
              ))}
            </div>

            {sourcePrefix === 'hydra::' && (
              <div className="space-y-2">
                <div className="text-xs font-medium text-muted-foreground">API Endpoint</div>
                <div className="space-y-1">
                  {HYDRA_ENDPOINTS.map((ep) => (
                    <button
                      key={ep.value}
                      onClick={() => handleEndpointChange(ep.value)}
                      className={cn(
                        'flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs transition-colors',
                        sourceSuffix === ep.value || value?.query?.endpoint === ep.value
                          ? 'bg-primary/10 text-primary font-medium'
                          : 'hover:bg-muted'
                      )}
                    >
                      <span className="font-mono text-[10px] text-muted-foreground w-24 shrink-0">
                        {ep.value}
                      </span>
                      <span>{ep.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {sourcePrefix === 'external::' && (
              <div className="space-y-2">
                <div className="text-xs font-medium text-muted-foreground">External URL</div>
                <input
                  type="url"
                  value={(value?.query?.endpoint as string) || ''}
                  onChange={(e) => handleQueryChange({ ...value?.query, endpoint: e.target.value })}
                  placeholder="https://api.example.com/data"
                  className="w-full rounded border bg-background px-2 py-1.5 text-xs outline-none focus:border-primary"
                />
              </div>
            )}

            {value && (
              <button
                onClick={handleClear}
                className="flex items-center gap-1 text-xs text-destructive hover:underline"
              >
                <Trash2 className="h-3 w-3" />
                Remove binding
              </button>
            )}
          </div>
        )}

        {/* Query Tab */}
        {activeTab === 'query' && (
          <QueryParamsEditor
            params={value?.query?.params as Record<string, string> | undefined}
            onChange={(params) => handleQueryChange({ ...value?.query, params })}
            disabled={!value?.source}
          />
        )}

        {/* Transform Tab */}
        {activeTab === 'transform' && (
          <TransformEditor
            value={value?.query?.transform}
            onChange={handleTransformChange}
            disabled={!value?.source}
          />
        )}

        {/* Options Tab */}
        {activeTab === 'options' && (
          <div className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                <RefreshCcw className="h-3 w-3" />
                Refresh Interval
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={5}
                  max={3600}
                  value={value?.refreshInterval ?? ''}
                  onChange={(e) => handleRefreshChange(e.target.value ? Number(e.target.value) : null)}
                  placeholder="30"
                  className="w-20 rounded border bg-background px-2 py-1 text-xs outline-none focus:border-primary"
                  disabled={!value?.source}
                />
                <span className="text-xs text-muted-foreground">seconds</span>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                <AlertTriangle className="h-3 w-3" />
                Fallback Strategy
              </div>
              <div className="space-y-1">
                {FALLBACK_STRATEGIES.map((fb) => (
                  <button
                    key={fb.value}
                    onClick={() => handleFallbackChange(fb.value)}
                    disabled={!value?.source}
                    className={cn(
                      'flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs transition-colors',
                      value?.fallback?.type === fb.value
                        ? 'bg-primary/10 text-primary font-medium'
                        : 'hover:bg-muted',
                      !value?.source && 'opacity-50 cursor-not-allowed'
                    )}
                  >
                    <span className="font-medium">{fb.label}</span>
                    <span className="text-muted-foreground">{fb.description}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Query Params Editor ────────────────────────────────────────────

interface QueryParamsEditorProps {
  params?: Record<string, string>;
  onChange: (params: Record<string, string>) => void;
  disabled?: boolean;
}

function QueryParamsEditor({ params, onChange, disabled }: QueryParamsEditorProps) {
  const entries = Object.entries(params || {});

  const handleAdd = () => {
    onChange({ ...params, '': '' });
  };

  const handleRemove = (key: string) => {
    const next = { ...params };
    delete next[key];
    onChange(next);
  };

  const handleKeyChange = (oldKey: string, newKey: string) => {
    const next: Record<string, string> = {};
    for (const [k, v] of Object.entries(params || {})) {
      next[k === oldKey ? newKey : k] = v;
    }
    onChange(next);
  };

  const handleValueChange = (key: string, newValue: string) => {
    onChange({ ...params, [key]: newValue });
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-xs font-medium text-muted-foreground">Query Parameters</div>
        <button
          onClick={handleAdd}
          disabled={disabled}
          className={cn(
            'flex items-center gap-1 text-xs text-primary hover:underline',
            disabled && 'opacity-50 cursor-not-allowed'
          )}
        >
          <Plus className="h-3 w-3" />
          Add
        </button>
      </div>

      {entries.length === 0 ? (
        <div className="py-4 text-center text-xs text-muted-foreground">
          No query parameters configured
        </div>
      ) : (
        <div className="space-y-2">
          {entries.map(([key, val], i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                type="text"
                value={key}
                onChange={(e) => handleKeyChange(key, e.target.value)}
                placeholder="key"
                className="w-28 rounded border bg-background px-2 py-1 text-xs font-mono outline-none focus:border-primary"
              />
              <span className="text-xs text-muted-foreground">=</span>
              <input
                type="text"
                value={val}
                onChange={(e) => handleValueChange(key, e.target.value)}
                placeholder="value"
                className="flex-1 rounded border bg-background px-2 py-1 text-xs font-mono outline-none focus:border-primary"
              />
              <button
                onClick={() => handleRemove(key)}
                className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Transform Editor ───────────────────────────────────────────────

interface TransformEditorProps {
  value?: string | Record<string, unknown>;
  onChange: (transform: string | Record<string, unknown> | undefined) => void;
  disabled?: boolean;
}

function TransformEditor({ value, onChange, disabled }: TransformEditorProps) {
  const currentOp = typeof value === 'string' ? value : undefined;
  const currentChain = typeof value === 'object' && value !== null && 'chain' in value
    ? (value.chain as string[])
    : undefined;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-xs font-medium text-muted-foreground">Transform Pipeline</div>
        {value && (
          <button
            onClick={() => onChange(undefined)}
            className="text-xs text-destructive hover:underline"
          >
            Clear
          </button>
        )}
      </div>

      <div className="grid grid-cols-3 gap-1">
        {TRANSFORM_OPS.map((op) => (
          <button
            key={op.value}
            onClick={() => {
              if (currentChain) {
                onChange({ chain: [...currentChain, op.value] });
              } else if (currentOp) {
                onChange({ chain: [currentOp, op.value] });
              } else {
                onChange(op.value);
              }
            }}
            disabled={disabled}
            className={cn(
              'rounded border px-2 py-1.5 text-[10px] transition-colors',
              (currentOp === op.value || currentChain?.includes(op.value))
                ? 'border-primary bg-primary/10 text-primary font-medium'
                : 'hover:bg-muted',
              disabled && 'opacity-50 cursor-not-allowed'
            )}
            title={op.description}
          >
            {op.label}
          </button>
        ))}
      </div>

      {currentChain && (
        <div className="space-y-1">
          <div className="text-[10px] font-medium text-muted-foreground">Pipeline Order</div>
          <div className="flex flex-wrap gap-1">
            {currentChain.map((step, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary"
              >
                {i > 0 && <span className="text-muted-foreground">→</span>}
                {step}
                <button
                  onClick={() => {
                    const next = currentChain.filter((_, idx) => idx !== i);
                    onChange(next.length === 1 ? next[0] : next.length === 0 ? undefined : { chain: next });
                  }}
                  className="ml-0.5 text-muted-foreground hover:text-destructive"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Helpers ────────────────────────────────────────────────────────

function getSourcePrefix(source: string): string {
  const idx = source.indexOf('::');
  return idx >= 0 ? source.slice(0, idx + 2) : source;
}
