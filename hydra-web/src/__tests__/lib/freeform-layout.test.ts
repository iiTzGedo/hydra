import { describe, it, expect } from 'vitest';
import {
  rectsOverlap,
  overlapsAny,
  findNonOverlappingPosition,
  gridToFreeform,
  freeformToGrid,
  type Rect,
  type GridParams,
} from '@/lib/freeform-layout';

// ── rectsOverlap ───────────────────────────────────────────────────

describe('rectsOverlap', () => {
  it('returns true for two overlapping rects', () => {
    const a: Rect = { x: 0, y: 0, w: 100, h: 100 };
    const b: Rect = { x: 50, y: 50, w: 100, h: 100 };
    expect(rectsOverlap(a, b)).toBe(true);
  });

  it('returns true when one rect is fully contained in the other', () => {
    const a: Rect = { x: 0, y: 0, w: 200, h: 200 };
    const b: Rect = { x: 50, y: 50, w: 50, h: 50 };
    expect(rectsOverlap(a, b)).toBe(true);
  });

  it('returns false for two non-overlapping rects (horizontal separation)', () => {
    const a: Rect = { x: 0, y: 0, w: 100, h: 100 };
    const b: Rect = { x: 200, y: 0, w: 100, h: 100 };
    expect(rectsOverlap(a, b)).toBe(false);
  });

  it('returns false for two non-overlapping rects (vertical separation)', () => {
    const a: Rect = { x: 0, y: 0, w: 100, h: 100 };
    const b: Rect = { x: 0, y: 200, w: 100, h: 100 };
    expect(rectsOverlap(a, b)).toBe(false);
  });

  it('returns false for edge-touching rects (shared right/left boundary)', () => {
    const a: Rect = { x: 0, y: 0, w: 100, h: 100 };
    const b: Rect = { x: 100, y: 0, w: 100, h: 100 };
    expect(rectsOverlap(a, b)).toBe(false);
  });

  it('returns false for edge-touching rects (shared top/bottom boundary)', () => {
    const a: Rect = { x: 0, y: 0, w: 100, h: 100 };
    const b: Rect = { x: 0, y: 100, w: 100, h: 100 };
    expect(rectsOverlap(a, b)).toBe(false);
  });

  it('returns false for corner-touching rects', () => {
    const a: Rect = { x: 0, y: 0, w: 100, h: 100 };
    const b: Rect = { x: 100, y: 100, w: 100, h: 100 };
    expect(rectsOverlap(a, b)).toBe(false);
  });

  it('is symmetric', () => {
    const a: Rect = { x: 10, y: 10, w: 80, h: 80 };
    const b: Rect = { x: 60, y: 60, w: 80, h: 80 };
    expect(rectsOverlap(a, b)).toBe(rectsOverlap(b, a));
  });
});

// ── overlapsAny ────────────────────────────────────────────────────

describe('overlapsAny', () => {
  it('returns false for empty others array', () => {
    const target: Rect = { x: 0, y: 0, w: 100, h: 100 };
    expect(overlapsAny(target, [])).toBe(false);
  });

  it('returns true when target overlaps at least one rect', () => {
    const target: Rect = { x: 50, y: 50, w: 100, h: 100 };
    const others: Rect[] = [
      { x: 200, y: 200, w: 100, h: 100 }, // no overlap
      { x: 100, y: 100, w: 100, h: 100 }, // overlaps
    ];
    expect(overlapsAny(target, others)).toBe(true);
  });

  it('returns false when target does not overlap any rect', () => {
    const target: Rect = { x: 0, y: 0, w: 80, h: 80 };
    const others: Rect[] = [
      { x: 100, y: 0, w: 80, h: 80 },
      { x: 0, y: 100, w: 80, h: 80 },
    ];
    expect(overlapsAny(target, others)).toBe(false);
  });
});

// ── findNonOverlappingPosition ─────────────────────────────────────

