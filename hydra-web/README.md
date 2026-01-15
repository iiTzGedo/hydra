<p align="center">
  <img src="../resources/assets/logos/hydra-logos-v1_dark_256.png" alt="Hydra Logo" width="128" height="128">
</p>

<h1 align="center">Hydra Web</h1>

<p align="center">
  <a href="https://react.dev/"><img src="https://img.shields.io/badge/React-18%2B-61DAFB.svg" alt="React"></a>
  <a href="https://www.typescriptlang.org/"><img src="https://img.shields.io/badge/TypeScript-5.0%2B-3178C6.svg" alt="TypeScript"></a>
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
- [UI Component Library](#ui-component-library)
- [State Management](#state-management)
- [API Integration](#api-integration)
- [Theming](#theming)
- [Authentication](#authentication)
- [Building for Production](#building-for-production)
- [Docker](#docker)
- [Development](#development)
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

## Quick Start

```bash
# Install dependencies
npm install

# Configure API endpoint
cp .env.example .env
# Edit .env: VITE_API_URL=http://localhost:8080/api/v1

# Start development server
npm run dev
```

## Installation

### Prerequisites

- Node.js 18+
- npm or yarn
- Running hydra-api instance

### Install Dependencies

```bash
npm install
```

### Environment Setup

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
VITE_API_URL=http://localhost:8080/api/v1
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Hydra API base URL | `http://localhost:8080/api/v1` |

## Project Structure

```
src/
├── api/                 # TanStack Query hooks for API calls
│   ├── auth.ts          # Authentication endpoints
│   ├── nodes.ts         # Node CRUD operations
│   ├── profiles.ts      # Profile history
│   ├── services.ts      # Service management
│   ├── networks.ts      # Network operations
│   ├── groups.ts        # Group management
│   ├── topologies.ts    # Topology generation
│   ├── timemachine.ts   # Historical state queries
│   ├── users.ts         # User management
│   └── mcp.ts           # MCP server integration
├── components/
│   ├── ui/              # Reusable UI components (shadcn-style)
│   ├── layout/          # App shell (sidebar, header, etc.)
│   ├── dashboard/       # Dashboard widgets
│   ├── topology/        # ReactFlow nodes and controls
│   ├── timemachine/     # Timeline scrubber and historical view
│   └── chat/            # MCP chat interface
├── pages/               # Route components
│   ├── auth/            # Login, register, password reset
│   ├── dashboard/       # Main dashboard
│   ├── nodes/           # Node list and details
│   ├── services/        # Service list and details
│   ├── networks/        # Network list and details
│   ├── groups/          # Group list, details, and creation
│   ├── topology/        # Interactive topology viewer
│   ├── timemachine/     # Historical state browser
│   ├── admin/           # Admin pages (users, tokens, etc.)
│   ├── chat/            # MCP chat page
│   ├── mcp/             # MCP server management
│   └── settings/        # User settings
├── stores/              # Zustand stores
│   ├── auth-store.ts    # Authentication state
│   ├── ui-store.ts      # UI preferences (theme, sidebar)
│   └── mcp-store.ts     # MCP server connections
├── types/               # TypeScript type definitions
├── lib/                 # Utilities and constants
│   ├── api-client.ts    # Axios instance with interceptors
│   ├── query-client.ts  # TanStack Query configuration
│   ├── constants.ts     # Routes, colors, labels
│   ├── utils.ts         # Helper functions
│   └── animations.ts    # Framer Motion variants
└── router/              # React Router configuration
```

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
| `/mcp/marketplace` | MCP Marketplace | Browse MCP servers |
| `/admin/users` | User Management | Admin user CRUD |
| `/admin/tokens` | Token Management | Registration tokens |
| `/admin/apikeys` | API Keys | API key management |
| `/admin/audit` | Audit Log | Activity audit trail |
| `/settings` | Settings | User preferences |

## UI Component Library

Built with Radix UI primitives and class-variance-authority (CVA) for variant management.

### Available Components

| Component | Description |
|-----------|-------------|
| `Button` | Primary actions with variants: default, destructive, outline, secondary, ghost, link, success, warning |
| `Card` | Container with CardHeader, CardTitle, CardDescription, CardContent, CardFooter |
| `Badge` | Status indicators: default, secondary, destructive, outline, success, warning, compute, network, iot |
| `Input` | Text input field |
| `Textarea` | Multi-line text input |
| `Label` | Form field labels |
| `Select` | Dropdown selection |
| `Dialog` | Modal dialogs |
| `DropdownMenu` | Action menus |
| `Tabs` | Tabbed navigation |
| `Table` | Data tables |
| `Tooltip` | Hover hints |
| `Avatar` | User avatars |
| `Skeleton` | Loading placeholders |
| `Progress` | Progress bars |
| `Checkbox` | Checkbox inputs |
| `Switch` | Toggle switches |
| `Slider` | Range sliders |
| `ScrollArea` | Custom scrollbars |
| `Separator` | Visual dividers |
| `Popover` | Floating content panels |
| `Command` | Command palette / autocomplete |

### Usage Example

```tsx
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

function NodeCard({ node }) {
  return (
    <Card className="hover:bg-accent/50 transition-colors">
      <CardHeader>
        <CardTitle>{node.nodeId}</CardTitle>
        <Badge variant={node.class}>{node.class}</Badge>
      </CardHeader>
      <CardContent>
        <p className="text-muted-foreground">{node.description}</p>
        <Button variant="outline" size="sm">View Details</Button>
      </CardContent>
    </Card>
  );
}
```

## State Management

### Zustand Stores

| Store | Purpose |
|-------|---------|
| `auth-store` | JWT tokens, user info, login/logout |
| `ui-store` | Theme, sidebar state, preferences |
| `mcp-store` | MCP server connections, chat state |

### TanStack Query

Server state managed via TanStack Query with automatic caching and refetching.

```typescript
// Example: Fetch nodes with caching
const { data, isLoading, error } = useNodes({ limit: 20, class: 'compute' });

// Example: Mutation with cache invalidation
const mutation = useUpdateNode();
await mutation.mutateAsync({ nodeId, data: { tags: ['production'] } });
```

## API Integration

All API calls use TanStack Query hooks defined in `src/api/`:

| Hook | Endpoint |
|------|----------|
| `useNodes` | GET `/nodes` |
| `useNode` | GET `/nodes/:nodeId` |
| `useServices` | GET `/services` |
| `useNetworks` | GET `/networks` |
| `useGroups` | GET `/groups` |
| `useTopology` | GET `/topologies/current` |
| `useTimeMachineState` | GET `/timemachine/state` |

## Theming

Dark theme with Geist Mono font. Colors defined using HSL CSS variables.

### Design Tokens

| Token | Description | Value |
|-------|-------------|-------|
| `--primary` | Primary actions | Hydra Blue |
| `--compute` | Compute nodes | Purple `#8B5CF6` |
| `--networking` | Network devices | Cyan `#06B6D4` |
| `--iot` | IoT devices | Green `#10B981` |
| `--success` | Success states | Green |
| `--warning` | Warning states | Amber |
| `--destructive` | Error/danger | Red |

Theme preference persisted in localStorage.

## Authentication

JWT authentication with access and refresh tokens:

1. Login stores tokens in auth store (memory)
2. Axios interceptor attaches `Authorization` header
3. 401 responses trigger automatic token refresh
4. Refresh failure redirects to login

### Role-Based Access

| Role | Access |
|------|--------|
| admin | Full access |
| operator | Infrastructure management |
| viewer | Read-only access |
| family | IoT controls only |

## Building for Production

```bash
# Build optimized bundle
npm run build

# Preview production build
npm run preview
```

Output in `dist/` directory with:
- Code splitting by route
- Tree shaking
- Asset hashing for cache busting
- Gzip-ready chunks

## Docker

### Building the Image

```bash
docker build -t hydra-web:latest .
```

### Running with Docker

```bash
docker run -p 3000:80 \
  -e VITE_API_URL=http://localhost:8080/api/v1 \
  hydra-web:latest
```

### Docker Compose

```bash
# Start with docker-compose
docker-compose -f docker-compose.dev.yml up hydra-web

# View logs
docker-compose -f docker-compose.dev.yml logs -f hydra-web
```

## Development

### Scripts

```bash
# Development server with HMR
npm run dev

# Type checking
npm run typecheck

# Lint code
npm run lint

# Format code
npm run format

# Build for production
npm run build

# Preview production build
npm run preview
```

### Tech Stack

| Library | Purpose |
|---------|---------|
| React 18 | UI framework |
| TypeScript 5 | Type safety |
| Vite | Build tool and dev server |
| TailwindCSS | Utility-first styling |
| Radix UI | Headless UI primitives |
| TanStack Query | Server state management |
| Zustand | Client state management |
| ReactFlow | Topology visualization |
| Framer Motion | Animations |
| Recharts | Dashboard charts |
| Axios | HTTP client |

## License

Apache-2.0 - See [LICENSE](../LICENSE) for details.
