
> **Version:** 0.3.0  
> **Last Updated:** 2025-01-02  
> **Status:** Technical Specification

---

## Overview

The `/install` endpoint is the primary mechanism for bootstrapping hydra-agent on new nodes. It serves dual purposes: delivering an executable installation script for curl-based deployments and providing direct binary downloads for manual installations.

**Why This Matters:**  
In a homelab environment with heterogeneous infrastructure (Proxmox hosts, LXCs, VMs, Docker hosts, ARM-based SBCs), having a single-command installation mechanism drastically reduces friction for onboarding new nodes. This endpoint transforms what would be a multi-step process into a one-liner.

**Authentication Options:**  
Node registration supports two authentication methods:

1. **User Credentials** (`--username` / `--password`) - Direct authentication as admin or operator
2. **Registration Token** (`--token`) - Pre-generated token for delegated/automated deployments

|Token Type|Created By|Used For|
|---|---|---|
|Node registration token|`admin` or `operator`|Registering new nodes via install script|
|User registration token|`admin` only|Creating new user accounts|

---

## API Schema

### GET /api/v1/install

Returns a bash installation script for curl-based deployment.

**Request:**

```http
GET /api/v1/install HTTP/1.1
Host: hydra.local
Accept: text/plain
```

**Response:**  
`200 OK`  
`Content-Type: text/x-shellscript`

```bash
#!/bin/bash
# Hydra Agent Installer
# Generated dynamically by hydra-api
...
```

**Query Parameters:**

|Parameter|Type|Required|Default|Description|
|---|---|---|---|---|
|`arch`|enum|No|auto-detect|Target architecture: `amd64`, `arm64`, `armv7`|
|`os`|enum|No|auto-detect|Target OS: `linux`, `darwin`, `freebsd`|
|`version`|string|No|`latest`|Agent version to install|
|`install-dir`|string|No|`/usr/local/bin`|Installation directory|
|`config-dir`|string|No|`/etc/hydra`|Configuration directory|
|`no-systemd`|boolean|No|`false`|Skip systemd service installation|
|`no-register`|boolean|No|`false`|Skip node registration step|

---

### GET /api/v1/install/{binary}

Direct binary download endpoint for manual installations.

**Available Binaries:**

|Binary Name|Description|
|---|---|
|`hydra-agent-linux-amd64`|Linux x86_64 static binary|
|`hydra-agent-linux-arm64`|Linux ARM64 static binary|
|`hydra-agent-linux-armv7`|Linux ARMv7 (32-bit) static binary|
|`hydra-agent-darwin-amd64`|macOS Intel binary|
|`hydra-agent-darwin-arm64`|macOS Apple Silicon binary|
|`hydra-agent-freebsd-amd64`|FreeBSD x86_64 binary|

**Response:**  
`200 OK`  
`Content-Type: application/octet-stream`  
`Content-Disposition: attachment; filename="hydra-agent-linux-amd64"`

**Error Responses:**

|HTTP|Code|Condition|
|---|---|---|
|404|`BINARY_NOT_FOUND`|Requested architecture/OS combination not available|
|503|`BINARY_UNAVAILABLE`|Binary exists but currently unavailable|

---

## Script Arguments

When running the script via curl, pass arguments using `bash -s --`:

```bash
curl -sSL https://hydra.local/api/v1/install | bash -s -- [OPTIONS]
```

### Authentication Arguments (one method required for registration)

**Method 1: User Credentials**

|Argument|Description|
|---|---|
|`--username`|User account username (admin or operator role)|
|`--password`|User account password|

**Method 2: Registration Token**

|Argument|Description|
|---|---|
|`--token`|Node registration token (created by admin or operator)|

> **Note:** Registration tokens for **node registration** can be created by both `admin` and `operator` roles via `POST /auth/tokens?scope=node`. Registration tokens for **user registration** can only be created by `admin` role. Node registration tokens are preferred for automated/bulk deployments as they avoid embedding user credentials in scripts.

### Optional Arguments

