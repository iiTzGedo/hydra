# Hydra Agent Distribution Update - Implementation Plan

> **Generated from**: `Some Updates.md`
> **Date**: 2026-01-14
> **Scope**: Agent distribution, CLI overhaul, sub-accounts, API updates
> **Status**: Planning - Awaiting Implementation

---

## Executive Summary

This plan details the implementation of a major update to the Hydra agent distribution system, shifting from pre-compiled binary distribution to bundled source code distribution with local compilation. Additionally, introduces sub-account hierarchy for user management and a significantly expanded agent CLI.

### Key Changes Overview

| Area | Current State | Proposed State |
|------|---------------|----------------|
| Distribution | Pre-compiled binaries via S3 | Bundled source code (S3 or local storage) |
| Installation | Download binary → systemd setup | Download bundle → build locally → install |
| Agent CLI | 5 commands (run, register, install, uninstall, status) | Full command hierarchy (login, register, config, node, service) |
| User Model | Flat user hierarchy | Sub-account system (admin/operator → family/viewer/agent) |
| Credentials | `/etc/hydra/credentials.json` | `/var/cv/hydra/` credential vault |
| Auth Flow | User OR token registration | User login → agent account → sub-account linkage → API key |

---

## Pre-Implementation Decisions (DECIDED)

### Decision 1: Node ID Migration Strategy ✅

**Issue**: Proposed regex `^[a-z]+([._-][a-z0-9]+){0,2}$` is more restrictive than current `^[a-z0-9][a-z0-9.-]{2,63}$`

| Option | Description | Impact |
|--------|-------------|--------|
| A. Backward Compatible | Keep current regex, proposed only for new nodes | No migration needed, schema inconsistency |
| B. Migration Script | Update API to migrate existing node IDs | Requires downtime, potential data issues |
| **C. Soft Validation** | **Warn on old format, enforce new on creation** | **Gradual adoption, dual validation logic** |

**Decision**: **Option C - Soft validation with warnings**
- Existing nodes with old format continue to work (with deprecation warning in logs)
- New node registrations must use the new stricter format
- Add migration guide for users who want to update existing node IDs

### Decision 2: Build Requirements on Target Machines ✅

**Issue**: Source bundle distribution requires Rust toolchain on target

| Option | Description | Trade-offs |
|--------|-------------|------------|
| A. Full Source Build | Install Rust, build from source | Longer install, ~500MB toolchain, works anywhere |
| **B. Hybrid Distribution** | **Offer both binary and source options** | **More maintenance, user choice** |
| C. Containerized Build | Include minimal build container | Docker dependency, isolated build |

**Decision**: **Option B - Hybrid with `source=local|obs|binary` parameter**
- `source=binary` - Download pre-compiled binary (existing behavior, fastest)
- `source=obs` - Download bundled source from S3/Garage, build locally
- `source=local` - Download bundled source from local storage, build locally
- Users choose based on their environment and preferences

### Decision 3: Agent Account Auto-Creation ✅

**Issue**: When should agent accounts be created?

| Option | Description |
|--------|-------------|
| **A. Explicit Pre-Creation** | **User must run `hydra register` before node registration** |
| B. Auto-Create on Node Register | Agent account auto-created when registering node |
| C. Lazy Creation | Created on first profile submission |

**Decision**: **Option A - Explicit pre-creation**
- Clear separation: `hydra register` (agent account) → `hydra node register` (node)
- Matches the flow described in `Some Updates.md`
- Provides user control over agent credentials before node setup

### Decision 4: Service ID Format Change ✅

**Issue**: Current `svc-<name>-<hash>` vs proposed `svc::<name>::<hash>`

| Option | Description | Impact |
|--------|-------------|--------|
| **A. Keep Current** | **Don't change service ID format** | **No migration, update docs to match** |
| B. Migrate All | Update all service IDs to new format | Breaking change, requires migration |
| C. Version-Based | New format for new profiles only | Dual format support, complexity |

**Decision**: **Option A - Keep current format (`svc-<name>-<hash>`)**
- No breaking changes to existing data
- Update `Some Updates.md` to reflect actual format used
- Service ID format remains: `svc-<sanitized_name>-<4 char hash>`

---

## Implementation Phases

### Phase 0: Schema & Validation Updates
**Priority**: Critical (blocks other phases)
**Estimated Files**: 6-8

