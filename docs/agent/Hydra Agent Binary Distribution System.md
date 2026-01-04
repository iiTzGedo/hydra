
## Technical Design Document v0.1.0

**Last Updated:** 2026-01-02  
**Status:** Draft  
**Author:** Architecture Review

---

## 1. Overview

### 1.1 Problem Statement

The current Hydra agent installation documentation assumes direct binary access, but lacks a centralized, versioned binary distribution mechanism. For homelab and small business deployments, users need:

- Centralized storage for multi-target compiled binaries
- Version management with retention policies
- Self-service installation with automatic target detection
- CI/CD integration for automated deployment pipelines

### 1.2 Solution

Implement an S3-compatible object storage layer (Garage) as the central binary repository, with API endpoints for installation and manual download, automated lifecycle management, and deployment scripts for CI/CD integration.

### 1.3 Key Design Decisions

|Decision|Choice|Rationale|
|---|---|---|
|Object Storage|Garage (S3-compatible)|Self-hosted, lightweight, homelab-friendly, S3 API compatibility|
|Bucket Name|`hydra-bucket` (default)|Consistent naming, configurable per deployment|
|Version Retention|Last 15 versions per target|Balance between rollback capability and storage efficiency|
|Target Detection|Runtime auto-detection|Reduces user friction, fallback to manual specification|

---

## 2. Architecture

### 2.1 Component Interaction

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        BINARY DISTRIBUTION FLOW                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────┐         ┌─────────────────────────────────────────┐     │
│  │  hydra-agent    │         │              Garage S3                  │     │
│  │  (Rust Source)  │         │         (Object Storage)                │     │
│  └────────┬────────┘         │  ┌─────────────────────────────────┐   │     │
│           │                  │  │        hydra-bucket             │   │     │
│           │ cargo build      │  │                                 │   │     │
│           │ --release        │  │  agents/                        │   │     │
│           ▼                  │  │  ├── linux-x86_64/              │   │     │
│  ┌─────────────────┐         │  │  │   ├── 0.3.0/                 │   │     │
│  │ Target Binaries │         │  │  │   │   └── hydra-agent        │   │     │
│  │ - linux-x86_64  │         │  │  │   ├── 0.3.1/                 │   │     │
│  │ - linux-aarch64 │         │  │  │   │   └── hydra-agent        │   │     │
│  │ - darwin-x86_64 │         │  │  │   └── latest -> 0.3.1/       │   │     │
│  │ - darwin-aarch64│         │  │  ├── linux-aarch64/             │   │     │
│  └────────┬────────┘         │  │  │   └── ...                    │   │     │
│           │                  │  │  ├── darwin-x86_64/             │   │     │
│           │ deploy.sh        │  │  │   └── ...                    │   │     │
│           ▼                  │  │  └── darwin-aarch64/            │   │     │
│  ┌─────────────────┐         │  │      └── ...                    │   │     │
│  │ Upload Script   │────────▶│  │                                 │   │     │
│  │ (S3 API)        │         │  │  manifests/                     │   │     │
│  └─────────────────┘         │  │  └── versions.json              │   │     │
│                              │  └─────────────────────────────────┘   │     │
│                              └──────────────────┬──────────────────────┘     │
│                                                 │                            │
│                                                 │ S3 API                     │
│                                                 ▼                            │
│                              ┌─────────────────────────────────────────┐     │
│                              │              hydra-api                  │     │
│                              │                                         │     │
│                              │  GET  /agent/install                    │     │
│                              │  GET  /agent/download/{target}          │     │
│                              │  GET  /health (includes storage check)  │     │
│                              └──────────────────┬──────────────────────┘     │
│                                                 │                            │
│                                                 │ Installation Script        │
│                                                 ▼                            │
│                              ┌─────────────────────────────────────────┐     │
│                              │           Target Nodes                  │     │
│                              │  (Linux x86_64, ARM64, macOS, etc.)     │     │
│                              └─────────────────────────────────────────┘     │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Storage Structure

