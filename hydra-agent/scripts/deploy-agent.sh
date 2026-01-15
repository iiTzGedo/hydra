#!/bin/bash
#
# Hydra Agent Deployment Script
# Cross-compiles agent for all targets and/or creates source bundles
# Uploads to object storage or local directory
#
# Usage:
#   ./scripts/deploy-agent.sh <version> [options]
#   ./scripts/deploy-agent.sh 0.3.1
#   ./scripts/deploy-agent.sh 0.3.1 --bundle
#   ./scripts/deploy-agent.sh 0.3.1 --bundle --output-dir /var/lib/hydra/bundles
#   ./scripts/deploy-agent.sh 0.3.1 --both
#
# Environment Variables:
#   HYDRA_S3_ENDPOINT    - S3/Garage endpoint URL (required for S3 upload)
#   HYDRA_S3_BUCKET      - Bucket name (default: hydra-bucket)
#   HYDRA_S3_ACCESS_KEY  - S3 access key ID (required for S3 upload)
#   HYDRA_S3_SECRET_KEY  - S3 secret access key (required for S3 upload)
#   SKIP_UPLOAD          - Set to "true" to skip S3 upload (build only)
#   TARGETS              - Comma-separated list of targets to build (default: all)
#
# Options:
#   --bundle             Create source bundle instead of compiling binaries
#   --output-dir <DIR>   Output to local directory instead of S3
#   --both               Create both binaries and source bundle
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
VERSION=""
S3_ENDPOINT="${HYDRA_S3_ENDPOINT:-}"
S3_BUCKET="${HYDRA_S3_BUCKET:-hydra-bucket}"
S3_ACCESS_KEY="${HYDRA_S3_ACCESS_KEY:-}"
S3_SECRET_KEY="${HYDRA_S3_SECRET_KEY:-}"
SKIP_UPLOAD="${SKIP_UPLOAD:-false}"
MAX_VERSIONS="${MAX_VERSIONS:-15}"

# Mode flags
MODE_BUNDLE=false
MODE_BINARY=true
OUTPUT_DIR=""

# Target configurations: "rust_target:hydra_target"
DEFAULT_TARGETS=(
    "x86_64-unknown-linux-gnu:linux-amd64"
    "aarch64-unknown-linux-gnu:linux-arm64"
    "armv7-unknown-linux-gnueabihf:linux-armv7"
    "x86_64-apple-darwin:darwin-amd64"
    "aarch64-apple-darwin:darwin-arm64"
    "x86_64-unknown-freebsd:freebsd-amd64"
    "x86_64-pc-windows-gnu:windows-amd64"
)

# Parse arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --bundle)
                MODE_BUNDLE=true
                MODE_BINARY=false
                shift
                ;;
            --both)
                MODE_BUNDLE=true
                MODE_BINARY=true
                shift
                ;;
            --output-dir)
                OUTPUT_DIR="$2"
                SKIP_UPLOAD=true
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            -*)
                error "Unknown option: $1"
                show_help
                exit 1
                ;;
            *)
                if [[ -z "$VERSION" ]]; then
                    VERSION="$1"
                else
                    error "Unexpected argument: $1"
                    exit 1
                fi
                shift
                ;;
        esac
    done
}

show_help() {
    cat << EOF
Hydra Agent Deployment Script

Usage: $0 <version> [options]

Arguments:
  version              Version number (semver format, e.g., 0.3.1)

Options:
  --bundle             Create source bundle instead of compiling binaries
  --both               Create both binaries and source bundle
  --output-dir <DIR>   Output to local directory instead of S3
  -h, --help           Show this help message

Examples:
  $0 0.3.1                           # Build binaries, upload to S3
  $0 0.3.1 --bundle                  # Create source bundle, upload to S3
  $0 0.3.1 --both                    # Create both binaries and bundle
  $0 0.3.1 --bundle --output-dir /var/lib/hydra/bundles  # Local bundle

Environment Variables:
  HYDRA_S3_ENDPOINT    S3/Garage endpoint URL
  HYDRA_S3_BUCKET      Bucket name (default: hydra-bucket)
  HYDRA_S3_ACCESS_KEY  S3 access key ID
  HYDRA_S3_SECRET_KEY  S3 secret access key
  SKIP_UPLOAD          Set to "true" to skip S3 upload
  TARGETS              Comma-separated list of targets
EOF
}

