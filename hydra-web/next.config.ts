import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Proxy API requests to hydra-api in development.
  // Only active when HYDRA_API_PROXY_TARGET is set.
  // In production, a reverse proxy (nginx/Caddy) handles /api routing.
  async rewrites() {
    const proxyTarget = process.env.HYDRA_API_PROXY_TARGET;
    if (!proxyTarget) return [];

    return [
      {
        source: '/api/:path*',
        destination: `${proxyTarget}/api/:path*`,
      },
    ];
  },

  // Transpile packages that need it
  transpilePackages: ['elkjs'],
};

export default nextConfig;
