<p align="center">
  <img src="../resources/assets/logos/hydra-logos-v1_dark_256.png" alt="Hydra Logo" width="128" height="128">
</p>

<h1 align="center">Hydra Web</h1>

<p align="center">
  <a href="https://react.dev/"><img src="https://img.shields.io/badge/React-18%2B-61DAFB.svg" alt="React"></a>
  <a href="https://www.typescriptlang.org/"><img src="https://img.shields.io/badge/TypeScript-5.0%2B-3178C6.svg" alt="TypeScript"></a>
  <a href="https://nodejs.org/"><img src="https://img.shields.io/badge/node-22%2B-green.svg" alt="Node.js"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue.svg" alt="License"></a>
</p>

<p align="center">
  React/TypeScript web dashboard for the <a href="https://github.com/yourorg/hydra">Hydra</a> infrastructure management platform.<br>
  Modern UI with topology visualization, time machine, and AI chat.
</p>

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Pages & Routes](#pages--routes)
- [Development](#development)
- [Testing](#testing)
- [Docker](#docker)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Features

- **Dashboard** - Infrastructure overview with stats, capacity gauges, and activity feed
- **Node Explorer** - Browse, search, and manage infrastructure nodes with profile history
- **Service Explorer** - Track services across runtimes (Docker, systemd, Kubernetes, etc.)
- **Network Explorer** - View auto-discovered networks and their members
- **Group Management** - Create dynamic groups with flexible selectors
- **Topology Viewer** - Interactive infrastructure visualization with ReactFlow
- **Time Machine** - Navigate historical infrastructure states with timeline scrubbing
- **Admin Dashboard** - User management, registration tokens, API keys, and audit logs
- **MCP Chat** - AI chat interface with LLM provider configuration and MCP server management
- **Notifications** - Real-time notification system with read tracking

## Quick Start

```bash
cd hydra-web

# Install dependencies
npm install

# Configure API endpoint
cp .env.example .env
# Edit .env: NEXT_PUBLIC_API_URL= (leave empty for relative /api/v1)

# Start development server
npm run dev
```

The dev server starts at `http://localhost:5173`. Requires a running [hydra-api](../hydra-api/README.md) instance.

## Installation

### Prerequisites

- Node.js 22+
- npm
- [Docker Engine](https://docs.docker.com/engine/install/) with the [Compose plugin](https://docs.docker.com/compose/install/) (`docker compose`) — for containerized deployment
- A running [hydra-api](../hydra-api/README.md) instance

### Install Dependencies

```bash
npm install
```

### Environment Setup

```bash
cp .env.example .env
```

Edit `.env` with your configuration (see [Configuration](#configuration) below).

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | API URL exposed to the browser (leave empty for relative `/api/v1`) | _(empty)_ |
| `HYDRA_API_URL` | Internal API URL for server components (SSR) | _(unset)_ |
| `HYDRA_API_PROXY_TARGET` | Dev-only rewrite proxy target | `http://localhost:8080` |

## Pages & Routes

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Infrastructure overview |
| `/login` | Login | User authentication |
| `/nodes` | Node Explorer | Browse and search nodes |
| `/nodes/:nodeId` | Node Details | Node info, profiles, services |
| `/services` | Service Explorer | All services across nodes |
| `/services/:serviceId` | Service Details | Service info and history |
| `/networks` | Network Explorer | Auto-discovered networks |
| `/networks/:networkId` | Network Details | Network members and config |
| `/groups` | Group Management | Logical groupings |
| `/groups/:groupId` | Group Details | Group members and selectors |
| `/topology` | Topology Viewer | Interactive infrastructure graph |
| `/timemachine` | Time Machine | Historical state navigation |
| `/chat` | MCP Chat | AI chat interface |
| `/mcp/marketplace` | MCP Marketplace | MCP server management |
| `/admin/users` | User Management | Admin user CRUD |
| `/admin/tokens` | Token Management | Registration tokens |
| `/admin/apikeys` | API Keys | API key management |
| `/admin/audit` | Audit Log | Activity audit trail |
| `/notifications` | Notifications | Notification center |
| `/settings` | Settings | User preferences |

## Development

### Scripts

| Script | Command | Description |
|--------|---------|-------------|
| `dev` | `npm run dev` | Start Vite dev server with HMR |
| `build` | `npm run build` | Type-check and build production bundle |
| `preview` | `npm run preview` | Preview production build locally |
| `lint` | `npm run lint` | Run ESLint |
| `lint:fix` | `npm run lint:fix` | Auto-fix lint issues |
| `typecheck` | `npm run typecheck` | Run TypeScript type checking |
| `test` | `npm run test` | Run Vitest unit tests |
| `test:watch` | `npm run test:watch` | Run tests in watch mode |
| `test:e2e` | `npm run test:e2e` | Run Playwright E2E tests |
| `serve` | `npm run serve` | Serve production build on port 3000 |

### Tech Stack

| Library | Version | Purpose |
|---------|---------|---------|
| React | 18 | UI framework |
| TypeScript | 5 | Type safety |
| Vite | 6 | Build tool and dev server |
| TailwindCSS | 3 | Utility-first styling |
| Radix UI | Latest | Headless UI primitives |
| TanStack Query | 5 | Server state management |
| Zustand | 4 | Client state management |
| ReactFlow | 12 | Topology visualization |
| Framer Motion | 11 | Animations |
| Recharts | 2 | Dashboard charts |
| Axios | 1 | HTTP client |

### Authentication

JWT authentication with access and refresh tokens:

1. Login stores tokens in the auth store (memory)
2. Axios interceptor attaches `Authorization` header to every request
3. 401 responses trigger automatic token refresh
4. Refresh failure redirects to `/login`

### Role-Based Access

| Role | Access |
|------|--------|
| `admin` | Full access |
| `operator` | Infrastructure management |
| `viewer` | Read-only access |
| `family` | IoT controls only |

### Theming

Dark theme with Geist Mono font. Colors defined using HSL CSS variables.

| Token | Description | Color |
|-------|-------------|-------|
| `--primary` | Primary actions | Hydra Blue |
| `--compute` | Compute nodes | Purple `#8B5CF6` |
| `--networking` | Network devices | Cyan `#06B6D4` |
| `--iot` | IoT devices | Green `#10B981` |
| `--success` | Success states | Green |
| `--warning` | Warning states | Amber |
| `--destructive` | Error/danger | Red |

Theme preference is persisted in `localStorage`.

## Testing

### Unit & Integration Tests

Tests use [Vitest](https://vitest.dev/) with [Testing Library](https://testing-library.com/) and [MSW](https://mswjs.io/) for API mocking.

```bash
# Run all unit tests
npm run test

# Run in watch mode
npm run test:watch
```

### End-to-End Tests

E2E tests use [Playwright](https://playwright.dev/) against a running dev environment.

```bash
# Install Playwright browsers (first time)
npx playwright install

# Run E2E tests
npm run test:e2e
```

Log in with the test account (`system_admin` / `system12345`).

## Docker

### Building the Image

```bash
docker build -t hydra-web:latest .
```

This builds the production bundle and serves it with Node `serve` (SPA routing via `-s` flag).

### Running with Docker

```bash
docker run -p 3000:3000 hydra-web:latest
```

> **Note:** `NEXT_PUBLIC_API_URL` is embedded in the browser bundle at build time. To change it, rebuild the image with the desired value. Leave it empty to use relative `/api/v1` behind a reverse proxy.

### Docker Compose

From the repository root:

```bash
# Start all Hydra services
docker compose up -d

# Start only hydra-web
docker compose up -d hydra-web

# View logs
docker compose logs -f hydra-web
```

## Security

- All API communication uses JWT tokens — no credentials stored in the browser beyond memory
- Axios interceptor handles token refresh transparently
- Role-based route guards prevent unauthorized page access
- CORS configured via the API (`HYDRA_CORS_ORIGINS`)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `NEXT_PUBLIC_API_URL` not working | Ensure the variable is set **before** `npm run build`; Next.js embeds `NEXT_PUBLIC_*` vars at build time |
| CORS errors in browser | Check `HYDRA_CORS_ORIGINS` in the API includes your web origin (e.g., `http://localhost:5173`) |
| Blank page after deploy | Verify `next.config.ts` rewrites are correct and `npm run build && npm start` completes without errors |
| 401 loops | Clear browser storage and re-login; the refresh token may have expired |
| `npm install` engine warning | Ensure Node.js >= 22 (`node --version`) |

## License

Apache-2.0 — See [LICENSE](../LICENSE) for details.
