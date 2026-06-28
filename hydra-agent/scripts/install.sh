#!/bin/bash
#
# Hydra Agent Install Script
# Builds and installs the agent from source bundle
#
# Usage:
#   ./install.sh [options]
#   ./install.sh -v 0.3.1
#   ./install.sh -v 0.3.1 -a -g
#   ./install.sh -v 0.3.1 -r <token>
#
# Options:
#   -v, --version <VER>     Version number for binary manifest (required)
#   -h, --help              Show help
#   -a, --aliased           Create 'hydra' alias
#   -g, --global            Add to PATH globally
#   -d, --install-dir <DIR> Installation directory [default: /usr/local/bin]
#   -c, --config <PATH>     Config file path [default: /etc/hydra/agent.toml]
#   -r, --register <TOKEN>  Auto-register with token after install
#

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
step()    { echo -e "${CYAN}[STEP]${NC} $*"; }

# Resolve agent root (parent of scripts/) and load .env without overriding
# variables already present in the environment. A no-op under `curl | bash`
# (no repo .env on the target node); picks up hydra-agent/.env when run locally.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo .)"
AGENT_ROOT="$(cd "${SCRIPT_DIR}/.." 2>/dev/null && pwd || echo .)"

load_env() {
    local env_file="${HYDRA_AGENT_ENV_FILE:-${AGENT_ROOT}/.env}"
    [[ -f "$env_file" ]] || return 0
    info "Loading environment from ${env_file}"
    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line#"${line%%[![:space:]]*}"}"          # ltrim
        [[ -z "$line" || "$line" == \#* ]] && continue    # skip blank/comment
        line="${line#export }"                            # allow 'export KEY=…'
        [[ "$line" != *=* ]] && continue
        local key="${line%%=*}" value="${line#*=}"
        key="${key%%[[:space:]]*}"                        # trim key
        value="${value%\"}"; value="${value#\"}"          # strip quotes
        value="${value%\'}"; value="${value#\'}"
        [[ -z "${!key:-}" ]] && export "${key}=${value}"  # set only if unset
    done < "$env_file"
}
load_env

# Default values
VERSION=""
INSTALL_DIR="/usr/local/bin"
CONFIG_DIR="/etc/hydra"
CONFIG_FILE="/etc/hydra/agent.toml"
VAULT_DIR="/var/cv/hydra"
CREATE_ALIAS=false
ADD_TO_PATH=false
REGISTER_TOKEN=""
API_URL="${HYDRA_API_URL:-}"

# System detection results
OS=""
ARCH=""
DISTRO=""

# Parse arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -v|--version)
                VERSION="$2"
                shift 2
                ;;
            -d|--install-dir)
                INSTALL_DIR="$2"
                shift 2
                ;;
            -c|--config)
                CONFIG_FILE="$2"
                CONFIG_DIR=$(dirname "$CONFIG_FILE")
                shift 2
                ;;
            -a|--aliased)
                CREATE_ALIAS=true
                shift
                ;;
            -g|--global)
                ADD_TO_PATH=true
                shift
                ;;
            -r|--register)
                REGISTER_TOKEN="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat << EOF
Hydra Agent Install Script

Builds and installs the hydra-agent from a source bundle.

Usage: $0 [options]

Options:
  -v, --version <VER>     Version number for binary manifest (required)
  -d, --install-dir <DIR> Installation directory [default: /usr/local/bin]
  -c, --config <PATH>     Config file path [default: /etc/hydra/agent.toml]
  -a, --aliased           Create 'hydra' alias symlink
  -g, --global            Add install directory to PATH globally
  -r, --register <TOKEN>  Auto-register with provided token after install
  -h, --help              Show this help message
Environment:
  HYDRA_API_URL           Override API URL in generated config

Examples:
  $0 -v 0.3.1                        # Basic install
  $0 -v 0.3.1 -a -g                  # Install with alias and PATH update
  $0 -v 0.3.1 -r reg_abc123          # Install and register with token
  $0 -v 0.3.1 -d /opt/hydra/bin      # Custom install directory

Prerequisites:
  - Rust toolchain (will be installed if missing)
  - Build essentials (gcc, make)
  - Network access (for Rust installation if needed)

For more information, visit: https://github.com/yourorg/hydra
EOF
}

