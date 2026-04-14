import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  esbuild: {
    jsx: 'automatic',
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/__tests__/setup.ts'],
    include: ['src/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}'],
    coverage: {
      reporter: ['text', 'html'],
      exclude: ['node_modules/', 'src/__tests__/setup.ts'],
    },
    env: {
      // Must match the BASE_URL in src/__tests__/msw/handlers.ts so MSW
      // intercepts Axios requests. This is a test fixture, not a deployment URL.
      NEXT_PUBLIC_API_URL: 'http://127.0.0.1:8080/api/v1',
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
