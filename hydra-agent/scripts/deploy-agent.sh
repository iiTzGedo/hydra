#!/bin/bash
#
# Hydra Agent Deployment Script
# Cross-compiles agent for all targets and uploads to object storage
#
# Usage:
#   ./scripts/deploy-agent.sh <version>
#   ./scripts/deploy-agent.sh 0.3.1
#
# Environment Variables:
#   HYDRA_S3_ENDPOINT    - S3/Garage endpoint URL (required)
#   HYDRA_S3_BUCKET      - Bucket name (default: hydra-bucket)
#   HYDRA_S3_ACCESS_KEY  - S3 access key ID (required)
#   HYDRA_S3_SECRET_KEY  - S3 secret access key (required)
#   SKIP_UPLOAD          - Set to "true" to skip S3 upload (build only)
#   TARGETS              - Comma-separated list of targets to build (default: all)
#
set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }

# Configuration
VERSION="${1:-}"
S3_ENDPOINT="${HYDRA_S3_ENDPOINT:-}"
S3_BUCKET="${HYDRA_S3_BUCKET:-hydra-bucket}"
S3_ACCESS_KEY="${HYDRA_S3_ACCESS_KEY:-}"
S3_SECRET_KEY="${HYDRA_S3_SECRET_KEY:-}"
SKIP_UPLOAD="${SKIP_UPLOAD:-false}"
MAX_VERSIONS="${MAX_VERSIONS:-15}"

# Target configurations: "rust_target:hydra_target"
DEFAULT_TARGETS=(
    "x86_64-unknown-linux-gnu:linux-amd64"
    "aarch64-unknown-linux-gnu:linux-arm64"
    "armv7-unknown-linux-gnueabihf:linux-armv7"
    "x86_64-apple-darwin:darwin-amd64"
    "aarch64-apple-darwin:darwin-arm64"
    "x86_64-unknown-freebsd:freebsd-amd64"
)

# Parse custom targets if provided
if [[ -n "${TARGETS:-}" ]]; then
    IFS=',' read -ra CUSTOM_TARGETS <<< "$TARGETS"
    BUILD_TARGETS=()
    for t in "${CUSTOM_TARGETS[@]}"; do
        for dt in "${DEFAULT_TARGETS[@]}"; do
            if [[ "$dt" == *":$t" ]]; then
                BUILD_TARGETS+=("$dt")
                break
            fi
        done
    done
else
    BUILD_TARGETS=("${DEFAULT_TARGETS[@]}")
fi

# Validate arguments
validate_args() {
    if [[ -z "$VERSION" ]]; then
        echo "Usage: $0 <version>"
        echo "Example: $0 0.3.1"
        exit 1
    fi

    # Validate semver format
    if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9._-]+)?$ ]]; then
        error "Version must be semver format (e.g., 0.3.1 or 0.3.1-beta)"
        exit 1
    fi

    # Validate S3 credentials if upload is enabled
    if [[ "$SKIP_UPLOAD" != "true" ]]; then
        if [[ -z "$S3_ENDPOINT" ]]; then
            error "HYDRA_S3_ENDPOINT is required"
            exit 1
        fi
        if [[ -z "$S3_ACCESS_KEY" ]] || [[ -z "$S3_SECRET_KEY" ]]; then
            error "HYDRA_S3_ACCESS_KEY and HYDRA_S3_SECRET_KEY are required"
            exit 1
        fi
    fi
}

# Detect native target
detect_native_target() {
    local os arch
    os=$(uname -s | tr '[:upper:]' '[:lower:]')
    arch=$(uname -m)

    case "$os" in
        linux)   os="linux" ;;
        darwin)  os="darwin" ;;
        freebsd) os="freebsd" ;;
    esac

    case "$arch" in
        x86_64|amd64)  arch="amd64" ;;
        aarch64|arm64) arch="arm64" ;;
        armv7l)        arch="armv7" ;;
    esac

    echo "${os}-${arch}"
}