### Phase 1: API Updates for Distribution
**Priority**: High
**Estimated Files**: 4-6

### Phase 2: Sub-Account System
**Priority**: High
**Estimated Files**: 8-10

### Phase 3: Agent CLI Overhaul
**Priority**: High
**Estimated Files**: 12-15

### Phase 4: Install Script & Bundling
**Priority**: Medium
**Estimated Files**: 3-4

### Phase 5: Documentation & Testing
**Priority**: Medium
**Estimated Files**: 5-8

---

## Phase 0: Schema & Validation Updates

### 0.1 Update Validation Patterns

**Files to modify**:
- `hydra-api/hydra/api/v1/models/nodes.py`
- `hydra-api/hydra/api/v1/models/auth.py`
- `hydra-agent/src/config/mod.rs`

**Tasks**:
- [ ] Update `nodeId` regex pattern (with backward compatibility mode)
- [ ] Update `tags` validation to `^[a-z]+[_:]?[a-z]+$`
- [ ] Update `networkId` validation to `^[a-z]{1,}[0-9a-z]*([\\-]?net$`
- [ ] Update `ipv4` and `cidr` validation patterns
- [ ] Add validation for profile version format `^E([0-9]|[1-9][0-9]+)-([0-9A-F]\\.){3}[0-9A-F]$`
- [ ] Ensure agent-side validation matches API-side

**Notes**:
- Consider adding a validation utility module for shared patterns
- Document breaking changes for nodeId format in migration notes

### 0.2 Create Shared Validation Module

**Files to create**:
- `hydra-api/hydra/api/v1/core/validators.py`

**Tasks**:
- [ ] Create centralized validation patterns module
- [ ] Add helper functions for pattern matching with deprecation warnings
- [ ] Unit tests for all validation patterns

---

## Phase 1: API Updates for Distribution

### 1.1 Storage Abstraction Layer

**Files to create**:
- `hydra-api/hydra/api/v1/services/storage.py`

**Files to modify**:
- `hydra-api/hydra/api/v1/core/deps.py` (add storage dependency)
- `hydra-api/hydra/api/v1/core/settings.py` (add local storage config)

**Tasks**:
- [ ] Create `StorageService` abstract class with methods:
  - `list_versions() -> List[str]`
  - `get_artifact(version: str, target: Optional[str] = None) -> bytes`
  - `upload_artifact(version: str, data: bytes, target: Optional[str] = None) -> bool`
  - `exists(version: str, target: Optional[str] = None) -> bool`
- [ ] Implement `S3BinaryStorageService` (existing functionality for pre-compiled binaries)
- [ ] Implement `S3BundleStorageService` (new, for source bundles in S3/Garage)
- [ ] Implement `LocalBundleStorageService` (new, for source bundles in local filesystem)
- [ ] Add factory function to select storage based on `source` parameter

**Storage Layout**:
```
# Binary storage (S3/Garage) - existing
agents/{target}/{version}/hydra-agent
  e.g., agents/linux-amd64/1.0.0/hydra-agent

# Bundle storage (S3/Garage or Local)
bundles/{version}/hydra-agent-{version}.zip
  e.g., bundles/1.0.0/hydra-agent-1.0.0.zip
```

**New Environment Variables**:
```
HYDRA_LOCAL_STORAGE_ENABLED=false
HYDRA_LOCAL_STORAGE_PATH=/var/lib/hydra/bundles
```

### 1.2 Update Agent Distribution Endpoints

**Files to modify**:
- `hydra-api/hydra/api/v1/routers/install.py`

**Current endpoints**:
- `GET /install` - Returns bash script
- `GET /install/{binary}` - Download binary (e.g., `hydra-agent-linux-amd64`)
- `GET /install/versions` - List versions

**Updated endpoints**:
- `GET /agent/install?source=local|obs|binary` - Returns install script
- `GET /agent/download?source=local|obs|binary&version=x.y.z` - Download bundle or binary
- `GET /agent/versions?source=local|obs|binary` - List available versions

**Tasks**:
- [ ] Rename router from `install.py` to `agent.py` (or keep as install but change paths)
- [ ] Add `source` query parameter enum: `local`, `obs`, `binary`
- [ ] Add `version` query parameter for specific version download
- [ ] Update download endpoint to handle both:
  - `source=binary` → Return pre-compiled binary (existing behavior)
  - `source=obs|local` → Return bundled source code (zip)