# Parse custom targets if provided
setup_targets() {
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
}

# Validate arguments
validate_args() {
    if [[ -z "$VERSION" ]]; then
        error "Version is required"
        show_help
        exit 1
    fi

    # Validate semver format
    if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9._-]+)?$ ]]; then
        error "Version must be semver format (e.g., 0.3.1 or 0.3.1-beta)"
        exit 1
    fi

    # Validate S3 credentials if upload is enabled
    if [[ "$SKIP_UPLOAD" != "true" ]] && [[ -z "$OUTPUT_DIR" ]]; then
        if [[ -z "$S3_ENDPOINT" ]]; then
            error "HYDRA_S3_ENDPOINT is required (or use --output-dir for local)"
            exit 1
        fi
        if [[ -z "$S3_ACCESS_KEY" ]] || [[ -z "$S3_SECRET_KEY" ]]; then
            error "HYDRA_S3_ACCESS_KEY and HYDRA_S3_SECRET_KEY are required"
            exit 1
        fi
    fi

    # If output-dir is specified, create it
    if [[ -n "$OUTPUT_DIR" ]]; then
        mkdir -p "$OUTPUT_DIR"
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

    # Determine binary name (Windows has .exe extension)
    local binary_name="hydra-agent"
    local output_binary_name="hydra-agent"
    if [[ "$rust_target" == *"windows"* ]]; then
        binary_name="hydra-agent.exe"
        output_binary_name="hydra-agent.exe"
    fi

    # Check if binary was created
    local binary_src="target/${rust_target}/release/${binary_name}"
    if [[ ! -f "$binary_src" ]]; then
        error "Binary not found: $binary_src"
        return 1
    fi

    # Create output directory
    local output_dir="${BUILD_DIR}/${hydra_target}"
    mkdir -p "$output_dir"

    # Copy and strip binary
    cp "$binary_src" "${output_dir}/${output_binary_name}"

    # Strip binary if strip is available (reduces size) - not for Windows or Darwin
    if command -v strip &> /dev/null && [[ "$rust_target" != *"darwin"* ]] && [[ "$rust_target" != *"windows"* ]]; then
        strip "${output_dir}/${output_binary_name}" 2>/dev/null || true
    fi

    # Generate checksum
    if command -v sha256sum &> /dev/null; then
        sha256sum "${output_dir}/${output_binary_name}" | awk '{print $1}' > "${output_dir}/${output_binary_name}.sha256"
    elif command -v shasum &> /dev/null; then
        shasum -a 256 "${output_dir}/${output_binary_name}" | awk '{print $1}' > "${output_dir}/${output_binary_name}.sha256"
    fi

    # Generate metadata
    local binary_size
    binary_size=$(stat -f%z "${output_dir}/${output_binary_name}" 2>/dev/null || stat -c%s "${output_dir}/${output_binary_name}")
    local checksum
    checksum=$(cat "${output_dir}/${output_binary_name}.sha256")

    cat > "${output_dir}/metadata.json" << EOF
{
    "version": "${VERSION}",
    "target": "${hydra_target}",
    "rustTarget": "${rust_target}",
    "binaryName": "${output_binary_name}",
    "buildTime": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "buildCommit": "$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')",
    "size": ${binary_size},
    "sha256": "${checksum}"
}
EOF

    success "Built ${hydra_target} (${binary_size} bytes)"
}