# Detect operating system and architecture
detect_system() {
    step "Detecting system..."

    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)

    # Normalize architecture
    case "$ARCH" in
        x86_64|amd64)
            ARCH="amd64"
            ;;
        aarch64|arm64)
            ARCH="arm64"
            ;;
        armv7l|armv7)
            ARCH="armv7"
            ;;
        *)
            warn "Unknown architecture: $ARCH"
            ;;
    esac

    # Detect Linux distribution
    if [[ "$OS" == "linux" ]]; then
        if [[ -f /etc/os-release ]]; then
            DISTRO=$(grep -oP '(?<=^ID=).+' /etc/os-release | tr -d '"')
        elif [[ -f /etc/lsb-release ]]; then
            DISTRO=$(grep -oP '(?<=^DISTRIB_ID=).+' /etc/lsb-release | tr '[:upper:]' '[:lower:]')
        elif [[ -f /etc/debian_version ]]; then
            DISTRO="debian"
        elif [[ -f /etc/redhat-release ]]; then
            DISTRO="rhel"
        else
            DISTRO="unknown"
        fi
    fi

    info "Operating System: ${OS}"
    info "Architecture: ${ARCH}"
    if [[ -n "$DISTRO" ]]; then
        info "Distribution: ${DISTRO}"
    fi

    # Validate supported platform
    case "${OS}-${ARCH}" in
        linux-amd64|linux-arm64|linux-armv7|darwin-amd64|darwin-arm64|freebsd-amd64)
            success "Platform supported: ${OS}-${ARCH}"
            ;;
        *)
            error "Unsupported platform: ${OS}-${ARCH}"
            error "Supported platforms: linux-amd64, linux-arm64, linux-armv7, darwin-amd64, darwin-arm64, freebsd-amd64"
            exit 1
            ;;
    esac
}

# Check and install build dependencies
check_dependencies() {
    step "Checking dependencies..."

    local missing_deps=()

    # Check for essential build tools
    if ! command -v gcc &> /dev/null; then
        missing_deps+=("gcc")
    fi

    if ! command -v make &> /dev/null; then
        missing_deps+=("make")
    fi

    # Install missing dependencies based on distro
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        warn "Missing dependencies: ${missing_deps[*]}"

        if [[ "$OS" == "linux" ]]; then
            case "$DISTRO" in
                ubuntu|debian|pop|mint|elementary)
                    info "Installing build essentials via apt..."
                    sudo apt-get update -qq
                    sudo apt-get install -y -qq build-essential
                    ;;
                fedora|rhel|centos|rocky|alma)
                    info "Installing development tools via dnf/yum..."
                    if command -v dnf &> /dev/null; then
                        sudo dnf groupinstall -y "Development Tools"
                    else
                        sudo yum groupinstall -y "Development Tools"
                    fi
                    ;;
                arch|manjaro|endeavouros)
                    info "Installing base-devel via pacman..."
                    sudo pacman -Sy --noconfirm base-devel
                    ;;
                alpine)
                    info "Installing build-base via apk..."
                    sudo apk add build-base
                    ;;
                *)
                    error "Please install build essentials manually: ${missing_deps[*]}"
                    exit 1
                    ;;
            esac
        elif [[ "$OS" == "darwin" ]]; then
            info "Installing Xcode command line tools..."
            xcode-select --install 2>/dev/null || true
        fi
    fi

    success "Dependencies satisfied"
}

# Check and install Rust toolchain
check_rust() {
    step "Checking Rust toolchain..."

    if command -v rustup &> /dev/null; then
        info "Rustup found"

        # Update to latest stable
        info "Updating to latest stable Rust..."
        rustup update stable --quiet

        # Ensure required components
        rustup component add --quiet rustfmt clippy 2>/dev/null || true
    elif command -v cargo &> /dev/null; then
        info "Cargo found (system installation)"
    else
        warn "Rust not found. Installing via rustup..."

        # Install rustup
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable

        # Source the environment
        if [[ -f "$HOME/.cargo/env" ]]; then
            source "$HOME/.cargo/env"
        fi

        if ! command -v cargo &> /dev/null; then
            error "Rust installation failed"
            exit 1
        fi
    fi

    info "Rust version: $(rustc --version)"
    info "Cargo version: $(cargo --version)"
    success "Rust toolchain ready"
}

