/**
 * Client-side data transform pipeline for dashboard widget bindings.
 *
 * Per Dashboard Technical Specification §6.4, transforms are applied after
 * the data binding layer fetches raw data and before the result is passed
 * to the widget component.
 *
 * Every transform is a pure function: (data: unknown) => unknown.
 * The top-level entry point is {@link applyTransform}.
 */

// ── Helpers ──────────────────────────────────────────────────────────

function toArray(data: unknown): unknown[] {
  if (Array.isArray(data)) return data;
  if (data == null) return [];
  return [data];
}

function getField(item: unknown, field: string): unknown {
  if (item == null || typeof item !== 'object') return undefined;
  return (item as Record<string, unknown>)[field];
}

function toNumber(value: unknown): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

// ── Individual transforms ────────────────────────────────────────────

function transformCount(data: unknown): number {
  return toArray(data).length;
}

function transformSum(data: unknown, field: string): number {
  return toArray(data).reduce<number>((acc, item) => acc + toNumber(getField(item, field)), 0);
}

function transformAvg(data: unknown, field: string): number {
  const arr = toArray(data);
  if (arr.length === 0) return 0;
  return transformSum(data, field) / arr.length;
}

function transformMin(data: unknown, field: string): number {
  const values = toArray(data).map((item) => toNumber(getField(item, field)));
  return values.length === 0 ? 0 : Math.min(...values);
}

function transformMax(data: unknown, field: string): number {
  const values = toArray(data).map((item) => toNumber(getField(item, field)));
  return values.length === 0 ? 0 : Math.max(...values);
}

function transformGroupBy(data: unknown, field: string): Record<string, unknown[]> {
  const result: Record<string, unknown[]> = {};
  for (const item of toArray(data)) {
    const key = String(getField(item, field) ?? 'undefined');
    (result[key] ??= []).push(item);
  }
  return result;
}

function transformCountBy(data: unknown, field: string): Record<string, number> {
  const groups = transformGroupBy(data, field);
  const result: Record<string, number> = {};
  for (const [key, items] of Object.entries(groups)) {
    result[key] = items.length;
  }
  return result;
}

function transformPluck(data: unknown, field: string): unknown[] {
  return toArray(data).map((item) => getField(item, field));
}

function transformSort(data: unknown, field: string, direction: 'asc' | 'desc' = 'asc'): unknown[] {
  const arr = [...toArray(data)];
  const multiplier = direction === 'desc' ? -1 : 1;
  return arr.sort((a, b) => {
    const va = getField(a, field);
    const vb = getField(b, field);
    if (typeof va === 'string' && typeof vb === 'string') {
      return va.localeCompare(vb) * multiplier;
    }
    return (toNumber(va) - toNumber(vb)) * multiplier;
  });
}

function transformFirst(data: unknown, n: number): unknown[] {
  return toArray(data).slice(0, Math.max(0, n));
}

function transformLast(data: unknown, n: number): unknown[] {
  const arr = toArray(data);
  return arr.slice(Math.max(0, arr.length - n));
}

function transformMap(data: unknown, template: string): unknown[] {
  return toArray(data).map((item) => {
    if (item == null || typeof item !== 'object') return String(item);
    return template.replace(/\{(\w+)\}/g, (_match, key: string) => {
      return String(getField(item, key) ?? '');
    });
  });
}

type FilterOp = 'eq' | 'ne' | 'gt' | 'gte' | 'lt' | 'lte' | 'contains' | 'in';

function transformFilter(data: unknown, field: string, op: FilterOp, value: unknown): unknown[] {
  return toArray(data).filter((item) => {
    const fieldValue = getField(item, field);
    switch (op) {
      case 'eq':
        return fieldValue === value;
      case 'ne':
        return fieldValue !== value;
      case 'gt':
        return toNumber(fieldValue) > toNumber(value);
      case 'gte':
        return toNumber(fieldValue) >= toNumber(value);
      case 'lt':
        return toNumber(fieldValue) < toNumber(value);
      case 'lte':
        return toNumber(fieldValue) <= toNumber(value);
      case 'contains':
        return typeof fieldValue === 'string' && typeof value === 'string' && fieldValue.includes(value);
      case 'in':
        return Array.isArray(value) && value.includes(fieldValue);
      default:
        return true;
    }
  });
}

