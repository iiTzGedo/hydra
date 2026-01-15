<p align="center">
  <img src="../resources/assets/logos/hydra-logos-v1_dark_256.png" alt="Hydra Logo" width="128" height="128">
</p>

<h1 align="center">Hydra Agent</h1>

<p align="center">
  <a href="https://www.rust-lang.org/"><img src="https://img.shields.io/badge/rust-1.75%2B-orange.svg" alt="Rust"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue.svg" alt="License"></a>
  <a href="#platform-support"><img src="https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows%20%7C%20FreeBSD-lightgrey.svg" alt="Platform"></a>
</p>

<p align="center">
  Lightweight, cross-platform infrastructure profiling agent for the <a href="https://github.com/yourorg/hydra">Hydra</a> platform.<br>
  Written in Rust for minimal resource usage (&lt;50MB RSS) and maximum portability.
</p>

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
  - [One-liner Install](#1-one-liner-install-recommended)
  - [Source Bundle Install](#2-source-bundle-install)
  - [Manual Build](#3-manual-build-from-source)
  - [Windows Installation](#windows-installation)
- [CLI Reference](#cli-reference)
  - [Global Options](#global-options)
  - [Commands](#commands)
- [Configuration](#configuration)
  - [Configuration File](#configuration-file)
  - [Configuration Schema](#configuration-schema)
  - [Validation Rules](#validation-rules)
- [Credential Vault](#credential-vault)
- [Agent Registration Flow](#agent-registration-flow)
- [Service Management](#service-management)
- [Cross-Compilation](#cross-compilation)
- [Deployment](#deployment)
- [Development](#development)
  - [Project Structure](#project-structure)
  - [Dev Mode](#dev-mode)
  - [Running Tests](#running-tests)
- [Platform Support](#platform-support)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Features

- **Cross-platform**: Linux (amd64/arm64/armv7), macOS (Intel/Apple Silicon), Windows, FreeBSD
- **Lightweight**: Single static binary with minimal dependencies
- **Comprehensive Profiling**: Hardware, network, storage, software, and service information
- **Package Detection**: Supports apt, dnf, pacman, apk, Homebrew, Chocolatey, winget, Scoop
- **Secure Communication**: TLS-encrypted API communication with API key authentication
- **Credential Vault**: Secure storage with platform-specific protections (Unix 0600 perms, Windows DPAPI)
- **Flexible Scheduling**: Systemd service, Windows Service, cron jobs, or one-time runs
- **Live Config Updates**: Configuration changes push to API automatically

## Quick Start

```bash
# Install the agent
curl -sSL https://hydra.local/api/v1/install | bash -s -- -v 0.3.1

# Login as admin/operator
hydra-agent login -u admin

# Register the agent account
hydra-agent register

# Register this machine as a node
hydra-agent node register

# Activate as system service
sudo hydra-agent service activate
```

## Installation

### 1. One-liner Install (Recommended)

Downloads source bundle from Hydra API, builds locally, and installs:

```bash
# Basic install
curl -sSL https://hydra.local/api/v1/install | bash -s -- -v 0.3.1

# With alias and PATH setup
curl -sSL https://hydra.local/api/v1/install | bash -s -- -v 0.3.1 -a -g

# With auto-registration
curl -sSL https://hydra.local/api/v1/install | bash -s -- \
  -v 0.3.1 -r <registration_token>
```

**Install script options:**

| Flag | Long Form | Description | Default |
|------|-----------|-------------|---------|
| `-v` | `--version` | Version to install (**required**) | - |
| `-d` | `--install-dir` | Binary installation directory | `/usr/local/bin` |
| `-c` | `--config` | Configuration file path | `/etc/hydra/agent.toml` |
| `-a` | `--aliased` | Create `hydra` alias symlink | `false` |
| `-g` | `--global` | Add to system PATH | `false` |
| `-r` | `--register` | Auto-register with token | - |
| `-h` | `--help` | Show help | - |

### 2. Source Bundle Install

Download and build from source bundle manually:

```bash
# Download bundle
curl -sSL https://hydra.local/api/v1/agent/download?source=obs \
  -o hydra-agent-0.3.1.zip

# Extract and build
unzip hydra-agent-0.3.1.zip
cd hydra-agent-0.3.1
./scripts/install.sh -v 0.3.1
```

### 3. Manual Build from Source

Clone repository and build directly:

```bash
# Clone repository
git clone https://github.com/yourorg/hydra.git
cd hydra/hydra-agent

# Build release binary
cargo build --release

# Install
sudo cp target/release/hydra-agent /usr/local/bin/
sudo chmod 755 /usr/local/bin/hydra-agent

# Create directories
sudo mkdir -p /etc/hydra /var/cv/hydra /var/log/hydra
sudo chmod 700 /var/cv/hydra

# Create configuration
sudo cp agent.example.toml /etc/hydra/agent.toml
sudo nano /etc/hydra/agent.toml  # Edit with your settings
```

### Windows Installation

**PowerShell (as Administrator):**

```powershell
# Download and run installer
Invoke-WebRequest -Uri "https://hydra.local/api/v1/install" -OutFile install.ps1
.\install.ps1 -Version 0.3.1

# With options
.\install.ps1 -Version 0.3.1 -CreateAlias -AddToPath -RegisterToken "reg_abc123"
```

**PowerShell install options:**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-Version` | Version to install (**required**) | - |
| `-InstallDir` | Installation directory | `C:\Program Files\Hydra Agent` |
| `-ConfigPath` | Configuration file path | `C:\ProgramData\Hydra\agent.toml` |
| `-CreateAlias` | Create `hydra.exe` alias | `false` |
| `-AddToPath` | Add to system PATH | `false` |
| `-RegisterToken` | Auto-register with token | - |
| `-ApiUrl` | Override API URL in config | - |
| `-SkipRust` | Skip Rust installation check | `false` |

## CLI Reference

### Global Options

```
hydra-agent [OPTIONS] <COMMAND>

Options:
  -V, --verbose         Enable verbose output (debug logging)
  -a, --aliased         Create 'hydra' alias symlink
  -c, --config <PATH>   Configuration file path [default: /etc/hydra/agent.toml]
                        [env: HYDRA_CONFIG]
  -m, --mode <MODE>     Operating mode: live, dev [default: live]
  -h, --help            Print help
      --version         Print version

Commands:
  login       Authenticate as admin/operator
  register    Register agent system account
  config      Manage agent configuration
  node        Node management operations
  service     Service lifecycle management
  run         Run profile collection
  status      Show agent status
  install     Install the agent as system service
  uninstall   Uninstall the agent
```

### Commands

#### `login` - Authenticate as Admin/Operator

Before registering an agent, authenticate as an admin or operator user:

```bash
hydra-agent login [OPTIONS]

Options:
  -u, --username <USER>   Username (admin or operator)
  -p, --password <PASS>   Password (prompts interactively if not provided)
  -r, --refresh           Refresh existing session using refresh token
  -s, --status            Show current login status
  -l, --logout            Clear current session

Examples:
  hydra-agent login -u admin                    # Interactive password prompt
  hydra-agent login -u admin -p mypassword      # Non-interactive
  hydra-agent login --refresh                   # Refresh expired session
  hydra-agent login --status                    # Check if logged in
  hydra-agent login --logout                    # Clear session
```

#### `register` - Register Agent System Account

Creates a system user account for the agent and obtains API credentials:

```bash
hydra-agent register [OPTIONS]

Options:
  -t, --token <TOKEN>     Registration token (required if not logged in)
  --username <ID>         Custom agent username [default: auto-generated]
  --password <PWD>        Custom agent password [default: auto-generated]
  -s, --status            Show registration status
  -c, --clear             Clear saved credentials

Auto-generated username format: agent-XXXXXXXX (8 alphanumeric chars)

Examples:
  # Using existing login session
  hydra-agent login -u admin
  hydra-agent register

  # Using registration token (no login required)
  hydra-agent register --token reg_abc123def456

  # Custom credentials
  hydra-agent register --username agent-webserver --password mySecurePass123

  # Check status
  hydra-agent register --status
```

#### `config` - Manage Configuration

Full CRUD operations on configuration with live API synchronization:

```bash
hydra-agent config <SUBCOMMAND>

Subcommands:
  get <KEY>              Get a configuration value
  set <KEY> <VALUE>      Set a configuration value
  unset <KEY> [VALUE]    Remove/clear a configuration value
  list                   List all configuration values
  path                   Show configuration file path
  init                   Initialize a new configuration file
  validate               Validate configuration syntax and values

Key Format: <section>.<key>
Sections: api, node, collection, schedule

Examples:
  # Get values
  hydra-agent config get node.node_id
  hydra-agent config get api.url

  # Set values (string)
  hydra-agent config set node.display_name "Production Server"
  hydra-agent config set api.url "https://hydra.example.com/api/v1"

  # Set values (arrays - comma-separated)
  hydra-agent config set node.tags "production,web,critical"
  hydra-agent config set collection.collectors "hardware,network,storage"

  # Set values (boolean/number)
  hydra-agent config set collection.include_packages true
  hydra-agent config set schedule.interval_seconds 3600

  # Unset values
  hydra-agent config unset node.description          # Clear string to empty
  hydra-agent config unset node.tags production      # Remove from array
  hydra-agent config unset schedule.enabled          # Set boolean to false

  # List all
  hydra-agent config list

  # Initialize new config
  hydra-agent config init --node-id my-server --api-url https://hydra.local/api/v1

  # Validate config
  hydra-agent config validate
```

**Note:** In `live` mode, changes to `node.*` fields automatically push to the API.

#### `node` - Node Management

Register and manage the current machine as a Hydra node:

```bash
hydra-agent node <SUBCOMMAND>

Subcommands:
  register      Register this machine as a node
  status        Show node registration status
  unregister    Unregister this node (removes from Hydra)
  info          Show detailed node information
  update        Update node properties

Options (for register/update):
  -t, --token <TOKEN>      Registration token
  --force                  Force re-registration
  --node-id <ID>           Override node ID from config
  --class <CLASS>          Node class: compute, networking, iot
  --node-type <TYPE>       Node type: physical, logical
  --kind <KIND>            Node kind (see below)
  --display-name <NAME>    Human-readable name
  --tags <TAGS>            Comma-separated tags

Node Kinds by Class:
  compute:    bare-metal, vm, lxc, docker, kubernetes-pod
  networking: router, switch, access-point, firewall, load-balancer
  iot:        sensor, actuator, controller, hub, bridge, appliance

Examples:
  # Basic registration
  hydra-agent node register

  # With metadata
  hydra-agent node register \
    --class compute \
    --kind bare-metal \
    --display-name "Web Server 01" \
    --tags "production,web,frontend"

  # Check status
  hydra-agent node status

  # Update existing node
  hydra-agent node update --tags "production,web,api"
```

#### `service` - Service Lifecycle Management

Manage the agent as a system service:

```bash
hydra-agent service <SUBCOMMAND>

Subcommands:
  activate      Setup and start as system service
  deactivate    Stop and remove system service
  start         Start the service
  stop          Stop the service
  restart       Restart the service
  status        Show service status
  enable        Enable service to start on boot
  disable       Disable service from starting on boot
  logs          View service logs
  run           Run profile collection (without service)

Options for activate:
  --install-dir <DIR>     Installation directory [default: /usr/local/bin]
  --no-start              Dont start service after activation
  --with-alias            Create 'hydra' alias symlink
  -d, --docker            Setup as Docker container instead of systemd
  -c, --cron <EXPR>       Setup as cron job instead of service

Options for run:
  --once                  Run single collection and exit
  --output <PATH>         Output profile to file (dev mode)

Examples:
  # Setup as systemd service (Linux)
  sudo hydra-agent service activate

  # Setup as Windows Service
  hydra-agent service activate

  # Setup with alias
  sudo hydra-agent service activate --with-alias

  # Setup as cron job (every 6 hours)
  sudo hydra-agent service activate --cron "0 */6 * * *"

  # Setup as Docker container
  sudo hydra-agent service activate --docker

  # Manual control
  sudo hydra-agent service start
  sudo hydra-agent service stop
  sudo hydra-agent service restart
  sudo hydra-agent service status

  # View logs
  hydra-agent service logs
  hydra-agent service logs --follow

  # One-time profile collection
  hydra-agent service run --once
```

#### `run` - Run Profile Collection

Execute profile collection manually:

```bash
hydra-agent run [OPTIONS]

Options:
  --once              Run once and exit (dont loop)
  --output <PATH>     Output profile to file instead of API (dev mode)

Examples:
  hydra-agent run                           # Continuous collection per schedule
  hydra-agent run --once                    # Single collection
  hydra-agent -m dev run --once             # Dev mode, no API calls
  hydra-agent -m dev run --output profile.json
```

#### `status` - Show Agent Status

Display comprehensive agent status:

```bash
hydra-agent status

Output includes:
  - Configuration file location and validity
  - Agent registration status (username, parent account)
  - API key status (expiration)
  - Node registration status
  - Service status (if running as service)
  - API connectivity
  - Last profile submission time
```

## Configuration

### Configuration File

| Platform | Default Path |
|----------|--------------|
| Linux/macOS/BSD | `/etc/hydra/agent.toml` |
| Windows | `C:\ProgramData\Hydra\agent.toml` |

Override with `--config` flag or `HYDRA_CONFIG` environment variable.

### Configuration Schema

```toml
# Hydra Agent Configuration

[api]
url = "https://hydra.local/api/v1"      # Base URL of Hydra API (required)
credentials_file = "/var/cv/hydra/credentials.json"  # Auto-determined
timeout_seconds = 30                     # Request timeout
retries = 3                              # Retry count for failed requests

[node]
node_id = "my-server-01"                 # Unique node identifier (required)
class = "compute"                        # Node class: compute, networking, iot
node_type = "physical"                   # Node type: physical, logical
kind = "bare-metal"                      # Node kind (optional, see below)
display_name = "My Server 01"            # Human-readable name
description = "Primary web server"       # Optional description
tags = ["production", "web"]             # Tags for grouping
parent_node_id = ""                      # Parent node (for VMs/containers)

[collection]
level = "neutral"                        # Collection depth: shallow, neutral, deep
collectors = [                           # Enabled collectors
  "hardware",
  "network",
  "storage",
  "software",
  "services"
]
include_packages = true                  # Include installed packages
include_users = true                     # Include user list
config_files = [                         # Config files to track (hashed)
  "/etc/nginx/nginx.conf",
  "/etc/ssh/sshd_config"
]

[schedule]
enabled = true                           # Enable scheduled collection
interval_seconds = 86400                 # Collection interval (default: 24 hours)
on_startup = true                        # Collect immediately on startup
```

### Validation Rules

| Field | Pattern | Examples |
|-------|---------|----------|
| `node_id` | `^[a-z]+([._-][a-z0-9]+){0,2}$` | `proxmox-01`, `web.server`, `ha_core` |
| `tags` | `^[a-z]+[_:]?[a-z]+$` (each) | `production`, `web_server`, `tier:frontend` |
| `parent_node_id` | Same as `node_id` | `hypervisor-01` |

## Credential Vault

The agent stores credentials securely in a vault directory with restricted permissions.

| Platform | Vault Directory |
|----------|-----------------|
| Linux/macOS/BSD | `/var/cv/hydra/` (0700 perms) |
| Windows | `C:\ProgramData\Hydra\vault\` (ACL: Admins+SYSTEM only) |

### Vault Contents

| File | Purpose | Contents |
|------|---------|----------|
| `.creds` | Agent credentials | user_id, username, password, parent_user_id |
| `.apikey` | API authentication | api_key, api_key_id, expires_at, node_id |
| `.session` | Active JWT session | access_token, refresh_token, expires_at |
| `.node` | Node registration | node_id, registered_at, status |

### Security

- **Unix**: File permissions 0600 (owner read/write only)
- **Windows**: DPAPI encryption + NTFS ACLs (Administrators and SYSTEM only)
- **API Key Expiry**: 90 days, auto-renewed by service

## Agent Registration Flow

```
1. Login (admin/operator)
   └── hydra-agent login -u admin
       └── Saves JWT session to vault

2. Register Agent Account
   └── hydra-agent register
       ├── Generates username (agent-XXXXXXXX) and password
       ├── POST /api/v1/auth/register (role=agent)
       ├── API auto-links as sub-account of logged-in user
       ├── Auto-login as agent user
       ├── Create API key (90-day expiry)
       └── Save credentials + API key to vault

3. Register Node
   └── hydra-agent node register
       ├── POST /api/v1/node/register
       └── Save node registration to vault

4. Activate Service
   └── sudo hydra-agent service activate
       └── Creates systemd/Windows service for scheduled profiling
```

## Service Management

### Linux (systemd)

```bash
# Activate service
sudo hydra-agent service activate

# Service file created at: /etc/systemd/system/hydra-agent.service

# Control service
sudo systemctl start hydra-agent
sudo systemctl stop hydra-agent
sudo systemctl restart hydra-agent
sudo systemctl status hydra-agent

# View logs
journalctl -u hydra-agent -f
```

### Windows

```powershell
# Activate as Windows Service
hydra-agent service activate

# Control service (PowerShell as Admin)
Start-Service HydraAgent
Stop-Service HydraAgent
Restart-Service HydraAgent
Get-Service HydraAgent

# View logs
Get-EventLog -LogName Application -Source HydraAgent -Newest 50
```

### Cron (Alternative)

```bash
# Setup as cron job (every 6 hours)
sudo hydra-agent service activate --cron "0 */6 * * *"

# Cron entry created in /etc/cron.d/hydra-agent
```

## Cross-Compilation

### Prerequisites

```bash
# Install Rust targets
rustup target add x86_64-unknown-linux-gnu       # Linux AMD64
rustup target add aarch64-unknown-linux-gnu      # Linux ARM64
rustup target add armv7-unknown-linux-gnueabihf  # Linux ARMv7 (Raspberry Pi)
rustup target add x86_64-apple-darwin            # macOS Intel
rustup target add aarch64-apple-darwin           # macOS Apple Silicon
rustup target add x86_64-unknown-freebsd         # FreeBSD
rustup target add x86_64-pc-windows-gnu          # Windows

# Install cross (recommended for cross-compilation)
cargo install cross
```

### Building

```bash
# Native build
cargo build --release

# Cross-compile with cargo (requires toolchain)
cargo build --release --target x86_64-unknown-linux-gnu

# Cross-compile with cross (uses Docker, easier setup)
cross build --release --target aarch64-unknown-linux-gnu

# Windows cross-compile
cross build --release --target x86_64-pc-windows-gnu
```

## Deployment

### Deploy Script

The `scripts/deploy-agent.sh` script handles building and distributing the agent:

```bash
# Build binaries for all targets and upload to S3
./scripts/deploy-agent.sh 0.3.1

# Create source bundle and upload to S3
./scripts/deploy-agent.sh 0.3.1 --bundle

# Create both binaries and bundle
./scripts/deploy-agent.sh 0.3.1 --both

# Deploy to local directory instead of S3
./scripts/deploy-agent.sh 0.3.1 --bundle --output-dir /var/lib/hydra/bundles
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HYDRA_S3_ENDPOINT` | S3/Garage endpoint URL | - |
| `HYDRA_S3_BUCKET` | Bucket name | `hydra-bucket` |
| `HYDRA_S3_ACCESS_KEY` | S3 access key ID | - |
| `HYDRA_S3_SECRET_KEY` | S3 secret access key | - |
| `SKIP_UPLOAD` | Skip S3 upload (build only) | `false` |
| `TARGETS` | Comma-separated targets | All |
| `MAX_VERSIONS` | Versions to retain in S3 | `15` |

### Output Structure

```
S3/Local Output:
├── agents/
│   ├── linux-amd64/
│   │   ├── 0.3.1/
│   │   │   ├── hydra-agent
│   │   │   ├── hydra-agent.sha256
│   │   │   └── metadata.json
│   │   └── latest
│   ├── windows-amd64/
│   │   └── 0.3.1/
│   │       ├── hydra-agent.exe
│   │       └── ...
│   └── ...
├── bundles/
│   ├── 0.3.1/
│   │   ├── hydra-agent-0.3.1.zip
│   │   └── hydra-agent-0.3.1.zip.sha256
│   └── latest
└── manifests/
    └── versions.json
```

## Development

### Project Structure

```
hydra-agent/
├── src/
│   ├── main.rs              # CLI entry point, argument parsing
│   ├── lib.rs               # Library exports
│   ├── api/
│   │   └── mod.rs           # API client (auth, registration, profiles)
│   ├── cli/
│   │   ├── mod.rs           # CLI command routing, global args
│   │   ├── login.rs         # Login command implementation
│   │   ├── register.rs      # Register command implementation
│   │   ├── config.rs        # Config command implementation
│   │   ├── node.rs          # Node command implementation
│   │   └── service.rs       # Service command implementation
│   ├── collectors/
│   │   ├── mod.rs           # Collector orchestration
│   │   ├── hardware.rs      # CPU, memory, GPU, BIOS info
│   │   ├── network.rs       # Interfaces, routes, DNS
│   │   ├── storage.rs       # Disks, filesystems, mounts
│   │   └── software.rs      # Packages, users, services
│   ├── config/
│   │   └── mod.rs           # TOML config parsing, validation
│   ├── platform/
│   │   ├── mod.rs           # Platform detection, traits
│   │   ├── paths.rs         # Platform-specific paths
│   │   ├── unix.rs          # Unix implementations
│   │   └── windows.rs       # Windows implementations
│   └── vault/
│       └── mod.rs           # Credential storage
├── scripts/
│   ├── deploy-agent.sh      # Build and deploy script
│   ├── install.sh           # Unix installer
│   └── install.ps1          # Windows installer
├── tests/
│   ├── collectors_test.rs   # Collector unit tests
│   └── config_test.rs       # Config validation tests
├── Cargo.toml               # Dependencies and build config
├── agent.example.toml       # Example configuration
└── README.md
```

### Dev Mode

Run the agent in development mode to skip API calls and output locally:

```bash
# Run collection without API
hydra-agent -m dev run --once

# Output to file
hydra-agent -m dev run --once --output profile.json

# Test config management
hydra-agent -m dev config list
hydra-agent -m dev config validate
```

In dev mode:
- API calls are skipped
- Profiles output to stdout or file
- No registration required
- Useful for testing collectors

### Running Tests

```bash
# Run all tests
cargo test

# Run with verbose output
cargo test -- --nocapture

# Run specific test
cargo test test_hardware_collector

# Run tests for a specific module
cargo test collectors::

# Run with coverage (requires cargo-tarpaulin)
cargo install cargo-tarpaulin
cargo tarpaulin --out Html
```

### Linting and Formatting

```bash
# Format code
cargo fmt

# Run clippy lints
cargo clippy -- -D warnings

# Check without building
cargo check
```

## Platform Support

| Platform | Architecture | Package Managers | Service Type |
|----------|--------------|------------------|--------------|
| Linux | amd64, arm64, armv7 | apt, dnf, pacman, apk | systemd, cron |
| macOS | Intel, Apple Silicon | Homebrew | launchd |
| Windows | amd64 | winget, Chocolatey, Scoop | Windows Service, Task Scheduler |
| FreeBSD | amd64 | pkg | rc.d |

### Raspberry Pi Support

ARM builds support Raspberry Pi:
- **Pi 3/4 (64-bit OS)**: Use `linux-arm64` target
- **Pi 3/4 (32-bit OS)**: Use `linux-armv7` target
- **Pi Zero/1**: Not supported (ARMv6)

## Security

### Credential Protection

| Platform | Method |
|----------|--------|
| Unix | File permissions (0600/0700), root ownership |
| Windows | DPAPI encryption, NTFS ACLs |

### Network Security

- All API communication uses HTTPS/TLS
- API key authentication (no passwords transmitted after registration)
- JWT tokens for session management
- Registration tokens are single-use

### Data Security

- No sensitive information in profiles (config files are hashed, not stored)
- Passwords never stored in plaintext
- API keys rotated automatically (90-day expiry)

## Troubleshooting

### Common Issues

**Agent won't start:**
```bash
# Check configuration
hydra-agent config validate

# Check API connectivity
hydra-agent status

# Run in verbose mode
hydra-agent -V service run --once
```

**Registration fails:**
```bash
# Check if already registered
hydra-agent register --status

# Clear and re-register
hydra-agent register --clear
hydra-agent register
```

**API connection errors:**
```bash
# Verify API URL
hydra-agent config get api.url

# Test connectivity
curl -k https://hydra.local/api/v1/health
```

**Permission denied:**
```bash
# Check vault permissions (Unix)
ls -la /var/cv/hydra/
sudo chmod 700 /var/cv/hydra/

# Check config permissions
ls -la /etc/hydra/agent.toml
```

### Log Locations

| Platform | Log Location |
|----------|--------------|
| Linux (systemd) | `journalctl -u hydra-agent` |
| Linux (file) | `/var/log/hydra/agent.log` |
| Windows | Event Log (Application) or `C:\ProgramData\Hydra\logs\` |
| macOS | `~/Library/Logs/hydra-agent.log` |

### Debug Mode

```bash
# Enable debug logging
hydra-agent -V <command>

# Environment variable
RUST_LOG=debug hydra-agent <command>
```

## License

Apache-2.0
