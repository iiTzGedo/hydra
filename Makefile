# Hydra Project Makefile
# Centralized task runner for all components

.PHONY: help test test-api test-web test-mcp test-agent \
        lint lint-api lint-web lint-mcp lint-agent lint-fix \
        typecheck typecheck-api typecheck-web typecheck-mcp \
        build build-web build-agent \
        docker-up docker-down docker-logs \
        setup setup-api setup-web setup-mcp setup-agent \
        clean

# Default target
help:
	@echo "Hydra Project Tasks"
	@echo ""
	@echo "Testing:"
	@echo "  make test          Run all tests"
	@echo "  make test-api      Run API tests (pytest)"
	@echo "  make test-web      Run Web tests (vitest)"
	@echo "  make test-mcp      Run MCP tests (pytest)"
	@echo "  make test-agent    Run Agent tests (cargo test)"
	@echo ""
	@echo "Linting:"
	@echo "  make lint          Lint all components"
	@echo "  make lint-fix      Auto-fix lint issues"
	@echo ""
	@echo "Type Checking:"
	@echo "  make typecheck     Type check all components"
	@echo ""
	@echo "Building:"
	@echo "  make build         Build all components"
	@echo "  make build-web     Build web frontend"
	@echo "  make build-agent   Build agent binary"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up     Start all services"
	@echo "  make docker-down   Stop all services"
	@echo "  make docker-logs   Tail service logs"
	@echo ""
	@echo "Setup:"
	@echo "  make setup         Install all dependencies"
	@echo "  make clean         Remove build artifacts"

# ── Testing ──────────────────────────────────────────────

test: test-api test-web test-mcp test-agent

test-api:
	cd hydra-api && python -m pytest tests/ -v

test-web:
	cd hydra-web && npx vitest run

test-mcp:
	cd hydra-mcp && python -m pytest tests/ -v

test-agent:
	cd hydra-agent && cargo test

# ── Linting ──────────────────────────────────────────────

lint: lint-api lint-web lint-mcp lint-agent

lint-api:
	cd hydra-api && python -m ruff check .

lint-web:
	cd hydra-web && npx eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0

lint-mcp:
	cd hydra-mcp && python -m ruff check .

lint-agent:
	cd hydra-agent && cargo clippy -- -D warnings

lint-fix:
	cd hydra-api && python -m ruff check --fix .
	cd hydra-mcp && python -m ruff check --fix .
	cd hydra-web && npx eslint . --ext ts,tsx --fix

# ── Type Checking ────────────────────────────────────────

typecheck: typecheck-api typecheck-web typecheck-mcp

typecheck-api:
	cd hydra-api && python -m mypy hydra/

typecheck-web:
	cd hydra-web && npx tsc --noEmit

typecheck-mcp:
	cd hydra-mcp && python -m mypy hydra_mcp/

# ── Building ─────────────────────────────────────────────

build: build-web build-agent

build-web:
	cd hydra-web && npm run build

build-agent:
	cd hydra-agent && cargo build --release

# ── Docker ───────────────────────────────────────────────

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

# ── Setup ────────────────────────────────────────────────

setup: setup-api setup-web setup-mcp setup-agent

setup-api:
	cd hydra-api && pip install -e ".[dev]"

setup-web:
	cd hydra-web && npm install

setup-mcp:
	cd hydra-mcp && pip install -e ".[dev]"

setup-agent:
	cd hydra-agent && cargo fetch

# ── Cleanup ──────────────────────────────────────────────

clean:
	rm -rf hydra-web/dist hydra-web/node_modules/.vite
	cd hydra-agent && cargo clean
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