- [ ] Update install script template to handle both workflows (binary vs source build)
- [ ] Add version validation against available versions
- [ ] Ensure backward compatibility (deprecation warnings for old endpoints)

**New Router Structure**:
```python
class StorageSource(str, Enum):
    BINARY = "binary"  # Pre-compiled binaries (default, fastest)
    OBS = "obs"        # Bundled source from S3/Garage
    LOCAL = "local"    # Bundled source from local storage

@router.get("/agent/versions")
async def list_versions(source: StorageSource = StorageSource.BINARY)

@router.get("/agent/download")
async def download_agent(
    source: StorageSource = StorageSource.BINARY,
    version: str = Query(default="latest"),
    target: str = Query(default=None)  # e.g., "linux-amd64" (required for binary)
)

@router.get("/agent/install")
async def get_install_script(
    source: StorageSource = StorageSource.BINARY,
    version: str = Query(default="latest"),
    # ... other existing params
)
```

### 1.3 Update Install Script Template

**Files to modify**:
- `hydra-api/hydra/api/v1/routers/install.py` (embedded script)

**Tasks**:
- [ ] Update script to download bundled zip instead of binary
- [ ] Add extraction step (unzip to `./hydra-agent/`)
- [ ] Add build dependencies check (rustup, cargo)
- [ ] Add local build step (cargo build --release)
- [ ] Update binary installation step to use locally built binary
- [ ] Add cleanup step (remove source after build)
- [ ] Preserve existing functionality for backward compatibility
- [ ] Add `--dev-mode` flag to skip API calls during installation

---

## Phase 2: Sub-Account System

### 2.1 Update User Model

**Files to modify**:
- `hydra-api/hydra/api/v1/models/auth.py`

**Schema additions**:
```python
class SubAccountInfo(BaseModel):
    user_id: str
    role: Role  # agent, viewer, family only
    created_at: datetime

class UserDocument(BaseModel):
    # ... existing fields
    parent_user_id: Optional[str] = None  # If this is a sub-account
    sub_accounts: List[SubAccountInfo] = []  # If this user has sub-accounts
    is_system_account: bool = False  # True for agent accounts
```

**Tasks**:
- [ ] Add `parent_user_id` field to user model
- [ ] Add `sub_accounts` list field to user model
- [ ] Add `is_system_account` boolean field
- [ ] Update MongoDB indexes for sub-account queries
- [ ] Add validation: only admin/operator can have sub-accounts
- [ ] Add validation: max 1 level of sub-accounting
- [ ] Add validation: sub-accounts limited to agent/viewer/family roles

### 2.2 Sub-Account Management Endpoints

**Files to modify**:
- `hydra-api/hydra/api/v1/routers/auth.py`
- `hydra-api/hydra/api/v1/services/auth.py`

**New endpoints**:
```
POST /auth/register/sub/{userId}   - Link existing user as sub-account
GET  /users/{userId}/subs          - List sub-accounts of a user
DELETE /auth/sub/{userId}          - Unlink sub-account
```

**Tasks**:
- [ ] Implement `POST /auth/register/sub/{userId}` endpoint
  - Validate caller is admin or operator
  - Validate target user exists and is family/viewer/agent
  - Validate target user doesn't already have a parent
  - Link user as sub-account
  - Handle `reset_password` option
- [ ] Implement `GET /users/{userId}/subs` endpoint
  - Return list of sub-accounts with role info
  - Only accessible by user themselves or admin
- [ ] Implement `DELETE /auth/sub/{userId}` endpoint
  - Unlink sub-account from parent
  - Validate permissions
- [ ] Update login endpoint to support sub-account parent password
- [ ] Add `is_system_account` check to web login (block agent users)

### 2.3 Agent User Auto-Registration Flow

**Files to modify**:
- `hydra-api/hydra/api/v1/routers/auth.py`
- `hydra-api/hydra/api/v1/services/auth.py`

**Tasks**:
- [ ] Update `/auth/register` to handle `role=agent` specially:
  - Require authenticated admin/operator session OR valid registration token
  - Auto-generate username if not provided (pattern: `agent-[0-9A-Z]{8}`)
  - Auto-generate password if not provided
  - Set `is_system_account = true`
- [ ] Implement auto-linking to parent user after agent registration
- [ ] Return generated credentials in response (for agent storage)

### 2.4 API Key Management for Sub-Accounts