|Argument|Default|Description|
|---|---|---|
|`--api-url`|Script source URL|Hydra API base URL|
|`--node-id`|hostname|Unique node identifier|
|`--node-class`|`compute`|Node class: `compute`, `networking`, `iot`|
|`--node-type`|`physical`|Node type: `physical`, `logical`|
|`--node-kind`|auto-detect|Specific kind (e.g., `bare-metal`, `vm`, `lxc`)|
|`--display-name`|hostname|Human-readable name|
|`--parent-node`|null|Parent node ID (for logical nodes)|
|`--tags`|empty|Comma-separated tags|
|`--collection-level`|`neutral`|Collection depth: `shallow`, `neutral`, `deep`|
|`--cron`|`0 */6 * * *`|Profile collection schedule|
|`--install-dir`|`/usr/local/bin`|Binary installation location|
|`--config-dir`|`/etc/hydra`|Configuration directory|
|`--no-systemd`|false|Skip systemd service setup|
|`--no-start`|false|Don't start service after install|
|`--dry-run`|false|Show what would be done without executing|
|`--unattended`|false|Skip all prompts|
|`--verify-ssl`|true|Verify TLS certificates|

---

## User Interaction Flow

### Scenario 1: Fresh System Bootstrap (First Admin)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  FRESH HYDRA INSTALLATION - FIRST NODE                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  User                 hydra-api               install.sh                │
│   │                       │                       │                     │
│   │  POST /auth/register  │                       │                     │
│   │  (bootstrap admin)    │                       │                     │
│   │──────────────────────►│                       │                     │
│   │                       │                       │                     │
│   │  201 Created          │                       │                     │
│   │  {admin credentials}  │                       │                     │
│   │◄──────────────────────│                       │                     │
│   │                       │                       │                     │
│   │  curl .../install | bash -s -- \              │                     │
│   │    --username admin --password ***            │                     │
│   │───────────────────────────────────────────────►                     │
│   │                       │                       │                     │
│   │                       │  GET /api/v1/install  │                     │
│   │                       │◄──────────────────────│                     │
│   │                       │                       │                     │
│   │                       │  POST /auth/login     │                     │
│   │                       │◄──────────────────────│                     │
│   │                       │                       │                     │
│   │                       │  POST /node/register  │                     │
│   │                       │  {node metadata}      │                     │
│   │                       │◄──────────────────────│                     │
│   │                       │                       │                     │
│   │                       │  201 Created          │                     │
│   │                       │  {apiKey: hyk_node_*} │                     │
│   │                       │──────────────────────►│                     │
│   │                       │                       │                     │
│   │                       │                       │  Write credentials  │
│   │                       │                       │  Start systemd      │
│   │  "Installation complete"                      │                     │
│   │◄──────────────────────────────────────────────│                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Scenario 2: Subsequent Node Onboarding

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ADDING NEW NODE TO EXISTING HYDRA DEPLOYMENT                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Admin creates credentials for operator (optional):                     │
│  - Via web UI: Settings → Users → Add User                              │
│  - Via API: POST /users with operator role                              │
│                                                                         │
│  On target node:                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ $ curl -sSL https://hydra.local/api/v1/install | bash -s -- \   │   │
│  │     --username operator --password *** \                         │   │
│  │     --node-id docker-host-02 \                                   │   │
│  │     --node-class compute \                                       │   │
│  │     --node-type logical \                                        │   │
│  │     --node-kind lxc \                                            │   │
│  │     --parent-node proxmox-01 \                                   │   │
│  │     --tags production,docker                                     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Scenario 3: Manual Installation (No curl)

For air-gapped or restricted environments:

```bash
# On machine with internet access
wget https://hydra.local/api/v1/install/hydra-agent-linux-amd64

# Transfer to target node (scp, usb, etc.)
scp hydra-agent-linux-amd64 user@target:/tmp/

# On target node
sudo mv /tmp/hydra-agent-linux-amd64 /usr/local/bin/hydra-agent
sudo chmod +x /usr/local/bin/hydra-agent

# Register with user credentials
hydra-agent register \
  --api-url https://hydra.local/api/v1 \
  --username operator \
  --password ***

# Install systemd service
sudo hydra-agent install
```

