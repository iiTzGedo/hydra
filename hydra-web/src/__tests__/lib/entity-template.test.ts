/**
 * Tests for resolveEntityVarsDeep — entity context template resolution.
 */

import { describe, it, expect } from 'vitest';
import { resolveEntityVarsDeep } from '@/lib/entity-template';

const TYPE = 'node';
const ID = 'node-abc-123';

describe('resolveEntityVarsDeep', () => {
  // ── String substitution ─────────────────────────────────────────

  it('substitutes {{entity.id}} in a plain string', () => {
    expect(resolveEntityVarsDeep('{{entity.id}}', TYPE, ID)).toBe(ID);
  });

  it('substitutes {{entity.type}} in a plain string', () => {
    expect(resolveEntityVarsDeep('{{entity.type}}', TYPE, ID)).toBe(TYPE);
  });

  it('substitutes within a larger string', () => {
    const input = '/nodes/{{entity.id}}/profiles/latest';
    const expected = `/nodes/${ID}/profiles/latest`;
    expect(resolveEntityVarsDeep(input, TYPE, ID)).toBe(expected);
  });

  it('substitutes multiple occurrences in one string', () => {
    const input = '{{entity.type}}/{{entity.id}}/{{entity.id}}';
    const expected = `${TYPE}/${ID}/${ID}`;
    expect(resolveEntityVarsDeep(input, TYPE, ID)).toBe(expected);
  });

  // ── Whitespace tolerance ────────────────────────────────────────

  it('handles extra whitespace inside braces: {{  entity.id  }}', () => {
    expect(resolveEntityVarsDeep('{{  entity.id  }}', TYPE, ID)).toBe(ID);
  });

  it('handles tab whitespace inside braces', () => {
    expect(resolveEntityVarsDeep('{{\tentity.type\t}}', TYPE, ID)).toBe(TYPE);
  });

  // ── Unknown fields (must NOT be substituted) ────────────────────

  it('does NOT substitute unknown field {{entity.foo}}', () => {
    expect(resolveEntityVarsDeep('{{entity.foo}}', TYPE, ID)).toBe('{{entity.foo}}');
  });

  it('does NOT substitute {{entity.name}}', () => {
    expect(resolveEntityVarsDeep('{{entity.name}}', TYPE, ID)).toBe('{{entity.name}}');
  });

  it('does NOT substitute bare {{nodeId}}', () => {
    expect(resolveEntityVarsDeep('{{nodeId}}', TYPE, ID)).toBe('{{nodeId}}');
  });

  // ── Non-string primitives ───────────────────────────────────────

  it('returns numbers unchanged', () => {
    expect(resolveEntityVarsDeep(42, TYPE, ID)).toBe(42);
  });

  it('returns booleans unchanged', () => {
    expect(resolveEntityVarsDeep(true, TYPE, ID)).toBe(true);
    expect(resolveEntityVarsDeep(false, TYPE, ID)).toBe(false);
  });

  it('returns null unchanged', () => {
    expect(resolveEntityVarsDeep(null, TYPE, ID)).toBeNull();
  });

  it('returns undefined unchanged', () => {
    expect(resolveEntityVarsDeep(undefined, TYPE, ID)).toBeUndefined();
  });

  // ── Object recursion ───────────────────────────────────────────

  it('resolves template vars inside object values', () => {
    const input = {
      endpoint: '/nodes/{{entity.id}}',
      label: 'Node details',
    };
    const result = resolveEntityVarsDeep(input, TYPE, ID);
    expect(result).toEqual({
      endpoint: `/nodes/${ID}`,
      label: 'Node details',
    });
  });

  it('does not mutate input object', () => {
    const input = { endpoint: '{{entity.id}}' };
    resolveEntityVarsDeep(input, TYPE, ID);
    expect(input.endpoint).toBe('{{entity.id}}');
  });

  it('resolves inside nested objects', () => {
    const input = {
      dataBinding: {
        source: 'api',
        query: {
          endpoint: '/nodes/{{entity.id}}/profiles/latest',
          params: { nodeId: '{{entity.id}}' },
        },
      },
    };
    const result = resolveEntityVarsDeep(input, TYPE, ID);
    expect(result).toEqual({
      dataBinding: {
        source: 'api',
        query: {
          endpoint: `/nodes/${ID}/profiles/latest`,
          params: { nodeId: ID },
        },
      },
    });
  });

  // ── Array recursion ────────────────────────────────────────────

  it('resolves template vars inside arrays', () => {
    const input = ['{{entity.id}}', '{{entity.type}}', 42];
    const result = resolveEntityVarsDeep(input, TYPE, ID);
    expect(result).toEqual([ID, TYPE, 42]);
  });

  it('resolves inside objects nested in arrays', () => {
    const input = [{ q: '/nodes/{{entity.id}}' }, { q: '/{{entity.type}}/list' }];
    const result = resolveEntityVarsDeep(input, TYPE, ID);
    expect(result).toEqual([
      { q: `/nodes/${ID}` },
      { q: `/${TYPE}/list` },
    ]);
  });

  // ── Deep nesting ───────────────────────────────────────────────

  it('handles deeply nested mixed structure', () => {
    const input = {
      widgets: [
        {
          instanceId: 'w1',
          dataBinding: {
            source: 'api',
            query: {
              endpoint: '/{{entity.type}}s/{{entity.id}}/services',
              params: { filter: 'active' },
            },
          },
          config: { title: 'Services for {{entity.id}}', count: 5 },
        },
      ],
    };
    const result = resolveEntityVarsDeep(input, TYPE, ID);
    expect(result).toEqual({
      widgets: [
        {
          instanceId: 'w1',
          dataBinding: {
            source: 'api',
            query: {
              endpoint: `/${TYPE}s/${ID}/services`,
              params: { filter: 'active' },
            },
          },
          config: { title: `Services for ${ID}`, count: 5 },
        },
      ],
    });
  });
});