# Build the agent
build_agent() {
    step "Building hydra-agent..."

    # Set up build environment
    export CARGO_TERM_COLOR=always

    # Build with release profile
    info "Running cargo build --release..."
    if cargo build --release; then
        success "Build completed successfully"
    else
        error "Build failed"
        exit 1
    fi

    # Verify binary exists
    if [[ ! -f "target/release/hydra-agent" ]]; then
        error "Binary not found at target/release/hydra-agent"
        exit 1
    fi

    # Show binary info
    local binary_size
    binary_size=$(stat -f%z "target/release/hydra-agent" 2>/dev/null || stat -c%s "target/release/hydra-agent")
    info "Binary size: $((binary_size / 1024 / 1024))MB"
}

# Install the binary
install_binary() {
    step "Installing binary..."

    # Create install directory
    if [[ ! -d "$INSTALL_DIR" ]]; then
        info "Creating directory: $INSTALL_DIR"
        sudo mkdir -p "$INSTALL_DIR"
    fi

    # Copy binary
    info "Installing to: ${INSTALL_DIR}/hydra-agent"
    sudo cp target/release/hydra-agent "${INSTALL_DIR}/hydra-agent"
    sudo chmod 755 "${INSTALL_DIR}/hydra-agent"

    # Create alias symlink
    if [[ "$CREATE_ALIAS" == "true" ]]; then
        info "Creating alias: hydra -> hydra-agent"
        sudo ln -sf "${INSTALL_DIR}/hydra-agent" "${INSTALL_DIR}/hydra"
    fi

    # Verify installation
    if [[ -x "${INSTALL_DIR}/hydra-agent" ]]; then
        success "Binary installed successfully"
    else
        error "Binary installation failed"
        exit 1
    fi

    # Show version
    "${INSTALL_DIR}/hydra-agent" --version 2>/dev/null || true
}

# Setup directories
setup_directories() {
    step "Setting up directories..."

    # Create config directory
    if [[ ! -d "$CONFIG_DIR" ]]; then
        info "Creating config directory: $CONFIG_DIR"
        sudo mkdir -p "$CONFIG_DIR"
    fi

    # Create vault directory with restricted permissions
    if [[ ! -d "$VAULT_DIR" ]]; then
        info "Creating vault directory: $VAULT_DIR"
        sudo mkdir -p "$VAULT_DIR"
        sudo chmod 700 "$VAULT_DIR"
    fi

    # Create log directory
    local log_dir="/var/log/hydra"
    if [[ ! -d "$log_dir" ]]; then
        info "Creating log directory: $log_dir"
        sudo mkdir -p "$log_dir"
    fi

    success "Directories created"
}

# Setup configuration
setup_config() {
    step "Setting up configuration..."

    if [[ -f "$CONFIG_FILE" ]]; then
        info "Configuration already exists at: $CONFIG_FILE"
        return
    fi

    # Look for example config
    local example_config=""
    if [[ -f "agent.example.toml" ]]; then
        example_config="agent.example.toml"
    elif [[ -f "config/agent.example.toml" ]]; then
        example_config="config/agent.example.toml"
    fi

    if [[ -n "$example_config" ]]; then
        info "Copying example config to: $CONFIG_FILE"
        sudo cp "$example_config" "$CONFIG_FILE"
        apply_api_url
        success "Configuration created"
        warn "Please edit $CONFIG_FILE before starting the agent"
    else
        # Create minimal config
        info "Creating minimal configuration..."
        sudo tee "$CONFIG_FILE" > /dev/null << 'EOF'
# Hydra Agent Configuration
# Edit this file with your settings

[node]
node_id = "CHANGE_ME"           # Unique node identifier
class = "compute"               # compute, networking, iot
node_type = "physical"          # physical, logical

[api]
url = "https://hydra.local/api/v1"
timeout_seconds = 30
retries = 3

[collection]
level = "neutral"               # minimal, neutral, full
include_packages = true
include_users = true

[schedule]
enabled = true
interval_seconds = 21600        # 6 hours
on_startup = true
EOF
        apply_api_url
        success "Minimal configuration created"
        warn "Please edit $CONFIG_FILE with your settings"
    fi
}

