export const CSRF_COOKIE_NAME = 'hydra_csrf';
export const CSRF_HEADER_NAME = 'X-CSRF-Token';

export function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_URL || '/api/v1';
}

export function getCookieValue(name: string): string | null {
  if (typeof document === 'undefined') {
    return null;
  }

  const cookie = document.cookie
    .split('; ')
    .find((entry) => entry.startsWith(`${name}=`));

  return cookie ? decodeURIComponent(cookie.split('=').slice(1).join('=')) : null;
}

export function getCsrfToken(): string | null {
  return getCookieValue(CSRF_COOKIE_NAME);
}

export function isMutationMethod(method?: string): boolean {
  const normalized = (method || 'GET').toUpperCase();
  return !['GET', 'HEAD', 'OPTIONS'].includes(normalized);
}
