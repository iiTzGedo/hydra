import { useEffect, useRef, useState, useCallback } from 'react';
import type { ReactNode } from 'react';
import type { DashboardWidgetInstance, FreeformPosition } from '@/types/dashboard';
import { findNonOverlappingPosition, overlapsAny } from '@/lib/freeform-layout';

const MIN_W = 80;
const MIN_H = 60;
const MAX_W = 2000;
const MAX_H = 2000;

interface DragState {
  instanceId: string;
  mode: 'move' | 'resize-br';
  startMouseX: number;
  startMouseY: number;
  startPos: FreeformPosition;
}

interface FreeformCanvasProps {
  widgets: DashboardWidgetInstance[];
  editable: boolean;
  canvasWidth: number;
  canvasMinHeight?: number;
  renderWidget: (widget: DashboardWidgetInstance) => ReactNode;
  onPositionChange: (instanceId: string, position: FreeformPosition) => void;
}

/**
 * Absolutely-positioned freeform canvas for dashboard widgets.
 *
 * - Drag to move: grab any widget by its body
 * - Resize: bottom-right resize handle (shown in edit mode only)
 * - Non-overlap enforcement: on mouse-up, if the dropped position overlaps
 *   another widget, a spiral search finds the nearest free slot. If none is
 *   found within 500 px, reverts to the pre-drag position.
 * - Canvas height auto-grows to fit all widgets + 200 px breathing room.
 * - Minimum widget size: 80 × 60 px. Maximum: 2000 × 2000 px.
 *
 * NOTE: Interactive widget content is disabled during edit mode — this is
 * intentional since edit mode is for rearrangement, not widget interaction.
 * The drag overlay sits above the widget content and captures pointer events.
 */
export function FreeformCanvas({
  widgets,
  editable,
  canvasWidth,
  canvasMinHeight = 600,
  renderWidget,
  onPositionChange,
}: FreeformCanvasProps) {
  const canvasRef = useRef<HTMLDivElement>(null);
  const [dragState, setDragState] = useState<DragState | null>(null);
  // Local ephemeral position used during drag — prevents pushing a history
  // entry on every pixel moved. onPositionChange is only called once, on mouseup.
  const [ephemeralPos, setEphemeralPos] = useState<FreeformPosition | null>(null);

  // Canvas height grows to accommodate all widgets + 200 px buffer.
  const canvasHeight =
    Math.max(
      canvasMinHeight,
      ...widgets.map(
        (w) => (w.freeformPosition?.y ?? 0) + (w.freeformPosition?.h ?? 0),
      ),
    ) + 200;

  const handleMouseDown = useCallback(
    (
      e: React.MouseEvent,
      widget: DashboardWidgetInstance,
      mode: 'move' | 'resize-br',
    ) => {
      if (!editable || !widget.freeformPosition) return;
      e.preventDefault();
      e.stopPropagation();
      // Clamp startPos so a widget that was placed out-of-bounds before
      // the fix doesn't produce garbage deltas (issue m4).
      const clampedStartPos: FreeformPosition = {
        x: Math.max(0, widget.freeformPosition.x),
        y: Math.max(0, widget.freeformPosition.y),
        w: Math.max(MIN_W, Math.min(MAX_W, widget.freeformPosition.w)),
        h: Math.max(MIN_H, Math.min(MAX_H, widget.freeformPosition.h)),
      };
      setDragState({
        instanceId: widget.instanceId,
        mode,
        startMouseX: e.clientX,
        startMouseY: e.clientY,
        startPos: clampedStartPos,
      });
      setEphemeralPos(clampedStartPos);
    },
    [editable],
  );

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!dragState) return;
      const dx = e.clientX - dragState.startMouseX;
      const dy = e.clientY - dragState.startMouseY;

      let next: FreeformPosition;
      if (dragState.mode === 'move') {
        next = {
          x: Math.max(0, Math.min(canvasWidth - dragState.startPos.w, dragState.startPos.x + dx)),
          y: Math.max(0, dragState.startPos.y + dy),
          w: dragState.startPos.w,
          h: dragState.startPos.h,
        };
      } else {
        // resize-br: clamp to [MIN, MAX]
        next = {
          x: dragState.startPos.x,
          y: dragState.startPos.y,
          w: Math.max(MIN_W, Math.min(MAX_W, dragState.startPos.w + dx)),
          h: Math.max(MIN_H, Math.min(MAX_H, dragState.startPos.h + dy)),
        };
      }

      // Only update LOCAL ephemeral state — do NOT call onPositionChange here.
      // Calling onPositionChange on every pixel would push a history entry per
      // pixel moved (C1 fix): a 200px drag would create 200+ undo steps.
      setEphemeralPos(next);
    },
    [dragState, canvasWidth],
  );

  const handleMouseUp = useCallback(() => {
    if (!dragState || !ephemeralPos) {
      setDragState(null);
      setEphemeralPos(null);
      return;
    }

    const others = widgets
      .filter(
        (w) =>
          w.instanceId !== dragState.instanceId && w.freeformPosition != null,
      )
      .map((w) => w.freeformPosition!);

    let final = ephemeralPos;
    if (overlapsAny(ephemeralPos, others)) {
      const settled = findNonOverlappingPosition(
        ephemeralPos,
        others,
        { maxX: canvasWidth, maxY: canvasHeight },
      );
      // No valid position found — revert to pre-drag position
      final = settled ?? dragState.startPos;
    }

    // Only commit if different from startPos — avoids a no-op history entry
    // when the user clicks a widget without actually dragging it.
    if (
      final.x !== dragState.startPos.x ||
      final.y !== dragState.startPos.y ||
      final.w !== dragState.startPos.w ||
      final.h !== dragState.startPos.h
    ) {
      onPositionChange(dragState.instanceId, final);
    }

    setDragState(null);
    setEphemeralPos(null);
  }, [dragState, ephemeralPos, widgets, canvasWidth, canvasHeight, onPositionChange]);

  useEffect(() => {
    if (!dragState) return;
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [dragState, handleMouseMove, handleMouseUp]);

  return (
    <div
      ref={canvasRef}
      data-freeform-canvas
      className="relative bg-background"
      style={{ width: canvasWidth, height: canvasHeight }}
    >
      {widgets.map((widget) => {
        // During a drag, show the ephemeral (live) position for the widget
        // being dragged; show the committed position for all others.
        const isDragging = dragState?.instanceId === widget.instanceId;
        const pos = isDragging && ephemeralPos ? ephemeralPos : widget.freeformPosition;
        if (!pos) return null;
        return (
          <div
            key={widget.instanceId}
            className="absolute border rounded-md overflow-hidden"
            style={{
              left: pos.x,
              top: pos.y,
              width: pos.w,
              height: pos.h,
            }}
          >
            {/* Drag surface — covers the widget, only active in edit mode.
                NOTE: Interactive widget content is disabled during edit mode —
                this is intentional since edit mode is for rearrangement. */}
            {editable ? (
              <div
                role="button"
                tabIndex={0}
                aria-label={`Drag widget ${widget.instanceId}`}
                className="absolute inset-0 cursor-grab z-10"
                onMouseDown={(e) => handleMouseDown(e, widget, 'move')}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') e.preventDefault();
                }}
              />
            ) : null}
            {renderWidget(widget)}
            {editable && (
              <button
                type="button"
                data-resize-handle
                aria-label="Resize widget"
                className="absolute bottom-0 right-0 z-20 w-3 h-3 bg-primary/40 cursor-nwse-resize"
                onMouseDown={(e) => {
                  e.stopPropagation();
                  handleMouseDown(e, widget, 'resize-br');
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
