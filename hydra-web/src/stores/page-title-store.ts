import { create } from 'zustand';

interface PageTitleState {
  title: string | null;
  subtitle: string | null;
  setPageTitle: (title: string | null, subtitle?: string | null) => void;
  clearPageTitle: () => void;
}

export const usePageTitleStore = create<PageTitleState>((set) => ({
  title: null,
  subtitle: null,
  setPageTitle: (title, subtitle = null) => set({ title, subtitle }),
  clearPageTitle: () => set({ title: null, subtitle: null }),
}));