**Files to modify**:
- `hydra-api/hydra/api/v1/routers/auth.py`
- `hydra-api/hydra/api/v1/services/auth.py`

**Tasks**:
- [ ] Update API key creation to include sub-account ownership
- [ ] Allow parent users to list/manage sub-account API keys
- [ ] Add filtering by sub-account in API key list endpoint
- [ ] Set default API key expiration to 90 days for agent accounts
- [ ] Add API key auto-renewal mechanism (or document renewal flow)

### 2.5 Permission Updates for Agent Role

**Files to modify**:
- `hydra-api/hydra/api/v1/core/permissions.py` (or wherever RBAC is defined)

**Tasks**:
- [ ] Verify agent role has permissions:
  - `profiles:create` - Submit profiles
  - `profiles:read` - Read own node profiles
  - `nodes:read` - Read own node
  - `nodes:update` - Update own node (status, tags, etc.)
  - `tokens:create:api` - Create API keys for self
  - `tokens:revoke` - Revoke own API keys
  - `tokens:read` - List own API keys
- [ ] Ensure agent cannot: create users, access other nodes, web login

---

## Phase 3: Agent CLI Overhaul

### 3.1 CLI Structure Refactoring

**Files to modify**:
- `hydra-agent/src/main.rs`

**Files to create**:
- `hydra-agent/src/cli/mod.rs`
- `hydra-agent/src/cli/login.rs`
- `hydra-agent/src/cli/register.rs`
- `hydra-agent/src/cli/config.rs`
- `hydra-agent/src/cli/node.rs`
- `hydra-agent/src/cli/service.rs`

**New CLI Structure**:
```
hydra-agent [GLOBAL OPTIONS] <COMMAND>

Global Options:
  -h, --help              Help documentation
  -a, --aliased           Create 'hydra' alias
  -c, --config <PATH>     Config file path [default: /etc/hydra/agent.toml]
  -m, --mode <MODE>       Operating mode: live, dev [default: live]

Commands:
  login                   Authenticate as admin/operator
  register                Register agent system account
  config                  Manage configuration
  node                    Node management operations
  service                 Service lifecycle management
  run                     Run profile collection (legacy, maps to service run)
  status                  Show agent status
```

**Tasks**:
- [ ] Refactor main.rs to use modular CLI structure
- [ ] Implement global options handling
- [ ] Create command modules with subcommand parsing
- [ ] Preserve backward compatibility for `run`, `status` commands

### 3.2 Login Command Implementation

**Files to create/modify**:
- `hydra-agent/src/cli/login.rs`
- `hydra-agent/src/auth/mod.rs` (new module)

**Command structure**:
```
hydra login [OPTIONS]

Options:
  -h, --help              Help for login
  -r, --refresh           Refresh existing session
  -u, --username <USER>   Username (admin/operator)
  -p, --password <PASS>   Password
```

**Tasks**:
- [ ] Implement login command with username/password
- [ ] Store JWT tokens in credential vault
- [ ] Implement token refresh functionality
- [ ] Add session validation (check if token expired)
- [ ] Secure password input (hide from terminal history)

### 3.3 Register Command Implementation

**Files to create/modify**:
- `hydra-agent/src/cli/register.rs`

**Command structure**:
```
hydra register [OPTIONS]

Options:
  -h, --help              Help for register
  -t, --token <TOKEN>     Registration token (if not logged in)
  -id, --username <ID>    Custom agent ID [default: auto-generated]
  -pwd, --password <PWD>  Custom password [default: auto-generated]
```

**Tasks**:
- [ ] Implement agent registration via logged-in user session
- [ ] Implement registration via token (alternative flow)
- [ ] Auto-generate username matching `^agent-[0-9A-Z]{8}$`
- [ ] Auto-generate secure password
- [ ] Call API to create agent account
- [ ] Handle auto-linking to parent account
- [ ] Auto-login as agent after registration
- [ ] Generate and store API key
- [ ] Store credentials in vault

### 3.4 Config Command Implementation

**Files to create/modify**:
- `hydra-agent/src/cli/config.rs`
- `hydra-agent/src/config/mod.rs`

**Command structure**:
```
hydra config [OPTIONS]

Options:
  -h, --help                   Help for config
  -s, --set <KEY>=<VALUE>      Set config value
  -g, --get <KEY>              Get config value
  -r, --unset <KEY>            Unset/reset config value

Key format: <section>.<key>
Sections: api, node, collection, schedule
```