```
hydra-bucket/
├── agents/
│   ├── linux-x86_64/
│   │   ├── 0.3.0/
│   │   │   ├── hydra-agent                    # Binary
│   │   │   ├── hydra-agent.sha256             # Checksum
│   │   │   └── metadata.json                  # Build metadata
│   │   ├── 0.3.1/
│   │   │   ├── hydra-agent
│   │   │   ├── hydra-agent.sha256
│   │   │   └── metadata.json
│   │   └── latest                             # Symlink marker file (contains "0.3.1")
│   ├── linux-aarch64/
│   │   └── ...
│   ├── darwin-x86_64/
│   │   └── ...
│   └── darwin-aarch64/
│       └── ...
├── manifests/
│   └── versions.json                          # Global version manifest
└── scripts/
    └── install.sh                             # Installation script template
```

### 2.3 Supported Targets

|Target ID|OS|Architecture|Notes|
|---|---|---|---|
|`linux-x86_64`|Linux|x86_64 (AMD64)|Primary target, most homelab servers|
|`linux-aarch64`|Linux|ARM64|Raspberry Pi 4/5, ARM servers|
|`darwin-x86_64`|macOS|Intel|Development machines|
|`darwin-aarch64`|macOS|Apple Silicon|M1/M2/M3 Macs|
|`windows-x86_64`|Windows|x86_64|Future support|

---

## 3. Object Storage Configuration

### 3.1 Garage Setup

Garage is an S3-compatible distributed object storage system designed for self-hosting. It's lightweight enough to run alongside hydra-api on the same host or on dedicated storage infrastructure.

**Reference:** https://garagehq.deuxfleurs.fr/documentation/quick-start/

### 3.2 Bucket Configuration

```toml
# /etc/hydra/storage.toml

[object_storage]
provider = "s3"
endpoint = "http://garage.home.lan:3900"    # Or localhost if co-located
bucket = "hydra-bucket"
region = "garage"                            # Required for S3 compat
access_key_id = "${HYDRA_S3_ACCESS_KEY}"
secret_access_key = "${HYDRA_S3_SECRET_KEY}"

[object_storage.options]
path_style = true                            # Required for Garage
verify_ssl = false                           # For internal deployments

[object_storage.lifecycle]
max_versions = 15                            # Per target
cleanup_schedule = "0 3 * * *"               # Daily at 3 AM
```

### 3.3 Lifecycle Policy Implementation

Since Garage doesn't natively support S3 lifecycle policies, implement version cleanup in hydra-api:

```python
# Pseudocode for lifecycle management
async def cleanup_old_versions(target: str, max_versions: int = 15):
    """Remove versions beyond retention limit for a target."""
    versions = await list_versions(target)  # Sorted newest first
    
    if len(versions) > max_versions:
        to_delete = versions[max_versions:]
        for version in to_delete:
            await delete_version(target, version)
            log.info(f"Deleted old version: {target}/{version}")
```

### 3.4 Version Manifest

```json
// hydra-bucket/manifests/versions.json
{
  "schemaVersion": 1,
  "generatedAt": "2026-01-02T10:00:00Z",
  "latestVersion": "0.3.1",
  "targets": {
    "linux-x86_64": {
      "latest": "0.3.1",
      "versions": [
        {
          "version": "0.3.1",
          "uploadedAt": "2026-01-02T09:00:00Z",
          "size": 8945632,
          "sha256": "a1b2c3d4e5f6...",
          "buildCommit": "abc123def"
        },
        {
          "version": "0.3.0",
          "uploadedAt": "2026-01-01T12:00:00Z",
          "size": 8912456,
          "sha256": "f6e5d4c3b2a1...",
          "buildCommit": "def456abc"
        }
      ]
    },
    "linux-aarch64": {
      "latest": "0.3.1",
      "versions": [...]
    }
  }
}
```

---

## 4. API Endpoints

### 4.1 Health Check Update

**Endpoint:** `GET /health`

The health endpoint must include object storage connectivity status.

```json
{
  "status": "healthy",
  "version": "0.3.1",
  "timestamp": "2026-01-02T10:00:00Z",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "disk": "ok",
    "object_storage": "ok"
  },
  "uptime_seconds": 86400
}
```

**Object Storage Health Check Logic:**

```python
async def check_object_storage_health() -> str:
    """Check object storage connectivity and bucket access."""
    try:
        # Verify bucket exists and is accessible
        await s3_client.head_bucket(Bucket=config.bucket)
        
        # Verify we can list objects (read permission)
        await s3_client.list_objects_v2(
            Bucket=config.bucket,
            Prefix="manifests/",
            MaxKeys=1
        )
        
        return "ok"
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            return "bucket_not_found"
        elif error_code == '403':
            return "access_denied"
        else:
            return f"error: {error_code}"
    except Exception as e:
        return f"unreachable: {str(e)}"
```

