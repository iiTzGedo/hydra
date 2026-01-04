# Hydra

AI-powered infrastructure management platform that creates a queryable knowledge graph of your infrastructure.

## Overview

Hydra profiles infrastructure state, builds relationships between entities, and exposes everything through the Model Context Protocol (MCP) for AI interaction. Unlike monitoring tools that focus on real-time metrics, Hydra focuses on **profiling** - capturing the structure, configuration, and relationships of your infrastructure.

## Components

| Component | Description | Technology |
|-----------|-------------|------------|
| **hydra-api** | Central REST API | Python/FastAPI |
| **hydra-agent** | Infrastructure profiler | Rust |
| **hydra-mcp** | AI interface layer | Python/MCP SDK |
| **hydra-web** | Web dashboard | React/TypeScript |

## Quick Start

### Prerequisites

- Python 3.11+
- Rust 1.75+
- Node.js 20+
- MongoDB 7.x
- Redis 7.x

### Development Setup

1. Clone the repository:
```bash
git clone https://github.com/hydra-project/hydra.git
cd hydra
```

2. Copy environment configuration:
```bash
cp .env.example .env
# Edit .env with your settings
```

3. Start with Docker Compose (includes local databases):
```bash
docker-compose -f docker-compose.dev.yml --profile local-db up -d
```

Or without local databases (using external MongoDB/Redis):
```bash
docker-compose -f docker-compose.dev.yml up -d
```

4. Access the services:
   - API: http://localhost:8080
   - Web UI: http://localhost:5173
   - API Docs: http://localhost:8080/docs

### Manual Development

**hydra-api:**
```bash
cd hydra-api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn hydra_api.main:app --reload
```

**hydra-agent:**
```bash
cd hydra-agent
cargo build --release
./target/release/hydra-agent --config config.toml
```

**hydra-web:**
```bash
cd hydra-web
npm install
npm run dev
```

## Documentation

See the `docs/` folder for comprehensive documentation:

1. **Product Documentation** - Vision, user journeys, use cases
2. **Technical Documentation** - Architecture, schemas, implementation
3. **API Reference** - All endpoints with examples
4. **Development Roadmap** - Phases and task breakdown

## License

Apache 2.0
