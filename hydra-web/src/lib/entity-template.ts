/**
 * Entity-context template variable resolution for embedded panels.
 * Mirrors the server-side resolver in
 * hydra-api/hydra/api/v1/services/dashboards/templating.py.
 *
 * Only resolves {{entity.id}} and {{entity.type}} — no other patterns are
 * matched, so unknown variables like {{entity.foo}} are passed through
 * unchanged.
 */

function substitute(value: string, entityType: string, entityId: string): string {
  const pattern = /\{\{\s*entity\.(id|type)\s*\}\}/g;
  return value.replace(pattern, (_, key) => (key === 'id' ? entityId : entityType));
}

/**
 * Recursively walks `obj` and replaces every occurrence of
 * `{{entity.id}}` and `{{entity.type}}` in string values.
 *
 * - Strings: substituted directly.
 * - Arrays: each element is processed recursively.
 * - Objects: each value is processed recursively; keys are left untouched.
 * - Numbers, booleans, null, undefined: returned as-is.
 */
export function resolveEntityVarsDeep<T>(obj: T, entityType: string, entityId: string): T {
  if (typeof obj === 'string') {
    return substitute(obj, entityType, entityId) as unknown as T;
  }
  if (Array.isArray(obj)) {
    return obj.map((v) => resolveEntityVarsDeep(v, entityType, entityId)) as unknown as T;
  }
  if (obj !== null && typeof obj === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
      out[k] = resolveEntityVarsDeep(v, entityType, entityId);
    }
    return out as unknown as T;
  }
  return obj;
}