**Degraded Status Handling:**

|Object Storage Status|Overall Status|HTTP Code|
|---|---|---|
|`ok`|`healthy`|200|
|`bucket_not_found`|`degraded`|200|
|`access_denied`|`degraded`|200|
|`unreachable`|`degraded`|200|

Note: Object storage unavailability degrades agent installation capability but doesn't prevent core API functionality. The API remains available for existing agents to submit profiles.

---

### 4.2 Agent Installation Endpoint

**Endpoint:** `GET /agent/install`

Returns a shell script that auto-detects the target platform and downloads/installs the agent.

**Query Parameters:**

|Parameter|Type|Required|Default|Description|
|---|---|---|---|---|
|`target`|string|No|auto-detect|Override target platform|
|`version`|string|No|`latest`|Specific version to install|
|`register`|boolean|No|`false`|Auto-register after install|

**Response:** `200 OK` (Content-Type: text/x-shellscript)

**Example Usage:**

```bash
# Auto-detect platform, install latest
curl -sSL https://hydra.local/api/v1/agent/install | bash

# Specify target and version
curl -sSL "https://hydra.local/api/v1/agent/install?target=linux-aarch64&version=0.3.0" | bash

# Install and register
curl -sSL "https://hydra.local/api/v1/agent/install?register=true" | bash -s -- \
  --username admin --password <password>
```

**Installation Script Logic:**

```bash
#!/bin/bash
set -euo pipefail

# Configuration (injected by API)
HYDRA_API_URL="{{API_URL}}"
REQUESTED_TARGET="{{TARGET}}"      # Empty if auto-detect
REQUESTED_VERSION="{{VERSION}}"    # "latest" or specific version
REGISTER_AFTER="{{REGISTER}}"

# Installation paths
INSTALL_DIR="/usr/local/bin"
CONFIG_DIR="/etc/hydra"
LOG_DIR="/var/log/hydra"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Detect target platform
detect_target() {
    local os=$(uname -s | tr '[:upper:]' '[:lower:]')
    local arch=$(uname -m)
    
    # Normalize OS
    case "$os" in
        linux)   os="linux" ;;
        darwin)  os="darwin" ;;
        mingw*|msys*|cygwin*) os="windows" ;;
        *) log_error "Unsupported OS: $os" ;;
    esac
    
    # Normalize architecture
    case "$arch" in
        x86_64|amd64)  arch="x86_64" ;;
        aarch64|arm64) arch="aarch64" ;;
        *) log_error "Unsupported architecture: $arch" ;;
    esac
    
    echo "${os}-${arch}"
}

# Determine target
if [[ -n "$REQUESTED_TARGET" ]]; then
    TARGET="$REQUESTED_TARGET"
    log_info "Using specified target: $TARGET"
else
    TARGET=$(detect_target)
    log_info "Detected target: $TARGET"
fi

# Download binary
VERSION="${REQUESTED_VERSION:-latest}"
DOWNLOAD_URL="${HYDRA_API_URL}/agent/download/${TARGET}?version=${VERSION}"

log_info "Downloading hydra-agent ${VERSION} for ${TARGET}..."
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

curl -sSL -o "${TMP_DIR}/hydra-agent" "${DOWNLOAD_URL}" || \
    log_error "Failed to download agent binary"

curl -sSL -o "${TMP_DIR}/hydra-agent.sha256" "${DOWNLOAD_URL}.sha256" || \
    log_warn "Checksum file not available, skipping verification"

# Verify checksum if available
if [[ -f "${TMP_DIR}/hydra-agent.sha256" ]]; then
    log_info "Verifying checksum..."
    cd "$TMP_DIR"
    sha256sum -c hydra-agent.sha256 || log_error "Checksum verification failed!"
    cd - > /dev/null
fi

# Install binary
log_info "Installing to ${INSTALL_DIR}/hydra-agent..."
sudo install -m 755 "${TMP_DIR}/hydra-agent" "${INSTALL_DIR}/hydra-agent"

# Create directories
sudo mkdir -p "$CONFIG_DIR" "$LOG_DIR"
sudo chmod 750 "$CONFIG_DIR"

# Verify installation
if "${INSTALL_DIR}/hydra-agent" --version > /dev/null 2>&1; then
    INSTALLED_VERSION=$("${INSTALL_DIR}/hydra-agent" --version | head -1)
    log_info "Successfully installed: $INSTALLED_VERSION"
else
    log_error "Installation verification failed"
fi

# Setup systemd service (Linux only)
if [[ "$(uname -s)" == "Linux" ]] && command -v systemctl &> /dev/null; then
    log_info "Setting up systemd service..."
    
    cat << 'EOF' | sudo tee /etc/systemd/system/hydra-agent.service > /dev/null
[Unit]
Description=Hydra Infrastructure Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/hydra-agent run
Restart=on-failure
RestartSec=10
Environment="HYDRA_CONFIG=/etc/hydra/agent.toml"

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    log_info "Systemd service created (not started)"
fi

# Registration (if requested)
if [[ "$REGISTER_AFTER" == "true" ]]; then
    log_info "To register this node, run:"
    echo "  hydra-agent register --api-url ${HYDRA_API_URL} --username <user> --password <pass>"
fi

log_info "Installation complete!"
log_info ""
log_info "Next steps:"
log_info "  1. Configure: Edit ${CONFIG_DIR}/agent.toml"
log_info "  2. Register:  hydra-agent register --api-url ${HYDRA_API_URL}"
log_info "  3. Start:     sudo systemctl start hydra-agent"
log_info "  4. Enable:    sudo systemctl enable hydra-agent"
```