# Create source bundle
create_bundle() {
    info "Creating source bundle..."

    local bundle_dir="${BUILD_DIR}/bundle"
    local bundle_name="hydra-agent-${VERSION}"
    local bundle_path="${bundle_dir}/${bundle_name}"

    mkdir -p "$bundle_path"

    # Copy source files
    info "Copying source files..."
    cp -r src "$bundle_path/"
    cp Cargo.toml "$bundle_path/"
    cp Cargo.lock "$bundle_path/" 2>/dev/null || warn "Cargo.lock not found"

    # Copy scripts
    info "Copying scripts..."
    mkdir -p "$bundle_path/scripts"
    cp scripts/install.sh "$bundle_path/scripts/" 2>/dev/null || create_install_script "$bundle_path/scripts/install.sh"

    # Create config template
    info "Creating config template..."
    cat > "$bundle_path/agent.example.toml" << 'EOF'
# Hydra Agent Configuration
# Copy this file to /etc/hydra/agent.toml and edit

[node]
node_id = "CHANGE_ME"
class = "compute"           # compute, networking, iot
node_type = "physical"      # physical, logical
# kind = "bare-metal"       # bare-metal, vm, lxc, docker, k8s-pod
# display_name = "My Server"
# tags = ["production"]

[api]
url = "https://hydra.local/api/v1"
timeout_seconds = 30
retries = 3

[collection]
level = "neutral"           # minimal, neutral, full
include_packages = true
include_users = true

[schedule]
enabled = true
interval_seconds = 21600    # 6 hours
on_startup = true
EOF

    # Create README
    info "Creating README..."
    cat > "$bundle_path/README.md" << EOF
# Hydra Agent v${VERSION}

## Quick Start

1. **Build the agent:**
   \`\`\`bash
   cd ${bundle_name}
   cargo build --release
   \`\`\`

2. **Install:**
   \`\`\`bash
   sudo cp target/release/hydra-agent /usr/local/bin/
   sudo cp agent.example.toml /etc/hydra/agent.toml
   \`\`\`

3. **Configure:**
   Edit \`/etc/hydra/agent.toml\` with your settings.

4. **Register:**
   \`\`\`bash
   hydra-agent login -u admin
   hydra-agent register
   hydra-agent node register
   \`\`\`

5. **Start:**
   \`\`\`bash
   sudo hydra-agent service activate
   \`\`\`

## Alternative: Use install script

\`\`\`bash
./scripts/install.sh -v ${VERSION}
\`\`\`

For full documentation, visit: https://github.com/yourorg/hydra
EOF

    # Create bundle metadata
    cat > "$bundle_path/bundle-metadata.json" << EOF
{
    "version": "${VERSION}",
    "bundleTime": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "buildCommit": "$(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')",
    "type": "source"
}
EOF

    # Create zip archive
    info "Creating zip archive..."
    local zip_file="${bundle_dir}/${bundle_name}.zip"
    (cd "$bundle_dir" && zip -rq "${bundle_name}.zip" "${bundle_name}")

    # Generate checksum for bundle
    if command -v sha256sum &> /dev/null; then
        sha256sum "$zip_file" | awk '{print $1}' > "${zip_file}.sha256"
    elif command -v shasum &> /dev/null; then
        shasum -a 256 "$zip_file" | awk '{print $1}' > "${zip_file}.sha256"
    fi

    local bundle_size
    bundle_size=$(stat -f%z "$zip_file" 2>/dev/null || stat -c%s "$zip_file")

    success "Bundle created: ${bundle_name}.zip (${bundle_size} bytes)"

    # Store bundle info for later upload
    BUNDLE_ZIP="${zip_file}"
    BUNDLE_SHA="${zip_file}.sha256"
}

# Create install script if it doesn't exist
create_install_script() {
    local script_path="$1"
    cat > "$script_path" << 'INSTALL_SCRIPT'
#!/bin/bash
#
# Hydra Agent Install Script
# Builds and installs the agent from source
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

# Default values
VERSION=""
INSTALL_DIR="/usr/local/bin"
CONFIG_DIR="/etc/hydra"
VAULT_DIR="/var/cv/hydra"
CREATE_ALIAS=false
ADD_TO_PATH=false
REGISTER_TOKEN=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -v|--version)     VERSION="$2"; shift 2 ;;
        -d|--install-dir) INSTALL_DIR="$2"; shift 2 ;;
        -c|--config)      CONFIG_DIR="$2"; shift 2 ;;
        -a|--aliased)     CREATE_ALIAS=true; shift ;;
        -g|--global)      ADD_TO_PATH=true; shift ;;
        -r|--register)    REGISTER_TOKEN="$2"; shift 2 ;;
        -h|--help)
            cat << EOF
Hydra Agent Install Script

Usage: $0 [options]

Options:
  -v, --version <VER>     Version number (required)
  -d, --install-dir <DIR> Installation directory [default: /usr/local/bin]
  -c, --config <PATH>     Config directory [default: /etc/hydra]
  -a, --aliased           Create 'hydra' alias
  -g, --global            Add to PATH globally
  -r, --register <TOKEN>  Auto-register with token
  -h, --help              Show this help
EOF
            exit 0
            ;;
        *) error "Unknown option: $1"; exit 1 ;;
    esac
done

# Detect system
detect_system() {
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)

    case "$ARCH" in
        x86_64|amd64) ARCH="amd64" ;;
        aarch64|arm64) ARCH="arm64" ;;
        armv7l) ARCH="armv7" ;;
    esac

    info "Detected: ${OS}-${ARCH}"
}

# Check Rust toolchain
check_rust() {
    if ! command -v cargo &> /dev/null; then
        warn "Rust not found. Installing..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        source "$HOME/.cargo/env"
    fi
    info "Rust version: $(rustc --version)"
}

# Build the agent
build_agent() {
    info "Building hydra-agent..."
    cargo build --release

    if [[ ! -f "target/release/hydra-agent" ]]; then
        error "Build failed - binary not found"
        exit 1
    fi
    success "Build complete"
}

# Install the agent
install_agent() {
    info "Installing to ${INSTALL_DIR}..."

    sudo mkdir -p "$INSTALL_DIR"
    sudo cp target/release/hydra-agent "${INSTALL_DIR}/hydra-agent"
    sudo chmod 755 "${INSTALL_DIR}/hydra-agent"

    if [[ "$CREATE_ALIAS" == "true" ]]; then
        sudo ln -sf "${INSTALL_DIR}/hydra-agent" "${INSTALL_DIR}/hydra"
        info "Created alias: hydra -> hydra-agent"
    fi

    success "Installed to ${INSTALL_DIR}/hydra-agent"
}

# Setup directories
setup_directories() {
    info "Setting up directories..."

    sudo mkdir -p "$CONFIG_DIR"
    sudo mkdir -p "$VAULT_DIR"
    sudo chmod 700 "$VAULT_DIR"

    if [[ ! -f "${CONFIG_DIR}/agent.toml" ]] && [[ -f "agent.example.toml" ]]; then
        sudo cp agent.example.toml "${CONFIG_DIR}/agent.toml"
        info "Created config at ${CONFIG_DIR}/agent.toml"
    fi
}

# Main
main() {
    echo ""
    echo "==================================="
    echo "  Hydra Agent Installer"
    echo "==================================="
    echo ""

    detect_system
    check_rust
    build_agent
    install_agent
    setup_directories

    if [[ -n "$REGISTER_TOKEN" ]]; then
        info "Registering with token..."
        "${INSTALL_DIR}/hydra-agent" register --token "$REGISTER_TOKEN"
    fi

    echo ""
    success "Installation complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Edit config: ${CONFIG_DIR}/agent.toml"
    echo "  2. Login: hydra-agent login -u <username>"
    echo "  3. Register: hydra-agent register"
    echo "  4. Register node: hydra-agent node register"
    echo "  5. Activate: sudo hydra-agent service activate"
    echo ""
}

main "$@"
INSTALL_SCRIPT
    chmod +x "$script_path"
}

# Upload binaries to S3/Garage
upload_binaries_to_s3() {
    if [[ "$SKIP_UPLOAD" == "true" ]]; then
        info "Skipping S3 upload (SKIP_UPLOAD=true)"
        return
    fi

    info "Uploading binaries to S3 (${S3_ENDPOINT})..."

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
        local rust_target="${target_pair%%:*}"
        local hydra_target="${target_pair##*:}"
        local output_dir="${BUILD_DIR}/${hydra_target}"

        if [[ ! -d "$output_dir" ]]; then
            warn "Skipping upload for ${hydra_target} (not built)"
            continue
        fi

        # Determine binary name (Windows has .exe extension)
        local binary_name="hydra-agent"
        if [[ "$rust_target" == *"windows"* ]]; then
            binary_name="hydra-agent.exe"
        fi

        info "Uploading ${hydra_target}..."

        # Upload binary
        s3cmd cp "${output_dir}/${binary_name}" \
            "s3://${S3_BUCKET}/agents/${hydra_target}/${VERSION}/${binary_name}" \
            --quiet

        # Upload checksum
        s3cmd cp "${output_dir}/${binary_name}.sha256" \
            "s3://${S3_BUCKET}/agents/${hydra_target}/${VERSION}/${binary_name}.sha256" \
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

# Upload bundle to S3/Garage
upload_bundle_to_s3() {
    if [[ "$SKIP_UPLOAD" == "true" ]]; then
        info "Skipping S3 bundle upload (SKIP_UPLOAD=true)"
        return
    fi

    if [[ -z "${BUNDLE_ZIP:-}" ]]; then
        warn "No bundle to upload"
        return
    fi

    info "Uploading bundle to S3 (${S3_ENDPOINT})..."

    export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY"
    export AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
    export AWS_DEFAULT_REGION="garage"

    # Upload bundle
    aws s3 --endpoint-url "$S3_ENDPOINT" cp "$BUNDLE_ZIP" \
        "s3://${S3_BUCKET}/bundles/${VERSION}/hydra-agent-${VERSION}.zip" \
        --quiet

    # Upload checksum
    aws s3 --endpoint-url "$S3_ENDPOINT" cp "$BUNDLE_SHA" \
        "s3://${S3_BUCKET}/bundles/${VERSION}/hydra-agent-${VERSION}.zip.sha256" \
        --quiet

    # Update latest marker
    echo "$VERSION" | aws s3 --endpoint-url "$S3_ENDPOINT" cp - \
        "s3://${S3_BUCKET}/bundles/latest" \
        --quiet

    success "Bundle uploaded to bundles/${VERSION}/"
}

# Copy bundle to local directory
copy_bundle_to_local() {
    if [[ -z "$OUTPUT_DIR" ]]; then
        return
    fi

    if [[ -z "${BUNDLE_ZIP:-}" ]]; then
        warn "No bundle to copy"
        return
    fi

    info "Copying bundle to ${OUTPUT_DIR}..."

    mkdir -p "${OUTPUT_DIR}/${VERSION}"
    cp "$BUNDLE_ZIP" "${OUTPUT_DIR}/${VERSION}/"
    cp "$BUNDLE_SHA" "${OUTPUT_DIR}/${VERSION}/"

    # Update latest symlink
    ln -sf "${VERSION}" "${OUTPUT_DIR}/latest"

    success "Bundle copied to ${OUTPUT_DIR}/${VERSION}/"
}

# Copy binaries to local directory
copy_binaries_to_local() {
    if [[ -z "$OUTPUT_DIR" ]]; then
        return
    fi

    info "Copying binaries to ${OUTPUT_DIR}..."

    for target_pair in "${BUILD_TARGETS[@]}"; do
        local rust_target="${target_pair%%:*}"
        local hydra_target="${target_pair##*:}"
        local source_dir="${BUILD_DIR}/${hydra_target}"

        if [[ ! -d "$source_dir" ]]; then
            continue
        fi

        # Determine binary name (Windows has .exe extension)
        local binary_name="hydra-agent"
        if [[ "$rust_target" == *"windows"* ]]; then
            binary_name="hydra-agent.exe"
        fi

        local target_dir="${OUTPUT_DIR}/agents/${hydra_target}/${VERSION}"
        mkdir -p "$target_dir"
        cp "${source_dir}/${binary_name}" "$target_dir/"
        cp "${source_dir}/${binary_name}.sha256" "$target_dir/"
        cp "${source_dir}/metadata.json" "$target_dir/"

        # Update latest marker
        echo "$VERSION" > "${OUTPUT_DIR}/agents/${hydra_target}/latest"

        info "Copied ${hydra_target}"
    done

    success "Binaries copied to ${OUTPUT_DIR}/agents/"
}

# Generate version manifest
generate_manifest() {
    if [[ "$SKIP_UPLOAD" == "true" ]] && [[ -z "$OUTPUT_DIR" ]]; then
        return
    fi

    info "Generating version manifest..."

    # Generate manifest locally first
    cat > "${BUILD_DIR}/versions.json" << EOF
{
    "schemaVersion": 1,
    "generatedAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "latestVersion": "${VERSION}",
    "bundleAvailable": ${MODE_BUNDLE},
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

    # Upload or copy manifest
    if [[ -n "$OUTPUT_DIR" ]]; then
        mkdir -p "${OUTPUT_DIR}/manifests"
        cp "${BUILD_DIR}/versions.json" "${OUTPUT_DIR}/manifests/"
    elif [[ "$SKIP_UPLOAD" != "true" ]]; then
        export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY"
        export AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
        export AWS_DEFAULT_REGION="garage"

        aws s3 --endpoint-url "$S3_ENDPOINT" cp "${BUILD_DIR}/versions.json" \
            "s3://${S3_BUCKET}/manifests/versions.json" \
            --quiet
    fi

    success "Manifest generated"
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
    parse_args "$@"

    echo ""
    echo "=========================================="
    echo "   Hydra Agent Deployment v${VERSION:-?}"
    echo "=========================================="
    echo ""

    validate_args
    setup_targets

    # Get script directory and change to agent root
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$script_dir/.."

    info "Working directory: $(pwd)"
    info "Version: ${VERSION}"
    info "Mode: $( [[ "$MODE_BUNDLE" == "true" ]] && echo "Bundle" || echo "" )$( [[ "$MODE_BINARY" == "true" ]] && [[ "$MODE_BUNDLE" == "true" ]] && echo " + " || echo "" )$( [[ "$MODE_BINARY" == "true" ]] && echo "Binary" || echo "" )"
    if [[ -n "$OUTPUT_DIR" ]]; then
        info "Output: ${OUTPUT_DIR}"
    else
        info "Upload: S3 (${S3_BUCKET})"
    fi

    # Create build directory
    BUILD_DIR="target/release-dist/${VERSION}"
    mkdir -p "$BUILD_DIR"
    info "Build output: ${BUILD_DIR}"

    # Build binaries if requested
    if [[ "$MODE_BINARY" == "true" ]]; then
        local native_target
        native_target=$(detect_native_target)
        info "Native target: ${native_target}"

        local build_cmd
        build_cmd=$(check_cross)
        info "Build tool: ${build_cmd}"

        echo ""
        echo "=== Building Binaries ==="
        echo ""

        local built_count=0
        local skipped_count=0
        for target_pair in "${BUILD_TARGETS[@]}"; do
            local rust_target="${target_pair%%:*}"
            local hydra_target="${target_pair##*:}"

            if ! can_build_target "$rust_target" "$hydra_target" "$build_cmd" "$native_target"; then
                warn "Skipping ${hydra_target} (no toolchain available)"
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
    fi

    # Create bundle if requested
    if [[ "$MODE_BUNDLE" == "true" ]]; then
        echo ""
        echo "=== Creating Source Bundle ==="
        echo ""

        create_bundle
    fi

    echo ""
    echo "=== Deploying Artifacts ==="
    echo ""

    # Upload/copy based on destination
    if [[ -n "$OUTPUT_DIR" ]]; then
        [[ "$MODE_BINARY" == "true" ]] && copy_binaries_to_local
        [[ "$MODE_BUNDLE" == "true" ]] && copy_bundle_to_local
    else
        [[ "$MODE_BINARY" == "true" ]] && upload_binaries_to_s3
        [[ "$MODE_BUNDLE" == "true" ]] && upload_bundle_to_s3
    fi

    generate_manifest
    [[ "$MODE_BINARY" == "true" ]] && cleanup_old_versions

    echo ""
    echo "=========================================="
    success "   Deployment Complete!"
    echo "=========================================="
    echo ""
    info "Version: ${VERSION}"
    info "Build output: ${BUILD_DIR}"
    if [[ -n "$OUTPUT_DIR" ]]; then
        info "Local output: ${OUTPUT_DIR}"
    else
        info "S3 bucket: ${S3_BUCKET}"
    fi
    echo ""
    info "Install commands:"
    echo "  # Binary install (default):"
    echo "  curl -sSL https://hydra.local/api/v1/install | bash"
    echo ""
    if [[ "$MODE_BUNDLE" == "true" ]]; then
        echo "  # Source bundle install:"
        echo "  curl -sSL https://hydra.local/api/v1/install?source=obs | bash"
    fi
    echo ""
}

main "$@"