describe('findNonOverlappingPosition', () => {
  const bounds = { maxX: 1200, maxY: 2000 };

  it('returns target unchanged when it is already free and within bounds', () => {
    const target: Rect = { x: 100, y: 100, w: 200, h: 150 };
    const result = findNonOverlappingPosition(target, [], bounds);
    expect(result).toEqual(target);
  });

  it('returns the target itself when others array is empty', () => {
    const target: Rect = { x: 300, y: 200, w: 120, h: 80 };
    const result = findNonOverlappingPosition(target, [], bounds);
    expect(result).toEqual(target);
  });

  it('finds an adjacent position when target overlaps a single other', () => {
    const other: Rect = { x: 0, y: 0, w: 300, h: 200 };
    const target: Rect = { x: 50, y: 50, w: 100, h: 80 };
    const result = findNonOverlappingPosition(target, [other], bounds);
    expect(result).not.toBeNull();
    if (result) {
      // Must not overlap the other rect
      expect(rectsOverlap(result, other)).toBe(false);
      // Must be within bounds
      expect(result.x).toBeGreaterThanOrEqual(0);
      expect(result.y).toBeGreaterThanOrEqual(0);
      expect(result.x + result.w).toBeLessThanOrEqual(bounds.maxX);
      expect(result.y + result.h).toBeLessThanOrEqual(bounds.maxY);
    }
  });

  it('preserves the original width and height', () => {
    const other: Rect = { x: 0, y: 0, w: 500, h: 300 };
    const target: Rect = { x: 100, y: 100, w: 120, h: 90 };
    const result = findNonOverlappingPosition(target, [other], bounds);
    expect(result).not.toBeNull();
    if (result) {
      expect(result.w).toBe(target.w);
      expect(result.h).toBe(target.h);
    }
  });

  it('returns null when all positions within maxRadius are blocked', () => {
    // Fill bounds with overlapping rects so no free slot exists
    const tinyBounds = { maxX: 200, maxY: 200 };
    const target: Rect = { x: 0, y: 0, w: 200, h: 200 };
    // One rect that exactly covers all bounds — no position can fit
    const blocker: Rect = { x: 0, y: 0, w: 200, h: 200 };
    const result = findNonOverlappingPosition(target, [blocker], tinyBounds, 500);
    expect(result).toBeNull();
  });

  it('finds a position among multiple others', () => {
    const others: Rect[] = [
      { x: 0, y: 0, w: 200, h: 200 },
      { x: 200, y: 0, w: 200, h: 200 },
      { x: 0, y: 200, w: 200, h: 200 },
    ];
    const target: Rect = { x: 50, y: 50, w: 100, h: 100 };
    const result = findNonOverlappingPosition(target, others, bounds);
    expect(result).not.toBeNull();
    if (result) {
      for (const o of others) {
        expect(rectsOverlap(result, o)).toBe(false);
      }
    }
  });
});

// ── Zero-canvas guards (I2) ────────────────────────────────────────

describe('gridToFreeform / freeformToGrid zero-canvas guards', () => {
  it('gridToFreeform returns safe defaults when canvasWidth is 0', () => {
    const grid: Rect = { x: 0, y: 0, w: 4, h: 2 };
    const params: GridParams = { cols: 12, rowHeight: 60, gap: 8, canvasWidth: 0 };
    const result = gridToFreeform(grid, params);
    expect(result).toEqual({ x: 0, y: 0, w: 200, h: 150 });
  });

  it('gridToFreeform returns safe defaults when canvasWidth is negative', () => {
    const grid: Rect = { x: 0, y: 0, w: 4, h: 2 };
    const params: GridParams = { cols: 12, rowHeight: 60, gap: 8, canvasWidth: -100 };
    const result = gridToFreeform(grid, params);
    expect(result).toEqual({ x: 0, y: 0, w: 200, h: 150 });
  });

  it('gridToFreeform returns safe defaults when cols is 0', () => {
    const grid: Rect = { x: 0, y: 0, w: 4, h: 2 };
    const params: GridParams = { cols: 0, rowHeight: 60, gap: 8, canvasWidth: 1200 };
    const result = gridToFreeform(grid, params);
    expect(result).toEqual({ x: 0, y: 0, w: 200, h: 150 });
  });

  it('freeformToGrid returns safe defaults when canvasWidth is 0', () => {
    const ff: Rect = { x: 8, y: 8, w: 200, h: 150 };
    const params: GridParams = { cols: 12, rowHeight: 60, gap: 8, canvasWidth: 0 };
    const result = freeformToGrid(ff, params);
    expect(result).toEqual({ x: 0, y: 0, w: 4, h: 2 });
  });

  it('freeformToGrid returns safe defaults when cols is 0', () => {
    const ff: Rect = { x: 8, y: 8, w: 200, h: 150 };
    const params: GridParams = { cols: 0, rowHeight: 60, gap: 8, canvasWidth: 1200 };
    const result = freeformToGrid(ff, params);
    expect(result).toEqual({ x: 0, y: 0, w: 4, h: 2 });
  });
});

// ── gridToFreeform ─────────────────────────────────────────────────