---

### 4.3 Agent Download Endpoint

**Endpoint:** `GET /agent/download/{target}`

Direct binary download for manual installation scenarios.

**Path Parameters:**

|Parameter|Type|Description|
|---|---|---|
|`target`|string|Target platform (e.g., `linux-x86_64`, `linux-aarch64`)|

**Query Parameters:**

|Parameter|Type|Required|Default|Description|
|---|---|---|---|---|
|`version`|string|No|`latest`|Specific version to download|

**Responses:**

|Status|Description|
|---|---|
|200|Binary file (Content-Type: application/octet-stream)|
|404|Target or version not found|
|503|Object storage unavailable|

**Response Headers:**

```
Content-Type: application/octet-stream
Content-Disposition: attachment; filename="hydra-agent-linux-x86_64-0.3.1"
Content-Length: 8945632
X-Hydra-Version: 0.3.1
X-Hydra-SHA256: a1b2c3d4e5f6...
```

**Example Usage:**

```bash
# Download latest for specific target
wget https://hydra.local/api/v1/agent/download/linux-x86_64

# Download specific version
curl -O https://hydra.local/api/v1/agent/download/linux-aarch64?version=0.3.0

# Download with checksum verification
curl -O https://hydra.local/api/v1/agent/download/linux-x86_64
curl -O https://hydra.local/api/v1/agent/download/linux-x86_64.sha256
sha256sum -c hydra-agent.sha256
```

**Implementation Notes:**

```python
@router.get("/agent/download/{target}")
async def download_agent(
    target: str,
    version: str = Query(default="latest"),
    storage: ObjectStorage = Depends(get_storage)
):
    """Stream agent binary from object storage."""
    
    # Validate target
    valid_targets = ["linux-x86_64", "linux-aarch64", "darwin-x86_64", "darwin-aarch64"]
    if target not in valid_targets:
        raise HTTPException(404, f"Unknown target: {target}")
    
    # Resolve 'latest' to actual version
    if version == "latest":
        version = await storage.get_latest_version(target)
        if not version:
            raise HTTPException(404, f"No versions available for {target}")
    
    # Get binary from storage
    object_key = f"agents/{target}/{version}/hydra-agent"
    
    try:
        binary_stream = await storage.get_object_stream(object_key)
        metadata = await storage.get_object_metadata(object_key)
        
        return StreamingResponse(
            binary_stream,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="hydra-agent-{target}-{version}"',
                "Content-Length": str(metadata["size"]),
                "X-Hydra-Version": version,
                "X-Hydra-SHA256": metadata.get("sha256", "")
            }
        )
    except ObjectNotFoundError:
        raise HTTPException(404, f"Version {version} not found for {target}")
    except StorageUnavailableError:
        raise HTTPException(503, "Object storage unavailable")
```

---

