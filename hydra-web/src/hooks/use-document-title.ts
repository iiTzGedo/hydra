import { useEffect } from 'react';

/**
 * Updates the document title with the given page title.
 * Automatically appends " | Hydra" suffix.
 *
 * @param title - The page-specific title (e.g., "Dashboard", "Node Explorer")
 * @example
 * useDocumentTitle('Dashboard');
 * // Sets document.title to "Dashboard | Hydra"
 */
export function useDocumentTitle(title: string) {
  useEffect(() => {
    const previousTitle = document.title;
    document.title = title ? `${title} | Hydra` : 'Hydra';

    return () => {
      document.title = previousTitle;
    };
  }, [title]);
}