**Tasks**:
- [ ] Implement `--set` with type-aware parsing:
  - String values: direct assignment
  - Array values: append to array
  - Boolean values: parse true/false
- [ ] Implement `--get` with formatted output
- [ ] Implement `--unset`:
  - Arrays: remove value from array
  - Strings: set to empty
  - Booleans: set to false
- [ ] Add validation for section and key names
- [ ] Persist changes to TOML file
- [ ] Display service restart reminder if running as service
- [ ] For `node.*` changes, trigger API update if in live mode

### 3.5 Node Command Implementation

**Files to create/modify**:
- `hydra-agent/src/cli/node.rs`

**Command structure**:
```
hydra node [COMMAND] [OPTIONS]

Commands:
  register                Register this machine as a node

Options:
  -h, --help              Help for node
  -u, --update <K>=<V>    Update node property (alias for config --set node.<key>)
```

**Tasks**:
- [ ] Implement `node register` command
  - Use config values (node_id, class, type, kind, tags, etc.)
  - Call `POST /nodes/register` API
  - Handle duplicate registration (idempotent)
  - Store registration confirmation
- [ ] Implement `--update` as alias for config updates
- [ ] Add validation for node_id uniqueness
- [ ] Display node status after registration

### 3.6 Service Command Implementation

**Files to create/modify**:
- `hydra-agent/src/cli/service.rs`

**Command structure**:
```
hydra service <COMMAND> [OPTIONS]

Commands:
  activate               Setup systemd/docker service
  start                  Start the service
  stop                   Stop the service
  run                    One-time profile collection

Options:
  -h, --help             Help for service
  -d, --docker           Use Docker instead of systemd (with activate)
  -c, --cron <EXPR>      Setup cron job (e.g., "0 */6 * * *")
```

**Tasks**:
- [ ] Implement `service activate`:
  - Detect init system (systemd, docker)
  - Generate service unit file
  - Enable service
  - Option for Docker-based service
- [ ] Implement `service start`:
  - Start systemd/docker service
  - Verify service is running
- [ ] Implement `service stop`:
  - Stop service gracefully
  - Confirm stopped status
- [ ] Implement `service run`:
  - One-time profile collection
  - Use existing collection logic
- [ ] Implement `--cron` option:
  - Generate crontab entry
  - Register with system cron
  - Document cron expression format

### 3.7 Credential Vault Implementation

**Files to create**:
- `hydra-agent/src/vault/mod.rs`

**Vault location**: `/var/cv/hydra/`
**Files in vault**:
- `.creds` - Agent credentials (username, password)
- `.apikey` - API key details
- `.session` - Current JWT session (for logged-in user)

**Tasks**:
- [ ] Create vault directory structure
- [ ] Implement secure file permissions (600 for files, 700 for directory)
- [ ] Implement credential storage:
  - Encrypt sensitive data at rest (optional, using system keyring)
  - Or use file permissions as primary protection
- [ ] Implement credential retrieval
- [ ] Add environment variable caching for quick access:
  - `HYDRA_API_KEY` - Current API key
  - `HYDRA_AGENT_USER` - Agent username
- [ ] Implement credential rotation (new API key when expired)

### 3.8 Dev Mode Implementation

**Files to modify**:
- `hydra-agent/src/main.rs`
- `hydra-agent/src/api/mod.rs`
- `hydra-agent/src/collectors/mod.rs`

**Tasks**:
- [ ] Add `--mode dev` global option
- [ ] In dev mode:
  - Skip API connectivity requirements
  - Skip agent/node registration
  - Output profiles to local directory (`~/hydra/profiles/`)
  - Log all would-be API calls
- [ ] Useful for testing collectors without API

---

## Phase 4: Install Script & Bundling

### 4.1 Update Deploy Script for Bundling

**Files to modify**:
- `hydra-agent/scripts/deploy-agent.sh`

**Current behavior**: Cross-compile binaries, upload to S3
**New behavior**: Bundle source code, upload to S3 or local storage

**Tasks**:
- [ ] Add `--bundle` mode to create source bundles instead of binaries
- [ ] Create zip archive containing:
  - `src/` - Rust source code
  - `Cargo.toml`, `Cargo.lock` - Dependencies
  - `scripts/install.sh` - Standalone install script
  - `agent.example.toml` - Config template
  - `README.md` - Quick start docs
