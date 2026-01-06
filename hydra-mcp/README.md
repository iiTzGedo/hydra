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

| Variable | Description | Default |
|----------|-------------|---------|
| `HYDRA_MCP_API_URL` | Hydra API base URL | `http://localhost:8080/api/v1` |
| `HYDRA_MCP_API_KEY` | API key for authentication | - |
| `HYDRA_MCP_API_TIMEOUT` | Request timeout (seconds) | `30` |
| `HYDRA_MCP_TOON_INDENT` | TOON indentation spaces | `2` |
| `HYDRA_MCP_TOON_DELIMITER` | Array field delimiter | `,` |
| `HYDRA_MCP_LOG_LEVEL` | Logging level | `INFO` |

## Usage

### Running the Server

```bash
# Via CLI entry point
hydra-mcp

# Or as a Python module
python -m hydra
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

```bash
# Build the image
docker build -t hydra-mcp .

# Run (stdio-based MCP server)
docker run -it --rm \
  -e HYDRA_MCP_API_URL=http://host.docker.internal:8080/api/v1 \
  hydra-mcp
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
│   └── server.py        # MCP server implementation
├── tests/
├── pyproject.toml
└── README.md
```

## License

Apache-2.0