---

## Functional Flow

### Phase 1: Pre-flight Checks

```bash
preflight_checks() {
    # 1. Verify running as root (or with sudo)
    check_root_privileges
    
    # 2. Detect platform
    detect_os          # linux, darwin, freebsd
    detect_arch        # amd64, arm64, armv7
    detect_init_system # systemd, openrc, launchd, none
    
    # 3. Verify prerequisites
    check_command "curl" || check_command "wget"
    check_network_connectivity "$API_URL"
    
    # 4. Check for existing installation
    if [ -f "/usr/local/bin/hydra-agent" ]; then
        prompt_upgrade_or_reinstall
    fi
    
    # 5. Detect virtualization (for auto node-type)
    detect_virtualization  # bare-metal, vm, lxc, docker, etc.
}
```

### Phase 2: Binary Download & Verification

```bash
download_agent() {
    local binary_name="hydra-agent-${OS}-${ARCH}"
    local download_url="${API_URL}/install/${binary_name}"
    local checksum_url="${download_url}.sha256"
    
    # Download binary
    curl -sSL -o /tmp/hydra-agent "$download_url"
    
    # Download and verify checksum
    curl -sSL -o /tmp/hydra-agent.sha256 "$checksum_url"
    
    if ! sha256sum -c /tmp/hydra-agent.sha256; then
        error "Checksum verification failed"
        exit 1
    fi
    
    # Move to install directory
    install -m 755 /tmp/hydra-agent "${INSTALL_DIR}/hydra-agent"
}
```

### Phase 3: Authentication & Registration

```bash
register_node() {
    local auth_header=""
    
    if [ -n "${TOKEN:-}" ]; then
        # Method 2: Use registration token directly
        auth_header="X-Registration-Token: ${TOKEN}"
    else
        # Method 1: Authenticate user to get access token
        local auth_response=$(curl -sSL -X POST "${API_URL}/auth/login" \
            -H "Content-Type: application/json" \
            -d "{\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\"}")
        
        local access_token=$(echo "$auth_response" | jq -r '.accessToken')
        
        if [ "$access_token" = "null" ]; then
            error "Authentication failed"
            exit 1
        fi
        
        auth_header="Authorization: Bearer ${access_token}"
    fi
    
    # Register node
    local register_response=$(curl -sSL -X POST "${API_URL}/node/register" \
        -H "${auth_header}" \
        -H "Content-Type: application/json" \
        -d "{
            \"nodeId\": \"${NODE_ID}\",
            \"class\": \"${NODE_CLASS}\",
            \"type\": \"${NODE_TYPE}\",
            \"kind\": \"${NODE_KIND}\",
            \"displayName\": \"${DISPLAY_NAME}\",
            \"parentNodeId\": ${PARENT_NODE:-null},
            \"tags\": [$(echo $TAGS | sed 's/,/\",\"/g' | sed 's/^/\"/;s/$/\"/')]
        }")
    
    # Extract and store API key
    local api_key=$(echo "$register_response" | jq -r '.apiKey')
    local api_key_id=$(echo "$register_response" | jq -r '.apiKeyId')
    
    if [ "$api_key" = "null" ]; then
        error "Node registration failed: $(echo "$register_response" | jq -r '.error // .message')"
        exit 1
    fi
    
    # Write credentials file
    mkdir -p "${CONFIG_DIR}"
    cat > "${CONFIG_DIR}/credentials.json" << EOF
{
    "nodeId": "${NODE_ID}",
    "apiKey": "${api_key}",
    "apiKeyId": "${api_key_id}",
    "registeredAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
    chmod 600 "${CONFIG_DIR}/credentials.json"
}
```

### Phase 4: Configuration Generation

