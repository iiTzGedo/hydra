/**
 * Unit tests for the widget transform pipeline.
 *
 * Covers all 14 transform operations from Dashboard Technical
 * Specification §6.4 plus edge cases (empty arrays, missing fields,
 * type coercion, nested chains).
 */

import { describe, expect, it } from 'vitest';
import { applyTransform } from '@/lib/widget-transforms';

const NODES = [
  { nodeId: 'n1', class: 'compute', status: 'online', cores: 4 },
  { nodeId: 'n2', class: 'compute', status: 'offline', cores: 8 },
  { nodeId: 'n3', class: 'networking', status: 'online', cores: 2 },
  { nodeId: 'n4', class: 'iot', status: 'degraded', cores: 1 },
  { nodeId: 'n5', class: 'compute', status: 'online', cores: 16 },
];

describe('Widget Transforms', () => {
  // ── count ──────────────────────────────────────────────────────

  describe('count', () => {
    it('counts array items', () => {
      expect(applyTransform(NODES, 'count')).toBe(5);
    });

    it('returns 0 for empty array', () => {
      expect(applyTransform([], 'count')).toBe(0);
    });

    it('returns 0 for null', () => {
      expect(applyTransform(null, 'count')).toBe(0);
    });

    it('wraps non-array in array (count 1)', () => {
      expect(applyTransform({ single: true }, 'count')).toBe(1);
    });
  });

  // ── sum ────────────────────────────────────────────────────────

  describe('sum', () => {
    it('sums a numeric field', () => {
      expect(applyTransform(NODES, 'sum(cores)')).toBe(31);
    });

    it('returns 0 for empty array', () => {
      expect(applyTransform([], 'sum(cores)')).toBe(0);
    });

    it('treats non-numeric as 0', () => {
      const items = [{ val: 'abc' }, { val: 10 }];
      expect(applyTransform(items, 'sum(val)')).toBe(10);
    });
  });

  // ── avg ────────────────────────────────────────────────────────

  describe('avg', () => {
    it('computes average of a numeric field', () => {
      expect(applyTransform(NODES, 'avg(cores)')).toBeCloseTo(6.2);
    });

    it('returns 0 for empty array', () => {
      expect(applyTransform([], 'avg(cores)')).toBe(0);
    });
  });

  // ── min / max ──────────────────────────────────────────────────

  describe('min', () => {
    it('finds minimum value', () => {
      expect(applyTransform(NODES, 'min(cores)')).toBe(1);
    });

    it('returns 0 for empty array', () => {
      expect(applyTransform([], 'min(cores)')).toBe(0);
    });
  });

  describe('max', () => {
    it('finds maximum value', () => {
      expect(applyTransform(NODES, 'max(cores)')).toBe(16);
    });
  });

  // ── group_by ───────────────────────────────────────────────────

  describe('group_by', () => {
    it('groups items by field value', () => {
      const result = applyTransform(NODES, 'group_by(class)') as Record<string, unknown[]>;
      expect(Object.keys(result).sort()).toEqual(['compute', 'iot', 'networking']);
      expect(result.compute).toHaveLength(3);
      expect(result.networking).toHaveLength(1);
    });

    it('uses "undefined" key for missing field', () => {
      const items = [{ a: 1 }, { a: 2, b: 'x' }];
      const result = applyTransform(items, 'group_by(b)') as Record<string, unknown[]>;
      expect(result['undefined']).toHaveLength(1);
      expect(result.x).toHaveLength(1);
    });
  });

  // ── count_by ───────────────────────────────────────────────────

  describe('count_by', () => {
    it('counts items per group', () => {
      const result = applyTransform(NODES, 'count_by(class)') as Record<string, number>;
      expect(result.compute).toBe(3);
      expect(result.networking).toBe(1);
      expect(result.iot).toBe(1);
    });
  });

  // ── pluck ──────────────────────────────────────────────────────

  describe('pluck', () => {
    it('extracts field values', () => {
      const result = applyTransform(NODES, 'pluck(nodeId)');
      expect(result).toEqual(['n1', 'n2', 'n3', 'n4', 'n5']);
    });
  });

  // ── sort ───────────────────────────────────────────────────────

  describe('sort', () => {
    it('sorts ascending by numeric field', () => {
      const result = applyTransform(NODES, 'sort(cores,asc)') as typeof NODES;
      expect(result[0].cores).toBe(1);
      expect(result[4].cores).toBe(16);
    });

    it('sorts descending by numeric field', () => {
      const result = applyTransform(NODES, 'sort(cores,desc)') as typeof NODES;
      expect(result[0].cores).toBe(16);
      expect(result[4].cores).toBe(1);
    });

    it('sorts by string field', () => {
      const result = applyTransform(NODES, 'sort(status,asc)') as typeof NODES;
      expect(result[0].status).toBe('degraded');
    });

    it('accepts object form', () => {
      const result = applyTransform(NODES, { sort: { field: 'cores', direction: 'desc' } }) as typeof NODES;
      expect(result[0].cores).toBe(16);
    });
  });

  // ── first / last ───────────────────────────────────────────────

  describe('first', () => {
    it('takes first N items', () => {
      const result = applyTransform(NODES, 'first(2)') as typeof NODES;
      expect(result).toHaveLength(2);
      expect(result[0].nodeId).toBe('n1');
    });

    it('returns all if N > array length', () => {
      expect(applyTransform(NODES, 'first(100)')).toHaveLength(5);
    });
  });

  describe('last', () => {
    it('takes last N items', () => {
      const result = applyTransform(NODES, 'last(2)') as typeof NODES;
      expect(result).toHaveLength(2);
      expect(result[0].nodeId).toBe('n4');
      expect(result[1].nodeId).toBe('n5');
    });
  });

  // ── map ────────────────────────────────────────────────────────

  describe('map', () => {
    it('applies template string', () => {
      const result = applyTransform(NODES, 'map({nodeId}: {status})');
      expect(result).toEqual([
        'n1: online',
        'n2: offline',
        'n3: online',
        'n4: degraded',
        'n5: online',
      ]);
    });
  });

  // ── filter ─────────────────────────────────────────────────────

  describe('filter', () => {
    it('filters by eq', () => {
      const result = applyTransform(NODES, { filter: { field: 'status', op: 'eq', value: 'online' } }) as typeof NODES;
      expect(result).toHaveLength(3);
    });

    it('filters by ne', () => {
      const result = applyTransform(NODES, { filter: { field: 'status', op: 'ne', value: 'online' } }) as typeof NODES;
      expect(result).toHaveLength(2);
    });

    it('filters by gt', () => {
      const result = applyTransform(NODES, { filter: { field: 'cores', op: 'gt', value: 4 } }) as typeof NODES;
      expect(result).toHaveLength(2); // 8 and 16
    });

    it('filters by lte', () => {
      const result = applyTransform(NODES, { filter: { field: 'cores', op: 'lte', value: 4 } }) as typeof NODES;
      expect(result).toHaveLength(3); // 4, 2, 1
    });

    it('filters by contains', () => {
      const items = [{ name: 'proxmox-01' }, { name: 'ha-core' }, { name: 'proxmox-02' }];
      const result = applyTransform(items, { filter: { field: 'name', op: 'contains', value: 'proxmox' } }) as typeof items;
      expect(result).toHaveLength(2);
    });

    it('filters by in', () => {
      const result = applyTransform(NODES, { filter: { field: 'class', op: 'in', value: ['compute', 'iot'] } }) as typeof NODES;
      expect(result).toHaveLength(4);
    });

    it('supports function-style syntax', () => {
      const result = applyTransform(NODES, 'filter(status,eq,online)') as typeof NODES;
      expect(result).toHaveLength(3);
    });
  });

  // ── chain ──────────────────────────────────────────────────────

  describe('chain', () => {
    it('applies transforms sequentially', () => {
      const result = applyTransform(NODES, {
        chain: [
          { filter: { field: 'class', op: 'eq', value: 'compute' } },
          'count',
        ],
      });
      expect(result).toBe(3);
    });

    it('chains sort + first', () => {
      const result = applyTransform(NODES, {
        chain: [
          { sort: { field: 'cores', direction: 'desc' } },
          { first: 3 },
          'pluck(cores)',
        ],
      }) as number[];
      expect(result).toEqual([16, 8, 4]);
    });

    it('handles empty chain', () => {
      expect(applyTransform(NODES, { chain: [] })).toBe(NODES);
    });
  });

  // ── none / passthrough ─────────────────────────────────────────

  describe('none / passthrough', () => {
    it('"none" returns data unchanged', () => {
      expect(applyTransform(NODES, 'none')).toBe(NODES);
    });

    it('null transform returns data unchanged', () => {
      expect(applyTransform(NODES, null)).toBe(NODES);
    });

    it('undefined transform returns data unchanged', () => {
      expect(applyTransform(NODES, undefined)).toBe(NODES);
    });

    it('empty string returns data unchanged', () => {
      expect(applyTransform(NODES, '')).toBe(NODES);
    });

    it('unknown transform returns data unchanged', () => {
      expect(applyTransform(NODES, 'unknown_op')).toBe(NODES);
    });
  });
});