// ── Transform parser ─────────────────────────────────────────────────

/**
 * Parse a transform specification from the query.transform field.
 *
 * Accepts:
 * - `"none"`, `"count"` — simple string names
 * - `"sum(cores)"`, `"sort(status,asc)"`, `"first(5)"` — function-style strings
 * - `{ chain: [...] }`, `{ sum: "cores" }` — object form
 */

interface ParsedTransform {
  type: string;
  args: unknown[];
}

const FUNCTION_RE = /^(\w+)\(([^)]*)\)$/;

function parseTransformSpec(raw: unknown): ParsedTransform | null {
  if (raw == null || raw === 'none' || raw === '') return null;

  if (typeof raw === 'string') {
    const match = FUNCTION_RE.exec(raw);
    if (match) {
      const name = match[1];
      const argsStr = match[2];
      const args = argsStr.split(',').map((s) => s.trim()).filter(Boolean);
      return { type: name, args };
    }
    return { type: raw, args: [] };
  }

  if (typeof raw === 'object' && !Array.isArray(raw)) {
    const obj = raw as Record<string, unknown>;
    if ('chain' in obj && Array.isArray(obj.chain)) {
      return { type: 'chain', args: obj.chain };
    }
    // Object form: { sum: "cores" }, { filter: { field, op, value } }
    const [key] = Object.keys(obj);
    if (key) {
      return { type: key, args: [obj[key]] };
    }
  }

  return null;
}

// ── Main dispatcher ──────────────────────────────────────────────────

/**
 * Apply a transform to fetched data.
 *
 * @param data   Raw data from the binding fetcher
 * @param transform  The `query.transform` value from the data binding
 * @returns Transformed data
 */
export function applyTransform(data: unknown, transform: unknown): unknown {
  const parsed = parseTransformSpec(transform);
  if (!parsed) return data;

  switch (parsed.type) {
    case 'count':
      return transformCount(data);

    case 'sum':
      return transformSum(data, String(parsed.args[0] ?? ''));

    case 'avg':
      return transformAvg(data, String(parsed.args[0] ?? ''));

    case 'min':
      return transformMin(data, String(parsed.args[0] ?? ''));

    case 'max':
      return transformMax(data, String(parsed.args[0] ?? ''));

    case 'group_by':
      return transformGroupBy(data, String(parsed.args[0] ?? ''));

    case 'count_by':
      return transformCountBy(data, String(parsed.args[0] ?? ''));

    case 'pluck':
      return transformPluck(data, String(parsed.args[0] ?? ''));

    case 'sort': {
      if (typeof parsed.args[0] === 'object' && parsed.args[0] !== null) {
        const spec = parsed.args[0] as { field: string; direction?: string };
        return transformSort(data, spec.field, (spec.direction as 'asc' | 'desc') ?? 'asc');
      }
      const field = String(parsed.args[0] ?? '');
      const direction = (String(parsed.args[1] ?? 'asc')) as 'asc' | 'desc';
      return transformSort(data, field, direction);
    }

    case 'first':
      return transformFirst(data, Number(parsed.args[0] ?? 10));

    case 'last':
      return transformLast(data, Number(parsed.args[0] ?? 10));

    case 'map':
      return transformMap(data, String(parsed.args[0] ?? '{value}'));

    case 'filter': {
      if (typeof parsed.args[0] === 'object' && parsed.args[0] !== null) {
        const spec = parsed.args[0] as { field: string; op: string; value: unknown };
        return transformFilter(data, spec.field, spec.op as FilterOp, spec.value);
      }
      const field = String(parsed.args[0] ?? '');
      const op = String(parsed.args[1] ?? 'eq') as FilterOp;
      const value = parsed.args[2];
      return transformFilter(data, field, op, value);
    }

    case 'chain': {
      const steps = Array.isArray(parsed.args[0]) ? (parsed.args[0] as unknown[]) : parsed.args;
      let result = data;
      for (const step of steps) {
        result = applyTransform(result, step);
      }
      return result;
    }

    default:
      return data;
  }
}
