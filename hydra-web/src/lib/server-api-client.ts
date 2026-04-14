import { cookies } from 'next/headers';

function getServerApiUrl(): string {
  const url = process.env.HYDRA_API_URL;
  if (!url) {
    throw new Error(
      'HYDRA_API_URL environment variable is required for server-side API calls. ' +
        'Set it to the internal hydra-api base URL (e.g., http://hydra-api:8080/api/v1).'
    );
  }
  return url;
}

/**
 * Server-side API client for React Server Components.
 * Forwards cookies from the incoming request to hydra-api.
 *
 * Requires HYDRA_API_URL environment variable — this must be an absolute URL
 * reachable from the Next.js server process (not the browser).
 * Examples:
 *   - Docker Compose: http://hydra-api:8080/api/v1
 *   - Same host:      http://localhost:8080/api/v1
 *   - Remote:         http://api.internal:8080/api/v1
 */
export async function serverFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const apiBaseUrl = getServerApiUrl();
  const cookieStore = await cookies();
  const cookieHeader = cookieStore.toString();

  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const url = `${apiBaseUrl}${normalizedPath}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Cookie: cookieHeader,
      ...options?.headers,
    },
    cache: 'no-store',
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  const data = await response.json();
  // hydra-api wraps responses in { success: true, data: T }
  return data.data ?? data;
}
