export type IconSource = 'hydra' | 'selfh-st' | 'simple-icons' | 'fallback';

export interface IconDescriptor {
  source: IconSource;
  slug: string;
  label?: string | null;
  url?: string | null;
  urlDark?: string | null;
  urlLight?: string | null;
  color?: string | null;
  fallback?: string | null;
}