# Check if cross compiler is available and Docker is running
check_cross() {
    if command -v cross &> /dev/null; then
        # cross requires Docker
        if command -v docker &> /dev/null && docker info &> /dev/null; then
            echo "cross"
            return
        else
            warn "cross found but Docker not running, falling back to cargo"
        fi
    fi
    echo "cargo"
}

# Check if a target can be built
can_build_target() {
    local rust_target="$1"
    local hydra_target="$2"
    local build_cmd="$3"
    local native_target="$4"

    # Native target can always be built with cargo
    if [[ "$hydra_target" == "$native_target" ]]; then
        return 0
    fi

    # Cross-compilation requires either 'cross' or installed toolchain
    if [[ "$build_cmd" == "cross" ]]; then
        return 0
    fi

    # Check if rustup target is installed
    if rustup target list --installed 2>/dev/null | grep -q "^${rust_target}$"; then
        # Also need linker - check for common cross-linkers
        case "$rust_target" in
            *-linux-gnu*)
                if [[ -x "/usr/bin/${rust_target}-gcc" ]] || [[ -x "/usr/local/bin/${rust_target}-gcc" ]]; then
                    return 0
                fi
                ;;
            *-apple-darwin*)
                # Darwin cross-compilation requires Xcode/osxcross
                if [[ "$(uname -s)" == "Darwin" ]]; then
                    return 0
                fi
                ;;
        esac
    fi

    return 1
}

# Build for a specific target
build_target() {
    local rust_target="$1"
    local hydra_target="$2"
    local build_cmd="$3"

    info "Building for ${hydra_target} (${rust_target})..."

    # Build with release profile
    if [[ "$build_cmd" == "cross" ]]; then
        cross build --release --target "$rust_target" 2>&1 | while read -r line; do
            echo "    $line"
        done
    else
        cargo build --release --target "$rust_target" 2>&1 | while read -r line; do
            echo "    $line"
        done
    fi

    # Check if binary was created
    local binary_src="target/${rust_target}/release/hydra-agent"
    if [[ ! -f "$binary_src" ]]; then
        error "Binary not found: $binary_src"
        return 1
    fi

    # Create output directory
    local output_dir="${BUILD_DIR}/${hydra_target}"
    mkdir -p "$output_dir"

    # Copy and strip binary
    cp "$binary_src" "${output_dir}/hydra-agent"

    # Strip binary if strip is available (reduces size)
    if command -v strip &> /dev/null && [[ "$rust_target" != *"darwin"* ]]; then
        strip "${output_dir}/hydra-agent" 2>/dev/null || true
    fi

    # Generate checksum
    if command -v sha256sum &> /dev/null; then
        sha256sum "${output_dir}/hydra-agent" | awk '{print $1}' > "${output_dir}/hydra-agent.sha256"
    elif command -v shasum &> /dev/null; then
        shasum -a 256 "${output_dir}/hydra-agent" | awk '{print $1}' > "${output_dir}/hydra-agent.sha256"
    fi

    # Generate metadata
    local binary_size
    binary_size=$(stat -f%z "${output_dir}/hydra-agent" 2>/dev/null || stat -c%s "${output_dir}/hydra-agent")
    local checksum
    checksum=$(cat "${output_dir}/hydra-agent.sha256")

    cat > "${output_dir}/metadata.json" << EOF
{
    "version": "${VERSION}",
    "target": "${hydra_target}",
    "rustTarget": "${rust_target}",
    "buildTime": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "buildCommit": "$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')",
    "size": ${binary_size},
    "sha256": "${checksum}"
}
EOF

    success "Built ${hydra_target} (${binary_size} bytes)"
}

