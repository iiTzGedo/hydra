<p align="center">
  <img src="../resources/assets/logos/hydra-logos-v1_dark_256.png" alt="Hydra Logo" width="128" height="128">
</p>

<h1 align="center">Hydra MCP</h1>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.12%2B-blue.svg" alt="Python"></a>
  <a href="https://modelcontextprotocol.io/"><img src="https://img.shields.io/badge/MCP-1.0-purple.svg" alt="MCP"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue.svg" alt="License"></a>
</p>

<p align="center">
  AI interface layer for <a href="https://github.com/yourorg/hydra">Hydra</a> infrastructure management.<br>
  Exposes infrastructure data through the <a href="https://modelcontextprotocol.io/">Model Context Protocol (MCP)</a>.
</p>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Available Tools](#available-tools)
- [Available Resources](#available-resources)
- [Available Prompts](#available-prompts)
- [TOON Output Format](#toon-output-format)
- [Docker](#docker)
- [Architecture](#architecture)
- [Development](#development)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Overview

The Hydra MCP service enables LLMs to interact with your infrastructure through a standardized protocol. It provides:

- **29 Tools** for querying and controlling infrastructure
- **8 Resources** for browsing infrastructure state (6 static + 2 dynamic patterns)
- **6 Prompts** for common infrastructure tasks

All responses are formatted using [TOON](https://github.com/toon-format/toon-python) (Text-Oriented Object Notation) for 30-60% token reduction compared to JSON.

## Features

- **Multi-Transport**: stdio (local), streamable-http (remote), SSE (legacy), HTTP (API integration)
- **Claude Desktop Compatible**: Works with Claude Desktop via stdio or streamable-http
- **Infrastructure Tools**: Query nodes, services, networks, groups, and topologies
- **Time Machine**: Historical state queries at any timestamp
- **Control Operations**: Service and IoT device control
- **Token Efficient**: TOON formatting reduces LLM token usage by 30-60%
- **Configurable**: Environment-based configuration for all settings

## Quick Start

```bash
# Install dependencies from uv.lock
cd hydra-mcp
uv sync --locked

# Set environment variables
export HYDRA_MCP_API_URL=http://localhost:8080/api/v1
export HYDRA_MCP_API_KEY=your-api-key

# Run with stdio (Claude Desktop local)
uv run hydra-mcp

# Or with streamable-http (Claude Desktop remote)
HYDRA_MCP_TRANSPORT=streamable-http uv run hydra-mcp
```

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- [Docker Engine](https://docs.docker.com/engine/install/) with the [Compose plugin](https://docs.docker.com/compose/install/) (`docker compose`) — for containerized deployment
- A running [hydra-api](../hydra-api/README.md) instance

## Installation

```bash
# Runtime dependencies
uv sync --locked

# Development dependencies
uv sync --dev --locked
```

> **Note:** The `toon-format` dependency is installed directly from GitHub. Ensure `git` is available in your environment.

## Configuration

Environment variables (prefix: `HYDRA_MCP_`):

### API Connection

| Variable | Description | Default |
|----------|-------------|---------|
| `HYDRA_MCP_API_URL` | Hydra API base URL | `http://localhost:8080/api/v1` |
| `HYDRA_MCP_API_KEY` | Hydra API key. Also used as the default server-side auth identity for network transports when requests do not forward auth headers. | - |
| `HYDRA_MCP_API_TIMEOUT` | Request timeout (seconds) | `30` |
| `HYDRA_MCP_INTERNAL_SECRET` | Optional shared secret for trusted Hydra internal forwarded auth headers. Use the same 32+ character value in Hydra API/Web and Hydra MCP. | - |

### Transport Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `HYDRA_MCP_TRANSPORT` | Transport mode | `stdio` |
| `HYDRA_MCP_HTTP_HOST` | Host for HTTP-based transports (`http`, `sse`, `streamable-http`) | `127.0.0.1` |
| `HYDRA_MCP_HTTP_PORT` | Port for HTTP-based transports (`http`, `sse`, `streamable-http`) | `8081` |
| `HYDRA_MCP_CORS_ORIGINS` | CORS allowed origins for HTTP-based transports (JSON array) | `["*"]` |

### TOON Formatting

| Variable | Description | Default |
|----------|-------------|---------|
| `HYDRA_MCP_TOON_INDENT` | Indentation spaces | `2` |
| `HYDRA_MCP_TOON_DELIMITER` | Array field delimiter | `,` |
| `HYDRA_MCP_TOON_LENGTH_MARKER` | Array length prefix | `` |

### Logging

| Variable | Description | Default |
|----------|-------------|---------|
| `HYDRA_MCP_LOG_LEVEL` | Logging level | `INFO` |
| `HYDRA_MCP_LOG_FORMAT` | Log format (`json` or `text`) | `json` |

## Usage

### Transport Modes

Hydra MCP supports **four transport modes**:

| Transport | Use Case | Claude Desktop | API Integration |
|-----------|----------|----------------|-----------------|
| `stdio` | Claude Desktop local (default) | ✅ | ❌ |
| `streamable-http` | Claude Desktop remote (recommended) | ✅ | ❌ |
| `sse` | Claude Desktop remote (legacy) | ✅ | ❌ |
| `http` | Hydra Web/API integration | ❌ | ✅ |

**Quick Start:**

```bash
# For Claude Desktop (local subprocess)
uv run hydra-mcp

# For Claude Desktop (remote HTTP) - RECOMMENDED
HYDRA_MCP_TRANSPORT=streamable-http uv run hydra-mcp

# For Hydra Web/API integration
HYDRA_MCP_TRANSPORT=http uv run hydra-mcp
```

### HTTP API Endpoints

When running in HTTP mode (`HYDRA_MCP_TRANSPORT=http`):

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with server info |
| `/tools` | GET | List available tools |
| `/tools/call` | POST | Execute a tool |
| `/resources` | GET | List available resources |
| `/resources/read` | POST | Read a resource |
| `/prompts` | GET | List available prompts |

**Example Requests:**

```bash
# Health check
curl http://localhost:8081/health

# List tools
curl http://localhost:8081/tools

# Call a tool
curl -X POST http://localhost:8081/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name": "list_nodes", "arguments": {"status": "active"}}'

# Read a resource
curl -X POST http://localhost:8081/resources/read \
  -H "Content-Type: application/json" \
  -d '{"uri": "infrastructure://overview"}'
```

### Claude Desktop Integration

**Config Location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Linux: `~/.config/claude-desktop/config.json`

**Option 1: Local (stdio)** - Claude Desktop spawns MCP process

```json
{
  "mcpServers": {
    "hydra": {
      "command": "uv",
      "args": ["--directory", "/path/to/hydra-mcp", "run", "hydra-mcp"],
      "env": {
        "HYDRA_MCP_API_URL": "http://localhost:8080/api/v1",
        "HYDRA_MCP_API_KEY": "your-api-key"
      }
    }
  }
}
```

**Option 2: Remote (streamable-http)** - Connect to running MCP server (recommended)

```bash
# Start MCP server.
# HYDRA_MCP_API_KEY is used as the default auth identity for network requests
# unless the client forwards Authorization or X-API-Key headers.
HYDRA_MCP_TRANSPORT=streamable-http \
HYDRA_MCP_API_URL=http://localhost:8080/api/v1 \
HYDRA_MCP_API_KEY=your-api-key \
uv run hydra-mcp
```

```json
{
  "mcpServers": {
    "hydra": {
      "url": "http://localhost:8081/mcp",
      "transport": "streamable-http"
    }
  }
}
```

```bash
# Or via Claude CLI
claude mcp add hydra --transport streamable-http http://localhost:8081/mcp
```

If Hydra API or Hydra Web will forward trusted internal auth headers to Hydra MCP, also set `HYDRA_MCP_INTERNAL_SECRET` to the same 32+ character value in every participating service.

## Available Tools

All 29 tools are implemented in `tool_handlers.py` and registered via the `@tool()` decorator.

### Node Tools

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `list_nodes` | List infrastructure nodes with filters (class, type, status, tags) | `nodes:read` |
| `get_node` | Get detailed node information including children and services | `nodes:read` |
| `get_node_profile` | Get hardware, network, storage profile for a node | `profiles:read` |

### Service Tools

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `list_services` | List services across infrastructure | `services:read` |
| `get_service` | Get detailed service information | `services:read` |
| `service_dependency_map` | Analyze service dependencies and identify critical paths | `services:read` |

### Command Tools

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `control_service` | Control a service. Internal-only; callable from trusted Hydra clients. | `commands:execute` |
| `control_node` | Control a node. Internal-only; callable from trusted Hydra clients. | `commands:execute` |
| `control_agent` | Control an agent. Internal-only; callable from trusted Hydra clients. | `commands:execute` |
| `get_command_status` | Get execution status for a command | `commands:read` |
| `list_command_catalog` | List available command definitions | `commands:read` |
| `list_commands` | List queued and historical commands | `commands:read` |
| `get_queue_status` | View command queue health and throughput | `commands:read` |

### Group Tools

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `list_groups` | List logical groups | `groups:read` |
| `get_group` | Get group details with member resolution | `groups:read` |

### Network & Topology Tools

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `list_networks` | List networks | `networks:read` |
| `get_network` | Get network details | `networks:read` |
| `get_topology` | Get infrastructure or network topology graph | `topologies:read` |

### Query & Analysis Tools

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `search_infrastructure` | Search across nodes, services, and entities | `nodes:read` |
| `query_infrastructure` | Execute raw queries against supported collections | `*:*` |
| `compare_profiles` | Compare two profiles to see changes between snapshots | `profiles:read` |
| `get_capacity` | Get infrastructure capacity summary | `nodes:read` |

### Time Machine Tools

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `time_machine_node` | Get node state at a specific timestamp | `profiles:read` |
| `time_machine_topology` | Get topology at a specific timestamp | `topologies:read` |

### IoT Tools

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `control_device` | Control IoT devices via Home Assistant | `iot:control` |

### Notification & Audit Tools

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `list_notifications` | List notifications visible to the current user | `notifications:read` |
| `get_notification_stats` | Get aggregated notification statistics | `notifications:read` |
| `list_audit_entries` | List audit log entries | `audit:read` |
| `delete_audit_entries` | Delete audit log entries within a time range | `audit:delete` |

## Available Resources

Resources provide browsable infrastructure data through URI-based access.

### Static Resources (6)

| URI | Description |
|-----|-------------|
| `infrastructure://overview` | High-level infrastructure summary |
| `infrastructure://nodes` | All infrastructure nodes |
| `infrastructure://services` | All services |
| `infrastructure://networks` | All networks |
| `infrastructure://topology/network` | Current network topology |
| `infrastructure://topology/infrastructure` | Current infrastructure topology |

### Dynamic Resource Patterns (2)

| URI Pattern | Description | Example |
|-------------|-------------|---------|
| `infrastructure://node/{nodeId}` | Specific node details | `infrastructure://node/proxmox-01` |
| `infrastructure://service/{serviceId}` | Specific service details | `infrastructure://service/svc-nginx-a1b2` |

## Available Prompts

| Prompt | Description | Required Args |
|--------|-------------|---------------|
| `capacity_planning` | Analyze capacity for new workloads | `workload` |
| `troubleshoot_network` | Diagnose network connectivity issues | `symptoms` |
| `infrastructure_audit` | Security and configuration audit | - |
| `service_dependency_map` | Map dependencies between services | - |
| `migration_planning` | Plan infrastructure migration | `source`, `target` |
| `documentation_generator` | Generate entity documentation | `entity_type`, `entity_id` |

## TOON Output Format

Responses use TOON format for optimal LLM consumption:

```
# Object notation
nodeId: proxmox-01
class: compute
status: active

# Tabular arrays
[3,]{id,name,status}:
node-1,Server 1,active
node-2,Server 2,active
node-3,Server 3,inactive

# Nested structures
network:
  cidr: 192.168.1.0/24
  gateway: 192.168.1.1
  nodes[5]: srv1,srv2,srv3,srv4,srv5
```

## Docker

### Building the Image

```bash
cd hydra-mcp
docker build -t hydra-mcp:latest .
```

### Running with HTTP Transport (Recommended for Docker)

```bash
docker run -d --name hydra-mcp \
  -p 8081:8081 \
  -e HYDRA_MCP_API_URL=http://host.docker.internal:8080/api/v1 \
  -e HYDRA_MCP_API_KEY=your-api-key \
  hydra-mcp:latest

# Check health
curl http://localhost:8081/health
```

If Hydra API or Hydra Web will call the built-in Hydra MCP service using forwarded internal auth headers, also provide the same `HYDRA_MCP_INTERNAL_SECRET` value to every participating container.

### Running with stdio Transport

```bash
# Interactive stdio mode (for testing)
docker run -it --rm \
  -e HYDRA_MCP_TRANSPORT=stdio \
  -e HYDRA_MCP_API_URL=http://host.docker.internal:8080/api/v1 \
  -e HYDRA_MCP_API_KEY=your-api-key \
  hydra-mcp:latest
```

### Docker Compose

```bash
# Start all services
docker compose up -d

# Start only hydra-mcp
docker compose up -d hydra-mcp

# View logs
docker compose logs -f hydra-mcp
```

## Architecture

Hydra MCP is split into a few focused modules:

| Module | Purpose |
|--------|---------|
| `server.py` | MCP server transports, auth middleware, resources, and prompts |
| `tool_handlers.py` | Tool definitions and implementations |
| `client.py` | Async Hydra API client with retry, auth forwarding, and response validation |
| `tools.py` | Tool registry infrastructure and schema validation |
| `auth.py` | Request-scoped auth context and permission checks |
| `config.py` | Pydantic settings loaded from environment variables |
| `toon.py` | TOON formatting helpers |
| `shared.py` | Shared singleton instances used by server and tools |

**Key Patterns:**
- **Tool Registry**: Tools are registered via the `@tool()` decorator in `tool_handlers.py`
- **Authorization**: Permission-based access control for all tools
- **TOON Formatting**: All responses use token-efficient TOON format
- **Multi-Transport**: Supports stdio, streamable-http, SSE, and HTTP modes

## Development

The test suite covers auth, tool execution, resources, prompts, query sanitization,
dependency analysis, packaging assumptions, and the HTTP transport.

```bash
# Install dev dependencies
uv sync --dev --locked

# Run tests
uv run pytest tests/

# Run with coverage
uv run pytest tests/ --cov=hydra_mcp --cov-report=html

# Run specific test file
uv run pytest tests/test_tools.py -v

# Type checking
uv run mypy hydra_mcp/

# Linting
uv run ruff check .

# Dependency audit
uv run pip-audit
```

### Adding New Tools

Tools are registered using the decorator pattern in `tool_handlers.py`:

```python
from hydra_mcp.tools import tool

@tool(
    name="my_tool",
    description="Tool description",
    schema={
        "type": "object",
        "properties": {
            "arg1": {"type": "string", "description": "Argument 1"}
        },
        "required": ["arg1"]
    },
    required_permission="resource:action"
)
async def my_tool(args: dict[str, Any]) -> str:
    """Tool implementation."""
    result = await client.get_node(args["arg1"])
    return toon.format(result)
```

## Security

Tool inputs are now strict at the top level: unknown arguments are rejected, oversized strings/arrays/objects fail validation, and internal/backend failures return generic client-safe messages while detailed causes stay in server logs.

### Authentication

Hydra MCP accepts two network-auth patterns:

- Forwarded request credentials via `Authorization` or `X-API-Key`
- A server-level fallback `HYDRA_MCP_API_KEY` configured on the Hydra MCP process

When request credentials are present, Hydra MCP validates and forwards those exact headers to Hydra API. When they are absent on network transports, Hydra MCP falls back to the configured `HYDRA_MCP_API_KEY` if one is set.

`HYDRA_MCP_INTERNAL_SECRET` is separate: it is only used to validate trusted `X-Hydra-Internal-*` forwarded auth headers from Hydra API/Web.

### Authorization

Tool permissions are enforced from the authenticated Hydra user or API key metadata:

| Permission | Used By |
|------------|---------|
| `nodes:read` | Node listing, node lookup, infrastructure search, capacity summaries |
| `profiles:read` | Node profiles, profile diffs, time-machine node lookups |
| `services:read` | Service listing, service lookup, dependency maps |
| `commands:read` | Command catalog, queue status, command history, command status |
| `commands:execute` | `control_service`, `control_node`, `control_agent` |
| `groups:read` | Group listing and detail |
| `networks:read` | Network listing and detail |
| `topologies:read` | Current and historical topologies |
| `iot:control` | IoT device control |
| `notifications:read` | Notification listing and stats |
| `audit:read` | Audit entry listing |
| `audit:delete` | Audit entry deletion |
| `*:*` | Raw infrastructure queries |

`control_service`, `control_node`, and `control_agent` are additionally restricted to trusted internal Hydra clients even when the caller has `commands:execute`.

### Transport Security

- **stdio**: Secure (local process)
- **streamable-http**: Requires network security (firewall, VPN, or TLS proxy)
- **http**: Requires network security (firewall, VPN, or TLS proxy)
- **sse**: Requires network security (firewall, VPN, or TLS proxy)

For production deployments, place Hydra MCP behind a reverse proxy with TLS termination (nginx, Traefik, Caddy).

## Troubleshooting

**Claude Desktop not connecting:**
- Verify transport matches: config says `streamable-http`, server must use `streamable-http`
- Check endpoint URL: `http://localhost:8081/mcp` for streamable-http
- Start the server from the project with `HYDRA_MCP_TRANSPORT=streamable-http uv run hydra-mcp`

**"Address already in use":**
- Stop old instance: `pkill hydra-mcp`
- Or use different port: `HYDRA_MCP_HTTP_PORT=8082`

**Tool calls return `AUTHORIZATION_DENIED` on network transports:**
- Set `HYDRA_MCP_API_KEY` on the Hydra MCP process, or send `Authorization` / `X-API-Key` on each request
- Internal-only command tools (`control_service`, `control_node`, `control_agent`) require trusted Hydra internal headers and are not available to external MCP clients

**HTTP transport returns 404 from Claude Desktop:**
- Expected! `http` transport is NOT MCP protocol compatible
- Use `streamable-http` or `sse` for Claude Desktop
- `http` transport is only for Hydra Web/API integration

**Built-in Hydra API/Web integration fails with 401:**
- Ensure Hydra API/Web and Hydra MCP share the same `HYDRA_MCP_INTERNAL_SECRET`
- Only internal forwarded requests should send `X-Hydra-Internal-*` headers

**API connection errors:**
- Verify `HYDRA_MCP_API_URL` points to running Hydra API
- Check API key is valid: `HYDRA_MCP_API_KEY`
- Test API directly: `curl $HYDRA_MCP_API_URL/health`

**Docker build fails:**
- Build from the `hydra-mcp/` directory so the Docker context includes `hydra_mcp/`, `pyproject.toml`, and `uv.lock`

## License

Apache-2.0 - See [LICENSE](../LICENSE) for details.