```bash
generate_config() {
    cat > "${CONFIG_DIR}/agent.toml" << EOF
[agent]
node_id = "${NODE_ID}"
node_class = "${NODE_CLASS}"
node_type = "${NODE_TYPE}"

[api]
base_url = "${API_URL}"
credentials_file = "${CONFIG_DIR}/credentials.json"
timeout_seconds = 30
retry_attempts = 3
verify_ssl = ${VERIFY_SSL}

[schedule]
cron = "${CRON_SCHEDULE}"
events = ["boot", "network_change", "package_change"]

[collection]
level = "${COLLECTION_LEVEL}"

[collectors]
hardware = true
network = true
storage = true
software = true
virtualization = true
users = true
services = true
configs = true

[logging]
level = "info"
format = "json"
file = "/var/log/hydra/agent.log"
EOF
    chmod 644 "${CONFIG_DIR}/agent.toml"
}
```

### Phase 5: Service Installation

```bash
install_service() {
    case "$INIT_SYSTEM" in
        systemd)
            install_systemd_service
            ;;
        openrc)
            install_openrc_service
            ;;
        launchd)
            install_launchd_service
            ;;
        *)
            warn "No init system detected, skipping service installation"
            ;;
    esac
}

install_systemd_service() {
    cat > /etc/systemd/system/hydra-agent.service << EOF
[Unit]
Description=Hydra Infrastructure Agent
Documentation=https://github.com/yourorg/hydra
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/hydra-agent run
Restart=on-failure
RestartSec=10
User=root
Environment=HYDRA_CONFIG=/etc/hydra/agent.toml

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/var/log/hydra /etc/hydra

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable hydra-agent.service
    
    if [ "$NO_START" != "true" ]; then
        systemctl start hydra-agent.service
    fi
}
```

---

## Sample Installation Cases

### Case 1: Proxmox Host (Bare Metal Hypervisor)

```bash
# Scenario: Primary Proxmox server that will host VMs and LXCs
# Using user credentials
curl -sSL https://hydra.home.lan/api/v1/install | bash -s -- \
  --username admin \
  --password 'SecureP@ss123' \
  --node-id proxmox-01 \
  --node-class compute \
  --node-type physical \
  --node-kind bare-metal \
  --display-name "Proxmox Host 01" \
  --tags production,hypervisor,critical \
  --collection-level deep \
  --cron "0 */4 * * *"

# Alternative: Using registration token (preferred for automation)
curl -sSL https://hydra.home.lan/api/v1/install | bash -s -- \
  --token reg_node_abc123... \
  --node-id proxmox-01 \
  --node-class compute \
  --node-type physical \
  --node-kind bare-metal \
  --display-name "Proxmox Host 01" \
  --tags production,hypervisor,critical \
  --collection-level deep \
  --cron "0 */4 * * *"
```

**Expected Behavior:**

- Full hardware profiling (CPU, memory, storage, network)
- Detects Proxmox VE software
- Discovers `qm` and `pct` commands for VM/LXC enumeration
- Registers with `bare-metal` kind
- Creates profile every 4 hours

---

### Case 2: LXC Container (Docker Host)

```bash
# Scenario: LXC running Docker containers on proxmox-01
curl -sSL https://hydra.home.lan/api/v1/install | bash -s -- \
  --username operator \
  --password 'Op3rat0r!' \
  --node-id docker-host-01 \
  --node-class compute \
  --node-type logical \
  --node-kind lxc \
  --display-name "Docker Host LXC" \
  --parent-node proxmox-01 \
  --tags production,docker,containers
```

**Expected Behavior:**

- Hardware section shows virtualized resources (passed through from LXC)
- `isVirtual: true` with `virtualizationType: lxc`
- Docker service discovery enabled
- Establishes parent-child relationship with proxmox-01

---

### Case 3: Raspberry Pi (ARM SBC)

```bash
# Scenario: Raspberry Pi 4 running Pi-hole
curl -sSL https://hydra.home.lan/api/v1/install | bash -s -- \
  --username operator \
  --password 'Op3rat0r!' \
  --node-id pihole-01 \
  --node-class compute \
  --node-type physical \
  --node-kind bare-metal \
  --display-name "Pi-hole DNS" \
  --tags dns,adblock,network-services \
  --collection-level shallow
```

