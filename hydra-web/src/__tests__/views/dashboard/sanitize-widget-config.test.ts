/**
 * Unit tests for sanitizeWidgetConfig.
 *
 * Verifies that each FieldType branch produces the correct output and that
 * the entity-ref type is not corrupted to Boolean (regression guard for the
 * Phase 5 review fix).
 */

import { describe, expect, it } from 'vitest';
import { sanitizeWidgetConfig } from '@/views/dashboard';
import type { FieldSchema } from '@/types/dashboard';

// ── entity-ref ─────────────────────────────────────────────────────────────

describe('sanitizeWidgetConfig — entity-ref', () => {
  it('preserves a valid entity-ref string ID', () => {
    const schema: FieldSchema[] = [
      { key: 'nodeId', label: 'Node', type: 'entity-ref', entityType: 'node', required: true },
    ];
    const result = sanitizeWidgetConfig({ nodeId: 'proxmox-01' }, schema);
    expect(result.nodeId).toBe('proxmox-01');
  });

  it('trims whitespace from a valid entity-ref value', () => {
    const schema: FieldSchema[] = [
      { key: 'nodeId', label: 'Node', type: 'entity-ref', entityType: 'node' },
    ];
    const result = sanitizeWidgetConfig({ nodeId: '  proxmox-01  ' }, schema);
    expect(result.nodeId).toBe('proxmox-01');
  });

  it('removes an empty-string entity-ref value', () => {
    const schema: FieldSchema[] = [
      { key: 'nodeId', label: 'Node', type: 'entity-ref', entityType: 'node' },
    ];
    const result = sanitizeWidgetConfig({ nodeId: '' }, schema);
    expect(result.nodeId).toBeUndefined();
  });

  it('removes a whitespace-only entity-ref value', () => {
    const schema: FieldSchema[] = [
      { key: 'nodeId', label: 'Node', type: 'entity-ref', entityType: 'node' },
    ];
    const result = sanitizeWidgetConfig({ nodeId: '   ' }, schema);
    expect(result.nodeId).toBeUndefined();
  });

  it('does NOT coerce a truthy entity-ref to Boolean(true)', () => {
    const schema: FieldSchema[] = [
      { key: 'nodeId', label: 'Node', type: 'entity-ref', entityType: 'node', required: true },
    ];
    const result = sanitizeWidgetConfig({ nodeId: 'proxmox-01' }, schema);
    // The regression: previously fell through to Boolean(rawValue) = true
    expect(result.nodeId).not.toBe(true);
    expect(typeof result.nodeId).toBe('string');
  });

  it('removes a non-string entity-ref value (e.g. null)', () => {
    const schema: FieldSchema[] = [
      { key: 'nodeId', label: 'Node', type: 'entity-ref', entityType: 'node' },
    ];
    const result = sanitizeWidgetConfig({ nodeId: null }, schema);
    expect(result.nodeId).toBeUndefined();
  });

  it('removes an undefined entity-ref value', () => {
    const schema: FieldSchema[] = [
      { key: 'nodeId', label: 'Node', type: 'entity-ref', entityType: 'node' },
    ];
    const result = sanitizeWidgetConfig({}, schema);
    expect(result.nodeId).toBeUndefined();
  });

  it('preserves entity-ref with entityType service', () => {
    const schema: FieldSchema[] = [
      { key: 'serviceId', label: 'Service', type: 'entity-ref', entityType: 'service' },
    ];
    const result = sanitizeWidgetConfig({ serviceId: 'svc-nginx-a1b2' }, schema);
    expect(result.serviceId).toBe('svc-nginx-a1b2');
  });
});

// ── string / enum / color (existing types — regression guard) ─────────────

describe('sanitizeWidgetConfig — string / enum / color', () => {
  it('preserves a valid string', () => {
    const schema: FieldSchema[] = [
      { key: 'title', label: 'Title', type: 'string' },
    ];
    const result = sanitizeWidgetConfig({ title: 'My Widget' }, schema);
    expect(result.title).toBe('My Widget');
  });

  it('removes an empty string', () => {
    const schema: FieldSchema[] = [
      { key: 'title', label: 'Title', type: 'string' },
    ];
    const result = sanitizeWidgetConfig({ title: '' }, schema);
    expect(result.title).toBeUndefined();
  });

  it('preserves a valid enum value', () => {
    const schema: FieldSchema[] = [
      {
        key: 'variant',
        label: 'Variant',
        type: 'enum',
        options: [{ value: 'compact', label: 'Compact' }, { value: 'full', label: 'Full' }],
      },
    ];
    const result = sanitizeWidgetConfig({ variant: 'compact' }, schema);
    expect(result.variant).toBe('compact');
  });

  it('removes an empty enum value', () => {
    const schema: FieldSchema[] = [
      {
        key: 'variant',
        label: 'Variant',
        type: 'enum',
        options: [{ value: 'compact', label: 'Compact' }],
      },
    ];
    const result = sanitizeWidgetConfig({ variant: '' }, schema);
    expect(result.variant).toBeUndefined();
  });

  it('preserves a valid color value', () => {
    const schema: FieldSchema[] = [
      { key: 'accentColor', label: 'Accent', type: 'color' },
    ];
    const result = sanitizeWidgetConfig({ accentColor: '#ff6600' }, schema);
    expect(result.accentColor).toBe('#ff6600');
  });
});