### 4.4 Version Listing Endpoint (Optional Enhancement)

**Endpoint:** `GET /agent/versions`

List available versions for all or specific targets.

```json
{
  "targets": {
    "linux-x86_64": {
      "latest": "0.3.1",
      "available": ["0.3.1", "0.3.0", "0.2.9"]
    },
    "linux-aarch64": {
      "latest": "0.3.1",
      "available": ["0.3.1", "0.3.0"]
    }
  }
}
```

---

## 5. Deployment Script

### 5.1 Build & Upload Script

This script compiles the agent for all targets and uploads to object storage.

```bash
#!/bin/bash
# scripts/deploy-agent.sh
set -euo pipefail

# Configuration
VERSION="${1:-}"
S3_ENDPOINT="${HYDRA_S3_ENDPOINT:-http://garage.home.lan:3900}"
S3_BUCKET="${HYDRA_S3_BUCKET:-hydra-bucket}"
S3_ACCESS_KEY="${HYDRA_S3_ACCESS_KEY}"
S3_SECRET_KEY="${HYDRA_S3_SECRET_KEY}"

# Targets to build
TARGETS=(
    "x86_64-unknown-linux-gnu:linux-x86_64"
    "aarch64-unknown-linux-gnu:linux-aarch64"
    "x86_64-apple-darwin:darwin-x86_64"
    "aarch64-apple-darwin:darwin-aarch64"
)

# Validate version
if [[ -z "$VERSION" ]]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 0.3.1"
    exit 1
fi

# Validate semver format
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9]+)?$ ]]; then
    echo "Error: Version must be semver format (e.g., 0.3.1 or 0.3.1-beta)"
    exit 1
fi

echo "=== Hydra Agent Deployment v${VERSION} ==="
echo ""

# Build directory
BUILD_DIR="target/release-dist"
mkdir -p "$BUILD_DIR"

# Build for each target
for target_pair in "${TARGETS[@]}"; do
    RUST_TARGET="${target_pair%%:*}"
    HYDRA_TARGET="${target_pair##*:}"
    
    echo "Building for ${HYDRA_TARGET} (${RUST_TARGET})..."
    
    # Cross-compile (requires cross or appropriate toolchain)
    if command -v cross &> /dev/null; then
        cross build --release --target "$RUST_TARGET"
    else
        cargo build --release --target "$RUST_TARGET"
    fi
    
    # Copy binary
    BINARY_SRC="target/${RUST_TARGET}/release/hydra-agent"
    BINARY_DST="${BUILD_DIR}/${HYDRA_TARGET}/hydra-agent"
    
    mkdir -p "${BUILD_DIR}/${HYDRA_TARGET}"
    cp "$BINARY_SRC" "$BINARY_DST"
    
    # Generate checksum
    sha256sum "$BINARY_DST" | awk '{print $1}' > "${BINARY_DST}.sha256"
    
    # Generate metadata
    cat > "${BUILD_DIR}/${HYDRA_TARGET}/metadata.json" << EOF
{
  "version": "${VERSION}",
  "target": "${HYDRA_TARGET}",
  "rustTarget": "${RUST_TARGET}",
  "buildTime": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "buildCommit": "$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')",
  "size": $(stat -f%z "$BINARY_DST" 2>/dev/null || stat -c%s "$BINARY_DST"),
  "sha256": "$(cat ${BINARY_DST}.sha256)"
}
EOF
    
    echo "  ✓ Built ${HYDRA_TARGET}"
done

echo ""
echo "=== Uploading to Object Storage ==="

# Configure AWS CLI for S3 access
export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
export AWS_DEFAULT_REGION="garage"

# S3 command with endpoint
s3cmd() {
    aws s3 --endpoint-url "$S3_ENDPOINT" "$@"
}

s3api() {
    aws s3api --endpoint-url "$S3_ENDPOINT" "$@"
}

# Upload binaries for each target
for target_pair in "${TARGETS[@]}"; do
    HYDRA_TARGET="${target_pair##*:}"
    
    echo "Uploading ${HYDRA_TARGET}..."
    
    # Upload binary
    s3cmd cp "${BUILD_DIR}/${HYDRA_TARGET}/hydra-agent" \
        "s3://${S3_BUCKET}/agents/${HYDRA_TARGET}/${VERSION}/hydra-agent"
    
    # Upload checksum
    s3cmd cp "${BUILD_DIR}/${HYDRA_TARGET}/hydra-agent.sha256" \
        "s3://${S3_BUCKET}/agents/${HYDRA_TARGET}/${VERSION}/hydra-agent.sha256"
    
    # Upload metadata
    s3cmd cp "${BUILD_DIR}/${HYDRA_TARGET}/metadata.json" \
        "s3://${S3_BUCKET}/agents/${HYDRA_TARGET}/${VERSION}/metadata.json"
    
    # Update latest marker
    echo "$VERSION" | s3cmd cp - "s3://${S3_BUCKET}/agents/${HYDRA_TARGET}/latest"
    
    echo "  ✓ Uploaded ${HYDRA_TARGET}"
done

# Update global manifest
echo ""
echo "Updating version manifest..."

# Generate versions.json
python3 << EOF
import json
import subprocess
from datetime import datetime

def list_versions(target):
    result = subprocess.run(
        ['aws', 's3', 'ls', '--endpoint-url', '$S3_ENDPOINT',
         f's3://$S3_BUCKET/agents/{target}/'],
        capture_output=True, text=True
    )
    versions = []
    for line in result.stdout.strip().split('\n'):
        parts = line.split()
        if parts and parts[-1].replace('/', '').replace('.', '').isdigit():
            versions.append(parts[-1].rstrip('/'))
    return sorted(versions, key=lambda v: list(map(int, v.split('.'))), reverse=True)

targets = {}
for target in ['linux-x86_64', 'linux-aarch64', 'darwin-x86_64', 'darwin-aarch64']:
    versions = list_versions(target)[:15]  # Keep only last 15
    if versions:
        targets[target] = {
            'latest': versions[0],
            'versions': versions
        }

manifest = {
    'schemaVersion': 1,
    'generatedAt': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
    'latestVersion': '$VERSION',
    'targets': targets
}

with open('${BUILD_DIR}/versions.json', 'w') as f:
    json.dump(manifest, f, indent=2)

print(json.dumps(manifest, indent=2))
EOF

s3cmd cp "${BUILD_DIR}/versions.json" "s3://${S3_BUCKET}/manifests/versions.json"

echo ""
echo "=== Cleanup Old Versions ==="

# Keep only last 15 versions per target
for target_pair in "${TARGETS[@]}"; do
    HYDRA_TARGET="${target_pair##*:}"
    
    # List versions, skip 'latest' marker
    VERSIONS=$(s3cmd ls "s3://${S3_BUCKET}/agents/${HYDRA_TARGET}/" | \
        awk '{print $NF}' | \
        grep -E '^[0-9]+\.[0-9]+\.[0-9]+' | \
        sort -V -r)
    
    COUNT=0
    for v in $VERSIONS; do
        COUNT=$((COUNT + 1))
        if [[ $COUNT -gt 15 ]]; then
            echo "Removing old version: ${HYDRA_TARGET}/${v}"
            s3cmd rm --recursive "s3://${S3_BUCKET}/agents/${HYDRA_TARGET}/${v}/"
        fi
    done
done

echo ""
echo "=== Deployment Complete ==="
echo "Version ${VERSION} deployed to all targets"
echo ""
echo "Install command:"
echo "  curl -sSL https://hydra.local/api/v1/agent/install | bash"
```