- [ ] Add `--output-dir` option for local storage deployment
- [ ] Preserve existing binary compilation mode (for backward compatibility)
- [ ] Add versioning to bundle filename: `hydra-agent-{version}.zip`

### 4.2 Create Standalone Install Script

**Files to create**:
- `hydra-agent/scripts/install.sh`

**Script responsibilities**:
1. Detect machine details (OS, arch, distro)
2. Check/install Rust toolchain
3. Build release binary
4. Install to specified directory
5. Setup PATH (optional)
6. Create config and vault directories
7. Generate default config file
8. Optional: Run registration with provided token

**Tasks**:
- [ ] Implement machine detection (uname, lsb_release, etc.)
- [ ] Implement Rust toolchain installation:
  - Check if rustup exists
  - Install rustup if missing
  - Install stable toolchain
  - Add required targets
- [ ] Implement cargo build with release profile
- [ ] Implement binary installation to `--install-dir`
- [ ] Implement PATH setup (bash/zsh profile update)
- [ ] Implement alias creation (`hydra` -> `hydra-agent`)
- [ ] Create `/etc/hydra/` and `/var/cv/hydra/` directories
- [ ] Generate default `agent.toml` from template
- [ ] Handle `--register <token>` option
- [ ] Add cleanup of build artifacts
- [ ] Add error handling and rollback

**Script Options** (matching `Some Updates.md`):
```bash
install.sh [OPTIONS]

Options:
  -v, --version <VER>     Version number for binary manifest (REQUIRED)
  -h, --help              Show help
  -a, --aliased           Create 'hydra' alias
  -g, --global            Add to PATH globally
  -d, --install-dir <DIR> Installation directory [default: /usr/local/bin]
  -c, --config <PATH>     Config file path [default: /etc/hydra/agent.toml]
  -r, --register <TOKEN>  Auto-register with token
```

### 4.3 Ensure Script Consistency

**Tasks**:
- [ ] Verify standalone `install.sh` matches API-generated script behavior
- [ ] Create test suite for installation scenarios:
  - Fresh install on Ubuntu
  - Fresh install on Debian
  - Fresh install on RHEL/CentOS
  - Fresh install on macOS
  - Fresh install on FreeBSD
  - Upgrade from existing installation
- [ ] Document differences between manual and API-driven installation

---

## Phase 5: Documentation & Testing

### 5.1 Update Agent Documentation

**Files to modify**:
- `hydra-agent/README.md`

**Files to create**:
- `docs/agent/Installation-Guide.md`
- `docs/agent/CLI-Reference.md`
- `docs/agent/Cross-Compilation-Guide.md`

**Tasks**:
- [ ] Update README with new installation options
- [ ] Document all CLI commands with examples
- [ ] Add cross-compilation prerequisites:
  - rustup installation
  - Toolchain setup for targets
  - Build commands for each target
- [ ] Add deployment documentation:
  - S3/Garage upload process
  - Local storage setup
- [ ] Add platform-specific guides:
  - Linux (Ubuntu, Debian, RHEL, Arch)
  - macOS (Intel, Apple Silicon)
  - FreeBSD
  - Raspberry Pi (armv7, arm64)

### 5.2 Update API Documentation

**Files to modify**:
- `docs/Hydra API Reference v0.3.0.md`

**Tasks**:
- [ ] Document new `/agent/*` endpoints
- [ ] Document sub-account endpoints
- [ ] Update user schema documentation
- [ ] Add examples for sub-account flows
- [ ] Document storage configuration options

### 5.3 Update Technical Documentation

**Files to modify**:
- `docs/Hydra Technical Documentation v0.3.0.md`

**Tasks**:
- [ ] Update architecture diagrams for new auth flow
- [ ] Document credential vault structure
- [ ] Document distribution model changes
- [ ] Update data flow diagrams

### 5.4 Testing Requirements

**API Tests**:
- [ ] Storage abstraction (local and S3)
- [ ] Sub-account creation and management
- [ ] Agent registration flow
- [ ] API key lifecycle

**Agent Tests**:
- [ ] CLI command parsing
- [ ] Config CRUD operations
- [ ] Vault read/write
- [ ] Service management commands

**Integration Tests**:
- [ ] Full installation flow (manual)
- [ ] Full installation flow (API-driven)
- [ ] Agent registration → node registration → profile submission
- [ ] API key expiration and renewal

