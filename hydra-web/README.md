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
- **MCP Chat** - AI chat interface with LLM provider configuration and MCP server management

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **TailwindCSS** - Utility-first styling
- **Radix UI** - Headless UI primitives
- **shadcn/ui patterns** - Component architecture with CVA variants
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

## UI Component Library

The application uses a shadcn/ui-inspired component library built with Radix UI primitives and class-variance-authority (CVA) for variant management.

### Available Components

| Component | Description |
|-----------|-------------|
| `Button` | Primary action buttons with variants: default, destructive, outline, secondary, ghost, link, success, warning |
| `Card` | Container component with CardHeader, CardTitle, CardDescription, CardContent, CardFooter |
| `Badge` | Status indicators with variants: default, secondary, destructive, outline, success, warning, compute, network, iot |
| `Input` | Text input field |
| `Textarea` | Multi-line text input |
| `Label` | Form field labels |
| `Select` | Dropdown selection with SelectTrigger, SelectContent, SelectItem |
| `Dialog` | Modal dialogs with DialogHeader, DialogTitle, DialogDescription, DialogContent |
| `DropdownMenu` | Action menus with DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem |
| `Tabs` | Tabbed navigation with TabsList, TabsTrigger, TabsContent |
| `Table` | Data tables with TableHeader, TableBody, TableRow, TableHead, TableCell |
| `Tooltip` | Hover hints with TooltipProvider, TooltipTrigger, TooltipContent |
| `Avatar` | User avatars with AvatarImage, AvatarFallback |
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
        <Button variant="outline" size="sm">
          View Details
        </Button>
      </CardContent>
    </Card>
  );
}
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Hydra API base URL | `http://localhost:8080/api/v1` |

### Theme

The app uses a dark theme with the Geist Mono font. Colors are defined using HSL CSS variables for easy customization.

#### Design Tokens

| Token | Description | Value |
|-------|-------------|-------|
| `--primary` | Primary actions | Hydra Blue |
| `--compute` | Compute nodes | Purple `#8B5CF6` |
| `--networking` | Network devices | Cyan `#06B6D4` |
| `--iot` | IoT devices | Green `#10B981` |
| `--success` | Success states | Green |
| `--warning` | Warning states | Amber |
| `--destructive` | Error/danger states | Red |

Theme preference is persisted in localStorage.

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