### 5.2 CI/CD Integration

**GitHub Actions Example:**

```yaml
# .github/workflows/agent-release.yml
name: Release Hydra Agent

on:
  push:
    tags:
      - 'agent-v*'

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Install Rust
        uses: dtolnay/rust-action@stable
        with:
          targets: x86_64-unknown-linux-gnu,aarch64-unknown-linux-gnu
      
      - name: Install cross
        run: cargo install cross --git https://github.com/cross-rs/cross
      
      - name: Extract version
        id: version
        run: echo "VERSION=${GITHUB_REF#refs/tags/agent-v}" >> $GITHUB_OUTPUT
      
      - name: Build and Deploy
        env:
          HYDRA_S3_ENDPOINT: ${{ secrets.HYDRA_S3_ENDPOINT }}
          HYDRA_S3_ACCESS_KEY: ${{ secrets.HYDRA_S3_ACCESS_KEY }}
          HYDRA_S3_SECRET_KEY: ${{ secrets.HYDRA_S3_SECRET_KEY }}
        run: |
          cd hydra-agent
          ./scripts/deploy-agent.sh ${{ steps.version.outputs.VERSION }}
```

---

## 6. Practical Use Cases

### 6.1 Homelab Scenario: New VM Provisioning

**Context:** User provisions a new Ubuntu VM in Proxmox and wants to add it to Hydra.