describe('gridToFreeform', () => {
  const params: GridParams = {
    cols: 12,
    rowHeight: 60,
    gap: 8,
    canvasWidth: 1200,
  };

  it('converts a 2×2 grid position to reasonable pixel dimensions', () => {
    const grid: Rect = { x: 0, y: 0, w: 2, h: 2 };
    const ff = gridToFreeform(grid, params);
    // colWidth = (1200 - 8*13) / 12 = (1200 - 104) / 12 = 1096 / 12 ≈ 91.33
    // x: gap + 0*(colWidth+gap) = 8
    // y: gap + 0*(rowHeight+gap) = 8
    // w: 2*colWidth + 1*gap ≈ 2*91.33 + 8 = 190.67
    // h: 2*60 + 1*8 = 128
    expect(ff.x).toBeGreaterThan(0);
    expect(ff.y).toBeGreaterThan(0);
    expect(ff.w).toBeGreaterThan(80);
    expect(ff.h).toBe(128);
  });

  it('places a 4-wide widget at x=0 correctly', () => {
    const grid: Rect = { x: 0, y: 0, w: 4, h: 2 };
    const ff = gridToFreeform(grid, params);
    expect(ff.x).toBe(params.gap);
    expect(ff.y).toBe(params.gap);
  });

  it('places a widget starting at column 4 at the correct x offset', () => {
    const gridAt0: Rect = { x: 0, y: 0, w: 4, h: 2 };
    const gridAt4: Rect = { x: 4, y: 0, w: 4, h: 2 };
    const ff0 = gridToFreeform(gridAt0, params);
    const ff4 = gridToFreeform(gridAt4, params);
    // x at col 4 should be > x at col 0
    expect(ff4.x).toBeGreaterThan(ff0.x);
  });

  it('handles different canvas widths (720px)', () => {
    const narrowParams: GridParams = { ...params, canvasWidth: 720 };
    const grid: Rect = { x: 0, y: 0, w: 6, h: 3 };
    const ff = gridToFreeform(grid, narrowParams);
    expect(ff.w).toBeGreaterThan(0);
    expect(ff.h).toBeGreaterThan(0);
  });

  it('handles different canvas widths (1920px)', () => {
    const wideParams: GridParams = { ...params, canvasWidth: 1920 };
    const grid: Rect = { x: 0, y: 0, w: 12, h: 4 };
    const ff = gridToFreeform(grid, wideParams);
    expect(ff.w).toBeCloseTo(1920 - wideParams.gap * 2, 0);
  });
});

// ── freeformToGrid ─────────────────────────────────────────────────

describe('freeformToGrid', () => {
  const params: GridParams = {
    cols: 12,
    rowHeight: 60,
    gap: 8,
    canvasWidth: 1200,
  };

  it('roundtrip: gridToFreeform then freeformToGrid returns original (1×1)', () => {
    const original: Rect = { x: 0, y: 0, w: 1, h: 1 };
    const ff = gridToFreeform(original, params);
    const back = freeformToGrid(ff, params);
    expect(back.x).toBe(original.x);
    expect(back.y).toBe(original.y);
    expect(back.w).toBe(original.w);
    expect(back.h).toBe(original.h);
  });

  it('roundtrip: gridToFreeform then freeformToGrid returns original (6×4)', () => {
    const original: Rect = { x: 3, y: 2, w: 6, h: 4 };
    const ff = gridToFreeform(original, params);
    const back = freeformToGrid(ff, params);
    expect(back.x).toBe(original.x);
    expect(back.y).toBe(original.y);
    expect(back.w).toBe(original.w);
    expect(back.h).toBe(original.h);
  });

  it('roundtrip: gridToFreeform then freeformToGrid returns original (12×2)', () => {
    const original: Rect = { x: 0, y: 0, w: 12, h: 2 };
    const ff = gridToFreeform(original, params);
    const back = freeformToGrid(ff, params);
    expect(back.x).toBe(original.x);
    expect(back.y).toBe(original.y);
    expect(back.w).toBe(original.w);
    expect(back.h).toBe(original.h);
  });

  it('roundtrip at 720px canvas width', () => {
    const narrowParams: GridParams = { ...params, canvasWidth: 720 };
    const original: Rect = { x: 0, y: 0, w: 4, h: 3 };
    const ff = gridToFreeform(original, narrowParams);
    const back = freeformToGrid(ff, narrowParams);
    expect(back.x).toBe(original.x);
    expect(back.y).toBe(original.y);
    expect(back.w).toBe(original.w);
    expect(back.h).toBe(original.h);
  });

  it('roundtrip at 1920px canvas width', () => {
    const wideParams: GridParams = { ...params, canvasWidth: 1920 };
    const original: Rect = { x: 6, y: 4, w: 6, h: 2 };
    const ff = gridToFreeform(original, wideParams);
    const back = freeformToGrid(ff, wideParams);
    expect(back.x).toBe(original.x);
    expect(back.y).toBe(original.y);
    expect(back.w).toBe(original.w);
    expect(back.h).toBe(original.h);
  });
});
