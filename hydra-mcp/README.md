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
  - [Infrastructure Queries](#infrastructure-queries)
  - [Analytics](#analytics)
  - [Time Machine](#time-machine)
  - [Control](#control)
- [Available Resources](#available-resources)
- [Available Prompts](#available-prompts)
- [TOON Output Format](#toon-output-format)
- [Docker](#docker)
- [Project Structure](#project-structure)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Overview

The Hydra MCP service enables LLMs to interact with your infrastructure through a standardized protocol. It provides:

- **18 Tools** for querying and controlling infrastructure
- **8 Resources** for browsing infrastructure state
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

### Infrastructure Queries

| Tool | Description |
|------|-------------|
| `list_nodes` | List infrastructure nodes with filters (class, type, status, tags) |
| `get_node` | Get detailed node information including children and services |
| `get_node_profile` | Get hardware, network, storage profile for a node |
| `list_services` | List services across infrastructure |
| `get_service` | Get detailed service information |
| `list_groups` | List logical groups |
| `get_group` | Get group details with member resolution |
| `list_networks` | List networks |
| `get_network` | Get network details |
| `get_topology` | Get infrastructure or network topology graph |
| `search_infrastructure` | Search across nodes, services, and entities |
| `service_dependency_map` | Map dependencies between services and identify critical paths |

### Analytics

| Tool | Description |
|------|-------------|
| `get_capacity` | Get infrastructure capacity summary |
| `compare_profiles` | Compare two profiles to see changes |
| `query_infrastructure` | Execute raw queries against collections |

### Time Machine

| Tool | Description |
|------|-------------|
| `time_machine_node` | Get node state at a specific timestamp |
| `time_machine_topology` | Get topology at a specific timestamp |

### Control

| Tool | Description |
|------|-------------|
| `control_service` | Control a service (start, stop, restart, reload) |
| `control_device` | Control IoT device via Home Assistant |

## Available Resources

| URI | Description |
|-----|-------------|
| `infrastructure://overview` | High-level infrastructure summary |
| `infrastructure://nodes` | All infrastructure nodes |
| `infrastructure://services` | All services |
| `infrastructure://networks` | All networks |
| `infrastructure://topology/network` | Current network topology |
| `infrastructure://topology/infrastructure` | Current infrastructure topology |
| `infrastructure://node/{nodeId}` | Specific node details |
| `infrastructure://service/{serviceId}` | Specific service details |

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

## Project Structure

```
hydra-mcp/
├── hydra/
│   ├── __init__.py      # Package exports
│   ├── __main__.py      # Module entry point
│   ├── config.py        # Settings via pydantic-settings
│   ├── client.py        # Async HTTP client for Hydra API
│   ├── toon.py          # TOON formatter wrapper
│   └── server.py        # MCP server (stdio + HTTP transport)
├── tests/               # Test suite
│   ├── conftest.py      # Test fixtures
│   └── test_*.py        # Test modules
├── .env.example         # Environment variable template
├── pyproject.toml       # Project configuration
├── Dockerfile           # Production Docker image
└── README.md            # This file
```

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=hydra --cov-report=html

# Type checking
mypy hydra

# Linting
ruff check hydra

# Formatting
ruff format hydra
```

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