---

## Identified Gaps & Improvements

### Items Omitted from `Some Updates.md`

1. **API Key Renewal Mechanism**
   - Document mentions 90-day expiration but not auto-renewal flow
   - **Recommendation**: Implement automatic renewal when key is within 7 days of expiry

2. **Error Handling in CLI**
   - No specification for CLI error messages or exit codes
   - **Recommendation**: Define standard exit codes (0=success, 1=error, 2=auth failure, etc.)

3. **Offline Mode Behavior**
   - `dev` mode mentioned but not fully specified
   - **Recommendation**: Define exactly what works offline and what doesn't

4. **Credential Encryption**
   - Vault mentioned but not encryption strategy
   - **Recommendation**: Use OS keyring where available, file permissions as fallback

5. **Concurrent Installation Handling**
   - What happens if install.sh is run twice simultaneously?
   - **Recommendation**: Add lock file mechanism

6. **Agent Upgrade Path**
   - No mention of how to upgrade existing agents
   - **Recommendation**: Add `hydra upgrade` command or version check in service

7. **Network Timeout Handling**
   - Agent-side behavior when API is unreachable
   - **Recommendation**: Define retry strategy, local queue for profiles

8. **Multi-User System Considerations**
   - Credential vault permissions when multiple users run agent
   - **Recommendation**: Document single-user vs system-wide installation

9. **Windows Support**
   - Explicitly not mentioned, should document as unsupported
   - **Recommendation**: Add "Supported Platforms" section to docs

10. **Agent Health Checks**
    - No endpoint for API to check agent health
    - **Recommendation**: Consider adding heartbeat mechanism

### Strengthening Recommendations

1. **Add Configuration Validation Command**
   ```
   hydra config validate
   ```
   Validates entire config file before service start

2. **Add Diagnostic Command**
   ```
   hydra diagnose
   ```
   Checks: API connectivity, credentials validity, permissions, config syntax

3. **Add Profile Preview Command**
   ```
   hydra profile preview
   ```
   Shows what would be collected without submitting

4. **Implement Structured Logging**
   - Add log levels (debug, info, warn, error)
   - Add `--verbose` flag to CLI
   - Consider log rotation for service mode

5. **Add Backup/Restore for Config**
   - Before config changes, backup previous
   - Allow rollback on failed changes

---

## Implementation Dependencies Graph

```
Phase 0 (Schema)
    │
    ├──► Phase 1 (API Distribution)
    │         │
    │         └──► Phase 4 (Install Script)
    │
    └──► Phase 2 (Sub-Accounts)
              │
              └──► Phase 3 (Agent CLI)
                        │
                        └──► Phase 5 (Docs & Testing)
```

**Critical Path**: Phase 0 → Phase 2 → Phase 3 (sub-accounts must exist for agent CLI auth flow)

**Parallel Work**:
- Phase 1 and Phase 2 can proceed in parallel after Phase 0
- Phase 4 depends only on Phase 1
- Phase 5 should start documentation during other phases

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking change to node ID format | Medium | High | Soft validation with deprecation warnings |
| Rust build failures on diverse platforms | Medium | Medium | Provide pre-built fallback, document requirements |
| Sub-account complexity | Low | High | Thorough testing, clear documentation |
| Credential security vulnerabilities | Low | High | Security review, file permissions audit |
| Backward compatibility issues | Medium | Medium | Version-gated features, deprecation period |

---

## Open Questions for Implementation

1. **Should agent accounts have usernames displayed in web UI?**
   - Currently users visible in admin panel
   - System accounts might clutter UI

2. **What happens to sub-accounts when parent is deleted?**
   - Cascade delete? Orphan? Reassign?

3. **Can registration tokens be used multiple times?**
   - Current: Yes (until expiry)
   - Should agent registration invalidate token?

4. **Should config file changes be atomic?**
   - Write to temp file, then rename
   - Prevents corruption on crash

5. **How to handle agent credentials if vault directory is deleted?**
   - Re-registration required?
   - Can parent re-generate?

---

## Next Steps

1. **Review and approve** this plan with the user
2. **Decide** on pre-implementation decisions (Section: Pre-Implementation Decisions)
3. **Prioritize** phases based on user needs
4. **Begin implementation** starting with Phase 0

---

*This plan will be referenced during implementation. Update as decisions are made and progress is tracked.*
