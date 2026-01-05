# Hydra API

Central REST API service for the Hydra infrastructure management platform.

## Quick Start

### Prerequisites

- Python 3.11+
- MongoDB 6.0+ (or access to development server)
- Redis 7+ (or access to development server)
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- [Garage](https://garagehq.deuxfleurs.fr/documentation/quick-start/) (or any S3 compatible storage) 

### Installation

```bash
# Navigate to hydra-api directory
cd hydra-api

# Install dependencies with uv (recommended)
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Or with pip
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Configuration

Create a `.env` file or set environment variables:

```bash
# Required
HYDRA_MONGODB_URI=mongodb://mongo-dev.db.nimi.labs:27017
HYDRA_MONGODB_DATABASE=hydra_dev
HYDRA_REDIS_URL=redis://redis-dev.db.nimi.labs:6379/0
HYDRA_JWT_SECRET=your-secret-key

# Optional
HYDRA_ENV=development
HYDRA_DEBUG=true
HYDRA_HOST=0.0.0.0
HYDRA_PORT=8080
HYDRA_JWT_EXPIRE_MINUTES=60
```

### Running the API

```bash
# Development mode with auto-reload
uvicorn hydra.main:app --reload --host 0.0.0.0 --port 8080

# Production mode
uvicorn hydra.main:app --host 0.0.0.0 --port 8080 --workers 4
```

The API will be available at `http://localhost:8080/api/v1`. API documentation is at:
- Swagger UI: `http://localhost:8080/api/v1/docs`
- ReDoc: `http://localhost:8080/api/v1/redoc`
- OpenAPI JSON: `http://localhost:8080/api/v1/openapi.json`

## Testing

### Running Unit Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=hydra --cov-report=html

# Run specific test file
pytest tests/test_auth.py

# Run specific test
pytest tests/test_nodes.py::test_list_nodes_success

# Run with verbose output
pytest -v

# Run async tests only
pytest -m asyncio
```

### Test Structure

```
tests/
├── conftest.py          # Shared fixtures and helpers
├── test_auth.py         # Authentication endpoint tests
├── test_health.py       # Health check and info endpoint tests
├── test_nodes.py        # Node management endpoint tests
└── test_profiles.py     # Profile management endpoint tests
```

### Writing Tests

Tests use pytest with async support via `pytest-asyncio`. Key fixtures are defined in `conftest.py`:

- `client` - Async HTTP client with mocked dependencies
- `mock_mongodb` - Mocked MongoDB instance
- `mock_redis` - Mocked Redis instance
- `admin_token` - JWT token with admin privileges
- `agent_token` - JWT token for agent authentication
- `viewer_token` - JWT token with read-only access
- `sample_node` - Sample node document
- `sample_profile` - Sample profile document
- `sample_user` - Sample user document

Example test:

```python
@pytest.mark.asyncio
async def test_get_node_success(
    client: AsyncClient,
    mock_mongodb,
    admin_token,
    sample_node,
    sample_user,
):
    """Test getting a single node."""
    mock_mongodb.users.find_one = AsyncMock(
        return_value={**sample_user, "userId": "user_admin123", "role": "admin"}
    )
    mock_mongodb.nodes.find_one = AsyncMock(return_value=sample_node)

    response = await client.get(
        f"/nodes/{sample_node['nodeId']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["nodeId"] == sample_node["nodeId"]
```

## Running with Docker

### Using docker-compose (Development)

From the project root:

```bash
# Start all services (uses external MongoDB/Redis)
docker-compose -f docker-compose.dev.yml up hydra-api

# Start with local MongoDB/Redis
docker-compose -f docker-compose.dev.yml --profile local-db up

# Build and start
docker-compose -f docker-compose.dev.yml up --build hydra-api

# View logs
docker-compose -f docker-compose.dev.yml logs -f hydra-api
```

### Building Docker Image

```bash
# Build the image
docker build -t hydra-api:dev .

# Run the container
docker run -p 8080:8080 \
  -e HYDRA_MONGODB_URI=mongodb://mongo-dev.db.nimi.labs:27017 \
  -e HYDRA_MONGODB_DATABASE=hydra_dev \
  -e HYDRA_REDIS_URL=redis://redis-dev.db.nimi.labs:6379/0 \
  -e HYDRA_JWT_SECRET=your-secret-key \
  hydra-api:dev
```

## API Endpoints

### Health & Info
- `GET /api/v1/health` - Health check with service status
- `GET /api/v1/info` - Service information and statistics

### Authentication
- `POST /api/v1/auth/register` - Register a new node (requires registration token)
- `GET /api/v1/auth/me` - Get current authenticated entity info
- `POST /api/v1/auth/refresh` - Refresh access token

### Nodes
- `GET /api/v1/nodes` - List nodes with filtering and pagination
- `GET /api/v1/nodes/{nodeId}` - Get node details
- `PATCH /api/v1/nodes/{nodeId}` - Update node metadata
- `DELETE /api/v1/nodes/{nodeId}` - Archive a node
- `GET /api/v1/nodes/{nodeId}/children` - Get child nodes

### Profiles
- `POST /api/v1/profiles` - Submit a new profile (agent only)
- `GET /api/v1/profiles/{profileId}` - Get profile by ID
- `GET /api/v1/nodes/{nodeId}/profiles` - List profiles for a node
- `GET /api/v1/nodes/{nodeId}/profiles/latest` - Get latest profile
- `GET /api/v1/nodes/{nodeId}/profiles/diff` - Compare two profiles

## Project Structure

```
hydra-api/
├── src/hydra/
│   ├── main.py              # Root app (mounts versioned APIs)
│   ├── __init__.py          # Package metadata
│   ├── core/                # Shared configuration and logging
│   ├── db/                  # Shared database clients and indexes
│   └── v1/                  # API v1 implementation
│       ├── main.py          # v1 FastAPI app
│       ├── routers/         # Route handlers
│       ├── core/            # v1 auth/deps/exceptions
│       ├── models/          # Pydantic models
│       └── services/        # Business logic
├── tests/                   # Test suite
├── Dockerfile               # Production Docker image
├── pyproject.toml           # Python project configuration
└── README.md                # This file
```

## Development

### Code Style

The project uses:
- `ruff` for linting and formatting
- `mypy` for type checking

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type check
mypy src/hydra
```

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```