**Expected Behavior:**

- Auto-detects `arm64` architecture
- Downloads ARM64 binary
- Light collection (shallow) suitable for low-resource device
- Profiles Pi-hole service if running as systemd unit

---

### Case 4: Network Device (OPNsense)

```bash
# Scenario: OPNsense firewall/router (FreeBSD-based)
# Note: Manual install may be preferred due to FreeBSD restrictions
wget https://hydra.home.lan/api/v1/install/hydra-agent-freebsd-amd64
chmod +x hydra-agent-freebsd-amd64
./hydra-agent-freebsd-amd64 register \
  --api-url https://hydra.home.lan/api/v1 \
  --username admin \
  --password 'SecureP@ss123' \
  --node-id opnsense-gw \
  --node-class networking \
  --node-type physical \
  --node-kind firewall \
  --display-name "OPNsense Gateway"
```

**Expected Behavior:**

- FreeBSD binary used
- Network device class enables network-specific collectors
- Collects routing tables, firewall rules (hashed), interface details
- No systemd (uses rc.d)

---

### Case 5: VM with Auto-Detection

```bash
# Scenario: Let the installer figure out the environment
curl -sSL https://hydra.home.lan/api/v1/install | bash -s -- \
  --username operator \
  --password 'Op3rat0r!' \
  --node-id media-server \
  --display-name "Plex Media Server"
```

**Expected Behavior:**

- Detects running in VM via `systemd-detect-virt`
- Auto-sets `node-type: logical`, `node-kind: vm`
- Uses hostname if `--node-id` not specified
- Default `neutral` collection level

---

### Case 6: Token-Based Bulk Deployment

```bash
# Scenario: Operator pre-generates a token for multiple node registrations
# Step 1: Operator creates a node registration token (via API or web UI)
#   POST /auth/tokens?scope=node
#   { "description": "Q1 node rollout", "maxUses": 10, "expiresIn": 604800 }
#   Returns: { "token": "reg_node_xyz789..." }

# Step 2: Use token in install script (no credentials in script)
curl -sSL https://hydra.home.lan/api/v1/install | bash -s -- \
  --token reg_node_xyz789... \
  --node-id worker-node-03 \
  --node-class compute \
  --node-type logical \
  --node-kind docker \
  --tags production,worker
```

**Why Use Tokens Over Credentials:**

- Credentials never leave operator's control
- Token can have limited uses (e.g., max 10 registrations)
- Token auto-expires (default 7 days)
- Better for CI/CD pipelines and Ansible playbooks
- Operators can generate tokens without sharing their password

---

### Case 7: Dry Run (Preview Mode)

```bash
# Scenario: See what would happen without making changes
curl -sSL https://hydra.home.lan/api/v1/install | bash -s -- \
  --token reg_node_xyz789... \
  --node-id test-node \
  --dry-run
```

**Output:**

```
[DRY RUN] Would perform the following actions:
  - Download: hydra-agent-linux-amd64
  - Install to: /usr/local/bin/hydra-agent
  - Create config: /etc/hydra/agent.toml
  - Authenticate as: admin
  - Register node: test-node (class=compute, type=physical, kind=bare-metal)
  - Create systemd service: hydra-agent.service
  - Enable and start service
No changes made.
```

---

## Testing Checklist

### Unit Tests (Script Functions)

|Test ID|Function|Test Case|Expected|
|---|---|---|---|
|UT-01|`detect_os`|Linux kernel|Returns `linux`|
|UT-02|`detect_os`|macOS|Returns `darwin`|
|UT-03|`detect_arch`|x86_64|Returns `amd64`|
|UT-04|`detect_arch`|aarch64|Returns `arm64`|
|UT-05|`detect_virtualization`|Bare metal|Returns `bare-metal`|
|UT-06|`detect_virtualization`|LXC container|Returns `lxc`|
|UT-07|`detect_virtualization`|KVM VM|Returns `vm`|
|UT-08|`validate_node_id`|`valid-node-01`|Pass|
|UT-09|`validate_node_id`|`Invalid_Node!`|Fail|
|UT-10|`parse_args`|All valid args|Parsed correctly|

