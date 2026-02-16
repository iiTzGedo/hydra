<p align="center">
  <img src="../resources/assets/logos/hydra-logos-v1_dark_256.png" alt="Hydra Logo" width="128" height="128">
</p>

<h1 align="center">Hydra API</h1>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python"></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg" alt="FastAPI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue.svg" alt="License"></a>
</p>

<p align="center">
  Central REST API service for the <a href="https://github.com/yourorg/hydra">Hydra</a> infrastructure management platform.<br>
  Built with FastAPI for high performance and automatic OpenAPI documentation.
</p>

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Required Variables](#required-variables)
  - [Optional Variables](#optional-variables)
  - [SMTP Configuration](#smtp-configuration)
  - [Object Storage Configuration](#object-storage-configuration)
- [Running the API](#running-the-api)
- [API Documentation](#api-documentation)
- [API Endpoints](#api-endpoints)
  - [Authentication](#authentication)
  - [Nodes](#nodes)
  - [Profiles](#profiles)
  - [Services](#services)
  - [Groups](#groups)
  - [Networks](#networks)
  - [Topologies](#topologies)
  - [Time Machine](#time-machine)
  - [Users & Admin](#users--admin)
  - [MCP Integration](#mcp-integration)
  - [AI & Chat](#ai--chat)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Docker](#docker)
- [Development](#development)
- [Security](#security)
- [License](#license)

## Features

- **RESTful API**: Clean, versioned API design (`/api/v1/`)
- **Authentication**: JWT tokens, API keys, registration tokens with RBAC
- **Infrastructure Management**: Full CRUD for nodes, services, networks, groups
- **Profile Versioning**: Hexadecimal versioning with automatic diff calculation
- **Time Machine**: Query historical infrastructure state at any timestamp
- **Topology Generation**: Automatic infrastructure and network graph generation
- **MCP Bridge**: LLM integration via Model Context Protocol proxy
- **AI Chat**: Built-in LLM bridge supporting Claude, GPT, and Ollama
- **Audit Logging**: Complete audit trail for write operations

## Quick Start

```bash
# Clone and navigate
cd hydra-api

# Install with uv (recommended)
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your MongoDB/Redis URIs

# Run development server
uvicorn hydra.main:app --reload --port 8080
```

## Installation

### Prerequisites

- Python 3.11+
- MongoDB 6.0+
- Redis 7+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- [Garage](https://garagehq.deuxfleurs.fr/) or S3-compatible storage (optional, for agent distribution)

### Install Dependencies

```bash
# With uv (recommended)
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configuration

Create a `.env` file or set environment variables:

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `HYDRA_MONGODB_URI` | MongoDB connection string | `mongodb://localhost:27017` |
| `HYDRA_MONGODB_DATABASE` | Database name | `hydra` |
| `HYDRA_REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `HYDRA_JWT_SECRET` | Secret key for JWT signing | `your-secure-secret-key` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HYDRA_ENV` | Environment name | `development` |
| `HYDRA_DEBUG` | Enable debug mode | `false` |
| `HYDRA_HOST` | Server bind address | `0.0.0.0` |
| `HYDRA_PORT` | Server port | `8080` |
| `HYDRA_JWT_EXPIRE_MINUTES` | JWT token expiry | `60` |
| `HYDRA_REFRESH_TOKEN_DAYS` | Refresh token expiry | `7` |
| `HYDRA_LOG_LEVEL` | Logging level | `INFO` |
| `HYDRA_LOG_FORMAT` | Log format (`json` or `text`) | `json` |

### SMTP Configuration

Optional email support for password reset:

| Variable | Description | Default |
|----------|-------------|---------|
| `HYDRA_SMTP_ENABLED` | Enable SMTP | `false` |
| `HYDRA_SMTP_HOST` | SMTP server | - |
| `HYDRA_SMTP_PORT` | SMTP port | `587` |
| `HYDRA_SMTP_USERNAME` | SMTP username | - |
| `HYDRA_SMTP_PASSWORD` | SMTP password | - |
| `HYDRA_SMTP_FROM_ADDRESS` | Sender email | - |
| `HYDRA_SMTP_FROM_NAME` | Sender name | `Hydra` |
| `HYDRA_SMTP_USE_TLS` | Use TLS | `true` |

### Object Storage Configuration

S3-compatible storage for agent binary distribution:

| Variable | Description | Default |
|----------|-------------|---------|
| `HYDRA_OBJECT_STORAGE_ENABLED` | Enable storage | `false` |
| `HYDRA_OBJECT_STORAGE_ENDPOINT` | S3 API endpoint | - |
| `HYDRA_OBJECT_STORAGE_BUCKET` | Bucket name | `hydra-bucket` |
| `HYDRA_OBJECT_STORAGE_ACCESS_KEY` | Access key | - |
| `HYDRA_OBJECT_STORAGE_SECRET_KEY` | Secret key | - |
| `HYDRA_OBJECT_STORAGE_REGION` | S3 region | `garage` |

## Running the API

```bash
# Development mode with auto-reload
uvicorn hydra.main:app --reload --host 0.0.0.0 --port 8080

# Production mode with workers
uvicorn hydra.main:app --host 0.0.0.0 --port 8080 --workers 4

# With gunicorn (recommended for production)
gunicorn hydra.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8080
```

## API Documentation

Interactive documentation is available when the API is running:

| Endpoint | Description |
|----------|-------------|
| `/api/v1/docs` | Swagger UI |
| `/api/v1/redoc` | ReDoc |
| `/api/v1/openapi.json` | OpenAPI schema |

## API Endpoints

### Health & Info

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check with service status |
| GET | `/api/v1/health/ready` | Readiness probe |
| GET | `/api/v1/health/live` | Liveness probe |

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register user or agent |
| POST | `/api/v1/auth/login` | Login and get tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Get current user info |
| POST | `/api/v1/auth/tokens` | Create registration token |
| GET | `/api/v1/auth/tokens` | List registration tokens |
| POST | `/api/v1/auth/apikeys` | Create API key |
| GET | `/api/v1/auth/apikeys` | List API keys |
| POST | `/api/v1/auth/password/reset` | Request password reset |
| POST | `/api/v1/auth/password/confirm` | Confirm password reset |

### Nodes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/nodes` | List nodes with filtering |
| POST | `/api/v1/nodes/register` | Register a new node |
| GET | `/api/v1/nodes/{node_id}` | Get node details |
| PATCH | `/api/v1/nodes/{node_id}` | Update node metadata |
| DELETE | `/api/v1/nodes/{node_id}` | Archive a node |
| POST | `/api/v1/nodes/{node_id}/apikey/refresh` | Refresh node API key |

### Profiles

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/profiles` | Submit new profile |
| GET | `/api/v1/profiles/{profileId}` | Get profile by ID |
| GET | `/api/v1/nodes/{nodeId}/profiles` | List node profiles |
| GET | `/api/v1/nodes/{nodeId}/profiles/diff` | Compare profiles |

### Services

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/services` | List services |
| GET | `/api/v1/services/{serviceId}` | Get service details |

### Groups

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/groups` | List groups |
| POST | `/api/v1/groups` | Create group |
| GET | `/api/v1/groups/{groupId}` | Get group details |
| PATCH | `/api/v1/groups/{groupId}` | Update group |
| DELETE | `/api/v1/groups/{groupId}` | Delete group |
| GET | `/api/v1/groups/{groupId}/members` | Get group members |

### Networks

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/networks` | List networks |
| GET | `/api/v1/networks/{networkId}` | Get network details |

### Topologies

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/topologies` | List topologies |
| GET | `/api/v1/topologies/current` | Get current topology |
| GET | `/api/v1/topologies/{id}` | Get topology by ID |
| POST | `/api/v1/topologies/regenerate` | Force regeneration |
| POST | `/api/v1/topologies/subgraph` | Get filtered subgraph |

### Time Machine

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/timemachine/state` | Get state at timestamp |
| GET | `/api/v1/timemachine/timeline` | Get event timeline |
| GET | `/api/v1/timemachine/compare` | Compare states |

### Users & Admin

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/users` | List users |
| GET | `/api/v1/users/{userId}` | Get user details |
| PATCH | `/api/v1/users/{userId}` | Update user |
| DELETE | `/api/v1/users/{userId}` | Delete user |
| GET | `/api/v1/users/{userId}/subs` | Get sub-accounts |

### MCP Integration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/mcp/info` | Get MCP server info |
| GET | `/api/v1/mcp/tools` | List available tools |
| POST | `/api/v1/mcp/tools/call` | Execute a tool |
| GET | `/api/v1/mcp/resources` | List resources |
| POST | `/api/v1/mcp/resources/read` | Read a resource |
| GET | `/api/v1/mcp/health` | MCP health check |

### AI & Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/chat/projects` | List chat projects |
| POST | `/api/v1/chat/projects` | Create chat project |
| GET | `/api/v1/chat/sessions` | List chat sessions |
| POST | `/api/v1/chat/sessions` | Create chat session |
| GET | `/api/v1/chat/sessions/{id}/messages` | Get session messages |
| POST | `/api/v1/chat/sessions/{id}/messages` | Send message |
| WS | `/api/v1/chat/ws` | WebSocket chat |

## Project Structure

```
hydra-api/
├── hydra/
│   ├── __init__.py              # Package metadata
│   ├── main.py                  # Root app (mounts versioned APIs)
│   ├── core/                    # Shared configuration and logging
│   │   ├── config.py            # Settings via pydantic-settings
│   │   └── logging.py           # Structured logging setup
│   ├── db/                      # Database clients
│   │   ├── mongodb.py           # MongoDB async client
│   │   ├── redis.py             # Redis async client
│   │   └── indexes.py           # Index definitions
│   └── api/
│       └── v1/                  # API v1 implementation
│           ├── main.py          # v1 FastAPI app
│           ├── core/            # Auth, deps, exceptions, validators
│           ├── routers/         # Route handlers (21 routers)
│           ├── models/          # Pydantic request/response models
│           └── services/        # Business logic layer
├── tests/                       # Test suite
│   ├── conftest.py              # Shared fixtures
│   ├── test_auth.py             # Auth tests
│   ├── test_nodes.py            # Node tests
│   ├── test_profiles.py         # Profile tests
│   └── test_validators.py       # Validator tests
├── Dockerfile                   # Production Docker image
├── pyproject.toml               # Project configuration
└── README.md                    # This file
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=hydra --cov-report=html

# Run specific test file
pytest tests/test_auth.py

# Run specific test
pytest tests/test_nodes.py::test_list_nodes_success -v

# Run async tests only
pytest -m asyncio
```

### Test Fixtures

Key fixtures defined in `conftest.py`:

| Fixture | Description |
|---------|-------------|
| `client` | Async HTTP client with mocked deps |
| `mock_mongodb` | Mocked MongoDB instance |
| `mock_redis` | Mocked Redis instance |
| `admin_token` | JWT with admin privileges |
| `agent_token` | JWT for agent auth |
| `viewer_token` | Read-only JWT |
| `sample_node` | Sample node document |
| `sample_profile` | Sample profile document |
| `sample_user` | Sample user document |

## Docker

### Building the Image

```bash
docker build -t hydra-api:latest .
```

### Running with Docker

```bash
docker run -p 8080:8080 \
  -e HYDRA_MONGODB_URI=mongodb://host.docker.internal:27017 \
  -e HYDRA_MONGODB_DATABASE=hydra \
  -e HYDRA_REDIS_URL=redis://host.docker.internal:6379/0 \
  -e HYDRA_JWT_SECRET=your-secret-key \
  hydra-api:latest
```

### Docker Compose

```bash
# Start with docker-compose
docker-compose -f docker-compose.dev.yml up hydra-api

# Start with local databases
docker-compose -f docker-compose.dev.yml --profile local-db up

# View logs
docker-compose -f docker-compose.dev.yml logs -f hydra-api
```

## Development

### Code Style

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type check
mypy hydra
```

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

### Adding New Endpoints

1. Create/update Pydantic models in `models/`
2. Implement business logic in `services/`
3. Add route handler in `routers/`
4. Register router in `v1/main.py`
5. Add tests in `tests/`

## Security

- **JWT Authentication**: Access tokens (short-lived) + refresh tokens
- **API Key Authentication**: For agents and programmatic access
- **Registration Tokens**: Scoped tokens for user/node registration
- **RBAC**: Role-based access control (admin, operator, viewer, family, agent)
- **Audit Logging**: All write operations logged with user context
- **Input Validation**: Pydantic models with strict validation patterns

### Role Hierarchy

| Role | Level | Permissions |
|------|-------|-------------|
| admin | 100 | Full access |
| operator | 50 | Infrastructure management |
| viewer | 25 | Read-only access |
| family | 10 | IoT controls only |
| agent | 0 | Own node only |

## License

Apache-2.0 - See [LICENSE](../LICENSE) for details.