# Upload to S3/Garage
upload_to_s3() {
    if [[ "$SKIP_UPLOAD" == "true" ]]; then
        info "Skipping S3 upload (SKIP_UPLOAD=true)"
        return
    fi

    info "Uploading to S3 (${S3_ENDPOINT})..."

    # Configure AWS CLI for S3 access
    export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY"
    export AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
    export AWS_DEFAULT_REGION="garage"

    # S3 command helper
    s3cmd() {
        aws s3 --endpoint-url "$S3_ENDPOINT" "$@"
    }

    # Upload binaries for each target
    for target_pair in "${BUILD_TARGETS[@]}"; do
        local hydra_target="${target_pair##*:}"
        local output_dir="${BUILD_DIR}/${hydra_target}"

        if [[ ! -d "$output_dir" ]]; then
            warn "Skipping upload for ${hydra_target} (not built)"
            continue
        fi

        info "Uploading ${hydra_target}..."

        # Upload binary
        s3cmd cp "${output_dir}/hydra-agent" \
            "s3://${S3_BUCKET}/agents/${hydra_target}/${VERSION}/hydra-agent" \
            --quiet

        # Upload checksum
        s3cmd cp "${output_dir}/hydra-agent.sha256" \
            "s3://${S3_BUCKET}/agents/${hydra_target}/${VERSION}/hydra-agent.sha256" \
            --quiet

        # Upload metadata
        s3cmd cp "${output_dir}/metadata.json" \
            "s3://${S3_BUCKET}/agents/${hydra_target}/${VERSION}/metadata.json" \
            --quiet

        # Update latest marker
        echo "$VERSION" | s3cmd cp - "s3://${S3_BUCKET}/agents/${hydra_target}/latest" \
            --quiet

        success "Uploaded ${hydra_target}"
    done
}

# Generate version manifest
generate_manifest() {
    if [[ "$SKIP_UPLOAD" == "true" ]]; then
        return
    fi

    info "Generating version manifest..."

    export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY"
    export AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
    export AWS_DEFAULT_REGION="garage"

    # Generate manifest locally first
    cat > "${BUILD_DIR}/versions.json" << EOF
{
    "schemaVersion": 1,
    "generatedAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "latestVersion": "${VERSION}",
    "targets": {
EOF

    local first=true
    for target_pair in "${BUILD_TARGETS[@]}"; do
        local hydra_target="${target_pair##*:}"
        local output_dir="${BUILD_DIR}/${hydra_target}"

        if [[ ! -d "$output_dir" ]]; then
            continue
        fi

        local metadata
        metadata=$(cat "${output_dir}/metadata.json")
        local size sha256 build_time
        size=$(echo "$metadata" | grep -o '"size": [0-9]*' | grep -o '[0-9]*')
        sha256=$(echo "$metadata" | grep -o '"sha256": "[^"]*"' | cut -d'"' -f4)
        build_time=$(echo "$metadata" | grep -o '"buildTime": "[^"]*"' | cut -d'"' -f4)

        if [[ "$first" != "true" ]]; then
            echo "," >> "${BUILD_DIR}/versions.json"
        fi
        first=false

        cat >> "${BUILD_DIR}/versions.json" << EOF
        "${hydra_target}": {
            "latest": "${VERSION}",
            "versions": [
                {
                    "version": "${VERSION}",
                    "uploadedAt": "${build_time}",
                    "size": ${size},
                    "sha256": "${sha256}"
                }
            ]
        }
EOF
    done

    cat >> "${BUILD_DIR}/versions.json" << EOF

    }
}
EOF

    # Upload manifest
    aws s3 --endpoint-url "$S3_ENDPOINT" cp "${BUILD_DIR}/versions.json" \
        "s3://${S3_BUCKET}/manifests/versions.json" \
        --quiet

    success "Manifest uploaded"
}

