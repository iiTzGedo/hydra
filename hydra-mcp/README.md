# Hydra MCP Service

AI interface layer for Hydra infrastructure management, exposing infrastructure data through the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

## Overview

The Hydra MCP service enables LLMs to interact with your infrastructure through a standardized protocol. It provides:

- **18 Tools** for querying and controlling infrastructure
- **8 Resources** for browsing infrastructure state
- **6 Prompts** for common infrastructure tasks

All responses are formatted using [TOON](https://github.com/toon-format/toon-python) (Text-Oriented Object Notation) for 30-60% token reduction compared to JSON.

## Installation

```bash
# From the hydra-mcp directory (using uv, recommended)
uv pip install -e .

# Or with pip (requires git for toon-format dependency)
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
| `HYDRA_MCP_TRANSPORT` | Transport mode: `stdio` or `http` | `stdio` |
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

The MCP server supports two transport modes:

#### stdio Transport (Default)

Standard input/output transport for Claude Desktop and MCP-compatible clients:

```bash
# Via CLI entry point
hydra-mcp

# Or as a Python module
python -m hydra

# Explicitly specify stdio transport
HYDRA_MCP_TRANSPORT=stdio hydra-mcp
```

#### HTTP Transport

HTTP REST API for web clients and direct access:

```bash
# Start with HTTP transport
HYDRA_MCP_TRANSPORT=http hydra-mcp

# Or with custom host/port
HYDRA_MCP_TRANSPORT=http HYDRA_MCP_HTTP_PORT=9000 hydra-mcp
```

### HTTP API Endpoints

When running in HTTP mode, the following endpoints are available:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with server info |
| `/tools` | GET | List available tools |
| `/tools/call` | POST | Execute a tool |
| `/resources` | GET | List available resources |
| `/resources/read` | POST | Read a resource |
| `/prompts` | GET | List available prompts |

#### Example HTTP Requests

```bash
# Health check
curl http://localhost:8081/health

# List tools
curl http://localhost:8081/tools

# Call a tool
curl -X POST http://localhost:8081/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name": "list_nodes", "arguments": {"status": "active"}}'

# List resources
curl http://localhost:8081/resources

# Read a resource
curl -X POST http://localhost:8081/resources/read \
  -H "Content-Type: application/json" \
  -d '{"uri": "infrastructure://overview"}'
```

### Claude Desktop Integration

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "hydra": {
      "command": "hydra-mcp",
      "env": {
        "HYDRA_MCP_API_URL": "http://localhost:8080/api/v1",
        "HYDRA_MCP_API_KEY": "your-api-key"
      }
    }
  }
}
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

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy hydra

# Linting
ruff check hydra
```

## Docker

### Building the Image

```bash
docker build -t hydra-mcp .
```

### Running with HTTP Transport (Recommended for Docker)

```bash
# Run with HTTP transport (default in Docker)
docker run -d --name hydra-mcp \
  -p 8081:8081 \
  -e HYDRA_MCP_API_URL=http://host.docker.internal:8080/api/v1 \
  hydra-mcp

# Check health
curl http://localhost:8081/health
```

### Running with stdio Transport

```bash
# Interactive stdio mode (for testing)
docker run -it --rm \
  -e HYDRA_MCP_TRANSPORT=stdio \
  -e HYDRA_MCP_API_URL=http://host.docker.internal:8080/api/v1 \
  hydra-mcp
```

### Docker Compose

The service is included in the main `docker-compose.dev.yml`:

```bash
# Start all services
docker-compose -f docker-compose.dev.yml up -d

# Start only hydra-mcp
docker-compose -f docker-compose.dev.yml up -d hydra-mcp

# View logs
docker-compose -f docker-compose.dev.yml logs -f hydra-mcp
```

## Architecture

```
hydra-mcp/
├── hydra/
│   ├── __init__.py      # Package exports
│   ├── __main__.py      # Module entry point
│   ├── config.py        # Settings via pydantic-settings
│   ├── client.py        # Async HTTP client for Hydra API
│   ├── toon.py          # TOON formatter wrapper
│   └── server.py        # MCP server (stdio + HTTP transport)
├── tests/
├── .env.example         # Environment variable template
├── pyproject.toml
├── Dockerfile
└── README.md
```

## License

Apache-2.0