### Integration Tests (API Interactions)

|Test ID|Scenario|Steps|Expected|
|---|---|---|---|
|IT-01|Valid credentials|Script with valid user/pass|201 Created, API key returned|
|IT-02|Invalid credentials|Script with bad password|Auth failure, script exits|
|IT-03|Insufficient role|Viewer tries to register|403 Forbidden|
|IT-04|Duplicate node|Re-register existing node|409 Conflict|
|IT-05|Network timeout|API unreachable|Retry 3x, then fail|
|IT-06|Binary checksum fail|Corrupt download|Script aborts|
|IT-07|Fresh install|No existing agent|Full install succeeds|
|IT-08|Upgrade|Agent already exists|Prompts for upgrade|
|IT-09|Valid node token|Script with valid reg token|201 Created, API key returned|
|IT-10|Expired node token|Token past expiry|401 Token expired|
|IT-11|Exhausted node token|Token at maxUses|401 Token exhausted|
|IT-12|User token for node|User reg token used for node|400 Invalid token scope|
|IT-13|Operator creates token|Operator generates node token|201 Token created|
|IT-14|Viewer creates token|Viewer tries to create token|403 Forbidden|

### End-to-End Tests (Full Flow)

|Test ID|Platform|Scenario|Validation|
|---|---|---|---|
|E2E-01|Ubuntu 22.04|Fresh install|Agent running, profile submitted|
|E2E-02|Debian 12 LXC|Install with parent|Parent-child relationship in API|
|E2E-03|Raspberry Pi OS|ARM install|ARM64 binary, working agent|
|E2E-04|FreeBSD 14|Manual install|Agent functional without systemd|
|E2E-05|macOS Sonoma|Dev install|Agent runs, profiles submitted|

### Security Tests

|Test ID|Vector|Test|Expected|
|---|---|---|---|
|SEC-01|Credential exposure|Check ps output|No passwords visible|
|SEC-02|File permissions|credentials.json perms|600 (owner only)|
|SEC-03|TLS validation|Invalid cert|Fails unless --no-verify|
|SEC-04|Privilege escalation|Run as non-root|Requires sudo/root|
|SEC-05|API key scope|Node API key|Can only access own node|

---

## Error Handling Matrix

|Error Code|Message|Cause|Resolution|
|---|---|---|---|
|`E001`|Authentication failed|Invalid username/password|Verify credentials|
|`E002`|Insufficient permissions|User role < operator|Use admin/operator account|
|`E003`|Node already exists|Duplicate nodeId|Choose different ID or use --force|
|`E004`|API unreachable|Network/DNS issue|Check API URL and connectivity|
|`E005`|Binary download failed|404 or network error|Check architecture compatibility|
|`E006`|Checksum mismatch|Corrupt download|Retry download|
|`E007`|Permission denied|Not running as root|Use sudo|
|`E008`|systemd not available|Non-systemd system|Use --no-systemd|
|`E009`|Config dir not writable|Filesystem permissions|Check /etc/hydra permissions|
|`E010`|Parent node not found|Invalid parentNodeId|Verify parent exists|
|`E011`|Registration token invalid|Malformed or unknown token|Verify token string|
|`E012`|Registration token expired|Token past expiresAt|Generate new token|
|`E013`|Registration token exhausted|Token at maxUses limit|Generate new token|
|`E014`|Token scope mismatch|User token used for node (or vice versa)|Use correct token type|
|`E015`|No auth method provided|Missing --username/--password or --token|Provide credentials or token|

---

## Generated Installation Script (Reference)