```bash
# SSH into new VM
ssh user@new-vm

# One-liner installation
curl -sSL https://hydra.home.lan/api/v1/agent/install | sudo bash

# Configure
sudo nano /etc/hydra/agent.toml
# Set: node_id = "ubuntu-vm-01"
# Set: api.base_url = "https://hydra.home.lan"

# Register with Hydra
sudo hydra-agent register --username admin --password <password>

# Start and enable
sudo systemctl enable --now hydra-agent

# Verify
sudo systemctl status hydra-agent
```

**Time to first profile:** ~2 minutes

### 6.2 Homelab Scenario: Raspberry Pi Fleet

**Context:** User has multiple Raspberry Pi devices (ARM64) running various services.

```bash
# On each Pi (auto-detects ARM64)
curl -sSL https://hydra.home.lan/api/v1/agent/install | sudo bash

# Or specify target explicitly for headless setup
curl -sSL "https://hydra.home.lan/api/v1/agent/install?target=linux-aarch64" | sudo bash
```

### 6.3 Enterprise Scenario: Ansible-Based Deployment

**Context:** IT team wants to deploy agents across 50 servers using Ansible.

```yaml
# playbooks/hydra-agent.yml
---
- name: Deploy Hydra Agent
  hosts: all
  become: true
  
  vars:
    hydra_api_url: "https://hydra.corp.local"
    hydra_version: "latest"
  
  tasks:
    - name: Download Hydra Agent
      get_url:
        url: "{{ hydra_api_url }}/api/v1/agent/download/{{ hydra_target }}"
        dest: /usr/local/bin/hydra-agent
        mode: '0755'
      vars:
        hydra_target: "linux-{{ 'aarch64' if ansible_architecture == 'aarch64' else 'x86_64' }}"
    
    - name: Create config directory
      file:
        path: /etc/hydra
        state: directory
        mode: '0750'
    
    - name: Deploy agent configuration
      template:
        src: agent.toml.j2
        dest: /etc/hydra/agent.toml
        mode: '0640'
    
    - name: Register agent
      command: >
        hydra-agent register
        --api-url {{ hydra_api_url }}
        --username {{ hydra_admin_user }}
        --password {{ hydra_admin_pass }}
      args:
        creates: /etc/hydra/credentials.json
    
    - name: Deploy systemd service
      copy:
        src: hydra-agent.service
        dest: /etc/systemd/system/hydra-agent.service
      notify: restart hydra-agent
    
    - name: Enable and start agent
      systemd:
        name: hydra-agent
        enabled: true
        state: started
  
  handlers:
    - name: restart hydra-agent
      systemd:
        name: hydra-agent
        state: restarted
```

### 6.4 CI/CD Scenario: Agent Version Rollback

**Context:** New agent version has a bug, need to rollback all nodes.

```bash
# Option 1: Force specific version via install endpoint
curl -sSL "https://hydra.home.lan/api/v1/agent/install?version=0.3.0" | sudo bash

# Option 2: Manual download and replace
sudo systemctl stop hydra-agent
curl -O https://hydra.home.lan/api/v1/agent/download/linux-x86_64?version=0.3.0
sudo mv hydra-agent /usr/local/bin/hydra-agent
sudo chmod +x /usr/local/bin/hydra-agent
sudo systemctl start hydra-agent
```

### 6.5 Development Scenario: Testing Pre-Release Agents

```bash
# Deploy beta version from CI
./scripts/deploy-agent.sh 0.4.0-beta1

# Install beta on test node
curl -sSL "https://hydra.home.lan/api/v1/agent/install?version=0.4.0-beta1" | sudo bash
```

---

## 7. Security Considerations

### 7.1 Binary Integrity

|Measure|Implementation|
|---|---|
|Checksum verification|SHA-256 hash for every binary|
|Signed binaries|(Future) GPG signing of releases|
|HTTPS only|TLS for all download endpoints|
|Version pinning|Explicit version in install commands|

### 7.2 Object Storage Access

