# Hydra Dashboard Technical Specification

> **Version:** 0.5.0  
> **Last Updated:** 2026-02-22  
> **Status:** Technical Specification — Customizable Dashboard Framework, Widget System Architecture, Board Model, Data Binding, Layout Engine, Plugin Widget Contributions  
> **Dependencies:** Phase 2 Technical Specification (Agent Architecture, Commands & Workflows), Plugin Architecture v0.4.0 (All 19 Integrations), Technical Documentation v0.3.0 (Data Model, RBAC, Services)

---

## Table of Contents

1. [Document Overview](#1-document-overview)
2. [Dashboard Framework Architecture](#2-dashboard-framework-architecture)
3. [Board Model](#3-board-model)
4. [Widget System Architecture](#4-widget-system-architecture)
5. [Widget Component Library](#5-widget-component-library)
6. [Data Source & Query Model](#6-data-source--query-model)
7. [Layout Engine](#7-layout-engine)
8. [Dashboard Templates & Presets](#8-dashboard-templates--presets)
9. [RBAC Integration](#9-rbac-integration)
10. [Plugin Widget Contributions](#10-plugin-widget-contributions)
11. [Real-Time Updates & Caching](#11-real-time-updates--caching)
12. [API Specification](#12-api-specification)
13. [Data Model](#13-data-model)
14. [hydra-web Implementation](#14-hydra-web-implementation)
15. [MCP Integration](#15-mcp-integration)
16. [Mobile, Tablet & Kiosk Modes](#16-mobile-tablet--kiosk-modes)
17. [Import, Export & Sharing](#17-import-export--sharing)
18. [Implementation Roadmap](#18-implementation-roadmap)
19. [Appendices](#19-appendices)

---

## 1. Document Overview

### 1.1 Purpose

This document specifies Hydra's customizable dashboard framework — a system that allows users of any role to create, configure, save, and share personalized dashboards composed from a diverse widget library. The widget library is sourced from three tiers: Hydra-native components, plugin-contributed widgets from all 19 integrations, and external/embed widgets for third-party content.

| Aspect | Scope |
|--------|-------|
| **Board Model** | Multi-board per user, templates, sharing, cloning, import/export |
| **Widget System** | Registry, lifecycle, data binding, rendering contracts, extensibility |
| **Layout Engine** | Grid-based with column modes, responsive breakpoints, display contexts |
| **Data Binding** | Structured query model for widget data sourcing, refresh, and caching |
| **Plugin Widgets** | Dynamic widget registration from enabled integrations |
| **RBAC** | Role-scoped widget libraries, board visibility, control-capable widgets |
| **Real-Time** | WebSocket push, polling intervals, stale data indicators |
| **Multi-Surface** | Desktop, mobile, tablet wall-mount, embedded panels, kiosk mode |

### 1.2 Design Principles

**Dashboards Are First-Class Entities**
Boards are not a secondary view layered on top of existing pages. They are a primary navigation surface — stored in MongoDB, versioned, shareable, and queryable by the MCP service. A user's "home" in Hydra can be a dashboard they built.

**Data Already Exists — Dashboards Consume It**
Unlike Glance (which scrapes external URLs) or Homarr (which connects to Docker sockets directly), Hydra's dashboards are backed by the Hydra API. All profiling data, service state, topology, integration enrichments — it's already collected and centralized. Widgets bind to API queries, not to external systems.

**Widgets Are Typed, Not Generic**
Every widget has a rendering contract (what it can display) and a data contract (what shape of data it needs). A "metric card" widget renders a number with a label and optional trend. A "status grid" renders a matrix of entity states with color coding. This typing enables validation, auto-suggestion, and plugin contribution without ambiguity.

**Progressive Complexity**
A new user can pick a pre-built template and have a working dashboard immediately. An advanced user can create custom boards with complex data bindings, conditional widgets, and cross-board linking. The system serves both without forcing either path.

**Every Widget Respects RBAC**
A `family` user's widget library only shows IoT-relevant widgets. An `operator` sees infrastructure and control widgets. Widgets that perform actions (restart a container, toggle a light) enforce the same permission checks as the underlying command execution system.

### 1.3 Component Responsibility Matrix

| Concern | hydra-api | hydra-web | hydra-mcp |
|---------|-----------|-----------|-----------|
| Board CRUD | Storage, validation, versioning | Editor UI, live preview | Board creation/query tools |
| Widget Registry | Serves registry with role filtering | Renders widgets, edit panels | Widget listing tools |
| Data Resolution | Resolves widget data queries | Fetches via TanStack Query | N/A (MCP reads boards, not widget data) |
| Plugin Widgets | Registers plugin-contributed widgets on enable | Dynamically loads plugin widget renderers | Exposes plugin widget capabilities |
| Layout | Stores layout definitions | Grid engine, drag-drop, responsive | N/A |
| Real-Time | WebSocket event dispatch | WebSocket subscription per widget | N/A |
| Templates | Stores and serves templates | Template picker, preview | Template application tools |

### 1.4 Practical Use Cases

These use cases ground every design decision in this document. If a feature doesn't serve at least one of these, it doesn't belong in v1.

| Use Case | Persona | What They Build |
|----------|---------|-----------------|
| **Infrastructure overview** | Homelabber (operator) | Board showing all compute nodes by status, total capacity gauges (CPU/RAM/disk), service health grid, mini topology, recent profile activity |
| **Docker fleet view** | Homelabber (operator) | Board per Docker host showing containers by compose project, image update status, port mapping table, volume usage, restart buttons |
| **IoT home control** | Family member | Board per room with light toggles, thermostat controls, scene activation buttons, sensor readings, presence indicators |
| **Network status board** | Network admin (operator) | Board showing all networking nodes, interface status, DHCP lease count, DNS query stats (Pi-hole/AdGuard), VPN tunnel status (Tailscale), firewall rule count (pfSense/OPNsense) |
| **Wall-mounted status display** | Anyone (kiosk mode) | Glance-style read-only board on a wall tablet — node status, service health, weather embed, RSS feed, clock. Auto-refreshes, no interaction needed |
| **Capacity planning view** | Homelabber (admin) | Board with storage fill gauges per node, RAM allocation bars, CPU headroom, profile age indicators, "capacity runway" estimates |
| **Monitoring aggregation** | Homelabber (operator) | Board pulling Prometheus metrics via plugin, Uptime Kuma status grid, Grafana iframe embed, custom alerting thresholds with color coding |
| **AI-assisted dashboard** | Any user via MCP | "Create me a dashboard showing my Docker hosts and their container counts" → MCP creates a board definition via API tools |
| **Proxmox cluster view** | Homelabber (operator) | Board showing cluster nodes, VM/LXC status grid, Ceph storage health, HA group status, resource allocation per host, migration history |
| **Personal operations hub** | Homelabber (admin) | Board with command execution queue, recent audit log entries, workflow triggers, integration health indicators, and a quick-run command panel |

---

## 2. Dashboard Framework Architecture

### 2.1 Architectural Overview

The dashboard framework is a layered system where each layer has a distinct responsibility:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                          │
│  Layout Engine · Widget Renderers · Edit Mode · Responsive Grid    │
├─────────────────────────────────────────────────────────────────────┤
│                        BINDING LAYER                               │
│  Data Source Resolution · Query Execution · Cache · WebSocket Sub  │
├─────────────────────────────────────────────────────────────────────┤
│                        REGISTRY LAYER                              │
│  Widget Registry · Plugin Widget Loader · Template Registry        │
├─────────────────────────────────────────────────────────────────────┤
│                        PERSISTENCE LAYER                           │
│  Board Collection · Widget Definitions · User Preferences          │
├─────────────────────────────────────────────────────────────────────┤
│                        DATA LAYER (existing)                       │
│  Nodes · Profiles · Services · Topology · Integrations · Commands  │
└─────────────────────────────────────────────────────────────────────┘
```

**Persistence Layer** — Boards, their widget configurations, and layout definitions are stored in MongoDB. This is the board's source of truth. The API serves and validates board CRUD.

**Registry Layer** — The widget registry is a runtime catalog of all available widget types — Hydra-native, plugin-contributed, and external. The template registry holds pre-built board definitions. Both are assembled at API startup and updated when plugins are enabled/disabled.

**Binding Layer** — Each widget instance on a board has a data source binding. The binding layer resolves these at render time — translating widget data queries into API calls, managing cache, and subscribing to WebSocket events for real-time widgets.

**Presentation Layer** — The layout engine positions widgets on a grid. Widget renderers are React components that receive resolved data and render according to the widget type's visual contract. Edit mode enables drag-drop, resize, configuration panels, and live preview.

### 2.2 Data Flow

```
User opens board
    │
    ▼
hydra-web loads board definition from API
    │  GET /dashboards/{boardId}
    ▼
Board definition contains widget instances with data bindings
    │
    ▼
For each widget instance:
    ├─ Resolve data source binding → API endpoint(s) + query params
    ├─ Execute via TanStack Query (with caching, dedup, stale-while-revalidate)
    ├─ Subscribe to WebSocket channel if widget supports real-time
    └─ Pass resolved data to widget renderer component
    │
    ▼
Layout engine positions all widgets according to grid definition
    │
    ▼
User sees rendered board with live data
```

### 2.3 Widget Instance Lifecycle

A widget goes through these states from creation to rendering:

```
REGISTERED (in registry)         — Widget type exists, has metadata
    │
    ▼
CONFIGURED (on board)            — User placed it, set data bindings + options
    │
    ▼
BOUND (data source resolved)     — API endpoint known, query params set
    │
    ▼
LOADING (data fetching)          — TanStack Query in flight
    │
    ▼
RENDERED (data displayed)        — Widget component has data, is visible
    │
    ├─► REFRESHING (re-fetch)    — Polling interval elapsed or WebSocket event
    ├─► STALE (source unavail.)  — API/integration unreachable, showing last known
    ├─► ERROR (binding failed)   — Invalid query, permission denied, source missing
    └─► RECONFIGURED             — User changed binding/options → back to BOUND
```

---

## 3. Board Model

### 3.1 What a Board Is

A board is a named, versioned, saveable arrangement of widget instances on a grid layout. Boards are scoped to a user (private) or shared with roles/all users (shared). Every user can have multiple boards. One board is designated as their "home" board — what they see when they open Hydra.

### 3.2 Board Types

| Type | Description | Created By | Visibility |
|------|-------------|------------|------------|
| **User Board** | Custom board created by a user | Any user | Private to creator, optionally shared |
| **Template Board** | Pre-built board shipped with Hydra or created by admins | Hydra / Admin | Available for cloning to all applicable roles |
| **Shared Board** | Board published to specific roles or all users | Operator / Admin | Read-only for recipients, editable by owner |
| **Kiosk Board** | Board optimized for passive display (no controls, auto-refresh) | Any user | Accessible via kiosk URL without full auth |

### 3.3 Board Definition Schema

```json
{
  "boardId": "board_abc123",
  "name": "Infrastructure Overview",
  "description": "Main operational view of all compute infrastructure",
  "icon": "server",
  "ownerId": "user_admin001",
  "ownerType": "user",
  "boardType": "user",
  "visibility": {
    "scope": "shared",
    "sharedWith": {
      "roles": ["admin", "operator"],
      "users": []
    }
  },
  "layout": {
    "mode": "grid",
    "columns": 12,
    "rowHeight": 80,
    "breakpoints": {
      "xl": { "columns": 12, "width": 1536 },
      "lg": { "columns": 12, "width": 1200 },
      "md": { "columns": 8, "width": 996 },
      "sm": { "columns": 4, "width": 768 },
      "xs": { "columns": 2, "width": 480 }
    },
    "compaction": "vertical",
    "margin": [16, 16],
    "containerPadding": [16, 16]
  },
  "widgets": [
    {
      "instanceId": "wi_001",
      "widgetType": "hydra::metric-card",
      "position": {
        "xl": { "x": 0, "y": 0, "w": 3, "h": 2 },
        "md": { "x": 0, "y": 0, "w": 4, "h": 2 },
        "sm": { "x": 0, "y": 0, "w": 2, "h": 2 }
      },
      "dataBinding": {
        "source": "hydra::nodes",
        "query": {
          "endpoint": "/nodes",
          "params": { "class": "compute", "status": "online" },
          "transform": "count"
        },
        "refreshInterval": 60
      },
      "config": {
        "title": "Compute Nodes Online",
        "icon": "server",
        "color": "green",
        "trend": { "enabled": true, "field": "count", "window": "24h" }
      }
    }
  ],
  "settings": {
    "theme": "inherit",
    "autoRefresh": true,
    "refreshInterval": 30,
    "showHeader": true,
    "kioskMode": false,
    "backgroundImage": null
  },
  "tags": ["infrastructure", "overview"],
  "isHome": true,
  "version": 1,
  "createdAt": "2026-02-20T10:00:00Z",
  "updatedAt": "2026-02-22T08:30:00Z",
  "clonedFrom": null
}
```

### 3.4 Board Lifecycle Operations

| Operation | Description | Permissions |
|-----------|-------------|-------------|
| **Create** | New empty board or from template | All roles |
| **Edit** | Modify layout, widgets, settings | Owner only |
| **Clone** | Duplicate a board (template or shared) as a new private board | All roles (for visible boards) |
| **Share** | Publish board to roles or specific users | Operator, Admin |
| **Unshare** | Revoke shared visibility | Owner, Admin |
| **Delete** | Remove board (soft delete, recoverable for 30 days) | Owner, Admin |
| **Set Home** | Designate board as user's default landing | Owner (for own boards) |
| **Export** | Export board definition as JSON or YAML | Owner, Admin |
| **Import** | Import board definition from JSON or YAML | All roles (validated against registry) |
| **Version** | Auto-versioned on save; previous versions browsable | Owner |

### 3.5 Board Navigation

Users access boards through:

1. **Sidebar "Dashboards" section** — Lists all boards the user owns or can see, with the home board pinned at top.
2. **Board tab bar** — When on a dashboard page, tabs across the top allow switching between boards (like Glance's page tabs).
3. **Quick switcher (Cmd+K)** — Universal search includes boards by name.
4. **Direct URL** — Every board has a stable URL: `/dashboards/{boardId}`.
5. **Kiosk URL** — Kiosk boards have a simplified URL: `/kiosk/{boardId}` with minimal chrome.

---

## 4. Widget System Architecture

### 4.1 Widget Type Definition

Every widget type — whether Hydra-native, plugin-contributed, or external — is defined by a registration object that declares its rendering contract, data contract, and configuration schema.

```json
{
  "widgetType": "hydra::metric-card",
  "displayName": "Metric Card",
  "description": "Displays a single numeric value with label, icon, optional trend line and comparison",
  "category": "data-display",
  "icon": "hash",
  "source": "hydra",
  "version": "1.0.0",
  "supportedDataShapes": ["scalar", "scalar-with-trend"],
  "configSchema": {
    "type": "object",
    "properties": {
      "title": { "type": "string", "maxLength": 64 },
      "icon": { "type": "string" },
      "color": { "type": "string", "enum": ["green", "blue", "amber", "red", "purple", "gray"] },
      "unit": { "type": "string", "maxLength": 16 },
      "trend": {
        "type": "object",
        "properties": {
          "enabled": { "type": "boolean" },
          "field": { "type": "string" },
          "window": { "type": "string", "enum": ["1h", "6h", "24h", "7d", "30d"] }
        }
      },
      "thresholds": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "value": { "type": "number" },
            "color": { "type": "string" },
            "label": { "type": "string" }
          }
        }
      }
    }
  },
  "defaultSize": { "w": 3, "h": 2 },
  "minSize": { "w": 2, "h": 1 },
  "maxSize": { "w": 12, "h": 4 },
  "permissions": {
    "view": ["admin", "operator", "viewer"],
    "interact": []
  },
  "tags": ["metric", "number", "kpi", "overview"]
}
```

### 4.2 Widget Categories

Widgets are organized by function, not by source. A user browsing the widget library sees categories, not "Hydra widgets" vs "Docker widgets."

| Category | What's In It | Example Widgets |
|----------|-------------|-----------------|
| **Data Display** | Read-only visualization of values and states | Metric Card, Gauge, Sparkline, Progress Bar, Stat Group |
| **Status & Health** | Entity status with color-coded indicators | Status Grid, Health Matrix, Uptime Bar, Node Status Card |
| **Tables & Lists** | Tabular and list views of entity collections | Entity Table, Service List, Log Feed, Activity Stream, Alert List |
| **Charts & Graphs** | Time-series and comparative visualizations | Line Chart, Bar Chart, Area Chart, Pie Chart, Heatmap |
| **Topology & Maps** | Spatial and relational views | Mini Topology (read-only ReactFlow), Network Map, Rack Diagram |
| **Controls & Actions** | Interactive widgets that trigger operations | Quick Action Button, Command Trigger, Service Control, IoT Toggle, Scene Button |
| **Infrastructure** | Node/service/network specific composite views | Node Summary Card, Service Detail Card, Network Summary, Capacity Planning Panel |
| **IoT & Home** | Smart home device interaction | Room Card, Climate Control, Light Card, Sensor Reading, Media Player |
| **Time & History** | Temporal views into Hydra data | Time Machine Scrubber, Profile Diff Summary, Change Log Feed, Timeline |
| **External & Embed** | Third-party content and feeds | IFrame Embed, RSS Feed, Markdown Block, HTML Block, Image/Link Bookmarks |
| **System & Meta** | Hydra operational widgets | Integration Health Panel, Audit Log Stream, API Status, Agent Status Grid, MCP Query Box |

### 4.3 Widget Registry

The widget registry is an in-memory catalog assembled at API startup and updated when plugins change. It is the single source of truth for what widgets exist.

```python
class WidgetRegistry:
    """
    Central registry for all widget types.
    Assembled at startup from:
      1. Hydra native widgets (hardcoded)
      2. Plugin-contributed widgets (dynamic, per enabled plugin)
      3. External widget types (always available)
    """

    def __init__(self):
        self._registry: dict[str, WidgetTypeDefinition] = {}

    def register(self, definition: WidgetTypeDefinition) -> None:
        """Register a widget type. Called by core init and plugin loaders."""
        self._registry[definition.widget_type] = definition

    def unregister(self, widget_type: str) -> None:
        """Remove a widget type. Called when a plugin is disabled."""
        self._registry.pop(widget_type, None)

    def list_for_role(self, role: str) -> list[WidgetTypeDefinition]:
        """Return widget types visible to a given role."""
        return [
            w for w in self._registry.values()
            if role in w.permissions.view
        ]

    def get(self, widget_type: str) -> WidgetTypeDefinition | None:
        """Look up a specific widget type."""
        return self._registry.get(widget_type)

    def list_by_category(self, category: str, role: str) -> list[WidgetTypeDefinition]:
        """Return widget types in a category, filtered by role."""
        return [
            w for w in self._registry.values()
            if w.category == category and role in w.permissions.view
        ]

    def validate_widget_instance(self, instance: WidgetInstance) -> ValidationResult:
        """Validate a widget instance against its type definition."""
        widget_type = self.get(instance.widget_type)
        if not widget_type:
            return ValidationResult(valid=False, error=f"Unknown widget type: {instance.widget_type}")
        # Validate config against configSchema
        # Validate dataBinding against supportedDataShapes
        # Validate size against min/max
        ...
```

**Registry Endpoint:**

```
GET /dashboards/widgets/registry
```

Returns the full widget type catalog, filtered by the requesting user's role. The frontend uses this to populate the widget picker in edit mode.

```json
{
  "widgets": [
    {
      "widgetType": "hydra::metric-card",
      "displayName": "Metric Card",
      "category": "data-display",
      "icon": "hash",
      "source": "hydra",
      "tags": ["metric", "number"],
      "defaultSize": { "w": 3, "h": 2 },
      "configSchema": { ... }
    },
    {
      "widgetType": "plg::docker::container-grid",
      "displayName": "Docker Containers",
      "category": "infrastructure",
      "icon": "container",
      "source": "plg::docker",
      "tags": ["docker", "container", "infrastructure"],
      "defaultSize": { "w": 6, "h": 4 },
      "configSchema": { ... }
    }
  ],
  "categories": [
    { "id": "data-display", "name": "Data Display", "icon": "bar-chart-2", "count": 6 },
    { "id": "status-health", "name": "Status & Health", "icon": "activity", "count": 5 },
    { "id": "controls-actions", "name": "Controls & Actions", "icon": "zap", "count": 8 }
  ],
  "total": 47
}
```

### 4.4 Widget Instance vs Widget Type

The distinction matters throughout the system:

- **Widget Type** — A template definition. "Metric Card" is a widget type. It exists in the registry regardless of whether anyone uses it. It defines *what's possible*.
- **Widget Instance** — A specific placement on a specific board with specific data bindings and configuration. "Node Count on my Infrastructure Overview board, bound to `GET /nodes?class=compute&status=online`, counting results, displayed in green" is a widget instance. It defines *what's shown*.

Multiple instances of the same type can exist on one board (e.g., three metric cards showing different numbers). Each instance has a unique `instanceId` within its board.

---

## 5. Widget Component Library

### 5.1 Hydra-Native Widgets

These are built into Hydra and always available. They form the core of the widget library.

#### 5.1.1 Data Display Widgets

| Widget Type | Data Shape | Renders | Interactive |
|-------------|-----------|---------|-------------|
| `hydra::metric-card` | scalar / scalar-with-trend | Number with label, icon, optional sparkline trend | No |
| `hydra::gauge` | scalar-with-range | Circular or semicircular gauge with thresholds | No |
| `hydra::progress-bar` | scalar-with-max | Horizontal bar with percentage fill, color thresholds | No |
| `hydra::sparkline` | time-series (compact) | Minimal line chart without axes, showing trend direction | No |
| `hydra::stat-group` | array-of-scalars | Row/grid of labeled numbers (e.g., "5 nodes · 23 services · 3 networks") | No |
| `hydra::donut-chart` | categorical-distribution | Ring chart with legend (e.g., node distribution by class) | No |

#### 5.1.2 Status & Health Widgets

| Widget Type | Data Shape | Renders | Interactive |
|-------------|-----------|---------|-------------|
| `hydra::status-grid` | array-of-status | Grid of colored dots/icons representing entity states (online/offline/stale) | Click navigates to entity |
| `hydra::health-matrix` | matrix-of-status | Rows × columns health grid (e.g., nodes × health checks) | Click navigates to entity |
| `hydra::node-status-card` | single-node | Card showing node name, class icon, status, last profile age, key specs | Click navigates to node |
| `hydra::service-status-bar` | array-of-service-status | Horizontal segmented bar, each segment = a service, colored by status | Click navigates to service |
| `hydra::uptime-bar` | uptime-history | 30/90 day uptime bar (green/red segments) per entity | No |

#### 5.1.3 Tables & Lists Widgets

| Widget Type | Data Shape | Renders | Interactive |
|-------------|-----------|---------|-------------|
| `hydra::entity-table` | paginated-entity-list | Configurable table with sortable columns, filters, row actions | Sort, filter, row click |
| `hydra::service-list` | service-array | Compact list of services with status badge, runtime icon, port | Click navigates |
| `hydra::activity-feed` | event-stream | Chronological feed of Hydra events (profile submitted, service changed, command executed) | Scroll, click event |
| `hydra::alert-list` | alert-array | Prioritized list of active alerts/warnings | Click to acknowledge |
| `hydra::log-viewer` | log-lines | Scrollable log output with syntax highlighting and level filtering | Scroll, filter |

#### 5.1.4 Charts & Graphs Widgets

| Widget Type | Data Shape | Renders | Interactive |
|-------------|-----------|---------|-------------|
| `hydra::line-chart` | multi-time-series | Multi-line chart with axis labels, legend, optional thresholds | Hover tooltip, zoom |
| `hydra::bar-chart` | categorical-values | Vertical or horizontal bars with labels | Hover tooltip |
| `hydra::area-chart` | time-series | Filled area chart, supports stacked mode | Hover tooltip |
| `hydra::heatmap` | matrix-values | Color-coded grid showing intensity (e.g., CPU usage across nodes over time) | Hover tooltip |

#### 5.1.5 Topology & Maps Widgets

| Widget Type | Data Shape | Renders | Interactive |
|-------------|-----------|---------|-------------|
| `hydra::mini-topology` | topology-graph | Read-only ReactFlow canvas showing subset of topology | Pan, zoom, click node |
| `hydra::network-map` | network-with-nodes | Network segments with attached node icons | Click navigates |

#### 5.1.6 Controls & Actions Widgets

| Widget Type | Data Shape | Renders | Interactive |
|-------------|-----------|---------|-------------|
| `hydra::quick-action` | command-ref | Button that triggers a registered command with pre-bound target and parameters | Click → confirm → execute |
| `hydra::command-trigger` | command-ref-with-form | Button that opens a parameter form before executing | Click → form → confirm → execute |
| `hydra::service-control` | service-ref | Start/stop/restart buttons for a specific service | Click → confirm → execute |
| `hydra::workflow-trigger` | workflow-ref | Button that triggers a saved workflow | Click → confirm → execute |

#### 5.1.7 Infrastructure Composite Widgets

| Widget Type | Data Shape | Renders | Interactive |
|-------------|-----------|---------|-------------|
| `hydra::node-summary` | full-node-with-profile | Multi-section card: name, specs (CPU/RAM/disk), services count, status, last profile, agent tier | Click sections navigate |
| `hydra::capacity-panel` | node-group-resources | Grouped resource bars (CPU/RAM/disk) across multiple nodes with utilization coloring | Hover for details |
| `hydra::network-summary` | network-with-stats | Network CIDR, gateway, node count, DHCP range, VLAN info | Click navigates |
| `hydra::profile-diff` | diff-result | Side-by-side or inline diff of two profile versions for a node | Expand/collapse sections |

#### 5.1.8 Time & History Widgets

| Widget Type | Data Shape | Renders | Interactive |
|-------------|-----------|---------|-------------|
| `hydra::time-machine-scrubber` | timeline-events | Horizontal timeline with event markers, scrub to point in time | Drag scrubber |
| `hydra::change-log` | change-event-stream | Chronological list of infrastructure changes (node added, service changed, profile updated) | Click event for details |
| `hydra::profile-timeline` | profile-version-list | Version history for a specific node's profiles with diff links | Click version |

#### 5.1.9 External & Embed Widgets

| Widget Type | Data Shape | Renders | Interactive |
|-------------|-----------|---------|-------------|
| `hydra::iframe-embed` | url | Embedded external page in an iframe | Full iframe interaction |
| `hydra::rss-feed` | rss-url | Parsed RSS feed with title, date, excerpt per item | Click opens link |
| `hydra::markdown-block` | markdown-string | Rendered markdown content (for notes, instructions, runbook excerpts) | Links clickable |
| `hydra::html-block` | html-string | Raw HTML rendering (sandboxed) | Depends on content |
| `hydra::bookmark-grid` | array-of-bookmarks | Grid of linked icons/images (like Homarr app bookmarks) | Click opens URL |
| `hydra::clock` | none (client-side) | Current time with configurable timezone and format | No |
| `hydra::weather` | weather-api-url | Current weather conditions for configured location | No |

#### 5.1.10 System & Meta Widgets

| Widget Type | Data Shape | Renders | Interactive |
|-------------|-----------|---------|-------------|
| `hydra::integration-health` | integration-status-array | Status indicators for each enabled integration | Click navigates to integration config |
| `hydra::agent-grid` | agent-status-array | Grid of all registered agents with tier, version, last seen | Click navigates to node |
| `hydra::audit-stream` | audit-log-entries | Live stream of audit log entries | Scroll, filter by action |
| `hydra::api-status` | api-health | API health indicators (DB, Redis, uptime, version) | No |
| `hydra::mcp-query` | none (interactive) | Text input that sends natural language queries to MCP service and displays results inline | Type, submit, view result |
| `hydra::execution-queue` | command-queue | Live view of pending/running/completed command executions | Click for details |

### 5.2 Plugin-Contributed Widgets

Each of the 19 integrations contributes widgets specific to its domain. These are registered dynamically when the plugin is enabled and removed when disabled.

#### 5.2.1 Proxmox VE (`plg::proxmox`)

| Widget Type | Renders | Interactive |
|-------------|---------|-------------|
| `plg::proxmox::cluster-status` | Cluster nodes with HA status, quorum indicator | No |
| `plg::proxmox::vm-grid` | Grid of VMs/LXCs with status, resource usage, host assignment | Click navigates |
| `plg::proxmox::resource-allocation` | Stacked bars showing allocated vs available CPU/RAM per host | Hover |
| `plg::proxmox::storage-pools` | Storage pool usage bars with type indicators (ZFS, LVM, Ceph) | No |
| `plg::proxmox::migration-history` | Recent VM/LXC migrations with source → destination | No |
| `plg::proxmox::backup-status` | Last backup status per VM/LXC with age indicator | No |

#### 5.2.2 Docker Engine (`plg::docker`)

| Widget Type | Renders | Interactive |
|-------------|---------|-------------|
| `plg::docker::container-grid` | Containers grouped by compose project with status dots | Click navigates |
| `plg::docker::container-table` | Detailed table: name, image, status, ports, created, uptime | Sort, filter |
| `plg::docker::image-updates` | Containers where running image differs from latest tag | Click to view diff |
| `plg::docker::volume-usage` | Volume list with size, mount points, orphan detection | No |
| `plg::docker::network-map` | Docker networks with connected containers | No |
| `plg::docker::compose-status` | Per-compose-project health (all up / partial / down) | Click expands |
| `plg::docker::container-control` | Start/stop/restart/remove buttons for a specific container | Click → confirm |

#### 5.2.3 Home Assistant (`plg::home-assistant`)

| Widget Type | Renders | Interactive |
|-------------|---------|-------------|
| `plg::ha::room-card` | Room with device icons, states, quick toggles | Toggle devices |
| `plg::ha::light-card` | Light entity with on/off toggle, brightness slider, color picker | Full control |
| `plg::ha::climate-card` | Thermostat with mode selector, temperature dial, current/target temp | Set temperature |
| `plg::ha::sensor-reading` | Single sensor value with unit, icon, optional history sparkline | No |
| `plg::ha::scene-button` | Button to activate a HA scene | Click → execute |
| `plg::ha::automation-toggle` | Toggle to enable/disable a HA automation | Toggle |
| `plg::ha::entity-state` | Any entity's current state with icon and last-changed time | No |
| `plg::ha::area-overview` | All devices in an area with status indicators | Click to expand |
| `plg::ha::media-player` | Media player controls (play/pause/volume/source) | Full control |

#### 5.2.4 Ansible (`plg::ansible`)

| Widget Type | Renders | Interactive |
|-------------|---------|-------------|
| `plg::ansible::playbook-status` | Last run status per playbook (success/failed/changed) | Click for details |
| `plg::ansible::inventory-summary` | Host/group counts from dynamic inventory | No |
| `plg::ansible::run-trigger` | Button to run a specific playbook against selected targets | Click → form → confirm |

#### 5.2.5 Terraform (`plg::terraform`)

| Widget Type | Renders | Interactive |
|-------------|---------|-------------|
| `plg::terraform::workspace-status` | Workspace list with last apply status, resource count, drift detection | Click navigates |
| `plg::terraform::resource-count` | Total managed resources across workspaces | No |
| `plg::terraform::plan-trigger` | Button to trigger terraform plan for a workspace | Click → confirm |

#### 5.2.6 Prometheus (`plg::prometheus`)

| Widget Type | Renders | Interactive |
|-------------|---------|-------------|
| `plg::prometheus::metric-chart` | PromQL-driven chart (line, area, bar) with configurable query | Hover tooltip |
| `plg::prometheus::alert-list` | Active Prometheus alerts with severity and labels | Click for details |
| `plg::prometheus::target-health` | Scrape target status grid | No |

#### 5.2.7 Network Plugins (`plg::unifi`, `plg::snmp`, `plg::pfsense`, `plg::opnsense`, `plg::tailscale`)

| Widget Type | Renders | Interactive |
|-------------|---------|-------------|
| `plg::unifi::client-count` | Connected clients by type (wired/wireless) with AP breakdown | No |
| `plg::unifi::ap-status` | Access point grid with status, client count, channel | No |
| `plg::snmp::interface-status` | Interface up/down status for SNMP-managed devices | No |
| `plg::pfsense::firewall-summary` | Active rule count, blocked count, interface states | No |
| `plg::opnsense::firewall-summary` | Active rule count, blocked count, interface states | No |
| `plg::tailscale::device-grid` | Tailscale devices with online status, exit node indicator | No |
| `plg::tailscale::overlay-map` | Overlay network topology visualization | Pan, zoom |

#### 5.2.8 DNS & Proxy Plugins (`plg::pihole`, `plg::adguard`, `plg::traefik`, `plg::npm`)

| Widget Type | Renders | Interactive |
|-------------|---------|-------------|
| `plg::pihole::stats` | Queries today, blocked %, top domains, top clients | No |
| `plg::pihole::toggle` | Enable/disable blocking toggle | Toggle |
| `plg::adguard::stats` | Queries today, blocked %, top domains, top clients | No |
| `plg::adguard::toggle` | Enable/disable protection toggle | Toggle |
| `plg::traefik::router-table` | Routers with rule, service, TLS status | Click for details |
| `plg::traefik::service-health` | Backend health per service | No |
| `plg::npm::proxy-table` | Proxy hosts with domain, target, SSL status | Click for details |

#### 5.2.9 Storage & Monitoring Plugins (`plg::truenas`, `plg::uptimekuma`, `plg::ipmi-redfish`)

| Widget Type | Renders | Interactive |
|-------------|---------|-------------|
| `plg::truenas::pool-status` | ZFS pools with health, usage, scrub status | No |
| `plg::truenas::dataset-usage` | Dataset hierarchy with space usage | No |
| `plg::uptimekuma::status-grid` | Monitor status grid (up/down/pending) with uptime % | No |
| `plg::uptimekuma::response-chart` | Response time chart per monitor | Hover |
| `plg::ipmi::sensor-readings` | Hardware sensor values (temps, fan speeds, voltages) | No |
| `plg::ipmi::power-control` | Power on/off/reset buttons for IPMI-managed hosts | Click → confirm |

---

## 6. Data Source & Query Model

### 6.1 Overview

Every widget instance needs data. The data source binding model defines how widgets declare their data needs and how the frontend resolves them.

### 6.2 Data Source Types

| Source Type | Prefix | Resolution | Examples |
|-------------|--------|------------|----------|
| **Hydra API** | `hydra::` | Direct API call to hydra-api endpoints | `hydra::nodes`, `hydra::services`, `hydra::topologies` |
| **Plugin Data** | `plg::{pluginId}::` | API call to plugin-specific endpoints or profile `pluginData` extraction | `plg::docker::containers`, `plg::ha::entities` |
| **Computed** | `computed::` | Client-side computation from other data sources | `computed::node-count-by-class` |
| **Static** | `static::` | Inline data in the widget config (for markdown blocks, bookmarks, etc.) | `static::markdown`, `static::bookmarks` |
| **External** | `external::` | HTTP fetch to external URLs (RSS, weather API, etc.) | `external::rss`, `external::http-json` |
| **WebSocket** | `ws::` | Real-time subscription to Hydra WebSocket channels | `ws::events`, `ws::commands` |

### 6.3 Data Binding Schema

```json
{
  "dataBinding": {
    "source": "hydra::nodes",
    "query": {
      "endpoint": "/nodes",
      "params": {
        "class": "compute",
        "status": "online",
        "fields": "nodeId,displayName,status,class"
      },
      "transform": "count"
    },
    "refreshInterval": 60,
    "realtimeChannel": null,
    "fallback": {
      "type": "cached",
      "maxAge": 300
    }
  }
}
```

### 6.4 Transform Operations

Transforms are applied client-side after data is fetched, converting raw API responses into the shape the widget renderer expects.

| Transform | Input | Output | Use Case |
|-----------|-------|--------|----------|
| `count` | Array | Scalar (length) | "How many compute nodes are online?" |
| `sum(field)` | Array of objects | Scalar (sum) | "Total RAM across all nodes" |
| `avg(field)` | Array of objects | Scalar (average) | "Average CPU allocation" |
| `min(field)` / `max(field)` | Array of objects | Scalar | "Oldest profile age" |
| `group_by(field)` | Array of objects | Object of arrays | "Nodes grouped by class" |
| `count_by(field)` | Array of objects | Object of counts | "Node count per network" |
| `pluck(field)` | Array of objects | Array of values | "All node names" |
| `sort(field, direction)` | Array of objects | Sorted array | "Services sorted by status" |
| `first(n)` | Array | Array (first n) | "5 most recent events" |
| `last(n)` | Array | Array (last n) | "Last 5 profiles" |
| `map(template)` | Array of objects | Array of objects (remapped) | Reshape fields for chart data |
| `filter(field, op, value)` | Array of objects | Filtered array | "Only nodes with status=degraded" |
| `chain(transforms)` | Any | Any | Sequential transform pipeline |
| `none` | Any | Passthrough | Widget handles raw data |

### 6.5 Multi-Source Bindings

Some widgets need data from multiple sources. For example, a "Node Summary Card" needs the node object, its latest profile, and its services.

```json
{
  "dataBinding": {
    "sources": {
      "node": {
        "source": "hydra::nodes",
        "query": { "endpoint": "/nodes/{nodeId}" }
      },
      "profile": {
        "source": "hydra::profiles",
        "query": { "endpoint": "/nodes/{nodeId}/profiles/latest" }
      },
      "services": {
        "source": "hydra::services",
        "query": { "endpoint": "/services", "params": { "nodeId": "{nodeId}" } }
      }
    },
    "params": {
      "nodeId": "proxmox-01"
    },
    "refreshInterval": 120
  }
}
```

The `{nodeId}` placeholder is resolved from `params`. This allows the same widget configuration to be parameterized — clone the widget, change `nodeId`, and it shows different data.

### 6.6 Data Binding for Plugin Widgets

Plugin widgets often need data from the `pluginData` section of node profiles. The binding model supports JSONPath-style extraction:

```json
{
  "dataBinding": {
    "source": "plg::docker::containers",
    "query": {
      "endpoint": "/nodes/{nodeId}/profiles/latest",
      "extract": "$.pluginData['plg::docker'].containers",
      "params": { "nodeId": "docker-host-01" }
    },
    "transform": "none",
    "refreshInterval": 60
  }
}
```

When a plugin provides its own API endpoints (exposed through the plugin framework), the binding uses those directly:

```json
{
  "dataBinding": {
    "source": "plg::prometheus::query",
    "query": {
      "endpoint": "/plugins/prometheus/query",
      "params": {
        "query": "node_cpu_seconds_total{mode='idle'}",
        "range": "1h",
        "step": "60s"
      }
    },
    "refreshInterval": 30
  }
}
```

---

## 7. Layout Engine

### 7.1 Grid System

Hydra uses a 12-column responsive grid system, based on the same principles as `react-grid-layout`. Each widget occupies a rectangular area defined by grid coordinates (x, y) and dimensions (w, h).

| Property | Description | Range |
|----------|-------------|-------|
| `x` | Column start position (0-indexed) | 0 to (columns - w) |
| `y` | Row start position | 0 to ∞ (infinite vertical scroll) |
| `w` | Width in grid columns | minSize.w to maxSize.w |
| `h` | Height in grid rows | minSize.h to maxSize.h |

Grid cells are responsive — the column count changes at breakpoints, and each widget stores separate positions per breakpoint.

### 7.2 Breakpoint Definitions

| Breakpoint | Min Width | Default Columns | Target |
|------------|-----------|-----------------|--------|
| `xs` | 0px | 2 | Mobile phone |
| `sm` | 480px | 4 | Large phone / small tablet |
| `md` | 996px | 8 | Tablet / small desktop |
| `lg` | 1200px | 12 | Desktop |
| `xl` | 1536px | 12 | Large desktop / ultrawide |

When a user designs a dashboard on desktop (`xl`), the system auto-generates layouts for smaller breakpoints using compaction rules. Users can manually override any breakpoint's layout.

### 7.3 Compaction Modes

| Mode | Behavior | Best For |
|------|----------|----------|
| `vertical` | Widgets float upward to fill vertical gaps | Most dashboards (default) |
| `horizontal` | Widgets float leftward to fill horizontal gaps | Column-oriented layouts |
| `none` | Widgets stay exactly where placed (gaps allowed) | Precise positioning |

### 7.4 Layout Modes

Beyond the standard grid, boards can use alternative layout modes for specific use cases:

| Mode | Description | Inspired By | Use Case |
|------|-------------|-------------|----------|
| `grid` | Standard responsive grid (default) | Homarr | Most dashboards |
| `columns` | Fixed column layout (small/full/small or custom ratios) | Glance | Information radiator / feed boards |
| `freeform` | Pixel-positioned widgets (no grid snap) | Grafana | Precise visual layouts |

#### 7.4.1 Column Mode Detail

Column mode divides the board into named columns with size ratios, inspired by Glance's `small/full/small` model. Widgets are placed into columns and stack vertically within each.

```json
{
  "layout": {
    "mode": "columns",
    "columns": [
      { "id": "left", "size": "small", "ratio": 0.25 },
      { "id": "center", "size": "full", "ratio": 0.5 },
      { "id": "right", "size": "small", "ratio": 0.25 }
    ]
  },
  "widgets": [
    {
      "instanceId": "wi_001",
      "widgetType": "hydra::clock",
      "column": "left",
      "order": 0,
      "config": { ... }
    },
    {
      "instanceId": "wi_002",
      "widgetType": "hydra::rss-feed",
      "column": "center",
      "order": 0,
      "config": { ... }
    }
  ]
}
```

Column mode is mobile-friendly — columns stack vertically on small breakpoints.

### 7.5 Edit Mode

Edit mode is a distinct UI state where the user can modify the board.

| Capability | Description |
|------------|-------------|
| **Drag & Drop** | Move widgets by dragging. Grid snapping provides alignment. |
| **Resize** | Drag widget edges/corners to resize within min/max constraints. |
| **Add Widget** | Opens widget picker panel (categorized, searchable, filterable by source). |
| **Configure Widget** | Opens config panel for selected widget: data binding, display options, thresholds. |
| **Remove Widget** | Delete widget from board (with undo). |
| **Reorder** | Tab-based ordering for column mode. |
| **Change Layout Mode** | Switch between grid/columns/freeform. |
| **Board Settings** | Name, description, icon, theme, refresh interval, kiosk settings. |
| **Live Preview** | Data bindings resolve and render while editing — WYSIWYG. |
| **Undo/Redo** | In-memory edit history during edit session. |
| **Save/Discard** | Explicit save commits changes; discard reverts to last saved state. |

### 7.6 Embedded Dashboard Panels

Dashboards aren't only full-page views. A subset of dashboard functionality supports embedded panels within other pages:

| Context | What It Shows | How |
|---------|--------------|-----|
| Node detail page | Mini dashboard panel of key widgets for that node | Pre-configured or user-customizable |
| Service detail page | Service-specific widgets (status, logs, dependencies) | Pre-configured |
| Network detail page | Network summary widgets | Pre-configured |
| Sidebar quickview | Collapsible widget panel on any page | User-configured |

Embedded panels use the same widget renderer components but with a simplified layout (single-column, no edit mode, compact sizing).

---

## 8. Dashboard Templates & Presets

### 8.1 Template System

Templates are pre-built board definitions that ship with Hydra or are created by admins. Users clone templates to create personal boards, which they can then customize.

### 8.2 Shipped Templates

| Template | Target Role | Contents |
|----------|------------|----------|
| **Infrastructure Overview** | operator, admin | Node count metrics, service health grid, capacity gauges, mini topology, recent activity |
| **Docker Fleet** | operator | Container grid per host, compose project status, image update alerts, volume usage |
| **IoT Home** | family | Room cards with device toggles, climate controls, scene buttons, sensor readings |
| **Network Status** | operator | Network node status, interface health, DNS stats, VPN status, firewall summary |
| **Capacity Planning** | admin | Storage fill gauges, RAM allocation bars, CPU headroom, capacity runway estimates |
| **Operations Hub** | admin | Execution queue, audit stream, integration health, workflow triggers, agent grid |
| **Monitoring Dashboard** | operator | Prometheus metric charts, Uptime Kuma status, alert list, response time graphs |
| **Glance Board** | any | Column-layout information radiator: clock, weather, RSS feed, bookmark grid, status bars |
| **Minimal Status** | viewer | Read-only node and service counts, health summary, last profile times |

### 8.3 Template Schema

Templates extend the board schema with additional metadata:

```json
{
  "templateId": "tmpl::infrastructure-overview",
  "name": "Infrastructure Overview",
  "description": "Comprehensive view of all compute infrastructure with status, capacity, and recent activity",
  "category": "infrastructure",
  "targetRoles": ["operator", "admin"],
  "requiredPlugins": [],
  "optionalPlugins": ["plg::proxmox", "plg::docker"],
  "preview": "/templates/previews/infrastructure-overview.png",
  "board": { ... },
  "variables": {
    "focusNetwork": {
      "type": "network-selector",
      "label": "Primary Network",
      "description": "Which network should the capacity widgets focus on?",
      "default": null
    }
  }
}
```

**Template Variables** allow templates to be parameterized on clone. When a user clones "Docker Fleet," they're asked "Which Docker hosts should this dashboard track?" and the node selectors are pre-filled.

### 8.4 Admin-Created Templates

Admins can save any personal board as a template, making it available for other users to clone. This enables organization-specific dashboard standardization.

```
POST /dashboards/templates
{
  "sourceBoardId": "board_abc123",
  "name": "Team Network View",
  "targetRoles": ["operator"],
  "variables": { ... }
}
```

---

## 9. RBAC Integration

### 9.1 Role-Based Widget Visibility

The widget registry filters by role. Each widget type declares which roles can view and interact with it.

| Widget Capability | admin | operator | viewer | family |
|-------------------|-------|----------|--------|--------|
| **View any widget** | ✓ | ✓ | Read-only subset | IoT-only subset |
| **Control widgets** (restart, toggle, trigger) | ✓ | ✓ | ✗ | IoT controls only |
| **System widgets** (audit, agent grid) | ✓ | ✓ | ✗ | ✗ |
| **Infrastructure widgets** (nodes, profiles) | ✓ | ✓ | ✓ (read-only) | ✗ |
| **IoT widgets** (HA room cards, lights, climate) | ✓ | ✓ | ✓ | ✓ |
| **Command/workflow triggers** | ✓ | ✓ | ✗ | ✗ |
| **External embeds** (iframe, RSS) | ✓ | ✓ | ✓ | ✓ |

### 9.2 Role-Based Board Access

| Operation | admin | operator | viewer | family |
|-----------|-------|----------|--------|--------|
| Create board | ✓ | ✓ | ✓ (limited widgets) | ✓ (IoT widgets only) |
| Edit own board | ✓ | ✓ | ✓ | ✓ |
| Share board | ✓ | ✓ | ✗ | ✗ |
| View shared boards | ✓ | ✓ | ✓ | Only if shared to family |
| Clone templates | ✓ | ✓ | ✓ | Applicable templates only |
| Create templates from board | ✓ | ✗ | ✗ | ✗ |
| Delete any board | ✓ | ✗ | ✗ | ✗ |
| Manage kiosk URLs | ✓ | ✓ | ✗ | ✗ |

### 9.3 Widget Action Enforcement

When a control widget (e.g., `plg::docker::container-control`) triggers an action, the permission check flows through the existing command execution system:

```
Widget click → "Restart container X on docker-host-01"
    │
    ▼
Frontend sends: POST /commands/execute
    {
      "commandId": "cmd::docker::restart-container",
      "target": { "nodeId": "docker-host-01" },
      "parameters": { "containerId": "abc123" }
    }
    │
    ▼
API checks RBAC: Does user's role have `commands:execute` on this node?
    │
    ▼
If confirmation required → return confirmation token → frontend shows confirm dialog
    │
    ▼
Normal command execution flow (poll/direct depending on agent tier)
```

The widget itself does not bypass any security. It's a UI convenience over the existing command API.

---

## 10. Plugin Widget Contributions

### 10.1 How Plugins Register Widgets

When a plugin is enabled, the plugin driver's `get_widget_definitions()` method is called, returning an array of `WidgetTypeDefinition` objects that are registered in the widget registry.

```python
class DockerPluginDriver(PluginDriver):
    def get_widget_definitions(self) -> list[WidgetTypeDefinition]:
        return [
            WidgetTypeDefinition(
                widget_type="plg::docker::container-grid",
                display_name="Docker Containers",
                description="Grid of Docker containers grouped by compose project",
                category="infrastructure",
                icon="container",
                source="plg::docker",
                supported_data_shapes=["container-array"],
                config_schema={ ... },
                default_size={"w": 6, "h": 4},
                min_size={"w": 4, "h": 2},
                max_size={"w": 12, "h": 8},
                permissions={"view": ["admin", "operator", "viewer"], "interact": ["admin", "operator"]},
                tags=["docker", "container", "infrastructure"],
                web_component="DockerContainerGrid"
            ),
            # ... more widget definitions
        ]
```

### 10.2 Frontend Widget Component Registration

Plugin widget renderers are React components loaded dynamically. Each plugin provides a component map:

```typescript
// plg::docker widget components (lazy loaded)
const DockerWidgets: PluginWidgetMap = {
  'plg::docker::container-grid': lazy(() => import('./widgets/ContainerGrid')),
  'plg::docker::container-table': lazy(() => import('./widgets/ContainerTable')),
  'plg::docker::compose-status': lazy(() => import('./widgets/ComposeStatus')),
  'plg::docker::container-control': lazy(() => import('./widgets/ContainerControl')),
  // ...
};
```

The main widget renderer uses this map to resolve which component to render:

```typescript
function WidgetRenderer({ instance, data, isEditing }: WidgetRendererProps) {
  const Component = useWidgetComponent(instance.widgetType);

  if (!Component) {
    return <WidgetError message={`Widget type ${instance.widgetType} not available. Plugin may be disabled.`} />;
  }

  return (
    <Suspense fallback={<WidgetSkeleton size={instance.position} />}>
      <Component data={data} config={instance.config} isEditing={isEditing} />
    </Suspense>
  );
}
```

### 10.3 Graceful Handling of Missing Plugins

When a board references a widget type from a plugin that's been disabled:

1. The widget renders a placeholder with a clear message: *"Docker Containers widget requires the Docker Engine integration, which is currently disabled."*
2. The board definition is not modified — the widget instance stays in the schema. Re-enabling the plugin restores it.
3. In the widget picker, disabled plugin widgets are shown grayed out with a "Requires: plg::docker" badge.
4. Board validation warns about unresolvable widgets but does not prevent saving.

---

## 11. Real-Time Updates & Caching

### 11.1 Refresh Strategy Per Widget

Each widget instance has a `refreshInterval` (in seconds). The frontend manages refresh through TanStack Query's `refetchInterval`.

| Data Type | Default Refresh | Rationale |
|-----------|-----------------|-----------|
| Node status | 30s | Status changes are operationally significant |
| Service status | 30s | Service failures need quick visibility |
| Profile data | 300s (5min) | Profiles are point-in-time, not real-time |
| Topology | 600s (10min) | Topology changes infrequently |
| IoT entity state | 10s | Smart home responsiveness expectations |
| Command execution queue | 5s | Users watching active operations |
| Prometheus metrics | 30s | Matches typical scrape interval |
| Uptime Kuma monitors | 60s | Matches typical check interval |
| External feeds (RSS) | 900s (15min) | External data changes slowly |
| Audit log | 15s | Recent activity should feel live |

### 11.2 WebSocket Channels

For widgets that need real-time push rather than polling:

| Channel | Events | Subscribed By |
|---------|--------|---------------|
| `ws::node-status` | Node online/offline/stale transitions | Status grid, node cards |
| `ws::service-status` | Service state changes | Service status widgets |
| `ws::command-events` | Execution started/completed/failed | Execution queue, command triggers |
| `ws::ha-state` | HA entity state changes | All IoT widgets |
| `ws::profile-submitted` | New profile received | Profile timeline, activity feed |
| `ws::discovery-event` | New device discovered | Activity feed, alert list |

The frontend subscribes to relevant channels per widget on mount and unsubscribes on unmount. This is managed by a central WebSocket connection with multiplexed channel subscriptions.

### 11.3 Cache Strategy

```typescript
// Per-widget TanStack Query configuration
const useWidgetData = (binding: DataBinding) => {
  return useQuery({
    queryKey: ['widget-data', binding.source, binding.query],
    queryFn: () => resolveDataBinding(binding),
    refetchInterval: binding.refreshInterval * 1000,
    staleTime: (binding.refreshInterval * 1000) / 2,
    gcTime: binding.refreshInterval * 1000 * 5,
    placeholderData: keepPreviousData,
    retry: 2,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30000),
  });
};
```

**Deduplication**: If two widgets on the same board bind to the same API endpoint with the same params, TanStack Query deduplicates the request automatically (same `queryKey`).

### 11.4 Stale Data Indicators

When a widget's data source is unreachable or stale beyond threshold:

- The widget renders with a subtle dimming overlay and a "Last updated: 5m ago" timestamp.
- If the source is an integration that's gone unhealthy, the overlay includes the integration name: *"Docker Engine integration unavailable"*.
- The widget does NOT blank out — it shows the last known data with the staleness indicator.

---

## 12. API Specification

### 12.1 Board Endpoints

#### List Boards

```
GET /dashboards
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `ownerId` | string | Filter by owner |
| `boardType` | enum | `user`, `template`, `shared`, `kiosk` |
| `tags` | string | Comma-separated tags |
| `search` | string | Full-text search on name/description |
| `limit` | integer | Max results (default: 20) |
| `offset` | integer | Pagination offset |

**Response:** `200 OK`

```json
{
  "boards": [
    {
      "boardId": "board_abc123",
      "name": "Infrastructure Overview",
      "description": "...",
      "icon": "server",
      "boardType": "user",
      "widgetCount": 8,
      "isHome": true,
      "updatedAt": "2026-02-22T08:30:00Z"
    }
  ],
  "total": 5,
  "limit": 20,
  "offset": 0
}
```

**Required Permission:** `dashboards:read`

---

#### Get Board

```
GET /dashboards/{boardId}
```

Returns full board definition including all widget instances and layout.

**Response:** `200 OK` — Full board schema as defined in §3.3.

**Required Permission:** `dashboards:read` + board visibility check

---

#### Create Board

```
POST /dashboards
```

**Request Body:** Full board schema (without `boardId`, `version`, timestamps — these are server-generated).

**Response:** `201 Created`

```json
{
  "boardId": "board_def456",
  "name": "My New Dashboard",
  "version": 1,
  "createdAt": "2026-02-22T10:00:00Z"
}
```

**Required Permission:** `dashboards:create`

---

#### Update Board

```
PUT /dashboards/{boardId}
```

Full replacement of board definition. Auto-increments version.

**Required Permission:** `dashboards:update` + owner or admin

---

#### Patch Board

```
PATCH /dashboards/{boardId}
```

Partial update — supports updating specific fields (name, settings, individual widget config) without full replacement.

```json
{
  "op": "update-widget",
  "instanceId": "wi_001",
  "changes": {
    "config": { "title": "Updated Title" }
  }
}
```

Supported operations:
- `update-settings` — Board-level settings
- `update-widget` — Single widget config/binding
- `add-widget` — Add widget instance
- `remove-widget` — Remove widget instance
- `update-layout` — Layout positions only
- `reorder-widgets` — Widget z-order (for column mode)

**Required Permission:** `dashboards:update` + owner or admin

---

#### Delete Board

```
DELETE /dashboards/{boardId}
```

Soft delete — recoverable for 30 days.

**Required Permission:** `dashboards:delete` + owner or admin

---

#### Clone Board

```
POST /dashboards/{boardId}/clone
```

Creates a new board from an existing board or template, owned by the requesting user.

**Request Body:**

```json
{
  "name": "My Infrastructure View",
  "variables": {
    "focusNetwork": "homenet-lan"
  }
}
```

**Required Permission:** `dashboards:create` + source board visibility

---

#### Set Home Board

```
POST /dashboards/{boardId}/set-home
```

Sets the board as the user's home dashboard.

**Required Permission:** Authenticated user, board visible to them

---

### 12.2 Widget Registry Endpoint

```
GET /dashboards/widgets/registry
```

Returns available widget types filtered by the requesting user's role and enabled plugins. Response as defined in §4.3.

**Required Permission:** `dashboards:read`

---

### 12.3 Template Endpoints

```
GET /dashboards/templates
POST /dashboards/templates
GET /dashboards/templates/{templateId}
DELETE /dashboards/templates/{templateId}
```

Template CRUD. Creating templates requires admin role. Listing and cloning respects `targetRoles`.

---

### 12.4 Export/Import Endpoints

```
GET /dashboards/{boardId}/export?format=json
GET /dashboards/{boardId}/export?format=yaml
POST /dashboards/import
```

Export returns the board definition in the requested format. Import validates against the widget registry (warns on missing widget types) and creates a new board.

---

## 13. Data Model

### 13.1 Collection: `dashboards`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:dashboards",
  "title": "Dashboard",
  "type": "object",
  "required": ["boardId", "name", "ownerId", "boardType", "layout", "widgets"],
  "properties": {
    "_id": { "type": "string" },
    "boardId": {
      "type": "string",
      "pattern": "^board_[a-z0-9]+$"
    },
    "name": { "type": "string", "maxLength": 128 },
    "description": { "type": "string", "maxLength": 2048 },
    "icon": { "type": "string", "maxLength": 64 },
    "ownerId": { "type": "string" },
    "ownerType": { "type": "string", "enum": ["user", "system"] },
    "boardType": { "type": "string", "enum": ["user", "template", "shared", "kiosk"] },
    "visibility": {
      "type": "object",
      "properties": {
        "scope": { "type": "string", "enum": ["private", "shared", "public"] },
        "sharedWith": {
          "type": "object",
          "properties": {
            "roles": { "type": "array", "items": { "type": "string" } },
            "users": { "type": "array", "items": { "type": "string" } }
          }
        }
      }
    },
    "layout": {
      "type": "object",
      "required": ["mode"],
      "properties": {
        "mode": { "type": "string", "enum": ["grid", "columns", "freeform"] },
        "columns": { "type": "integer", "minimum": 1, "maximum": 24 },
        "rowHeight": { "type": "integer", "minimum": 40, "maximum": 200 },
        "breakpoints": { "type": "object" },
        "compaction": { "type": "string", "enum": ["vertical", "horizontal", "none"] },
        "margin": { "type": "array", "items": { "type": "integer" }, "minItems": 2, "maxItems": 2 },
        "containerPadding": { "type": "array", "items": { "type": "integer" }, "minItems": 2, "maxItems": 2 },
        "columnDefinitions": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "id": { "type": "string" },
              "size": { "type": "string" },
              "ratio": { "type": "number" }
            }
          }
        }
      }
    },
    "widgets": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["instanceId", "widgetType"],
        "properties": {
          "instanceId": { "type": "string", "pattern": "^wi_[a-z0-9]+$" },
          "widgetType": { "type": "string" },
          "position": { "type": "object" },
          "column": { "type": "string" },
          "order": { "type": "integer" },
          "dataBinding": { "type": "object" },
          "config": { "type": "object" }
        }
      }
    },
    "settings": {
      "type": "object",
      "properties": {
        "theme": { "type": "string", "enum": ["inherit", "light", "dark", "custom"] },
        "autoRefresh": { "type": "boolean", "default": true },
        "refreshInterval": { "type": "integer", "minimum": 5, "maximum": 3600 },
        "showHeader": { "type": "boolean", "default": true },
        "kioskMode": { "type": "boolean", "default": false },
        "kioskAutoScroll": { "type": "boolean", "default": false },
        "kioskScrollSpeed": { "type": "integer", "minimum": 1, "maximum": 10 },
        "backgroundImage": { "type": ["string", "null"] },
        "customCss": { "type": ["string", "null"], "maxLength": 10000 }
      }
    },
    "tags": { "type": "array", "items": { "type": "string" } },
    "isHome": { "type": "boolean", "default": false },
    "version": { "type": "integer", "minimum": 1 },
    "clonedFrom": { "type": ["string", "null"] },
    "deletedAt": { "type": ["string", "null"], "format": "date-time" },
    "createdAt": { "type": "string", "format": "date-time" },
    "updatedAt": { "type": "string", "format": "date-time" }
  }
}
```

**Indexes:**

```javascript
db.dashboards.createIndexes([
  { key: { "boardId": 1 }, unique: true },
  { key: { "ownerId": 1, "boardType": 1 } },
  { key: { "ownerId": 1, "isHome": 1 } },
  { key: { "visibility.scope": 1, "visibility.sharedWith.roles": 1 } },
  { key: { "boardType": 1 } },
  { key: { "tags": 1 } },
  { key: { "deletedAt": 1 }, expireAfterSeconds: 2592000 },  // 30 day TTL for soft deletes
  { key: { "name": "text", "description": "text", "tags": "text" } }  // Full-text search
])
```

### 13.2 Collection: `dashboard_versions`

Stores previous versions of boards for version history.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:dashboard_versions",
  "title": "DashboardVersion",
  "type": "object",
  "required": ["boardId", "version", "snapshot", "savedAt"],
  "properties": {
    "_id": { "type": "string" },
    "boardId": { "type": "string" },
    "version": { "type": "integer" },
    "snapshot": { "type": "object", "description": "Complete board definition at this version" },
    "savedBy": { "type": "string" },
    "savedAt": { "type": "string", "format": "date-time" },
    "changeDescription": { "type": "string" }
  }
}
```

**Indexes:**

```javascript
db.dashboard_versions.createIndexes([
  { key: { "boardId": 1, "version": -1 } },
  { key: { "savedAt": -1 } }
])
```

### 13.3 Collection: `dashboard_templates`

Stores templates separately from user boards.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:dashboard_templates",
  "title": "DashboardTemplate",
  "type": "object",
  "required": ["templateId", "name", "board", "targetRoles"],
  "properties": {
    "_id": { "type": "string" },
    "templateId": { "type": "string", "pattern": "^tmpl::[a-z0-9-]+$" },
    "name": { "type": "string" },
    "description": { "type": "string" },
    "category": { "type": "string" },
    "targetRoles": { "type": "array", "items": { "type": "string" } },
    "requiredPlugins": { "type": "array", "items": { "type": "string" } },
    "optionalPlugins": { "type": "array", "items": { "type": "string" } },
    "preview": { "type": "string" },
    "board": { "type": "object", "description": "Board definition (same schema as dashboards collection)" },
    "variables": { "type": "object" },
    "source": { "type": "string", "enum": ["system", "user"] },
    "createdBy": { "type": "string" },
    "createdAt": { "type": "string", "format": "date-time" },
    "updatedAt": { "type": "string", "format": "date-time" }
  }
}
```

---

## 14. hydra-web Implementation

### 14.1 Component Architecture

```
src/
├── features/
│   └── dashboards/
│       ├── pages/
│       │   ├── DashboardListPage.tsx       # Board list/picker
│       │   ├── DashboardViewPage.tsx       # Board view (renders widgets)
│       │   ├── DashboardEditPage.tsx       # Board editor (edit mode)
│       │   ├── KioskPage.tsx               # Kiosk view (minimal chrome)
│       │   └── TemplateBrowserPage.tsx     # Template picker for cloning
│       ├── components/
│       │   ├── board/
│       │   │   ├── BoardGrid.tsx           # Grid layout engine (react-grid-layout)
│       │   │   ├── BoardColumns.tsx        # Column layout engine
│       │   │   ├── BoardFreeform.tsx       # Freeform layout engine
│       │   │   ├── BoardHeader.tsx         # Board name, tabs, actions
│       │   │   ├── BoardTabBar.tsx         # Multi-board tab switching
│       │   │   └── BoardSettings.tsx       # Board config panel
│       │   ├── widgets/
│       │   │   ├── WidgetRenderer.tsx      # Dynamic widget component resolver
│       │   │   ├── WidgetWrapper.tsx       # Common widget chrome (title bar, menu, resize handles)
│       │   │   ├── WidgetPicker.tsx        # Widget library browser (categories, search, drag to add)
│       │   │   ├── WidgetConfigurator.tsx  # Widget config panel (data binding, options)
│       │   │   ├── WidgetError.tsx         # Error/missing plugin placeholder
│       │   │   ├── WidgetSkeleton.tsx      # Loading skeleton
│       │   │   └── WidgetStaleOverlay.tsx  # Stale data indicator
│       │   ├── native-widgets/
│       │   │   ├── MetricCard.tsx
│       │   │   ├── Gauge.tsx
│       │   │   ├── StatusGrid.tsx
│       │   │   ├── EntityTable.tsx
│       │   │   ├── LineChart.tsx
│       │   │   ├── MiniTopology.tsx
│       │   │   ├── QuickAction.tsx
│       │   │   ├── RssFeed.tsx
│       │   │   ├── IframeEmbed.tsx
│       │   │   ├── MarkdownBlock.tsx
│       │   │   ├── BookmarkGrid.tsx
│       │   │   ├── Clock.tsx
│       │   │   ├── ActivityFeed.tsx
│       │   │   ├── AuditStream.tsx
│       │   │   ├── ExecutionQueue.tsx
│       │   │   ├── McpQueryBox.tsx
│       │   │   └── ... (all native widgets)
│       │   └── data-binding/
│       │       ├── DataBindingEditor.tsx   # Visual editor for data source selection
│       │       ├── TransformPicker.tsx     # Transform chain builder
│       │       ├── SourceSelector.tsx      # Source type picker (hydra, plugin, external)
│       │       └── PreviewPanel.tsx        # Live data preview during binding config
│       ├── hooks/
│       │   ├── useBoard.ts                # Board load/save/patch
│       │   ├── useWidgetData.ts           # Data binding resolution + TanStack Query
│       │   ├── useWidgetRegistry.ts       # Widget type catalog
│       │   ├── useWebSocketWidget.ts      # WebSocket subscription for real-time widgets
│       │   ├── useBoardEditor.ts          # Edit mode state (undo/redo, dirty tracking)
│       │   └── useKioskMode.ts            # Auto-refresh, scroll, minimal chrome
│       ├── stores/
│       │   └── dashboardStore.ts          # Zustand store for dashboard state
│       └── utils/
│           ├── layoutEngine.ts            # Grid → pixel position calculations
│           ├── dataTransforms.ts          # Client-side transform implementations
│           ├── widgetComponentMap.ts       # Widget type → React component map
│           └── exportImport.ts            # JSON/YAML serialization
```

### 14.2 Key Dependencies

| Library | Purpose | Justification |
|---------|---------|---------------|
| `react-grid-layout` | Grid layout engine with drag-drop and resize | Industry standard for dashboard grids, supports breakpoints |
| `recharts` | Chart widgets (line, bar, area, pie) | Already in stack (per technical docs), React-native |
| `@tanstack/react-query` | Data fetching, caching, and refresh management | Already in stack, handles dedup and stale-while-revalidate |
| `reactflow` (existing) | Mini topology widget | Already used for full topology viewer |
| `zustand` (existing) | Dashboard editor state | Already the state management solution |
| `js-yaml` | YAML export/import | Lightweight, for Glance-style YAML board definitions |

### 14.3 Widget Renderer Contract

Every widget component (native or plugin-contributed) must conform to this interface:

```typescript
interface WidgetComponentProps<TData = unknown, TConfig = Record<string, unknown>> {
  /** Resolved data from the data binding layer */
  data: TData;
  /** Widget-specific configuration from the board definition */
  config: TConfig;
  /** Whether the dashboard is in edit mode */
  isEditing: boolean;
  /** Widget instance dimensions in pixels (resolved from grid) */
  dimensions: { width: number; height: number };
  /** Loading state from the data layer */
  isLoading: boolean;
  /** Error from the data layer */
  error: Error | null;
  /** Callback for widgets that need to execute commands */
  onExecuteCommand?: (commandId: string, target: CommandTarget, params: Record<string, unknown>) => Promise<void>;
  /** Callback for widgets that need to navigate */
  onNavigate?: (path: string) => void;
}
```

---

## 15. MCP Integration

### 15.1 Dashboard Tools for AI

The MCP service exposes dashboard-related tools so AI models can create, query, and modify dashboards.

| Tool | Description | Parameters |
|------|-------------|------------|
| `list_dashboards` | List boards for the current user | `boardType`, `tags` |
| `get_dashboard` | Get full board definition | `boardId` |
| `create_dashboard` | Create a new board from a description | `name`, `description`, `widgets` (simplified) |
| `create_dashboard_from_template` | Clone a template | `templateId`, `name`, `variables` |
| `add_widget_to_dashboard` | Add a widget to an existing board | `boardId`, `widgetType`, `dataBinding`, `config` |
| `remove_widget_from_dashboard` | Remove a widget | `boardId`, `instanceId` |
| `list_widget_types` | List available widget types | `category`, `source` |
| `list_templates` | List available templates | `category`, `targetRole` |

### 15.2 AI-Created Dashboard Flow

```
User: "Create me a dashboard showing my Docker hosts with container counts and a network topology"
    │
    ▼
MCP identifies needed widgets:
  - hydra::metric-card (one per Docker host, bound to container count)
  - plg::docker::compose-status (per host)
  - hydra::mini-topology (network mode)
    │
    ▼
MCP calls create_dashboard with widget definitions:
  POST /dashboards
  {
    "name": "Docker Overview",
    "layout": { "mode": "grid", "columns": 12 },
    "widgets": [
      { "widgetType": "hydra::metric-card", "dataBinding": { ... }, "config": { "title": "docker-host-01 Containers" } },
      { "widgetType": "hydra::metric-card", "dataBinding": { ... }, "config": { "title": "docker-host-02 Containers" } },
      { "widgetType": "plg::docker::compose-status", "dataBinding": { ... } },
      { "widgetType": "hydra::mini-topology", "dataBinding": { ... } }
    ]
  }
    │
    ▼
Board created → MCP returns board URL to user
```

### 15.3 Dashboard as MCP Resource

Boards are exposed as MCP resources, allowing the AI to read dashboard definitions and understand what the user is monitoring:

```
Resource: dashboard://board_abc123
Content: Board definition JSON with widget types, data bindings, and configs
```

This lets the AI answer questions like "What am I monitoring on my infrastructure overview?" by reading the board definition.

---

## 16. Mobile, Tablet & Kiosk Modes

### 16.1 Responsive Behavior

The grid layout system handles responsive behavior through breakpoints (§7.2). On mobile:

- Widgets reflow to 2-column (xs) or 4-column (sm) layouts.
- Interactive widgets (toggles, buttons) are touch-optimized with larger hit targets.
- Edit mode uses a simplified interface — tap-to-configure rather than drag-to-position.
- Chart widgets switch to simplified renderings (no hover tooltips, larger touch areas).

### 16.2 Kiosk Mode

Kiosk mode is designed for wall-mounted displays (tablets, spare monitors). It strips the UI to just the dashboard content.

| Feature | Behavior |
|---------|----------|
| **No sidebar** | Full-width dashboard |
| **No header** | No user menu, no navigation |
| **Auto-refresh** | All widgets refresh on their intervals (or board-global interval) |
| **Auto-scroll** | Optionally scrolls vertically through the dashboard if content overflows |
| **No edit** | Read-only, no interaction except scroll |
| **Authentication** | Kiosk URL can be token-authenticated (no login page) or IP-restricted |
| **Multi-board rotation** | Cycle through multiple boards on a timer (e.g., 30s per board) |
| **Wake lock** | Prevent screen dimming via Wake Lock API |

**Kiosk URL:**

```
https://hydra.local/kiosk/{boardId}?token={kiosk-token}&rotate=board_abc,board_def&interval=30
```

### 16.3 Mobile App Dashboard

The React Native mobile app renders boards using a simplified native widget renderer. Not all widget types are available on mobile — complex widgets (topology, heatmap, freeform layout) fall back to a "View on desktop" placeholder. IoT control widgets are prioritized for mobile.

---

## 17. Import, Export & Sharing

### 17.1 Export Formats

| Format | Use Case |
|--------|----------|
| **JSON** | Full fidelity export for backup and transfer between Hydra instances |
| **YAML** | Human-readable/editable format, inspired by Glance's YAML configuration model |

### 17.2 Import Validation

On import, the API validates:

1. **Schema validity** — Board definition conforms to the dashboards schema.
2. **Widget type resolution** — All referenced widget types exist in the registry. Missing types generate warnings (not errors) — the board is imported with placeholders.
3. **Data binding resolution** — Data sources are checked for existence (do the referenced nodes/services/networks exist?). Missing references generate warnings.
4. **RBAC check** — Widget types and board visibility are validated against the importing user's role.

### 17.3 Sharing Model

| Sharing Method | Description |
|----------------|-------------|
| **Role sharing** | Board visible to all users of specified roles |
| **User sharing** | Board visible to specific named users |
| **Public** | Board visible to all authenticated users |
| **Kiosk token** | Board accessible via kiosk URL with token (no full auth required) |
| **Template conversion** | Board converted to a template (admin only) |
| **Export file** | Board definition shared as JSON/YAML file |

---

## 18. Implementation Roadmap

### Phase 1: Foundation (Core Framework)

| Task | Component | Priority |
|------|-----------|----------|
| Dashboard collection in MongoDB | API | P0 |
| Board CRUD endpoints | API | P0 |
| Widget registry (Hydra-native types only) | API | P0 |
| Grid layout engine integration (`react-grid-layout`) | Web | P0 |
| Widget renderer framework | Web | P0 |
| 6 core native widgets: Metric Card, Status Grid, Entity Table, Line Chart, Activity Feed, Markdown Block | Web | P0 |
| Board view page (render a saved board) | Web | P0 |
| Basic edit mode (drag, resize, add, remove, configure) | Web | P0 |
| Board list/picker page | Web | P0 |

### Phase 2: Widget Library Expansion

| Task | Component | Priority |
|------|-----------|----------|
| All native widgets (§5.1) implemented | Web | P0 |
| Widget picker with categories and search | Web | P0 |
| Data binding editor UI | Web | P0 |
| Transform pipeline (client-side) | Web | P0 |
| Multi-source bindings | Web | P1 |
| Column layout mode | Web | P1 |
| Board settings panel | Web | P0 |
| Set home board | API + Web | P0 |

### Phase 3: Plugin Widgets

| Task | Component | Priority |
|------|-----------|----------|
| Plugin widget registration API | API | P0 |
| Dynamic widget component loading (lazy) | Web | P0 |
| Docker plugin widgets (§5.2.2) | Web | P0 |
| Proxmox plugin widgets (§5.2.1) | Web | P0 |
| Home Assistant plugin widgets (§5.2.3) | Web | P0 |
| Prometheus plugin widgets (§5.2.6) | Web | P1 |
| All remaining plugin widgets | Web | P1 |
| Missing plugin graceful degradation | Web | P0 |

### Phase 4: Templates, Sharing & Polish

| Task | Component | Priority |
|------|-----------|----------|
| Template system (schema, CRUD, clone) | API | P0 |
| Template browser page | Web | P0 |
| Shipped templates (§8.2) created | API | P0 |
| Board sharing (role, user, public) | API + Web | P1 |
| Board versioning and history | API | P1 |
| Export/import (JSON, YAML) | API + Web | P1 |
| Admin template creation from boards | API + Web | P1 |

### Phase 5: Real-Time & Advanced

| Task | Component | Priority |
|------|-----------|----------|
| WebSocket channels for real-time widgets | API + Web | P1 |
| Kiosk mode | Web | P1 |
| Kiosk token authentication | API | P1 |
| Multi-board rotation (kiosk) | Web | P2 |
| MCP dashboard tools | MCP | P1 |
| MCP dashboard resources | MCP | P1 |
| Freeform layout mode | Web | P2 |
| Embedded dashboard panels (node detail, etc.) | Web | P2 |
| Mobile widget renderers | Mobile | P2 |
| Custom CSS per board | Web | P2 |

---

## 19. Appendices

### A. Widget Type ID Conventions

| Source | Pattern | Examples |
|--------|---------|----------|
| Hydra native | `hydra::{widget-name}` | `hydra::metric-card`, `hydra::status-grid` |
| Plugin | `plg::{plugin-id}::{widget-name}` | `plg::docker::container-grid`, `plg::ha::room-card` |
| Community plugin | `plg::{community-plugin-id}::{widget-name}` | `plg::custom-integration::my-widget` |

### B. Data Shape Reference

| Shape | Structure | Used By |
|-------|-----------|---------|
| `scalar` | `{ value: number }` | Metric Card, Gauge, Progress Bar |
| `scalar-with-trend` | `{ value: number, trend: number[] }` | Metric Card (with sparkline) |
| `scalar-with-range` | `{ value: number, min: number, max: number }` | Gauge |
| `scalar-with-max` | `{ value: number, max: number }` | Progress Bar |
| `array-of-scalars` | `[{ label: string, value: number }]` | Stat Group |
| `array-of-status` | `[{ id: string, name: string, status: string }]` | Status Grid |
| `categorical-distribution` | `[{ label: string, value: number }]` | Donut Chart |
| `time-series` | `[{ timestamp: string, value: number }]` | Line/Area Chart |
| `multi-time-series` | `{ series: [{ name: string, data: TimePoint[] }] }` | Multi-Line Chart |
| `paginated-entity-list` | `{ items: object[], total: number }` | Entity Table |
| `service-array` | `Service[]` | Service List |
| `event-stream` | `Event[]` | Activity Feed |
| `topology-graph` | `{ nodes: TopologyNode[], edges: TopologyEdge[] }` | Mini Topology |
| `container-array` | `DockerContainer[]` | Docker Container Grid |
| `ha-entity-array` | `HAEntity[]` | HA Room Card, Entity Table |

### C. Board Size Limits

| Constraint | Limit | Rationale |
|------------|-------|-----------|
| Max widgets per board | 50 | Performance — 50 simultaneous TanStack Query subscriptions |
| Max board name length | 128 chars | UI rendering |
| Max board description | 2048 chars | Storage |
| Max custom CSS | 10,000 chars | Safety |
| Max boards per user | 25 | Storage management |
| Max shared boards per user | 10 | Prevent catalog pollution |
| Board soft-delete retention | 30 days | Recovery window |
| Board version history | Last 50 versions | Storage management |
| Max template variables | 10 | UX complexity |

### D. Permission Mapping

| API Endpoint | Permission |
|-------------|------------|
| `GET /dashboards` | `dashboards:read` |
| `GET /dashboards/{id}` | `dashboards:read` + visibility |
| `POST /dashboards` | `dashboards:create` |
| `PUT /dashboards/{id}` | `dashboards:update` + owner |
| `PATCH /dashboards/{id}` | `dashboards:update` + owner |
| `DELETE /dashboards/{id}` | `dashboards:delete` + owner/admin |
| `POST /dashboards/{id}/clone` | `dashboards:create` + source visibility |
| `POST /dashboards/{id}/set-home` | authenticated |
| `GET /dashboards/widgets/registry` | `dashboards:read` |
| `GET /dashboards/templates` | `dashboards:read` |
| `POST /dashboards/templates` | `dashboards:templates:create` (admin) |
| `GET /dashboards/{id}/export` | `dashboards:read` + owner/admin |
| `POST /dashboards/import` | `dashboards:create` |
