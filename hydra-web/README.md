# Hydra Web

React/TypeScript web dashboard for the Hydra infrastructure management platform.

## Features

- **Dashboard** - Infrastructure overview with stats, capacity gauges, and activity feed
- **Node Explorer** - Browse, search, and manage infrastructure nodes with profile history
- **Service Explorer** - Track services across runtimes (Docker, systemd, Kubernetes, etc.)
- **Network Explorer** - View auto-discovered networks and their members
- **Group Management** - Create dynamic groups with flexible selectors
- **Topology Viewer** - Interactive infrastructure visualization with ReactFlow
- **Time Machine** - Navigate historical infrastructure states with timeline scrubbing
- **Admin Dashboard** - User management, registration tokens, API keys, and audit logs
- **MCP Chat** - AI chat interface (placeholder for hydra-mcp integration)

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **TailwindCSS** - Utility-first styling
- **TanStack Query** - Server state management
- **Zustand** - Client state management
- **ReactFlow** - Topology visualization
- **Framer Motion** - Animations
- **Recharts** - Dashboard charts
- **Axios** - HTTP client

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn
- Running hydra-api instance

### Installation

```bash
# Install dependencies
npm install

# Copy environment template
cp .env.example .env

# Configure API endpoint in .env
VITE_API_URL=http://localhost:8080/api/v1
```

### Development

```bash
# Start development server
npm run dev

# Run type checking
npm run typecheck

# Lint code
npm run lint

# Build for production
npm run build

# Preview production build
npm run preview
```

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
│   └── users.ts         # User management
├── components/
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
│   └── chat/            # MCP chat page
├── stores/              # Zustand stores
│   ├── auth-store.ts    # Authentication state
│   └── ui-store.ts      # UI preferences (theme, sidebar)
├── types/               # TypeScript type definitions
├── lib/                 # Utilities and constants
│   ├── api-client.ts    # Axios instance with interceptors
│   ├── query-client.ts  # TanStack Query configuration
│   ├── constants.ts     # Routes, colors, labels
│   ├── utils.ts         # Helper functions
│   └── animations.ts    # Framer Motion variants
└── router/              # React Router configuration
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Hydra API base URL | `http://localhost:8080/api/v1` |

### Theme

The app supports light and dark modes, toggled via the header. Theme preference is persisted in localStorage.

Custom colors are defined in `tailwind.config.js`:

- **Primary**: Hydra Blue `#3B82F6`
- **Compute**: Purple `#8B5CF6`
- **Networking**: Cyan `#06B6D4`
- **IoT**: Green `#10B981`

## Authentication

The app uses JWT authentication with access and refresh tokens:

1. Login stores tokens in the auth store (memory)
2. Axios interceptor attaches `Authorization` header
3. 401 responses trigger automatic token refresh
4. Refresh failure redirects to login

### Role-Based Access

Routes and UI elements are gated by user role:

- **admin** - Full access
- **operator** - Infrastructure management
- **viewer** - Read-only access
- **family** - IoT controls only

## API Integration

All API calls use TanStack Query for caching and synchronization:

```typescript
// Example: Fetch nodes with automatic caching
const { data, isLoading, error } = useNodes({ limit: 20, class: 'compute' });

// Example: Mutation with cache invalidation
const mutation = useUpdateNode();
await mutation.mutateAsync({ nodeId, data: { tags: ['production'] } });
```

Query keys are defined in `src/lib/query-client.ts` for consistent cache management.

## Building for Production

```bash
# Build optimized bundle
npm run build

# Output in dist/ directory
# Serve with any static file server
```

The build output is optimized with:
- Code splitting by route
- Tree shaking
- Asset hashing for cache busting
- Gzip-ready chunks

## License

Part of the Hydra project. See root LICENSE file.