apply_api_url() {
    if [[ -z "$API_URL" ]]; then
        return
    fi

    if [[ ! -f "$CONFIG_FILE" ]]; then
        return
    fi

    info "Setting API URL in config: $API_URL"

    local tmp_file
    tmp_file=$(mktemp)

    awk -v api_url="$API_URL" '
        BEGIN { in_api = 0; done = 0 }
        /^\[api\]/ { in_api = 1; print; next }
        /^\[/ { in_api = 0; print; next }
        {
            if (in_api && !done && $1 == "url" && $2 == "=") {
                print "url = \"" api_url "\""
                done = 1
                next
            }
            print
        }
        END {
            if (in_api && !done) {
                print "url = \"" api_url "\""
            }
        }
    ' "$CONFIG_FILE" > "$tmp_file"

    sudo cp "$tmp_file" "$CONFIG_FILE"
    sudo chmod 644 "$CONFIG_FILE"
    rm -f "$tmp_file"
}

# Add to PATH
setup_path() {
    if [[ "$ADD_TO_PATH" != "true" ]]; then
        return
    fi

    step "Adding to PATH..."

    # Check if already in PATH
    if echo "$PATH" | grep -q "$INSTALL_DIR"; then
        info "Already in PATH"
        return
    fi

    local profile_file=""
    local shell_name=$(basename "$SHELL")

    case "$shell_name" in
        bash)
            if [[ -f "$HOME/.bashrc" ]]; then
                profile_file="$HOME/.bashrc"
            elif [[ -f "$HOME/.bash_profile" ]]; then
                profile_file="$HOME/.bash_profile"
            fi
            ;;
        zsh)
            profile_file="$HOME/.zshrc"
            ;;
        fish)
            profile_file="$HOME/.config/fish/config.fish"
            ;;
    esac

    if [[ -n "$profile_file" ]]; then
        if ! grep -q "hydra-agent" "$profile_file" 2>/dev/null; then
            echo "" >> "$profile_file"
            echo "# Hydra Agent" >> "$profile_file"
            echo "export PATH=\"\$PATH:$INSTALL_DIR\"" >> "$profile_file"
            info "Added to $profile_file"
            info "Run 'source $profile_file' or restart your shell"
        fi
    fi

    # Also add to /etc/profile.d for system-wide availability
    if [[ -d /etc/profile.d ]] && [[ "$EUID" -eq 0 || -w /etc/profile.d ]]; then
        sudo tee /etc/profile.d/hydra-agent.sh > /dev/null << EOF
# Hydra Agent PATH
export PATH="\$PATH:$INSTALL_DIR"
EOF
        info "Added system-wide PATH configuration"
    fi

    success "PATH updated"
}

# Register with token
register_agent() {
    if [[ -z "$REGISTER_TOKEN" ]]; then
        return
    fi

    step "Registering agent with token..."

    if "${INSTALL_DIR}/hydra-agent" register --token "$REGISTER_TOKEN"; then
        success "Agent registered successfully"
    else
        warn "Registration failed. You can register manually later with:"
        warn "  hydra-agent register --token <token>"
    fi
}

# Cleanup build artifacts
cleanup() {
    step "Cleaning up..."

    # Remove target directory to save space
    if [[ -d "target" ]]; then
        info "Removing build artifacts..."
        rm -rf target
    fi

    success "Cleanup complete"
}

# Print completion summary
print_summary() {
    echo ""
    echo "=========================================="
    success "   Hydra Agent Installation Complete!"
    echo "=========================================="
    echo ""
    info "Binary:  ${INSTALL_DIR}/hydra-agent"
    if [[ "$CREATE_ALIAS" == "true" ]]; then
        info "Alias:   ${INSTALL_DIR}/hydra"
    fi
    info "Config:  ${CONFIG_FILE}"
    info "Vault:   ${VAULT_DIR}"
    info "Version: ${VERSION}"
    echo ""
    echo "Next steps:"
    echo ""
    echo "  1. Edit configuration:"
    echo "     sudo nano ${CONFIG_FILE}"
    echo ""
    echo "  2. Login (if not using token):"
    echo "     hydra-agent login -u <username>"
    echo ""
    echo "  3. Register agent account:"
    echo "     hydra-agent register"
    echo ""
    echo "  4. Register this node:"
    echo "     hydra-agent node register"
    echo ""
    echo "  5. Activate as system service:"
    echo "     sudo hydra-agent service activate"
    echo ""
    echo "For help:"
    echo "  hydra-agent --help"
    echo ""
}

# Main function
main() {
    parse_args "$@"

    echo ""
    echo "=========================================="
    echo "   Hydra Agent Installer v${VERSION:-?}"
    echo "=========================================="
    echo ""

    # Validate version
    if [[ -z "$VERSION" ]]; then
        error "Version is required. Use -v <version>"
        show_help
        exit 1
    fi

    # Run installation steps
    detect_system
    check_dependencies
    check_rust
    build_agent
    install_binary
    setup_directories
    setup_config
    setup_path
    register_agent
    cleanup
    print_summary
}

# Run main
main "$@"