|Concern|Mitigation|
|---|---|
|Credential exposure|Environment variables, not config files|
|Bucket access|Separate read-only credentials for API download|
|Network isolation|Internal network access to Garage|
|Audit logging|S3 access logging enabled|

### 7.3 Installation Script Safety

|Risk|Mitigation|
|---|---|
|Script injection|API generates script server-side, not user input|
|MITM attacks|HTTPS with certificate validation|
|Privilege escalation|Minimal sudo usage, documented clearly|
|Verification|Checksum validation before execution|

---

## 8. Monitoring & Observability

### 8.1 Metrics

```
# Object storage metrics
hydra_object_storage_healthy{} gauge
hydra_agent_downloads_total{target, version} counter
hydra_agent_installs_total{target, version, method} counter

# Version metrics  
hydra_agent_versions_available{target} gauge
hydra_agent_latest_version{target, version} info
```

### 8.2 Alerts

|Alert|Condition|Severity|
|---|---|---|
|ObjectStorageDown|object_storage check != "ok" for 5m|Warning|
|NoAgentBinaries|versions_available == 0 for any target|Critical|
|HighDownloadErrors|download error rate > 10%|Warning|

---

## 9. Configuration Reference

### 9.1 API Service Configuration Addition

```yaml
# config/hydra-api.yaml (additions)

object_storage:
  enabled: true
  provider: "s3"
  endpoint: "${HYDRA_S3_ENDPOINT}"
  bucket: "${HYDRA_S3_BUCKET:-hydra-bucket}"
  region: "garage"
  access_key_id: "${HYDRA_S3_ACCESS_KEY}"
  secret_access_key: "${HYDRA_S3_SECRET_KEY}"
  path_style: true
  verify_ssl: false
  
  # Lifecycle settings
  lifecycle:
    max_versions_per_target: 15
    cleanup_enabled: true
    cleanup_schedule: "0 3 * * *"  # Daily at 3 AM
  
  # Health check settings
  health_check:
    enabled: true
    timeout_seconds: 5
    required_for_healthy: false  # true = degrade if unavailable
```

### 9.2 Environment Variables

|Variable|Required|Default|Description|
|---|---|---|---|
|`HYDRA_S3_ENDPOINT`|Yes|-|Garage/S3 endpoint URL|
|`HYDRA_S3_BUCKET`|No|`hydra-bucket`|Bucket name|
|`HYDRA_S3_ACCESS_KEY`|Yes|-|S3 access key ID|
|`HYDRA_S3_SECRET_KEY`|Yes|-|S3 secret access key|
|`HYDRA_S3_REGION`|No|`garage`|S3 region (for Garage compatibility)|

---

## 10. Implementation Checklist

### Phase 1: Object Storage Foundation

- [ ] Configure Garage instance
- [ ] Create `hydra-bucket` with appropriate permissions
- [ ] Generate read/write credentials for API service
- [ ] Generate read-only credentials for download operations
- [ ] Test S3 connectivity from API service

### Phase 2: API Endpoints

- [ ] Add object storage client to hydra-api
- [ ] Update `/health` endpoint with storage check
- [ ] Implement `GET /agent/download/{target}`
- [ ] Implement `GET /agent/install`
- [ ] Add `GET /agent/versions` (optional)
- [ ] Add error handling for storage unavailability

### Phase 3: Deployment Pipeline

- [ ] Create `deploy-agent.sh` script
- [ ] Test cross-compilation for all targets
- [ ] Verify upload to object storage
- [ ] Test lifecycle cleanup (15 version retention)
- [ ] Document CI/CD integration

### Phase 4: Testing & Documentation

- [ ] Test install script on Linux x86_64
- [ ] Test install script on Linux ARM64
- [ ] Test install script on macOS
- [ ] Test version rollback scenarios
- [ ] Update API documentation
- [ ] Update installation guide

---

## 11. Future Enhancements

|Enhancement|Priority|Notes|
|---|---|---|
|GPG-signed binaries|Medium|Security improvement|
|Delta updates|Low|Reduce bandwidth for updates|
|Auto-update daemon|Medium|Push updates to nodes|
|Windows support|Low|Expand platform coverage|
|Multi-bucket support|Low|Separate buckets per environment|
|CDN integration|Low|For geographically distributed deployments|

---

_End of Technical Design Document_