```bash
#!/bin/bash
#
# Hydra Agent Installer
# Generated by hydra-api v0.3.0
#
# Usage:
#   curl -sSL https://hydra.local/api/v1/install | bash -s -- [OPTIONS]
#
# Authentication (one required):
#   --username        User account for registration
#   --password        User password
#   --token           Node registration token (alternative to user/pass)
#
# Options:
#   --api-url         API base URL (default: derived from script source)
#   --node-id         Node identifier (default: hostname)
#   --node-class      compute|networking|iot (default: compute)
#   --node-type       physical|logical (default: auto-detect)
#   --node-kind       Specific kind (default: auto-detect)
#   --display-name    Human-readable name (default: hostname)
#   --parent-node     Parent node ID for logical nodes
#   --tags            Comma-separated tags
#   --collection-level shallow|neutral|deep (default: neutral)
#   --cron            Collection schedule (default: "0 */6 * * *")
#   --install-dir     Binary location (default: /usr/local/bin)
#   --config-dir      Config location (default: /etc/hydra)
#   --no-systemd      Skip systemd service setup
#   --no-start        Don't start service after install
#   --no-register     Skip node registration
#   --verify-ssl      Verify TLS certs (default: true)
#   --dry-run         Preview actions without executing
#   --unattended      Skip all prompts
#   --help            Show this help
#
set -euo pipefail

# Configuration defaults
API_URL="${HYDRA_API_URL:-https://hydra.local/api/v1}"
INSTALL_DIR="/usr/local/bin"
CONFIG_DIR="/etc/hydra"
COLLECTION_LEVEL="neutral"
CRON_SCHEDULE="0 */6 * * *"
VERIFY_SSL="true"
NO_SYSTEMD="false"
NO_START="false"
NO_REGISTER="false"
DRY_RUN="false"
UNATTENDED="false"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }

# ... (full script implementation)
# See full script in agent repository

main() {
    parse_args "$@"
    preflight_checks
    download_agent
    
    if [ "$NO_REGISTER" != "true" ]; then
        register_node
    fi
    
    generate_config
    
    if [ "$NO_SYSTEMD" != "true" ]; then
        install_service
    fi
    
    success "Hydra agent installation complete!"
    info "Node ID: ${NODE_ID}"
    info "Config: ${CONFIG_DIR}/agent.toml"
    
    if [ "$NO_SYSTEMD" != "true" ] && [ "$NO_START" != "true" ]; then
        info "Service status: $(systemctl is-active hydra-agent)"
    fi
}

main "$@"
```

---

## Solutions Architect Considerations

### Scalability

For environments with 50+ nodes, consider:

1. **Parallel Installation**: Use Ansible/Terraform to deploy agents in parallel
2. **Binary Caching**: Host binaries on local artifact server to reduce API load
3. **Registration Token Alternative**: For bulk deployments, pre-create registration tokens

### Security Hardening

1. **TLS Everywhere**: Never disable SSL verification in production
2. **Credential Rotation**: Node API keys should be rotated periodically via `/node/{nodeId}/apikey/refresh`
3. **Least Privilege**: Use `operator` role for routine installations, reserve `admin` for initial setup
4. **Audit Trail**: All registrations are logged with `registeredBy` user

### High Availability

1. **API Redundancy**: If running HA hydra-api, use load balancer URL
2. **Offline Fallback**: Pre-stage binaries for network outages
3. **Credential Backup**: Store credentials.json in secure backup

### Multi-Site Deployment

For geographically distributed homelabs:

```bash
# Site A (primary)
curl -sSL https://hydra-primary.site-a.lan/api/v1/install | bash -s -- ...

# Site B (replica or separate instance)
curl -sSL https://hydra.site-b.lan/api/v1/install | bash -s -- \
  --tags site:b,region:west
```

---

## Related Documentation

- [Node Registration API](https://claude.ai/docs/api/nodes#post-noderegister)
- [Authentication System](https://claude.ai/docs/api/auth)
- [Agent Configuration Reference](https://claude.ai/docs/agent/configuration)
- [RBAC Roles and Permissions](https://claude.ai/docs/security/rbac)