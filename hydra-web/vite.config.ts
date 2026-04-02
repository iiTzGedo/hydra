/// <reference types="vitest" />
import path from 'path';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

function buildConnectSources(apiBaseUrl: string): string[] {
  const sources = new Set(["'self'"]);
  if (!apiBaseUrl || !/^https?:\/\//.test(apiBaseUrl)) {
    return Array.from(sources);
  }

  const apiUrl = new URL(apiBaseUrl);
  sources.add(apiUrl.origin);
  sources.add(`${apiUrl.protocol === 'https:' ? 'wss:' : 'ws:'}//${apiUrl.host}`);
  return Array.from(sources);
}

function buildContentSecurityPolicy(apiBaseUrl: string): string {
  return [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    `connect-src ${buildConnectSources(apiBaseUrl).join(' ')}`,
    "img-src 'self' data: blob:",
    "worker-src 'self' blob:",
  ].join('; ');
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, '');
  const apiBaseUrl = env.VITE_API_URL || '/api/v1';
  const csp = buildContentSecurityPolicy(apiBaseUrl);

  return {
    plugins: [
      react(),
      {
        name: 'hydra-csp',
        transformIndexHtml(html) {
          return html.replace('__HYDRA_CSP__', csp);
        },
      },
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
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
        VITE_API_URL: 'http://localhost:8080/api/v1',
      },
    },
    optimizeDeps: {
      include: ['elkjs/lib/elk.bundled.js'],
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: 'http://localhost:8080',
          changeOrigin: true,
          ws: true,
        },
      },
    },
    build: {
      sourcemap: false,
      commonjsOptions: {
        include: [/elkjs/, /node_modules/],
      },
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ['react', 'react-dom', 'react-router-dom'],
            ui: ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu', '@radix-ui/react-tabs'],
            query: ['@tanstack/react-query', 'axios'],
            charts: ['@xyflow/react'],
          },
        },
      },
    },
  };
});
