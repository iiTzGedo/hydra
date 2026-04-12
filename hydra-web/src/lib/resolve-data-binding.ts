/**
 * Data binding resolution layer for dashboard widgets.
 *
 * Per Dashboard Technical Specification §6, resolves a DataBinding's source
 * prefix to the appropriate fetcher, calls the API, and applies transforms.
 *
 * Source prefixes handled:
 * - `hydra::` — Direct API call via apiClient
 * - `static::` — Inline data from the binding's query.data field
 * - `computed::` — Client-side computation
 * - `external::` — HTTP fetch to external URLs
 * - `plg::` / `ws::` — Deferred to Wave 5
 */

import { apiClient } from '@/lib/api-client';
import { applyTransform } from '@/lib/widget-transforms';
import type { DashboardDataBindingQuery } from '@/types/dashboard';

interface BindingLike {
  source: string;
  query: DashboardDataBindingQuery;
}

function getSourcePrefix(source: string): string {
  const idx = source.indexOf('::');
  return idx >= 0 ? source.slice(0, idx + 2) : source;
}

/**
 * Substitute `{placeholder}` tokens in a string or in object values.
 */
export function substituteParams(
  target: Record<string, unknown> | undefined,
  params: Record<string, unknown>,
): Record<string, unknown> | undefined {
  if (!target) return target;

  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(target)) {
    if (typeof value === 'string') {
      result[key] = value.replace(/\{(\w+)\}/g, (_match, paramKey: string) => {
        return String(params[paramKey] ?? `{${paramKey}}`);
      });
    } else {
      result[key] = value;
    }
  }
  return result;
}

// ── Source resolvers ─────────────────────────────────────────────────

async function resolveHydraBinding(binding: BindingLike): Promise<unknown> {
  const query = binding.query;
  const endpoint = query.endpoint;

  if (!endpoint || typeof endpoint !== 'string') {
    throw new Error(`hydra:: binding missing query.endpoint (source: ${binding.source})`);
  }

  const params = query.params as Record<string, unknown> | undefined;

  const response = await apiClient.get<{ data: unknown }>(endpoint, {
    params: params ?? undefined,
  });

  // The Hydra API wraps all responses in { data: T, meta?: ... }
  let data: unknown = response.data?.data ?? response.data;

  // Apply transform if specified
  if (query.transform) {
    data = applyTransform(data, query.transform);
  }

  return data;
}

function resolveStaticBinding(binding: BindingLike): unknown {
  const data = binding.query.data;
  if (binding.query.transform) {
    return applyTransform(data, binding.query.transform);
  }
  return data ?? null;
}

function resolveComputedBinding(binding: BindingLike): unknown {
  // Computed bindings evaluate client-side expressions.
  // For Wave 2, support basic computed sources:
  const source = binding.source;

  if (source === 'computed::current-time') {
    return { timestamp: Date.now(), iso: new Date().toISOString() };
  }

  // Default: return the query data as-is (custom computed sources are a
  // Wave 4+ extension).
  return binding.query.data ?? null;
}

async function resolveExternalBinding(binding: BindingLike): Promise<unknown> {
  const url = binding.query.endpoint;
  if (!url || typeof url !== 'string') {
    throw new Error(`external:: binding missing query.endpoint (source: ${binding.source})`);
  }

  const response = await fetch(url, {
    headers: { Accept: 'application/json' },
    signal: AbortSignal.timeout(10_000),
  });

  if (!response.ok) {
    throw new Error(`External fetch failed: ${response.status} ${response.statusText}`);
  }

  let data: unknown = await response.json();

  if (binding.query.transform) {
    data = applyTransform(data, binding.query.transform);
  }

  return data;
}

// ── Main dispatcher ──────────────────────────────────────────────────

/**
 * Resolve a data binding by dispatching to the appropriate source handler.
 *
 * @param binding  The data binding configuration from a widget instance
 * @returns        The resolved (and optionally transformed) data
 */
export async function resolveDataBinding(binding: BindingLike): Promise<unknown> {
  const prefix = getSourcePrefix(binding.source);

  switch (prefix) {
    case 'hydra::':
      return resolveHydraBinding(binding);
    case 'static::':
      return resolveStaticBinding(binding);
    case 'computed::':
      return resolveComputedBinding(binding);
    case 'external::':
      return resolveExternalBinding(binding);
    case 'plg::':
    case 'ws::':
      throw new Error(`Source prefix "${prefix}" is not yet supported (Wave 5)`);
    default:
      throw new Error(`Unknown data binding source prefix: "${prefix}" (source: ${binding.source})`);
  }
}
