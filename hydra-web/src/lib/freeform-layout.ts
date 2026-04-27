/**
 * Freeform layout utilities for absolute-positioned widget canvas.
 *
 * Provides:
 * - `rectsOverlap` / `overlapsAny` — axis-aligned overlap tests
 * - `findNonOverlappingPosition` — spiral search for a free slot
 * - `gridToFreeform` / `freeformToGrid` — conversion between RGL grid coords
 *   and pixel-space freeform coords
 */

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface CanvasBounds {
  maxX: number;
  maxY: number;
}

export interface GridParams {
  cols: number;
  rowHeight: number;
  gap: number;
  canvasWidth: number;
}

/**
 * Returns true if rect `a` and rect `b` overlap.
 * Edge-touching (shared boundary) does NOT count as overlap.
 */
export function rectsOverlap(a: Rect, b: Rect): boolean {
  return !(
    a.x + a.w <= b.x ||
    b.x + b.w <= a.x ||
    a.y + a.h <= b.y ||
    b.y + b.h <= a.y
  );
}

/**
 * Returns true if `target` overlaps any rect in `others`.
 */
export function overlapsAny(target: Rect, others: Rect[]): boolean {
  return others.some((o) => rectsOverlap(target, o));
}

function isWithin(r: Rect, bounds: CanvasBounds): boolean {
  return (
    r.x >= 0 &&
    r.y >= 0 &&
    r.x + r.w <= bounds.maxX &&
    r.y + r.h <= bounds.maxY
  );
}

/**
 * Finds a non-overlapping position for `target` using a spiral-outward search
 * from the target's current position. Checks 8 cardinal + diagonal directions
 * at each radius step of 10 px. Returns `null` if no valid position is found
 * within `maxRadius` (default 500 px).
 */
export function findNonOverlappingPosition(
  target: Rect,
  others: Rect[],
  bounds: CanvasBounds,
  maxRadius = 500,
): Rect | null {
  // If the target is already valid, return it immediately.
  if (isWithin(target, bounds) && !overlapsAny(target, others)) {
    return target;
  }

  const step = 10;
  for (let r = step; r <= maxRadius; r += step) {
    const candidates: Rect[] = [
      { ...target, x: target.x + r, y: target.y },
      { ...target, x: target.x - r, y: target.y },
      { ...target, x: target.x, y: target.y + r },
      { ...target, x: target.x, y: target.y - r },
      { ...target, x: target.x + r, y: target.y + r },
      { ...target, x: target.x + r, y: target.y - r },
      { ...target, x: target.x - r, y: target.y + r },
      { ...target, x: target.x - r, y: target.y - r },
    ];
    for (const c of candidates) {
      if (isWithin(c, bounds) && !overlapsAny(c, others)) {
        return c;
      }
    }
  }

  return null;
}

/**
 * Converts a grid position (column/row units as used by react-grid-layout) to
 * pixel coordinates suitable for the freeform canvas.
 *
 * @param grid  - RGL position in grid units { x, y, w, h }
 * @param params - Layout parameters: cols, rowHeight, gap, canvasWidth
 */
export function gridToFreeform(grid: Rect, params: GridParams): Rect {
  // I2: guard against zero/negative canvas or zero cols to prevent NaN/negative colWidth.
  if (params.canvasWidth <= 0 || params.cols <= 0) {
    return { x: 0, y: 0, w: 200, h: 150 };
  }
  const colWidth =
    (params.canvasWidth - params.gap * (params.cols + 1)) / params.cols;
  return {
    x: params.gap + grid.x * (colWidth + params.gap),
    y: params.gap + grid.y * (params.rowHeight + params.gap),
    w: grid.w * colWidth + (grid.w - 1) * params.gap,
    h: grid.h * params.rowHeight + (grid.h - 1) * params.gap,
  };
}

/**
 * Converts pixel coordinates from the freeform canvas back to grid units.
 * Rounds to nearest integer grid unit. This is the inverse of `gridToFreeform`.
 *
 * @param ff     - Freeform pixel position { x, y, w, h }
 * @param params - Layout parameters: cols, rowHeight, gap, canvasWidth
 */
export function freeformToGrid(ff: Rect, params: GridParams): Rect {
  // I2: guard against zero/negative canvas or zero cols to prevent NaN/negative colWidth.
  if (params.canvasWidth <= 0 || params.cols <= 0) {
    return { x: 0, y: 0, w: 4, h: 2 };
  }
  const colWidth =
    (params.canvasWidth - params.gap * (params.cols + 1)) / params.cols;
  return {
    x: Math.round((ff.x - params.gap) / (colWidth + params.gap)),
    y: Math.round((ff.y - params.gap) / (params.rowHeight + params.gap)),
    w: Math.round((ff.w + params.gap) / (colWidth + params.gap)),
    h: Math.round((ff.h + params.gap) / (params.rowHeight + params.gap)),
  };
}