// ── number ────────────────────────────────────────────────────────────────

describe('sanitizeWidgetConfig — number', () => {
  it('preserves a valid number', () => {
    const schema: FieldSchema[] = [
      { key: 'limit', label: 'Limit', type: 'number' },
    ];
    const result = sanitizeWidgetConfig({ limit: 10 }, schema);
    expect(result.limit).toBe(10);
  });

  it('parses a numeric string', () => {
    const schema: FieldSchema[] = [
      { key: 'limit', label: 'Limit', type: 'number' },
    ];
    const result = sanitizeWidgetConfig({ limit: '42' }, schema);
    expect(result.limit).toBe(42);
  });

  it('removes empty string for number', () => {
    const schema: FieldSchema[] = [
      { key: 'limit', label: 'Limit', type: 'number' },
    ];
    const result = sanitizeWidgetConfig({ limit: '' }, schema);
    expect(result.limit).toBeUndefined();
  });

  it('clamps to min', () => {
    const schema: FieldSchema[] = [
      { key: 'limit', label: 'Limit', type: 'number', min: 1 },
    ];
    const result = sanitizeWidgetConfig({ limit: -5 }, schema);
    expect(result.limit).toBe(1);
  });

  it('clamps to max', () => {
    const schema: FieldSchema[] = [
      { key: 'limit', label: 'Limit', type: 'number', max: 100 },
    ];
    const result = sanitizeWidgetConfig({ limit: 200 }, schema);
    expect(result.limit).toBe(100);
  });
});

// ── boolean ───────────────────────────────────────────────────────────────

describe('sanitizeWidgetConfig — boolean', () => {
  it('preserves true', () => {
    const schema: FieldSchema[] = [
      { key: 'collapsible', label: 'Collapsible', type: 'boolean' },
    ];
    const result = sanitizeWidgetConfig({ collapsible: true }, schema);
    expect(result.collapsible).toBe(true);
  });

  it('preserves false', () => {
    const schema: FieldSchema[] = [
      { key: 'collapsible', label: 'Collapsible', type: 'boolean' },
    ];
    const result = sanitizeWidgetConfig({ collapsible: false }, schema);
    expect(result.collapsible).toBe(false);
  });
});

// ── defaultCollapsed cleanup ──────────────────────────────────────────────

describe('sanitizeWidgetConfig — collapsible/defaultCollapsed cleanup', () => {
  it('removes defaultCollapsed when collapsible is false', () => {
    const schema: FieldSchema[] = [
      { key: 'collapsible', label: 'Collapsible', type: 'boolean' },
      { key: 'defaultCollapsed', label: 'Start collapsed', type: 'boolean' },
    ];
    const result = sanitizeWidgetConfig({ collapsible: false, defaultCollapsed: true }, schema);
    expect(result.defaultCollapsed).toBeUndefined();
  });

  it('keeps defaultCollapsed when collapsible is true', () => {
    const schema: FieldSchema[] = [
      { key: 'collapsible', label: 'Collapsible', type: 'boolean' },
      { key: 'defaultCollapsed', label: 'Start collapsed', type: 'boolean' },
    ];
    const result = sanitizeWidgetConfig({ collapsible: true, defaultCollapsed: true }, schema);
    expect(result.defaultCollapsed).toBe(true);
  });
});

// ── mixed schema ──────────────────────────────────────────────────────────

describe('sanitizeWidgetConfig — mixed schema with entity-ref', () => {
  it('handles a schema with multiple field types including entity-ref', () => {
    const schema: FieldSchema[] = [
      { key: 'title', label: 'Title', type: 'string' },
      { key: 'nodeId', label: 'Node', type: 'entity-ref', entityType: 'node' },
      { key: 'limit', label: 'Limit', type: 'number', min: 1, max: 50 },
      { key: 'collapsible', label: 'Collapsible', type: 'boolean' },
    ];
    const result = sanitizeWidgetConfig(
      { title: 'Node Health', nodeId: 'proxmox-01', limit: 5, collapsible: true },
      schema,
    );
    expect(result.title).toBe('Node Health');
    expect(result.nodeId).toBe('proxmox-01');
    expect(result.limit).toBe(5);
    expect(result.collapsible).toBe(true);
  });

  it('omits only the entity-ref field when it is empty, leaving others intact', () => {
    const schema: FieldSchema[] = [
      { key: 'title', label: 'Title', type: 'string' },
      { key: 'nodeId', label: 'Node', type: 'entity-ref', entityType: 'node' },
    ];
    const result = sanitizeWidgetConfig({ title: 'Overview', nodeId: '' }, schema);
    expect(result.title).toBe('Overview');
    expect(result.nodeId).toBeUndefined();
  });
});
