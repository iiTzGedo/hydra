<p align="center">
  <img src="../resources/assets/logos/hydra-logos-v1_dark_256.png" alt="Hydra Logo" width="128" height="128">
</p>

<h1 align="center">Hydra MCP</h1>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python"></a>
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
  - [API Connection](#api-connection)
  - [Transport Settings](#transport-settings)
  - [TOON Formatting](#toon-formatting)
  - [Logging](#logging)
- [Usage](#usage)
  - [Transport Modes](#transport-modes)
  - [HTTP API Endpoints](#http-api-endpoints)
  - [Claude Desktop Integration](#claude-desktop-integration)
- [Available Tools](#available-tools)
  - [Node Tools](#node-tools-3)
  - [Service Tools](#service-tools-3)
  - [Group Tools](#group-tools-2)
  - [Network Tools](#network-tools-2)
  - [Topology & Query Tools](#topology--query-tools-3)
  - [Profile & Capacity Tools](#profile--capacity-tools-2)
  - [Time Machine Tools](#time-machine-tools-2)
  - [IoT/Control Tools](#iotcontrol-tools-2)
- [Available Resources](#available-resources)
  - [Static Resources](#static-resources-6)
  - [Dynamic Resource Patterns](#dynamic-resource-patterns-2)
- [Available Prompts](#available-prompts)
- [TOON Output Format](#toon-output-format)
- [Docker](#docker)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Development](#development)
  - [Test Coverage](#test-coverage)
  - [Adding New Tools](#adding-new-tools)
- [Security](#security)
  - [Authentication](#authentication)
  - [Authorization](#authorization)
  - [Transport Security](#transport-security)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Overview

The Hydra MCP service enables LLMs to interact with your infrastructure through a standardized protocol. It provides:

- **19 Tools** for querying and controlling infrastructure
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
# Install with uv
cd hydra-mcp
uv pip install -e .

# Set environment variables
export HYDRA_MCP_API_URL=http://localhost:8080/api/v1
export HYDRA_MCP_API_KEY=your-api-key

# Run with stdio (Claude Desktop local)
hydra-mcp

# Or with streamable-http (Claude Desktop remote)
HYDRA_MCP_TRANSPORT=streamable-http hydra-mcp
```

## Installation

```bash
# From the hydra-mcp directory (using uv, recommended)
uv pip install -e .

# Or with pip
pip install -e .

# With dev dependencies
uv pip install -e ".[dev]"
```

> **Note:** The `toon-format` dependency is installed directly from GitHub. Ensure `git` is available in your environment.

## Configuration

Environment variables (prefix: `HYDRA_MCP_`):

### API Connection

| Variable | Description | Default |
|----------|-------------|---------|
| `HYDRA_MCP_API_URL` | Hydra API base URL | `http://localhost:8080/api/v1` |
| `HYDRA_MCP_API_KEY` | API key for authentication | - |
| `HYDRA_MCP_API_TIMEOUT` | Request timeout (seconds) | `30` |

### Transport Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `HYDRA_MCP_TRANSPORT` | Transport mode | `stdio` |
| `HYDRA_MCP_HTTP_HOST` | HTTP server host | `0.0.0.0` |
| `HYDRA_MCP_HTTP_PORT` | HTTP server port | `8081` |
| `HYDRA_MCP_CORS_ORIGINS` | CORS allowed origins (JSON array) | `["*"]` |

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
hydra-mcp

# For Claude Desktop (remote HTTP) - RECOMMENDED
HYDRA_MCP_TRANSPORT=streamable-http hydra-mcp

# For Hydra Web/API integration
HYDRA_MCP_TRANSPORT=http hydra-mcp
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
      "command": "/path/to/hydra-mcp",
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
# Start MCP server
HYDRA_MCP_TRANSPORT=streamable-http \
HYDRA_MCP_API_URL=http://localhost:8080/api/v1 \
HYDRA_MCP_API_KEY=your-api-key \
hydra-mcp
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

## Available Tools

All 19 tools are implemented in `tool_handlers.py` and registered via the `@register_tool()` decorator pattern.

### Node Tools (3)

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `list_nodes` | List infrastructure nodes with filters (class, type, status, tags) | `nodes:read` |
| `get_node` | Get detailed node information including children and services | `nodes:read` |
| `get_node_profile` | Get hardware, network, storage profile for a node | `profiles:read` |

### Service Tools (3)

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `list_services` | List services across infrastructure | `services:read` |
| `get_service` | Get detailed service information | `services:read` |
| `control_service` | Control a service (start, stop, restart, reload) | `services:control` |

### Group Tools (2)

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `list_groups` | List logical groups | `groups:read` |
| `get_group` | Get group details with member resolution | `groups:read` |

### Network Tools (2)

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `list_networks` | List networks | `networks:read` |
| `get_network` | Get network details | `networks:read` |

### Topology & Query Tools (3)

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `get_topology` | Get infrastructure or network topology graph | `topologies:read` |
| `search_infrastructure` | Search across nodes, services, and entities | `nodes:read` |
| `query_infrastructure` | Execute raw queries against collections | `nodes:read` |

### Profile & Capacity Tools (2)

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `compare_profiles` | Compare two profiles to see changes | `profiles:read` |
| `get_capacity` | Get infrastructure capacity summary | `profiles:read` |

### Time Machine Tools (2)

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `time_machine_node` | Get node state at a specific timestamp | `nodes:read`, `profiles:read` |
| `time_machine_topology` | Get topology at a specific timestamp | `topologies:read` |

### IoT/Control Tools (2)

| Tool | Description | Required Permission |
|------|-------------|---------------------|
| `control_device` | Control IoT device via Home Assistant | `iot:control` |
| `service_dependency_map` | Map dependencies between services and identify critical paths | `services:read` |

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
docker-compose -f docker-compose.dev.yml up -d

# Start only hydra-mcp
docker-compose -f docker-compose.dev.yml up -d hydra-mcp

# View logs
docker-compose -f docker-compose.dev.yml logs -f hydra-mcp
```

## Architecture

The codebase was refactored from a monolithic 2,299-line server to a modular architecture:

| Module | Lines | Purpose |
|--------|-------|---------|
| `server.py` | 818 | MCP server with stdio + HTTP transport |
| `tool_handlers.py` | 835 | 19 tool implementations using registry pattern |
| `client.py` | 542 | Async HTTP client for Hydra API |
| `tools.py` | 212 | Tool registry infrastructure (decorator-based) |
| `auth.py` | 203 | Authorization module with role-based permissions |
| `config.py` | 124 | Settings via pydantic-settings |
| `toon.py` | 88 | TOON formatter wrapper |
| `shared.py` | 48 | Shared globals (client, settings, formatter) |

**Key Patterns:**
- **Tool Registry**: Tools are registered via `@register_tool()` decorator in `tool_handlers.py`
- **Authorization**: Permission-based access control for all tools
- **TOON Formatting**: All responses use token-efficient TOON format
- **Multi-Transport**: Supports stdio, streamable-http, SSE, and HTTP modes

## Project Structure

```
hydra-mcp/
├── hydra_mcp/
│   ├── __init__.py         # Package exports
│   ├── __main__.py         # Module entry point
│   ├── config.py           # Settings via pydantic-settings (124 lines)
│   ├── client.py           # Async HTTP client for Hydra API (542 lines)
│   ├── toon.py             # TOON formatter wrapper (88 lines)
│   ├── shared.py           # Shared globals (48 lines)
│   ├── auth.py             # Authorization and permissions (203 lines)
│   ├── tools.py            # Tool registry infrastructure (212 lines)
│   ├── tool_handlers.py    # 19 tool implementations (835 lines)
│   └── server.py           # MCP server with transports (818 lines)
├── tests/                  # Test suite (3 test files, 75+ tests)
│   ├── conftest.py         # Test fixtures
│   └── test_*.py           # Test modules
├── .env.example            # Environment variable template
├── pyproject.toml          # Project configuration
├── Dockerfile              # Production Docker image
└── README.md               # This file
```

## Development

### Test Coverage

The test suite includes 75+ tests across 3 test files:
- `test_auth.py` - Authorization and permissions
- `test_tools.py` - Tool registry and validation
- `test_server.py` - Server transport and handlers

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=hydra_mcp --cov-report=html

# Run specific test file
pytest tests/test_tools.py -v

# Type checking
mypy hydra_mcp

# Linting
ruff check hydra_mcp

# Formatting
ruff format hydra_mcp
```

### Adding New Tools

Tools are registered using the decorator pattern in `tool_handlers.py`:

```python
from hydra_mcp.tools import register_tool

@register_tool(
    name="my_tool",
    description="Tool description",
    input_schema={
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
    # Tool logic here
    result = await client.get(f"/endpoint/{args['arg1']}")
    return toon.format(result)
```

## Security

### Authentication

All API requests require a valid API key configured via `HYDRA_MCP_API_KEY`. The key is passed as a bearer token in the `Authorization` header.

### Authorization

Tools are protected by role-based permissions defined in `auth.py`:

| Permission | Required For | Granted To |
|------------|--------------|------------|
| `nodes:read` | Viewing nodes | viewer, operator, admin |
| `profiles:read` | Viewing profiles | viewer, operator, admin |
| `services:read` | Viewing services | viewer, operator, admin |
| `services:control` | Controlling services | operator, admin |
| `iot:control` | Controlling IoT devices | family, operator, admin |
| `groups:read` | Viewing groups | viewer, operator, admin |
| `networks:read` | Viewing networks | viewer, operator, admin |
| `topologies:read` | Viewing topologies | viewer, operator, admin |

**Note:** The `agent` role has minimal permissions and cannot use MCP tools. Use `viewer` or higher for AI interaction.

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
- Test server: `curl http://localhost:8081/mcp`

**"Address already in use":**
- Stop old instance: `pkill hydra-mcp`
- Or use different port: `HYDRA_MCP_HTTP_PORT=8082`

**HTTP transport returns 404 from Claude Desktop:**
- Expected! `http` transport is NOT MCP protocol compatible
- Use `streamable-http` or `sse` for Claude Desktop
- `http` transport is only for Hydra Web/API integration

**API connection errors:**
- Verify `HYDRA_MCP_API_URL` points to running Hydra API
- Check API key is valid: `HYDRA_MCP_API_KEY`
- Test API directly: `curl $HYDRA_MCP_API_URL/health`

## License

Apache-2.0 - See [LICENSE](../LICENSE) for details.