# Cleanup old versions
cleanup_old_versions() {
    if [[ "$SKIP_UPLOAD" == "true" ]]; then
        return
    fi

    info "Cleaning up old versions (keeping last ${MAX_VERSIONS})..."

    export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY"
    export AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
    export AWS_DEFAULT_REGION="garage"

    for target_pair in "${BUILD_TARGETS[@]}"; do
        local hydra_target="${target_pair##*:}"

        # List versions (excluding 'latest' marker)
        local versions
        versions=$(aws s3 --endpoint-url "$S3_ENDPOINT" ls "s3://${S3_BUCKET}/agents/${hydra_target}/" 2>/dev/null | \
            awk '{print $NF}' | \
            grep -E '^[0-9]+\.[0-9]+\.[0-9]+' | \
            sort -V -r || true)

        local count=0
        for v in $versions; do
            count=$((count + 1))
            if [[ $count -gt $MAX_VERSIONS ]]; then
                info "Removing old version: ${hydra_target}/${v}"
                aws s3 --endpoint-url "$S3_ENDPOINT" rm --recursive \
                    "s3://${S3_BUCKET}/agents/${hydra_target}/${v}/" \
                    --quiet 2>/dev/null || true
            fi
        done
    done
}

# Main
main() {
    echo ""
    echo "=========================================="
    echo "   Hydra Agent Deployment v${VERSION:-?}"
    echo "=========================================="
    echo ""

    validate_args

    # Get script directory and change to agent root
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$script_dir/.."

    info "Working directory: $(pwd)"
    info "Version: ${VERSION}"
    info "Targets: ${#BUILD_TARGETS[@]}"

    # Create build directory
    BUILD_DIR="target/release-dist/${VERSION}"
    mkdir -p "$BUILD_DIR"
    info "Build output: ${BUILD_DIR}"

    # Detect native target and build tool
    local native_target
    native_target=$(detect_native_target)
    info "Native target: ${native_target}"

    local build_cmd
    build_cmd=$(check_cross)
    info "Build tool: ${build_cmd}"

    echo ""
    echo "=== Building Binaries ==="
    echo ""

    # Build each target
    local built_count=0
    local skipped_count=0
    for target_pair in "${BUILD_TARGETS[@]}"; do
        local rust_target="${target_pair%%:*}"
        local hydra_target="${target_pair##*:}"

        # Check if target can be built
        if ! can_build_target "$rust_target" "$hydra_target" "$build_cmd" "$native_target"; then
            warn "Skipping ${hydra_target} (no toolchain available, use 'cross' with Docker for cross-compilation)"
            skipped_count=$((skipped_count + 1))
            continue
        fi

        if build_target "$rust_target" "$hydra_target" "$build_cmd"; then
            built_count=$((built_count + 1))
        else
            warn "Failed to build ${hydra_target}"
        fi
    done

    if [[ $built_count -eq 0 ]]; then
        error "No targets were built successfully"
        exit 1
    fi

    echo ""
    echo "=== Uploading to Storage ==="
    echo ""

    upload_to_s3
    generate_manifest
    cleanup_old_versions

    echo ""
    echo "=========================================="
    success "   Deployment Complete!"
    echo "=========================================="
    echo ""
    info "Version:         ${VERSION}"
    info "Targets built:   ${built_count}/${#BUILD_TARGETS[@]}"
    if [[ $skipped_count -gt 0 ]]; then
        warn "Targets skipped: ${skipped_count} (missing toolchain)"
    fi
    info "Build output:    ${BUILD_DIR}"
    if [[ "$SKIP_UPLOAD" != "true" ]]; then
        info "S3 bucket:       ${S3_BUCKET}"
        info "S3 path:         agents/{target}/${VERSION}/hydra-agent"
    fi
    echo ""
    info "Install command:"
    echo "  curl -sSL https://hydra.local/api/v1/install | bash"
    echo ""
    if [[ $skipped_count -gt 0 ]]; then
        echo ""
        info "To build all targets, install 'cross' and run Docker:"
        echo "  cargo install cross"
        echo "  docker start"
        echo ""
    fi
}

main "$@"
