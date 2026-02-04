import { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { cn } from '@/lib/utils';

interface VirtualListProps<T> {
  items: T[];
  renderItem: (item: T, index: number) => React.ReactNode;
  itemHeight: number;
  keyExtractor: (item: T, index: number) => string;
  className?: string;
  containerHeight?: number | string;
  overscan?: number;
  onEndReached?: () => void;
  endReachedThreshold?: number;
  isLoadingMore?: boolean;
  emptyComponent?: React.ReactNode;
  headerComponent?: React.ReactNode;
  footerComponent?: React.ReactNode;
}

/**
 * VirtualList - High-performance list virtualization
 * 
 * Only renders visible items + overscan, dramatically improving performance
 * for long lists (1000+ items).
 * 
 * Usage:
 * <VirtualList
 *   items={largeArray}
 *   renderItem={(item) => <div>{item.name}</div>}
 *   itemHeight={48}
 *   keyExtractor={(item) => item.id}
 *   containerHeight={400}
 *   onEndReached={loadMore}
 * />
 */
export function VirtualList<T>({
  items,
  renderItem,
  itemHeight,
  keyExtractor,
  className,
  containerHeight = 400,
  overscan = 5,
  onEndReached,
  endReachedThreshold = 100,
  isLoadingMore,
  emptyComponent,
  headerComponent,
  footerComponent,
}: VirtualListProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [containerWidth, setContainerWidth] = useState(0);

  // Calculate visible range
  const totalHeight = items.length * itemHeight;
  const containerHeightNum = typeof containerHeight === 'number' 
    ? containerHeight 
    : containerRef.current?.clientHeight ?? 400;

  const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
  const visibleCount = Math.ceil(containerHeightNum / itemHeight) + overscan * 2;
  const endIndex = Math.min(items.length, startIndex + visibleCount);

  const visibleItems = useMemo(() => {
    return items.slice(startIndex, endIndex);
  }, [items, startIndex, endIndex]);

  // Handle scroll
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const newScrollTop = e.currentTarget.scrollTop;
    setScrollTop(newScrollTop);

    // Check if end reached
    if (onEndReached) {
      const scrollBottom = newScrollTop + containerHeightNum;
      const threshold = totalHeight - endReachedThreshold;
      
      if (scrollBottom >= threshold && !isLoadingMore) {
        onEndReached();
      }
    }
  }, [containerHeightNum, totalHeight, endReachedThreshold, onEndReached, isLoadingMore]);

  // Update container width on resize
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerWidth(entry.contentRect.width);
      }
    });

    resizeObserver.observe(container);
    setContainerWidth(container.clientWidth);

    return () => resizeObserver.disconnect();
  }, []);

  if (items.length === 0 && emptyComponent) {
    return (
      <div
        ref={containerRef}
        className={cn('overflow-auto', className)}
        style={{ height: containerHeight }}
      >
        {emptyComponent}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={cn('overflow-auto relative', className)}
      style={{ height: containerHeight }}
      onScroll={handleScroll}
    >
      {/* Header */}
      {headerComponent && (
        <div className="sticky top-0 z-10 bg-card">{headerComponent}</div>
      )}

      {/* Virtual spacer */}
      <div style={{ height: totalHeight, position: 'relative' }}>
        {visibleItems.map((item, index) => {
          const actualIndex = startIndex + index;
          const offsetTop = actualIndex * itemHeight;

          return (
            <div
              key={keyExtractor(item, actualIndex)}
              className="absolute left-0 right-0"
              style={{
                top: offsetTop,
                height: itemHeight,
                width: containerWidth,
              }}
            >
              {renderItem(item, actualIndex)}
            </div>
          );
        })}
      </div>

      {/* Footer / Loading indicator */}
      {(footerComponent || isLoadingMore) && (
        <div className="sticky bottom-0 z-10 bg-card border-t border-border">
          {isLoadingMore ? (
            <div className="flex items-center justify-center py-4">
              <div className="h-5 w-5 rounded-full border-2 border-primary border-t-transparent animate-spin" />
              <span className="ml-2 text-sm text-muted-foreground">Loading more...</span>
            </div>
          ) : (
            footerComponent
          )}
        </div>
      )}
    </div>
  );
}

// Window-based virtual list (renders based on window scroll)
interface WindowVirtualListProps<T> {
  items: T[];
  renderItem: (item: T, index: number) => React.ReactNode;
  itemHeight: number;
  keyExtractor: (item: T, index: number) => string;
  className?: string;
  overscan?: number;
}

export function WindowVirtualList<T>({
  items,
  renderItem,
  itemHeight,
  keyExtractor,
  className,
  overscan = 5,
}: WindowVirtualListProps<T>) {
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(window.innerHeight);

  useEffect(() => {
    const handleScroll = () => setScrollTop(window.scrollY);
    const handleResize = () => setViewportHeight(window.innerHeight);

    window.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  const totalHeight = items.length * itemHeight;
  const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
  const visibleCount = Math.ceil(viewportHeight / itemHeight) + overscan * 2;
  const endIndex = Math.min(items.length, startIndex + visibleCount);

  const visibleItems = items.slice(startIndex, endIndex);

  return (
    <div className={className} style={{ height: totalHeight, position: 'relative' }}>
      {visibleItems.map((item, index) => {
        const actualIndex = startIndex + index;
        const offsetTop = actualIndex * itemHeight;

        return (
          <div
            key={keyExtractor(item, actualIndex)}
            className="absolute left-0 right-0"
            style={{ top: offsetTop, height: itemHeight }}
          >
            {renderItem(item, actualIndex)}
          </div>
        );
      })}
    </div>
  );
}
