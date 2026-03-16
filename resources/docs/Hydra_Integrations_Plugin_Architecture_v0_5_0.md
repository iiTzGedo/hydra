# Hydra Integrations & Plugin Architecture

> **Version:** 0.4.0  
> **Last Updated:** 2026-02-13  
> **Status:** Technical Specification — Plugin System Architecture, Cross-Component Integration, All 15 Provider Specifications  
> **Dependencies:** Phase 2 Technical Specification (Agent Architecture, Command Execution, Controls Framework)

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Plugin System Architecture](#2-plugin-system-architecture)
3. [Agent Plugin Awareness & Tier Mapping](#3-agent-plugin-awareness--tier-mapping)
4. [API-Agent Plugin Communication](#4-api-agent-plugin-communication)
5. [Architectural Changes to Hydra](#5-architectural-changes-to-hydra)
6. [Core Integrations — Proxmox VE](#6-core-integrations--proxmox-ve)
7. [Core Integrations — Docker Engine](#7-core-integrations--docker-engine)
8. [Core Integrations — Home Assistant](#8-core-integrations--home-assistant)
9. [Core Integrations — Ansible](#9-core-integrations--ansible)
10. [Core Integrations — Terraform](#10-core-integrations--terraform)
11. [Core Integrations — Prometheus](#11-core-integrations--prometheus)
12. [Default Integrations — Podman](#12-default-integrations--podman)
13. [Default Integrations — UniFi](#13-default-integrations--unifi)
14. [Default Integrations — SNMP](#14-default-integrations--snmp)
15. [Default Integrations — pfSense](#15-default-integrations--pfsense)
16. [Default Integrations — OPNsense](#16-default-integrations--opnsense)
17. [Default Integrations — Traefik](#17-default-integrations--traefik)
18. [Default Integrations — Nginx Proxy Manager](#18-default-integrations--nginx-proxy-manager)
19. [Default Integrations — Pi-hole](#19-default-integrations--pi-hole)
20. [Default Integrations — AdGuard Home](#20-default-integrations--adguard-home)
21. [Default Integrations — TrueNAS](#21-default-integrations--truenas)
22. [Default Integrations — Uptime Kuma](#22-default-integrations--uptime-kuma)
23. [Default Integrations — Tailscale](#23-default-integrations--tailscale)
24. [Default Integrations — IPMI/Redfish](#24-default-integrations--ipmiredfish)
25. [Community Plugin Development](#25-community-plugin-development)
26. [Implementation Roadmap](#26-implementation-roadmap)
27. [Appendices](#27-appendices)

---

## 1. Architecture Overview

### 1.1 What Integrations Are

Integrations in Hydra are **provider-scoped plugins** that extend Hydra's operational surface across all four components (API, Agent, Web, MCP). Each integration represents a single external provider — Docker and Podman are separate plugins, pfSense and OPNsense are separate plugins — because different providers have different APIs, authentication models, failure modes, and operational semantics even when they serve similar functions.

An integration is not a data source. It is a **capability extension** that can touch any or all of six integration surfaces within Hydra.

### 1.2 The Six Integration Touchpoints

Every plugin declares which of these surfaces it extends:

| Touchpoint | What It Does | Example |
|---|---|---|
| **Profile Enrichment** | Adds data to node profiles beyond what the agent collects natively | Docker plugin adds container images, ports, volumes, compose metadata to the host node's profile |
| **Discovery Provider** | Registers as a discovery source alongside network scans | Proxmox plugin reports "these 4 LXCs exist on this cluster" as discovered nodes |
| **Command Provider** | Contributes new `cmd::*` building blocks to the command catalog | Ansible plugin adds `cmd::ansible::run-playbook`, `cmd::ansible::gather-facts` |
| **Execution Handler** | Registers as an alternative execution path for existing commands | Docker plugin routes `cmd::service::restart` through Docker API instead of agent shell |
| **Topology Provider** | Contributes relationship edges to the knowledge graph | Home Assistant plugin provides area→device→entity hierarchy |
| **Workflow Block Provider** | Adds custom workflow block types with specialized lifecycle | Terraform plugin adds `terraform_apply` block with plan→approve→apply lifecycle and state management |

A plugin may implement one touchpoint (Prometheus: Profile Enrichment + Topology only) or all six (Proxmox VE). The plugin manifest declares capabilities, and Hydra only wires up what's declared.

### 1.3 Plugin Classification

| Classification | Ships With Hydra | Active by Default | Maintained By |
|---|---|---|---|
| **Core** | Yes | Available in registry, user enables and configures | Hydra project team |
| **Default** | Yes | Available in registry, user enables and configures | Hydra project team |
| **Community** | No (installed from registry) | User installs, enables, configures | Third-party authors |

The distinction between Core and Default is **depth of integration and testing priority**, not user experience. Core plugins are the integrations most homelabbers will need and that integrate deepest with Hydra's architecture. Default plugins cover common homelab infrastructure but are less tightly coupled.

**Core Plugins (6):** Proxmox VE, Docker Engine, Home Assistant, Ansible, Terraform, Prometheus

**Default Plugins (9):** Podman, UniFi, SNMP, pfSense, OPNsense, Traefik, Nginx Proxy Manager, Pi-hole, AdGuard Home, TrueNAS, Uptime Kuma, Tailscale, IPMI/Redfish

> Note: Default list is 13 plugins. Total: 19 integrations at launch.

### 1.4 Design Principles

**Provider Separation.** Each provider is its own plugin. Docker ≠ Podman. pfSense ≠ OPNsense. Pi-hole ≠ AdGuard Home. Even when providers serve similar functions, their APIs, auth models, error handling, and operational semantics differ enough that a driver-variant pattern would create leaky abstractions.

**Cross-Component by Design.** Plugins are not API-only or agent-only. A single plugin manifest describes behavior across all four Hydra components. The API is the central orchestrator, but agents must be plugin-aware to execute plugin-specific logic locally.

**API as Plugin Authority.** The API maintains the plugin registry, configuration, credentials, and health state. It directs agents on which plugin logic to activate and routes commands through the appropriate plugin execution path.

**Graceful Degradation.** If a plugin's external system is unreachable, Hydra falls back to native capabilities. Docker integration down? Service control falls back to agent shell execution. Proxmox unreachable? VM profiling uses agent-collected data only.

**Tier-Aware Capability.** Not all agent tiers support all plugin capabilities. A lite-tier agent can detect and report that Docker is present, but cannot proxy Docker API calls. The plugin system respects the agent tier matrix.

---

## 2. Plugin System Architecture

### 2.1 Plugin Manifest

Every plugin declares its capabilities, requirements, and behavior through a manifest:

```json
{
  "$id": "hydra:plugin_manifest",
  "type": "object",
  "required": ["pluginId", "name", "version", "provider", "classification", "touchpoints", "requirements"],
  "properties": {
    "pluginId": {
      "type": "string",
      "pattern": "^plg::[a-z0-9-]+$",
      "examples": ["plg::proxmox-ve", "plg::docker", "plg::ansible"],
      "description": "Unique plugin identifier"
    },
    "name": {
      "type": "string",
      "examples": ["Proxmox VE", "Docker Engine"]
    },
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$"
    },
    "provider": {
      "type": "string",
      "description": "The external system this plugin integrates with",
      "examples": ["proxmox-ve", "docker-engine", "home-assistant"]
    },
    "classification": {
      "type": "string",
      "enum": ["core", "default", "community"]
    },
    "category": {
      "type": "string",
      "enum": [
        "virtualization",
        "container-runtime",
        "iot-smart-home",
        "networking",
        "iac-orchestration",
        "reverse-proxy",
        "dns",
        "storage",
        "monitoring",
        "remote-management"
      ]
    },
    "touchpoints": {
      "type": "object",
      "properties": {
        "profileEnrichment": { "type": "boolean", "default": false },
        "discoveryProvider": { "type": "boolean", "default": false },
        "commandProvider": { "type": "boolean", "default": false },
        "executionHandler": { "type": "boolean", "default": false },
        "topologyProvider": { "type": "boolean", "default": false },
        "workflowBlockProvider": { "type": "boolean", "default": false }
      }
    },
    "requirements": {
      "type": "object",
      "properties": {
        "minimumAgentTier": {
          "type": "string",
          "enum": ["none", "lite", "normal", "max"],
          "description": "Minimum agent tier required for agent-side plugin features. 'none' means API-only plugin."
        },
        "agentSideExecution": {
          "type": "boolean",
          "description": "Whether any plugin logic runs on the agent"
        },
        "apiSideExecution": {
          "type": "boolean",
          "description": "Whether plugin logic runs on the API server"
        },
        "localAccess": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Local resources the agent needs access to",
          "examples": [["docker-socket", "filesystem"], ["unix-socket:/var/run/docker.sock"]]
        },
        "networkAccess": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Network endpoints the API or agent needs to reach",
          "examples": [["https://proxmox-host:8006/api2/json"], ["http://homeassistant:8123/api"]]
        }
      }
    },
    "configuration": {
      "type": "object",
      "description": "Schema for plugin-specific configuration",
      "properties": {
        "connectionConfig": {
          "type": "object",
          "description": "How to connect to the external system (URL, credentials, etc.)"
        },
        "featureFlags": {
          "type": "object",
          "description": "Toggle individual plugin capabilities"
        }
      }
    },
    "commands": {
      "type": "array",
      "items": { "$ref": "#/definitions/pluginCommand" },
      "description": "Commands this plugin contributes to the command catalog"
    },
    "workflowBlocks": {
      "type": "array",
      "items": { "$ref": "#/definitions/workflowBlock" },
      "description": "Custom workflow block types this plugin provides"
    }
  }
}
```

### 2.2 Plugin Lifecycle

```
INSTALL → CONFIGURE → ENABLE → ACTIVE → (DISABLE | ERROR)
    ↓          ↓          ↓        ↓           ↓
  Plugin    User sets   Plugin   Plugin     Plugin stops
  files     connection  starts   runs       receiving
  loaded    + feature   health   normally   traffic,
  into      config +    checks   across     agent modules
  registry  credentials          components deactivated
```

**State Transitions:**

| From | To | Trigger | Side Effects |
|---|---|---|---|
| `installed` | `configured` | User provides connection details + credentials | Credentials encrypted and stored |
| `configured` | `enabled` | User enables plugin | API starts health checks, notifies agents of new plugin |
| `enabled` | `active` | First successful health check | Plugin commands appear in catalog, profile enrichment begins |
| `active` | `error` | Health check fails 3 consecutive times | Commands remain in catalog but marked unavailable, fallback paths activate |
| `error` | `active` | Health check succeeds | Full capability restored |
| `active` | `disabled` | User disables plugin | Commands removed from catalog, agent modules deactivated, enrichment stops |
| `disabled` | `enabled` | User re-enables plugin | Full reactivation |

### 2.3 Plugin Registry (MongoDB Collection)

```json
{
  "$id": "hydra:plugin_registry",
  "collection": "plugins",
  "type": "object",
  "required": ["pluginId", "name", "classification", "status"],
  "properties": {
    "_id": { "type": "string" },
    "pluginId": {
      "type": "string",
      "pattern": "^plg::[a-z0-9-]+$"
    },
    "name": { "type": "string" },
    "version": { "type": "string" },
    "classification": {
      "type": "string",
      "enum": ["core", "default", "community"]
    },
    "category": { "type": "string" },
    "status": {
      "type": "string",
      "enum": ["installed", "configured", "enabled", "active", "error", "disabled"]
    },
    "touchpoints": {
      "type": "object",
      "properties": {
        "profileEnrichment": { "type": "boolean" },
        "discoveryProvider": { "type": "boolean" },
        "commandProvider": { "type": "boolean" },
        "executionHandler": { "type": "boolean" },
        "topologyProvider": { "type": "boolean" },
        "workflowBlockProvider": { "type": "boolean" }
      }
    },
    "configuration": {
      "type": "object",
      "description": "Plugin-specific configuration (connection details, feature flags)"
    },
    "credentials": {
      "type": "object",
      "description": "Encrypted credentials for external system access",
      "properties": {
        "encryptedPayload": { "type": "string" },
        "encryptionKeyId": { "type": "string" },
        "credentialType": {
          "type": "string",
          "enum": ["api-key", "username-password", "token", "certificate", "ssh-key"]
        }
      }
    },
    "health": {
      "type": "object",
      "properties": {
        "status": {
          "type": "string",
          "enum": ["healthy", "degraded", "unhealthy", "unknown"]
        },
        "lastCheck": { "type": "string", "format": "date-time" },
        "lastSuccess": { "type": "string", "format": "date-time" },
        "consecutiveFailures": { "type": "integer" },
        "lastError": { "type": ["string", "null"] },
        "responseTimeMs": { "type": "integer" }
      }
    },
    "nodeBindings": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "nodeId": { "type": "string" },
          "enabled": { "type": "boolean" },
          "connectionMethod": {
            "type": "string",
            "enum": ["api-direct", "agent-proxy", "agent-local"]
          },
          "commandRouting": {
            "type": "object",
            "properties": {
              "enabled": { "type": "boolean", "default": false },
              "allowedCommands": {
                "type": "object",
                "additionalProperties": { "type": "boolean" }
              }
            }
          }
        }
      }
    },
    "agentModules": {
      "type": "object",
      "description": "Agent-side module configuration pushed to agents",
      "properties": {
        "detection": {
          "type": "object",
          "description": "How the agent detects this integration locally",
          "properties": {
            "method": {
              "type": "string",
              "enum": ["socket-check", "process-check", "port-check", "file-check", "command-check"]
            },
            "target": { "type": "string" }
          }
        },
        "minimumTier": {
          "type": "string",
          "enum": ["lite", "normal", "max"]
        },
        "capabilities": {
          "type": "object",
          "properties": {
            "lite": { "type": "array", "items": { "type": "string" } },
            "normal": { "type": "array", "items": { "type": "string" } },
            "max": { "type": "array", "items": { "type": "string" } }
          }
        }
      }
    },
    "installedAt": { "type": "string", "format": "date-time" },
    "configuredAt": { "type": ["string", "null"], "format": "date-time" },
    "enabledAt": { "type": ["string", "null"], "format": "date-time" },
    "updatedAt": { "type": "string", "format": "date-time" }
  }
}
```

**Indexes:**

```javascript
db.plugins.createIndexes([
  { key: { "pluginId": 1 }, unique: true },
  { key: { "classification": 1, "status": 1 } },
  { key: { "category": 1 } },
  { key: { "nodeBindings.nodeId": 1 } },
  { key: { "status": 1, "health.status": 1 } }
])
```

### 2.4 Per-Node Plugin Configuration

Plugins bind to specific nodes. The binding is stored in the plugin registry (in `nodeBindings`) and also reflected in the node document for fast lookup:

```json
{
  "nodeId": "docker-host-01",
  "plugins": {
    "plg::docker": {
      "enabled": true,
      "connectionMethod": "agent-local",
      "status": "active",
      "commandRouting": {
        "enabled": true,
        "allowedCommands": {
          "cmd::service::start": true,
          "cmd::service::stop": true,
          "cmd::service::restart": true,
          "cmd::service::logs": true,
          "cmd::service::inspect": true,
          "cmd::docker::pull": true,
          "cmd::docker::compose-up": true,
          "cmd::docker::prune": false,
          "cmd::docker::network-create": false
        }
      },
      "lastEnriched": "2026-02-13T12:00:00Z"
    },
    "plg::prometheus": {
      "enabled": true,
      "connectionMethod": "api-direct",
      "status": "active",
      "commandRouting": {
        "enabled": false
      },
      "exporterPort": 9100
    }
  }
}
```

---

## 3. Agent Plugin Awareness & Tier Mapping

### 3.1 Why Agents Must Be Plugin-Aware

The agent is not a dumb executor. It needs plugin awareness for three reasons:

1. **Local Resource Access.** Some plugins require access to local resources (Docker socket, filesystem paths, IPMI tools) that the API cannot reach remotely. The agent is the only component that can interact with these.

2. **Performance.** Proxying every Docker API call through API→agent→Docker socket adds latency. Agent-side plugin modules can batch operations, cache state, and respond to direct API calls (max tier) with pre-collected data.

3. **Detection.** The agent is the only component that can detect which integrations are available on a node. It checks for Docker sockets, running processes, listening ports, and installed tools, then reports availability to the API.

### 3.2 Plugin Capabilities by Agent Tier

| Plugin Capability | lite | normal | max | Description |
|---|:---:|:---:|:---:|---|
| **Detection & Reporting** | ✓ | ✓ | ✓ | Agent detects if integration is locally available and reports to API during profile submission |
| **Profile Collection** | ✓ | ✓ | ✓ | Agent collects integration-specific profile data (e.g., Docker container list) during scheduled collection |
| **Poll-Based Plugin Commands** | ✗ | ✓ | ✓ | Agent picks up plugin-specific commands during poll cycle and executes locally |
| **Plugin API Proxy** | ✗ | ✗ | ✓ | Agent exposes plugin endpoints on its HTTP server, allowing API to make synchronous plugin calls through the agent |
| **Deep Integration** | ✗ | ✗ | ✓ | Agent maintains persistent connections to local integration APIs (Docker socket watch, metrics proxy) |

### 3.3 Agent Plugin Module Architecture

The agent binary includes plugin modules compiled via Rust feature flags:

```rust
// Agent plugin module structure
pub mod plugins {
    pub mod detection;     // All tiers: detect local integrations
    
    #[cfg(feature = "plugin-docker")]
    pub mod docker;        // Docker-specific collection + execution
    
    #[cfg(feature = "plugin-podman")]
    pub mod podman;        // Podman-specific collection + execution
    
    #[cfg(feature = "plugin-proxmox")]
    pub mod proxmox;       // Proxmox API client (for max-tier on hypervisors)
    
    #[cfg(feature = "plugin-prometheus")]
    pub mod prometheus;    // Prometheus metrics proxy
    
    #[cfg(feature = "plugin-ipmi")]
    pub mod ipmi;          // IPMI/Redfish tool wrappers
    
    pub mod registry;      // Plugin state management
}
```

**Tier-to-Feature Mapping:**

| Feature Flag | lite | normal | max |
|---|:---:|:---:|:---:|
| `plugin-detection` | ✓ | ✓ | ✓ |
| `plugin-docker` | detection only | + collection + poll-exec | + proxy + watch |
| `plugin-podman` | detection only | + collection + poll-exec | + proxy |
| `plugin-proxmox` | detection only | detection only | + API client |
| `plugin-prometheus` | detection only | detection only | + metrics proxy |
| `plugin-ipmi` | detection only | + poll-exec | + direct exec |

### 3.4 Agent Plugin Detection

At startup and during each profile collection cycle, the agent runs detection for all compiled plugin modules:

```rust
pub struct PluginDetection {
    pub plugin_id: String,
    pub available: bool,
    pub method: DetectionMethod,
    pub details: Option<PluginDetails>,
}

pub enum DetectionMethod {
    SocketCheck { path: String, accessible: bool },
    ProcessCheck { name: String, running: bool, pid: Option<u32> },
    PortCheck { port: u16, listening: bool },
    FileCheck { path: String, exists: bool },
    CommandCheck { command: String, available: bool, version: Option<String> },
}

pub struct PluginDetails {
    pub version: Option<String>,
    pub socket_path: Option<String>,
    pub api_endpoint: Option<String>,
    pub status: String,
}
```

**Detection Report (included in every profile submission and health check):**

```json
{
  "plugins": {
    "plg::docker": {
      "available": true,
      "method": "socket-check",
      "details": {
        "socketPath": "/var/run/docker.sock",
        "version": "24.0.7",
        "apiVersion": "1.43",
        "status": "connected"
      }
    },
    "plg::prometheus": {
      "available": true,
      "method": "port-check",
      "details": {
        "port": 9100,
        "version": "node_exporter 1.7.0",
        "status": "listening"
      }
    },
    "plg::ipmi": {
      "available": true,
      "method": "command-check",
      "details": {
        "command": "ipmitool",
        "version": "1.8.19",
        "status": "available"
      }
    },
    "plg::proxmox-ve": {
      "available": false,
      "method": "process-check",
      "details": null
    }
  }
}
```

### 3.5 Agent Plugin Configuration Push

When a plugin is enabled for a node, the API pushes plugin configuration to the agent. How this push happens depends on the tier:

| Tier | Config Delivery Method |
|---|---|
| **lite** | Agent receives plugin config in the response body of its next profile submission (`POST /profiles` response includes `pluginConfig` field) |
| **normal** | Same as lite, plus plugin config included in poll response (`GET /commands/pending` response includes `pluginUpdates` field) |
| **max** | Direct push via `POST /config` to agent's HTTP server (immediate), with poll/submission as fallback |

**Plugin Config Payload (API → Agent):**

```json
{
  "pluginUpdates": [
    {
      "pluginId": "plg::docker",
      "action": "enable",
      "config": {
        "socketPath": "/var/run/docker.sock",
        "collectCompose": true,
        "collectVolumes": true,
        "collectNetworks": true
      },
      "commandRouting": {
        "enabled": true,
        "commands": ["cmd::service::start", "cmd::service::stop", "cmd::service::restart", "cmd::service::logs"]
      }
    },
    {
      "pluginId": "plg::prometheus",
      "action": "enable",
      "config": {
        "exporterPort": 9100,
        "metricsProxy": true
      },
      "commandRouting": {
        "enabled": false
      }
    }
  ]
}
```

---

## 4. API-Agent Plugin Communication

### 4.1 Communication Patterns by Tier

The communication between API and agent for plugin operations follows the same tier-aware dispatch model as command execution, but with plugin-specific routing:

```
Plugin operation request arrives at API
    │
    ├── Does this plugin require agent-side execution?
    │   ├── NO → API executes directly (e.g., calls Proxmox API, queries Prometheus)
    │   │        Agent is not involved.
    │   │
    │   └── YES → Route to agent based on tier
    │       │
    │       ├── Agent tier = "lite"
    │       │   └── Plugin operation type?
    │       │       ├── Profile collection → ✓ Collected during scheduled cycle
    │       │       ├── Detection → ✓ Reported during profile submission
    │       │       └── Command/Proxy → ✗ REJECT: "Agent tier 'lite' does not support
    │       │                             plugin command execution"
    │       │
    │       ├── Agent tier = "normal"
    │       │   └── Plugin operation type?
    │       │       ├── Profile collection → ✓ Collected during scheduled cycle
    │       │       ├── Detection → ✓ Reported during profile submission
    │       │       ├── Command execution → ✓ Queued for next poll cycle
    │       │       │   └── Agent picks up plugin command, executes locally,
    │       │       │       reports result via POST /commands/{id}/result
    │       │       └── Proxy/Watch → ✗ REJECT: "Agent tier 'normal' does not
    │       │                           support plugin proxy"
    │       │
    │       └── Agent tier = "max"
    │           └── Plugin operation type?
    │               ├── Profile collection → ✓ Collected during scheduled cycle
    │               ├── Detection → ✓ Reported during profile submission + health check
    │               ├── Command execution → ✓ Direct call to agent HTTP server
    │               │   ├── SUCCESS → Synchronous result
    │               │   └── FAILURE → Fallback to poll queue
    │               └── Proxy → ✓ Direct call to agent plugin proxy endpoint
    │                   └── e.g., GET /plugins/docker/containers
    │                       Agent proxies to Docker socket, returns result
```

### 4.2 Profile Enrichment Flow

Profile enrichment happens during the agent's collection cycle. The agent knows which plugins are enabled (from config push) and collects plugin-specific data:

```
┌──────────────────────────────────────────────────────┐
│  Agent Profile Collection Cycle                       │
│                                                       │
│  1. Collect native profile data (hardware, network,   │
│     storage, software, services)                      │
│                                                       │
│  2. For each enabled plugin:                          │
│     ├── plg::docker → Collect container list,         │
│     │   images, networks, volumes, compose            │
│     ├── plg::prometheus → Snapshot key metrics        │
│     │   from node_exporter                            │
│     └── plg::ipmi → Collect sensor readings,          │
│         fan speeds, temperatures                      │
│                                                       │
│  3. Submit profile with plugin enrichment sections:   │
│     POST /profiles                                    │
│     {                                                 │
│       "nodeId": "server-01",                          │
│       "hardware": { ... },                            │
│       "network": { ... },                             │
│       "pluginData": {                                 │
│         "plg::docker": { containers: [...] },         │
│         "plg::prometheus": { metrics: {...} },        │
│         "plg::ipmi": { sensors: [...] }               │
│       },                                              │
│       "pluginDetection": {                            │
│         "plg::docker": { available: true, ... },      │
│         "plg::prometheus": { available: true, ... }   │
│       }                                               │
│     }                                                 │
│                                                       │
│  4. API merges plugin data into profile,              │
│     updates node's plugin status                      │
└──────────────────────────────────────────────────────┘
```

**API-Side Profile Enrichment:**

Some plugins enrich profiles from the API side (when the API has direct network access to the external system):

```
┌──────────────────────────────────────────────────────┐
│  API Post-Submission Enrichment                       │
│                                                       │
│  After receiving agent profile submission:             │
│                                                       │
│  1. Check which API-side plugins are enabled for      │
│     this node                                         │
│                                                       │
│  2. For each enabled API-side plugin:                 │
│     ├── plg::proxmox-ve → Call Proxmox API for        │
│     │   VM/LXC allocation, snapshots, backups         │
│     ├── plg::home-assistant → Call HA API for          │
│     │   entity states, device attributes              │
│     └── plg::uptime-kuma → Call UK API for health     │
│         status of services on this node               │
│                                                       │
│  3. Merge API-collected plugin data into stored       │
│     profile                                           │
└──────────────────────────────────────────────────────┘
```

### 4.3 Command Execution Through Plugins

When a command targets a node with an enabled plugin that handles that command:

```python
async def resolve_plugin_execution(node: Node, command: Command) -> ExecutionPath:
    """
    Resolve execution path considering plugins.
    Priority: plugin-via-api → plugin-via-agent-direct → plugin-via-agent-poll 
              → native-agent-direct → native-agent-poll → error
    """
    
    # 1. Check for plugin that handles this command
    for plugin_id, binding in node.plugins.items():
        if not binding.enabled:
            continue
        if not binding.command_routing.enabled:
            continue
        if not binding.command_routing.allowed_commands.get(command.command_id, False):
            continue
        
        plugin = await get_plugin(plugin_id)
        if plugin.health.status not in ("healthy", "degraded"):
            continue
        
        # Determine execution location
        if plugin.requirements.api_side_execution and not plugin.requirements.agent_side_execution:
            # API-only plugin (e.g., Proxmox API call, HA API call)
            return ExecutionPath(
                method="plugin-api-direct",
                plugin=plugin_id,
                fallback=resolve_native_agent_path(node)
            )
        
        elif plugin.requirements.agent_side_execution:
            # Agent-side plugin execution
            agent = node.agent
            
            if agent.tier == "max" and agent.server_status.reachable:
                return ExecutionPath(
                    method="plugin-agent-direct",
                    plugin=plugin_id,
                    endpoint=f"/plugins/{plugin.provider}/execute",
                    fallback=ExecutionPath(
                        method="plugin-agent-poll",
                        plugin=plugin_id,
                        fallback=resolve_native_agent_path(node)
                    )
                )
            elif agent.tier in ("normal", "max"):
                return ExecutionPath(
                    method="plugin-agent-poll",
                    plugin=plugin_id,
                    fallback=resolve_native_agent_path(node)
                )
            else:
                # lite tier — can't execute plugin commands
                continue
    
    # 2. No plugin handles this command, fall back to native execution
    return resolve_native_agent_path(node)
```

### 4.4 Max-Tier Agent Plugin Proxy Endpoints

Max-tier agents expose plugin-specific endpoints on their HTTP server:

```
Agent HTTP Server (max tier)
├── /health                              # Standard health check
├── /execute                             # Standard command execution
├── /probe                               # Network probing
├── /config                              # Configuration push
├── /update                              # Self-update
│
└── /plugins/                            # Plugin proxy namespace
    ├── /plugins/docker/
    │   ├── GET  /containers             # List containers
    │   ├── POST /containers/{id}/exec   # Execute in container
    │   ├── GET  /images                 # List images
    │   ├── GET  /networks               # List networks
    │   └── GET  /compose                # Parse compose files
    │
    ├── /plugins/podman/
    │   ├── GET  /containers
    │   ├── POST /containers/{id}/exec
    │   └── GET  /images
    │
    ├── /plugins/prometheus/
    │   └── GET  /metrics                # Proxy node_exporter metrics
    │
    └── /plugins/ipmi/
        ├── GET  /sensors                # Read sensor data
        └── POST /power                  # Power control (on/off/cycle)
```

These endpoints are authenticated with the same API-to-agent secret used for standard agent server calls. The agent validates that the requesting API has the correct secret before proxying to local resources.

### 4.5 Plugin Command in Poll-Based Execution

For normal-tier agents, plugin commands follow the standard poll cycle with plugin-specific metadata:

**API queues plugin command:**

```json
{
  "executionId": "exec_abc123",
  "commandId": "cmd::docker::pull",
  "plugin": "plg::docker",
  "parameters": {
    "image": "nginx:latest"
  },
  "target": {
    "nodeId": "docker-host-01"
  },
  "executionContext": {
    "type": "plugin-agent",
    "pluginId": "plg::docker",
    "pluginVersion": "1.0.0"
  }
}
```

**Agent picks up during poll, recognizes plugin context:**

```rust
async fn execute_plugin_command(cmd: &QueuedCommand) -> CommandResult {
    let plugin_id = &cmd.execution_context.plugin_id;
    
    match plugin_id.as_str() {
        "plg::docker" => {
            let docker = plugins::docker::get_client()?;
            match cmd.command_id.as_str() {
                "cmd::docker::pull" => docker.pull_image(&cmd.parameters).await,
                "cmd::docker::compose-up" => docker.compose_up(&cmd.parameters).await,
                "cmd::docker::prune" => docker.prune(&cmd.parameters).await,
                _ => Err(PluginError::UnsupportedCommand(cmd.command_id.clone()))
            }
        },
        "plg::podman" => {
            let podman = plugins::podman::get_client()?;
            // Similar dispatch
        },
        _ => Err(PluginError::UnknownPlugin(plugin_id.clone()))
    }
}
```

---

## 5. Architectural Changes to Hydra

Implementing the plugin system requires changes across all four Hydra components plus the database layer.

### 5.1 Database Changes

**New Collections:**

| Collection | Purpose |
|---|---|
| `plugins` | Plugin registry — configuration, status, health, node bindings |
| `plugin_commands` | Plugin-contributed commands — separate from core commands to allow hot-loading when plugins enable/disable |
| `plugin_workflow_blocks` | Plugin-contributed workflow block type definitions |

**Modified Collections:**

| Collection | Changes |
|---|---|
| `nodes` | Add `plugins` field (per-node plugin bindings, see §2.4) |
| `profiles` | Add `pluginData` field (plugin-enriched profile sections) and `pluginDetection` field |
| `executions` | Add `executionContext.pluginId` and `executionContext.pluginVersion` for plugin-routed executions |
| `commands` | Add `source` field (`"core"` or `"plugin::<pluginId>"`) to distinguish core vs plugin-contributed commands |

**New Indexes:**

```javascript
// Plugin commands — fast lookup when building command palette
db.plugin_commands.createIndexes([
  { key: { "pluginId": 1, "commandId": 1 }, unique: true },
  { key: { "commandId": 1 }, unique: true },
  { key: { "pluginId": 1, "status": 1 } }
])

// Plugin workflow blocks
db.plugin_workflow_blocks.createIndexes([
  { key: { "pluginId": 1, "blockType": 1 }, unique: true },
  { key: { "blockType": 1 }, unique: true }
])
```

### 5.2 hydra-api Changes

```
hydra-api/
├── src/
│   ├── plugins/                        # NEW: Plugin system
│   │   ├── __init__.py
│   │   ├── registry.py                 # Plugin lifecycle management
│   │   ├── loader.py                   # Plugin manifest loading + validation
│   │   ├── health.py                   # Plugin health check scheduler
│   │   ├── router.py                   # Plugin execution path resolution
│   │   ├── config_push.py              # Push plugin config to agents
│   │   ├── enrichment.py               # API-side profile enrichment coordinator
│   │   │
│   │   ├── drivers/                    # Plugin driver implementations
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # Abstract base driver
│   │   │   ├── proxmox_ve.py           # Proxmox VE driver
│   │   │   ├── docker.py               # Docker Engine driver (API-side)
│   │   │   ├── home_assistant.py       # Home Assistant driver
│   │   │   ├── ansible.py              # Ansible driver
│   │   │   ├── terraform.py            # Terraform driver
│   │   │   ├── prometheus.py           # Prometheus driver
│   │   │   ├── podman.py               # Podman driver (API-side)
│   │   │   ├── unifi.py                # UniFi driver
│   │   │   ├── snmp.py                 # SNMP driver
│   │   │   ├── pfsense.py              # pfSense driver
│   │   │   ├── opnsense.py             # OPNsense driver
│   │   │   ├── traefik.py              # Traefik driver
│   │   │   ├── nginx_proxy_manager.py  # NPM driver
│   │   │   ├── pihole.py               # Pi-hole driver
│   │   │   ├── adguard_home.py         # AdGuard Home driver
│   │   │   ├── truenas.py              # TrueNAS driver
│   │   │   ├── uptime_kuma.py          # Uptime Kuma driver
│   │   │   ├── tailscale.py            # Tailscale driver
│   │   │   └── ipmi_redfish.py         # IPMI/Redfish driver
│   │   │
│   │   └── api/                        # Plugin API endpoints
│   │       ├── __init__.py
│   │       └── routes.py               # CRUD + health + test endpoints
│   │
│   ├── commands/
│   │   ├── registry.py                 # MODIFIED: Query plugin_commands alongside core commands
│   │   └── resolver.py                 # MODIFIED: Plugin-aware execution path resolution
│   │
│   ├── profiles/
│   │   └── service.py                  # MODIFIED: Accept and store pluginData from agent submissions
│   │
│   └── discovery/
│       └── providers.py                # MODIFIED: Query plugin discovery providers
```

**API Plugin Base Driver:**

```python
from abc import ABC, abstractmethod
from typing import Optional
from enum import Enum

class PluginTouchpoint(Enum):
    PROFILE_ENRICHMENT = "profileEnrichment"
    DISCOVERY_PROVIDER = "discoveryProvider"
    COMMAND_PROVIDER = "commandProvider"
    EXECUTION_HANDLER = "executionHandler"
    TOPOLOGY_PROVIDER = "topologyProvider"
    WORKFLOW_BLOCK_PROVIDER = "workflowBlockProvider"

class PluginDriver(ABC):
    """Base class for all plugin drivers on the API side."""
    
    plugin_id: str
    touchpoints: set[PluginTouchpoint]
    
    @abstractmethod
    async def connect(self, config: dict, credentials: dict) -> bool:
        """Establish connection to external system."""
        pass
    
    @abstractmethod
    async def health_check(self) -> dict:
        """Return health status. Must complete within 10 seconds."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up resources."""
        pass
    
    # ── Touchpoint methods (implement based on declared touchpoints) ──
    
    async def enrich_profile(self, node_id: str, profile: dict) -> dict:
        """Profile Enrichment: Return additional profile data from external system."""
        raise NotImplementedError(f"{self.plugin_id} does not support profile enrichment")
    
    async def discover_nodes(self) -> list[dict]:
        """Discovery Provider: Return list of discovered nodes."""
        raise NotImplementedError(f"{self.plugin_id} does not support discovery")
    
    def get_commands(self) -> list[dict]:
        """Command Provider: Return list of commands this plugin contributes."""
        raise NotImplementedError(f"{self.plugin_id} does not provide commands")
    
    async def execute_command(self, command_id: str, target: dict, params: dict) -> dict:
        """Execution Handler: Execute a command through the external system's API."""
        raise NotImplementedError(f"{self.plugin_id} does not handle execution")
    
    async def get_topology_edges(self, node_id: str) -> list[dict]:
        """Topology Provider: Return relationship edges for the knowledge graph."""
        raise NotImplementedError(f"{self.plugin_id} does not provide topology")
    
    def get_workflow_blocks(self) -> list[dict]:
        """Workflow Block Provider: Return custom workflow block type definitions."""
        raise NotImplementedError(f"{self.plugin_id} does not provide workflow blocks")
```

### 5.3 hydra-agent Changes

```
hydra-agent/
├── src/
│   ├── plugins/                        # NEW: Plugin system
│   │   ├── mod.rs                      # Plugin module coordinator
│   │   ├── detection.rs                # Integration detection (all tiers)
│   │   ├── registry.rs                 # Local plugin state management
│   │   ├── config.rs                   # Plugin config received from API
│   │   │
│   │   ├── docker/                     # Docker plugin module
│   │   │   ├── mod.rs
│   │   │   ├── detection.rs            # Socket check, version detection
│   │   │   ├── collector.rs            # Profile data collection
│   │   │   ├── executor.rs             # Command execution via Docker API
│   │   │   └── proxy.rs                # HTTP proxy endpoints (max tier)
│   │   │
│   │   ├── podman/                     # Podman plugin module
│   │   │   ├── mod.rs
│   │   │   ├── detection.rs
│   │   │   ├── collector.rs
│   │   │   ├── executor.rs
│   │   │   └── proxy.rs
│   │   │
│   │   ├── prometheus/                 # Prometheus plugin module
│   │   │   ├── mod.rs
│   │   │   ├── detection.rs            # Check for node_exporter
│   │   │   ├── collector.rs            # Snapshot metrics at collection time
│   │   │   └── proxy.rs               # Metrics proxy (max tier)
│   │   │
│   │   └── ipmi/                       # IPMI plugin module
│   │       ├── mod.rs
│   │       ├── detection.rs            # Check for ipmitool/ipmi-sensors
│   │       ├── collector.rs            # Sensor readings
│   │       └── executor.rs             # Power control commands
│   │
│   ├── server/
│   │   ├── mod.rs
│   │   └── handlers.rs                 # MODIFIED: Add /plugins/* routes for max tier
│   │
│   ├── collector/
│   │   └── mod.rs                      # MODIFIED: Call plugin collectors during cycle
│   │
│   └── poller/
│       └── mod.rs                      # MODIFIED: Handle plugin commands in poll response
```

**Key Agent Changes:**

1. **Collection cycle modification:** After native profile collection, iterate enabled plugin modules and call their collectors. Plugin data is included in the profile submission under `pluginData`.

2. **Poll response handling:** When the agent polls for pending commands, it now inspects `executionContext` for plugin commands and routes to the appropriate plugin executor.

3. **Plugin config management:** The agent stores plugin configuration received from the API in its local config. When an API push updates plugin config, the agent activates/deactivates plugin modules accordingly.

4. **HTTP server routes (max tier):** The axum router is extended with `/plugins/{provider}/*` routes that proxy to local integration APIs.

### 5.4 hydra-web Changes

```
hydra-web/
├── src/
│   ├── features/
│   │   ├── plugins/                    # NEW: Plugin management UI
│   │   │   ├── PluginRegistry.tsx      # Browse available plugins
│   │   │   ├── PluginConfig.tsx        # Configure a plugin (connection, credentials)
│   │   │   ├── PluginHealth.tsx        # Health dashboard for active plugins
│   │   │   ├── PluginNodeBindings.tsx  # Manage which nodes use which plugins
│   │   │   └── PluginCommandRouting.tsx # Fine-grained command routing config
│   │   │
│   │   ├── command-center/
│   │   │   ├── CommandPalette.tsx      # MODIFIED: Include plugin-contributed commands
│   │   │   ├── WorkflowCanvas.tsx      # MODIFIED: Support plugin workflow blocks
│   │   │   └── blocks/
│   │   │       ├── TerraformBlock.tsx  # Custom UI for Terraform workflow block
│   │   │       └── AnsibleBlock.tsx    # Custom UI for Ansible workflow block
│   │   │
│   │   ├── nodes/
│   │   │   └── NodeDetail.tsx          # MODIFIED: Show plugin-enriched data
│   │   │
│   │   └── topology/
│   │       └── TopologyGraph.tsx       # MODIFIED: Include plugin-provided edges
```

### 5.5 hydra-mcp Changes

```
hydra-mcp/
├── src/
│   ├── tools/
│   │   ├── plugin_tools.py            # NEW: Dynamic tool generation from plugin commands
│   │   │   # When a plugin is enabled, its commands become available as MCP tools
│   │   │   # e.g., plg::docker enabled → cmd::docker::pull → MCP tool docker_pull
│   │   │
│   │   ├── discovery.py               # MODIFIED: Include plugin discovery providers
│   │   └── topology.py                # MODIFIED: Include plugin topology edges
│   │
│   ├── resources/
│   │   └── plugin_resources.py        # NEW: Plugin data as MCP resources
│   │       # e.g., docker://containers, prometheus://metrics, ha://entities
```

### 5.6 API Endpoints for Plugin Management

```
# Plugin Registry
GET    /plugins                         # List all available plugins (core + default + installed community)
GET    /plugins/{pluginId}              # Get plugin details + status + health
PUT    /plugins/{pluginId}              # Update plugin configuration
POST   /plugins/{pluginId}/enable       # Enable plugin
POST   /plugins/{pluginId}/disable      # Disable plugin
POST   /plugins/{pluginId}/test         # Test connection to external system
GET    /plugins/{pluginId}/health       # Detailed health check

# Plugin-Node Bindings
GET    /plugins/{pluginId}/nodes        # List nodes bound to this plugin
POST   /plugins/{pluginId}/nodes        # Bind plugin to a node
DELETE /plugins/{pluginId}/nodes/{nodeId} # Unbind plugin from node
PUT    /plugins/{pluginId}/nodes/{nodeId} # Update node-specific plugin config

# Plugin Commands (auto-populated when plugin is active)
GET    /plugins/{pluginId}/commands     # List commands contributed by this plugin

# Community Plugin Management
POST   /plugins/install                 # Install community plugin from registry
DELETE /plugins/{pluginId}/uninstall    # Uninstall community plugin

# Node-centric view
GET    /nodes/{nodeId}/plugins          # List plugins active on this node
```

---

## 6. Core Integrations — Proxmox VE

### 6.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::proxmox-ve` |
| **Category** | Virtualization |
| **Classification** | Core |
| **External System** | Proxmox Virtual Environment (PVE) |
| **API** | Proxmox REST API (`/api2/json`) |
| **Authentication** | API Token (PVEAPIToken) or Username/Password |
| **Direction** | Bidirectional |
| **Minimum Agent Tier** | `lite` (detection), `max` (local API proxy on hypervisor) |
| **Primary Execution** | API-direct (API calls Proxmox REST API directly) |

### 6.2 Touchpoint Matrix

| Touchpoint | Supported | Details |
|---|---|---|
| Profile Enrichment | ✓ | VM/LXC allocation, snapshots, backup schedules, resource limits, cluster status |
| Discovery Provider | ✓ | VMs and LXCs on cluster nodes, with current state |
| Command Provider | ✓ | `cmd::proxmox::create-lxc`, `cmd::proxmox::create-vm`, `cmd::proxmox::migrate`, `cmd::proxmox::snapshot`, `cmd::proxmox::backup`, `cmd::proxmox::clone`, `cmd::proxmox::resize-disk` |
| Execution Handler | ✓ | Routes `cmd::node::reboot`, `cmd::node::shutdown`, `cmd::node::suspend` for VMs/LXCs through PVE API |
| Topology Provider | ✓ | Host→VM/LXC parent-child relationships, cluster membership, storage mapping |
| Workflow Block Provider | ✗ | — |

### 6.3 Configuration Schema

```json
{
  "pluginId": "plg::proxmox-ve",
  "configuration": {
    "connection": {
      "host": "proxmox-01.home.lan",
      "port": 8006,
      "verifyTls": true,
      "tlsCaCert": "/etc/hydra/certs/proxmox-ca.pem"
    },
    "credentials": {
      "type": "api-token",
      "tokenId": "hydra@pve!hydra-api",
      "tokenSecret": "encrypted::..."
    },
    "features": {
      "discovery": true,
      "profileEnrichment": true,
      "commandExecution": true,
      "backupMonitoring": true,
      "haMonitoring": true
    },
    "polling": {
      "healthCheckIntervalSeconds": 60,
      "discoveryRefreshIntervalSeconds": 300
    }
  }
}
```

### 6.4 Profile Enrichment Data

When enabled for a Proxmox hypervisor node, the API enriches the node's profile with:

```json
{
  "pluginData": {
    "plg::proxmox-ve": {
      "cluster": {
        "name": "homelab",
        "nodes": ["proxmox-01", "proxmox-02"],
        "quorate": true,
        "version": "8.1.3"
      },
      "guests": [
        {
          "vmid": 100,
          "type": "lxc",
          "name": "pihole",
          "status": "running",
          "cpus": 2,
          "memoryMb": 512,
          "diskGb": 8,
          "template": false,
          "snapshots": ["pre-update-2026-01-15"],
          "backupSchedule": "daily-02:00",
          "lastBackup": "2026-02-12T02:00:00Z",
          "tags": ["dns", "network"],
          "nodeId": "pihole-lxc"
        }
      ],
      "storage": [
        {
          "name": "local-lvm",
          "type": "lvmthin",
          "totalGb": 500,
          "usedGb": 200,
          "availableGb": 300,
          "content": ["rootdir", "images"]
        }
      ],
      "ha": {
        "enabled": true,
        "groups": [
          {
            "name": "critical-services",
            "members": [100, 101, 102],
            "restrictedNodes": ["proxmox-01"]
          }
        ]
      }
    }
  }
}
```

### 6.5 Discovery Provider

The Proxmox plugin registers as a discovery source. When discovery runs, the API queries Proxmox for all VMs and LXCs:

```python
async def discover_nodes(self) -> list[dict]:
    nodes = await self.api.get("/cluster/resources", type="vm")
    
    discovered = []
    for vm in nodes:
        discovered.append({
            "source": "plg::proxmox-ve",
            "ip": vm.get("ip"),  # From QEMU guest agent or LXC network config
            "type": "logical",
            "kind": "lxc" if vm["type"] == "lxc" else "vm",
            "displayName": vm["name"],
            "parentNodeId": vm["node"],  # Proxmox host
            "metadata": {
                "vmid": vm["vmid"],
                "status": vm["status"],
                "template": vm.get("template", False)
            },
            "confidence": "high",
            "eligibility": {
                "agentInstallable": vm["status"] == "running" and vm["type"] in ("qemu", "lxc"),
                "reason": None if vm["status"] == "running" else "VM/LXC is not running"
            }
        })
    
    return discovered
```

### 6.6 Commands

| Command ID | Description | Parameters | Target | Dangerous | Role |
|---|---|---|---|---|---|
| `cmd::proxmox::create-lxc` | Create new LXC container | `template`, `hostname`, `cores`, `memory`, `storage`, `network`, `password` | Proxmox host node | Yes | admin |
| `cmd::proxmox::create-vm` | Create new QEMU VM | `iso`, `name`, `cores`, `memory`, `storage`, `network` | Proxmox host node | Yes | admin |
| `cmd::proxmox::migrate` | Live-migrate VM/LXC to another host | `vmid`, `targetNode`, `online` | Source Proxmox host | Yes | admin |
| `cmd::proxmox::snapshot` | Create VM/LXC snapshot | `vmid`, `name`, `description`, `includeRam` | Proxmox host | No | operator |
| `cmd::proxmox::backup` | Trigger immediate backup | `vmid`, `storage`, `mode`, `compress` | Proxmox host | No | operator |
| `cmd::proxmox::clone` | Clone VM/LXC | `vmid`, `newVmid`, `name`, `full`, `targetStorage` | Proxmox host | Yes | admin |
| `cmd::proxmox::resize-disk` | Resize VM/LXC disk | `vmid`, `disk`, `size` | Proxmox host | Yes | admin |

**Execution Handler — Rerouting Core Commands:**

When `cmd::node::reboot` or `cmd::node::shutdown` targets a VM or LXC that is a child of a Proxmox host, the plugin intercepts and routes through PVE API:

```python
async def execute_command(self, command_id: str, target: dict, params: dict) -> dict:
    if command_id == "cmd::node::reboot":
        vmid = await self.resolve_vmid(target["nodeId"])
        vm_type = await self.resolve_vm_type(vmid)
        
        if vm_type == "lxc":
            result = await self.api.post(f"/nodes/{self.host}/lxc/{vmid}/status/reboot")
        else:
            result = await self.api.post(f"/nodes/{self.host}/qemu/{vmid}/status/reboot")
        
        return {
            "success": True,
            "output": f"Reboot initiated for VMID {vmid} via Proxmox API",
            "executionMethod": "plugin-api-direct",
            "plugin": "plg::proxmox-ve"
        }
```

### 6.7 Topology Edges

```json
[
  {
    "source": "proxmox-01",
    "target": "pihole-lxc",
    "relationship": "hosts",
    "metadata": { "vmid": 100, "type": "lxc" }
  },
  {
    "source": "proxmox-01",
    "target": "proxmox-02",
    "relationship": "cluster-member",
    "metadata": { "clusterName": "homelab" }
  },
  {
    "source": "proxmox-01",
    "target": "local-lvm",
    "relationship": "provides-storage",
    "metadata": { "type": "lvmthin" }
  }
]
```

### 6.8 Tier-Specific Behavior

| Tier | Behavior |
|---|---|
| **lite** | Agent on hypervisor detects Proxmox is running (process check for `pveproxy`). Reports detection to API. All plugin operations are API-direct (API calls PVE REST API). |
| **normal** | Same as lite. Proxmox plugin operations are API-side, so normal tier adds no extra capability beyond detection. |
| **max** | Agent can optionally proxy PVE API calls through its HTTP server, useful when API cannot reach PVE directly (network segmentation). Agent exposes `/plugins/proxmox-ve/api/*` that proxies to local `https://localhost:8006/api2/json/*`. |

---

## 7. Core Integrations — Docker Engine

### 7.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::docker` |
| **Category** | Container Runtime |
| **Classification** | Core |
| **External System** | Docker Engine |
| **API** | Docker Engine API via Unix socket (`/var/run/docker.sock`) or TCP |
| **Authentication** | Socket permissions (local), TLS client certs (remote) |
| **Direction** | Bidirectional |
| **Minimum Agent Tier** | `lite` (detection + collection), `normal` (+ command execution), `max` (+ socket proxy) |
| **Primary Execution** | Agent-local (agent accesses Docker socket directly) |

### 7.2 Touchpoint Matrix

| Touchpoint | Supported | Details |
|---|---|---|
| Profile Enrichment | ✓ | Container images, ports, volumes, networks, compose projects, resource limits |
| Discovery Provider | ✓ | Running and stopped containers as service entities |
| Command Provider | ✓ | `cmd::docker::pull`, `cmd::docker::compose-up`, `cmd::docker::compose-down`, `cmd::docker::prune`, `cmd::docker::network-create`, `cmd::docker::volume-create`, `cmd::docker::exec` |
| Execution Handler | ✓ | Routes `cmd::service::start`, `cmd::service::stop`, `cmd::service::restart`, `cmd::service::logs`, `cmd::service::inspect` for Docker containers |
| Topology Provider | ✓ | Host→container, Docker network→container membership, volume→container |
| Workflow Block Provider | ✗ | — |

### 7.3 Configuration Schema

```json
{
  "pluginId": "plg::docker",
  "configuration": {
    "connection": {
      "method": "socket",
      "socketPath": "/var/run/docker.sock",
      "tcpHost": null,
      "tcpPort": null,
      "tlsEnabled": false
    },
    "features": {
      "collectImages": true,
      "collectVolumes": true,
      "collectNetworks": true,
      "collectCompose": true,
      "collectResourceLimits": true,
      "collectHealthStatus": true
    }
  }
}
```

### 7.4 Profile Enrichment Data

```json
{
  "pluginData": {
    "plg::docker": {
      "version": "24.0.7",
      "apiVersion": "1.43",
      "rootDir": "/var/lib/docker",
      "storageDriver": "overlay2",
      "containers": [
        {
          "id": "a1b2c3d4",
          "name": "nginx",
          "image": "nginx:1.25",
          "imageId": "sha256:...",
          "status": "running",
          "created": "2026-01-15T10:00:00Z",
          "ports": [
            { "hostPort": 80, "containerPort": 80, "protocol": "tcp" },
            { "hostPort": 443, "containerPort": 443, "protocol": "tcp" }
          ],
          "volumes": [
            { "hostPath": "/data/nginx/conf", "containerPath": "/etc/nginx", "mode": "ro" }
          ],
          "networks": ["frontend", "backend"],
          "labels": { "com.docker.compose.project": "webstack" },
          "resources": {
            "cpuShares": 1024,
            "memoryLimitMb": 256,
            "memoryUsageMb": 45
          },
          "health": {
            "status": "healthy",
            "lastCheck": "2026-02-13T12:00:00Z"
          },
          "restartPolicy": "unless-stopped",
          "serviceId": "svc::docker::nginx"
        }
      ],
      "images": [
        {
          "id": "sha256:...",
          "repoTags": ["nginx:1.25"],
          "sizeMb": 142,
          "created": "2026-01-10T00:00:00Z"
        }
      ],
      "networks": [
        {
          "name": "frontend",
          "driver": "bridge",
          "subnet": "172.18.0.0/16",
          "containers": ["nginx", "traefik"]
        }
      ],
      "volumes": [
        {
          "name": "nginx_conf",
          "driver": "local",
          "mountpoint": "/var/lib/docker/volumes/nginx_conf/_data",
          "usedByContainers": ["nginx"]
        }
      ],
      "compose": [
        {
          "project": "webstack",
          "file": "/opt/stacks/webstack/docker-compose.yml",
          "services": ["nginx", "app", "redis"],
          "status": "running"
        }
      ]
    }
  }
}
```

### 7.5 Commands

| Command ID | Description | Parameters | Target | Dangerous | Role |
|---|---|---|---|---|---|
| `cmd::docker::pull` | Pull Docker image | `image`, `tag` | Docker host node | No | operator |
| `cmd::docker::compose-up` | Start compose project | `projectPath`, `services`, `detach`, `build` | Docker host node | No | operator |
| `cmd::docker::compose-down` | Stop compose project | `projectPath`, `removeVolumes`, `removeOrphans` | Docker host node | Yes | operator |
| `cmd::docker::prune` | Remove unused containers, images, volumes | `all`, `volumes`, `filter` | Docker host node | Yes | admin |
| `cmd::docker::network-create` | Create Docker network | `name`, `driver`, `subnet`, `labels` | Docker host node | No | admin |
| `cmd::docker::volume-create` | Create Docker volume | `name`, `driver`, `labels` | Docker host node | No | admin |
| `cmd::docker::exec` | Execute command in running container | `containerId`, `command`, `user`, `workdir` | Docker host node | Yes | admin |

### 7.6 Execution Handler — Service Commands

Docker plugin intercepts service control commands for Docker-managed services:

```python
# OS-aware command translation for Docker services
DOCKER_COMMAND_MAP = {
    "cmd::service::start":   "docker start {containerId}",
    "cmd::service::stop":    "docker stop {containerId}",
    "cmd::service::restart": "docker restart {containerId}",
    "cmd::service::logs":    "docker logs {containerId} --tail {lines}",
    "cmd::service::inspect": "docker inspect {containerId}",
}
```

The agent determines whether a service is Docker-managed by checking the `svc::docker::*` prefix on the serviceId. If the Docker plugin is enabled with command routing for the target service command, the agent executes through the Docker API/CLI instead of systemd/shell.

### 7.7 Tier-Specific Behavior

| Tier | Behavior |
|---|---|
| **lite** | Detects Docker (socket check `/var/run/docker.sock`). Collects container list, images, networks, volumes during profile collection cycle via Docker CLI commands. Reports to API. |
| **normal** | Everything in lite. Picks up Docker commands from poll queue, executes via Docker CLI/API locally, reports results. |
| **max** | Everything in normal. Exposes `/plugins/docker/*` proxy endpoints on agent HTTP server. API can make synchronous calls: `GET /plugins/docker/containers`, `POST /plugins/docker/containers/{id}/restart`. Can maintain Docker event stream for real-time container state changes. |

---

## 8. Core Integrations — Home Assistant

### 8.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::home-assistant` |
| **Category** | IoT & Smart Home |
| **Classification** | Core |
| **External System** | Home Assistant |
| **API** | Home Assistant REST API (`/api/*`) + WebSocket API |
| **Authentication** | Long-lived access token |
| **Direction** | Bidirectional |
| **Minimum Agent Tier** | `none` (API-only plugin — API calls HA directly) |
| **Primary Execution** | API-direct |

### 8.2 Touchpoint Matrix

| Touchpoint | Supported | Details |
|---|---|---|
| Profile Enrichment | ✓ | Entity states, device attributes, area assignments |
| Discovery Provider | ✓ | All HA-managed devices and entities as IoT nodes |
| Command Provider | ✓ | `cmd::ha::turn-on`, `cmd::ha::turn-off`, `cmd::ha::toggle`, `cmd::ha::set-value`, `cmd::ha::trigger-automation`, `cmd::ha::trigger-scene`, `cmd::ha::set-hvac-mode` |
| Execution Handler | ✓ | Routes all `cmd::iot::*` commands through HA API |
| Topology Provider | ✓ | Area→device→entity hierarchy |
| Workflow Block Provider | ✗ | — |

### 8.3 Configuration Schema

```json
{
  "pluginId": "plg::home-assistant",
  "configuration": {
    "connection": {
      "url": "http://homeassistant.local:8123",
      "verifyTls": false
    },
    "credentials": {
      "type": "token",
      "longLivedToken": "encrypted::..."
    },
    "features": {
      "discovery": true,
      "profileEnrichment": true,
      "commandExecution": true,
      "websocketEvents": false,
      "areaMapping": true
    },
    "filters": {
      "includeDomains": ["light", "switch", "climate", "sensor", "binary_sensor", "media_player", "lock", "cover", "fan"],
      "excludeEntities": [],
      "includeAreas": []
    }
  }
}
```

### 8.4 Profile Enrichment Data

Home Assistant enriches IoT node profiles with entity state data:

```json
{
  "pluginData": {
    "plg::home-assistant": {
      "version": "2026.2.1",
      "areas": [
        {
          "areaId": "living_room",
          "name": "Living Room",
          "devices": 8,
          "entities": 15
        }
      ],
      "devices": [
        {
          "deviceId": "hue_bridge_001",
          "name": "Philips Hue Bridge",
          "manufacturer": "Philips",
          "model": "BSB002",
          "area": "living_room",
          "entityCount": 6,
          "integration": "hue"
        }
      ],
      "entities": [
        {
          "entityId": "light.living_room_main",
          "friendlyName": "Living Room Main Light",
          "domain": "light",
          "state": "on",
          "attributes": {
            "brightness": 200,
            "color_temp": 350,
            "supported_features": 63
          },
          "deviceId": "hue_bridge_001",
          "area": "living_room",
          "lastChanged": "2026-02-13T08:30:00Z"
        }
      ]
    }
  }
}
```

### 8.5 Commands

| Command ID | Description | Parameters | Target | Role |
|---|---|---|---|---|
| `cmd::ha::turn-on` | Turn on entity | `entityId`, `brightness`, `color_temp`, `rgb_color` | HA instance | family |
| `cmd::ha::turn-off` | Turn off entity | `entityId` | HA instance | family |
| `cmd::ha::toggle` | Toggle entity state | `entityId` | HA instance | family |
| `cmd::ha::set-value` | Set entity value | `entityId`, `value` | HA instance | family |
| `cmd::ha::trigger-automation` | Trigger automation | `automationId` | HA instance | operator |
| `cmd::ha::trigger-scene` | Activate scene | `sceneId` | HA instance | family |
| `cmd::ha::set-hvac-mode` | Set HVAC mode | `entityId`, `mode`, `temperature` | HA instance | family |

### 8.6 MCP — Family Role Access

The Home Assistant plugin is unique in enabling `family` role users to interact with Hydra through MCP. When a family user's LLM connects:

```
Family member: "Turn off the living room lights"
→ MCP tool list (filtered for family role): only HA tools visible
→ Calls cmd::ha::turn-off(entityId="light.living_room_main")
→ Plugin routes through HA API: POST /api/services/light/turn_off
→ Result returned to LLM
```

### 8.7 Tier-Specific Behavior

Home Assistant is an **API-only plugin**. No agent-side execution is needed because the API communicates directly with the HA REST API over the network. The agent tier is irrelevant for this plugin's functionality — it works identically regardless of whether the node has a lite, normal, or max agent, or no agent at all (IoT nodes typically don't have agents).

---

## 9. Core Integrations — Ansible

### 9.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::ansible` |
| **Category** | IaC & Orchestration |
| **Classification** | Core |
| **External System** | Ansible (CLI-based, runs on Hydra API host or dedicated control node) |
| **API** | Ansible CLI invocation (not REST API) — `ansible-playbook`, `ansible`, `ansible-inventory` |
| **Authentication** | SSH keys (for target hosts), vault passwords (for encrypted vars) |
| **Direction** | Hydra → Ansible → Target Nodes |
| **Minimum Agent Tier** | `none` (Ansible runs on API host, SSHes to targets) |
| **Primary Execution** | API-local (Ansible runs on the same host as hydra-api, or on a designated Ansible control node accessible to the API) |

### 9.2 Why Ansible Is Different

Ansible is not a service with a REST API. It is a CLI tool that runs on a control node, reads inventory and playbooks, and SSHes to target machines. This makes it fundamentally different from integrations like Proxmox or Home Assistant.

Hydra's Ansible plugin must:
1. **Manage Ansible on the API host (or a control node).** Ansible must be installed and SSH-accessible to target infrastructure.
2. **Generate dynamic inventory from Hydra's node registry.** Hydra knows about all registered nodes — this becomes Ansible's inventory.
3. **Provide a playbook/role catalog.** Users select from available playbooks in the Command Center, not write ad-hoc Ansible commands.
4. **Handle fan-out execution.** When a workflow targets N nodes, Ansible handles parallel SSH to all of them, rather than Hydra queuing N individual commands.

### 9.3 Touchpoint Matrix

| Touchpoint | Supported | Details |
|---|---|---|
| Profile Enrichment | ✓ | Ansible facts gathered during playbook runs can enrich node profiles (gathered facts → hardware/software/network data) |
| Discovery Provider | ✓ | Can discover nodes from Ansible static inventory files (for importing existing infrastructure into Hydra) |
| Command Provider | ✓ | `cmd::ansible::run-playbook`, `cmd::ansible::run-role`, `cmd::ansible::gather-facts`, `cmd::ansible::run-ad-hoc` |
| Execution Handler | ✓ | Routes batch execution — when a workflow targets N nodes, Ansible handles the fan-out via SSH |
| Topology Provider | ✓ | Inventory groups → node membership (e.g., "webservers" group contains [node-01, node-02, node-03]) |
| Workflow Block Provider | ✓ | `playbook_run` block type with host pattern, variables, role selection, and parallelism config |

### 9.4 Configuration Schema

```json
{
  "pluginId": "plg::ansible",
  "configuration": {
    "ansibleConfig": {
      "controlNodeType": "local",
      "controlNode": null,
      "ansibleBinary": "/usr/bin/ansible-playbook",
      "configFile": "/etc/hydra/ansible/ansible.cfg",
      "inventorySource": "hydra-dynamic",
      "staticInventoryPaths": [],
      "playbookPaths": ["/etc/hydra/ansible/playbooks"],
      "rolePaths": ["/etc/hydra/ansible/roles"],
      "vaultPasswordFile": "/etc/hydra/ansible/vault-pass",
      "sshPrivateKeyFile": "/etc/hydra/ssh/hydra-ansible",
      "forks": 10,
      "timeout": 30
    },
    "features": {
      "dynamicInventory": true,
      "factGathering": true,
      "playbook Catalog": true,
      "batchExecution": true,
      "vaultSupport": true
    },
    "restrictions": {
      "allowedPlaybooks": [],
      "blockedPlaybooks": [],
      "allowAdHoc": false,
      "maxParallelForks": 20,
      "executionTimeoutSeconds": 3600
    }
  }
}
```

### 9.5 Dynamic Inventory Generator

Hydra generates an Ansible dynamic inventory script from its node registry:

```python
#!/usr/bin/env python3
"""Hydra Ansible Dynamic Inventory Script"""

import json
import sys
from hydra_api_client import HydraClient

def get_inventory():
    client = HydraClient()
    nodes = client.list_nodes(status="active", node_class="compute")
    
    inventory = {
        "_meta": {"hostvars": {}},
        "all": {"hosts": [], "children": ["hydra_compute", "hydra_by_kind", "hydra_by_tag"]}
    }
    
    # Group by class
    inventory["hydra_compute"] = {"hosts": []}
    
    # Group by kind
    kind_groups = {}
    tag_groups = {}
    
    for node in nodes:
        hostname = node["nodeId"]
        ip = get_primary_ip(node)
        
        if not ip:
            continue
        
        inventory["_meta"]["hostvars"][hostname] = {
            "ansible_host": ip,
            "ansible_user": node.get("sshUser", "root"),
            "hydra_node_id": node["nodeId"],
            "hydra_class": node["class"],
            "hydra_kind": node.get("kind"),
            "hydra_tags": node.get("tags", [])
        }
        
        inventory["hydra_compute"]["hosts"].append(hostname)
        
        # Kind grouping
        kind = node.get("kind", "unknown")
        group_name = f"hydra_{kind}"
        if group_name not in kind_groups:
            kind_groups[group_name] = {"hosts": []}
        kind_groups[group_name]["hosts"].append(hostname)
        
        # Tag grouping
        for tag in node.get("tags", []):
            group_name = f"hydra_tag_{tag}"
            if group_name not in tag_groups:
                tag_groups[group_name] = {"hosts": []}
            tag_groups[group_name]["hosts"].append(hostname)
    
    inventory.update(kind_groups)
    inventory.update(tag_groups)
    
    return inventory

if __name__ == "__main__":
    if "--list" in sys.argv:
        print(json.dumps(get_inventory(), indent=2))
    elif "--host" in sys.argv:
        # Per-host vars (handled by _meta above)
        print(json.dumps({}))
```

This means any Ansible playbook run through Hydra automatically targets the right hosts using Hydra's node registry as the source of truth.

### 9.6 Commands — Deep Specification

#### 9.6.1 cmd::ansible::run-playbook

```json
{
  "commandId": "cmd::ansible::run-playbook",
  "name": "Run Ansible Playbook",
  "description": "Execute a pre-registered Ansible playbook against specified hosts",
  "parameters": {
    "required": ["playbook"],
    "properties": {
      "playbook": {
        "type": "string",
        "description": "Playbook name or path (must be in allowed playbooks catalog)",
        "examples": ["site.yml", "update-packages.yml", "deploy-monitoring.yml"]
      },
      "limit": {
        "type": "string",
        "description": "Ansible host pattern to limit execution",
        "examples": ["proxmox-01", "hydra_lxc", "hydra_tag_production"]
      },
      "extraVars": {
        "type": "object",
        "description": "Extra variables passed to playbook",
        "examples": [{"package_name": "nginx", "version": "1.25"}]
      },
      "tags": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Only run plays/tasks with these tags"
      },
      "skipTags": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Skip plays/tasks with these tags"
      },
      "check": {
        "type": "boolean",
        "default": false,
        "description": "Dry run (--check mode)"
      },
      "diff": {
        "type": "boolean",
        "default": true,
        "description": "Show diff of changes"
      },
      "verbosity": {
        "type": "integer",
        "minimum": 0,
        "maximum": 4,
        "default": 0,
        "description": "Ansible verbosity level (0-4)"
      },
      "forks": {
        "type": "integer",
        "default": 10,
        "description": "Number of parallel processes"
      },
      "becomeMethod": {
        "type": "string",
        "enum": ["sudo", "su", "doas"],
        "default": "sudo"
      }
    }
  },
  "target": {
    "type": "node-group",
    "description": "Can target single node, node group, or Ansible host pattern"
  },
  "dangerous": true,
  "requiredRole": "admin",
  "confirmation": true,
  "timeout": 3600
}
```

**Execution Flow:**

```
User submits cmd::ansible::run-playbook
    │
    ├── API validates playbook is in allowed catalog
    ├── API resolves host pattern → list of target node IDs
    ├── API checks all target nodes are reachable
    ├── API creates execution record with status "running"
    │
    ├── API invokes Ansible CLI:
    │   ansible-playbook \
    │     -i /etc/hydra/ansible/inventory.py \
    │     --limit "proxmox-01,docker-host-01" \
    │     --extra-vars '{"package_name": "nginx"}' \
    │     --diff \
    │     /etc/hydra/ansible/playbooks/update-packages.yml
    │
    ├── API captures stdout/stderr in real-time
    │   ├── Streams to WebSocket if web client connected
    │   └── Stores in execution log
    │
    ├── On completion:
    │   ├── Parse Ansible JSON callback output
    │   ├── Extract per-host results (ok, changed, failed, skipped)
    │   ├── If fact gathering was included → enrich node profiles
    │   └── Update execution record with results
    │
    └── Return execution result
```

#### 9.6.2 cmd::ansible::gather-facts

```json
{
  "commandId": "cmd::ansible::gather-facts",
  "name": "Gather Ansible Facts",
  "description": "Run Ansible fact gathering on target nodes and optionally enrich Hydra profiles",
  "parameters": {
    "required": [],
    "properties": {
      "limit": {
        "type": "string",
        "description": "Host pattern"
      },
      "enrichProfiles": {
        "type": "boolean",
        "default": true,
        "description": "Merge gathered facts into Hydra node profiles"
      },
      "subset": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Gather only specific fact subsets",
        "examples": [["hardware", "network", "virtual"]]
      }
    }
  },
  "dangerous": false,
  "requiredRole": "operator"
}
```

#### 9.6.3 cmd::ansible::run-ad-hoc

```json
{
  "commandId": "cmd::ansible::run-ad-hoc",
  "name": "Run Ansible Ad-Hoc Command",
  "description": "Execute a single Ansible module against target hosts",
  "parameters": {
    "required": ["module"],
    "properties": {
      "module": {
        "type": "string",
        "description": "Ansible module name",
        "examples": ["ping", "shell", "apt", "yum", "service", "copy"]
      },
      "args": {
        "type": "string",
        "description": "Module arguments"
      },
      "limit": {
        "type": "string"
      }
    }
  },
  "dangerous": true,
  "requiredRole": "admin",
  "confirmation": true,
  "restricted": {
    "allowAdHoc": "configurable",
    "blockedModules": ["raw", "script"]
  }
}
```

### 9.7 Workflow Block — playbook_run

The Ansible plugin contributes a `playbook_run` workflow block type. This differs from a simple `cmd::ansible::run-playbook` command because it has:
- Specialized UI in the workflow canvas with host pattern picker, variable editor, and role selector
- Pre-execution validation (checks all target hosts are reachable)
- Integrated output display within the workflow step
- Support for conditional branching based on per-host results

```json
{
  "blockType": "playbook_run",
  "plugin": "plg::ansible",
  "displayName": "Run Playbook",
  "description": "Execute an Ansible playbook as a workflow step",
  "icon": "ansible",
  "inputs": {
    "playbook": { "type": "select", "source": "playbook-catalog" },
    "limit": { "type": "host-pattern-picker" },
    "extraVars": { "type": "key-value-editor" },
    "tags": { "type": "tag-selector" },
    "check": { "type": "boolean", "label": "Dry Run" }
  },
  "outputs": {
    "results": {
      "type": "per-host-results",
      "schema": {
        "host": "string",
        "status": "enum:ok|changed|failed|unreachable|skipped",
        "taskResults": "array"
      }
    },
    "summary": {
      "type": "object",
      "schema": {
        "totalHosts": "integer",
        "ok": "integer",
        "changed": "integer",
        "failed": "integer"
      }
    }
  },
  "conditionalOutputs": {
    "allSucceeded": "summary.failed == 0",
    "anyFailed": "summary.failed > 0",
    "allChanged": "summary.changed == summary.totalHosts"
  },
  "lifecycle": {
    "preExecution": ["validate-playbook-exists", "validate-hosts-reachable"],
    "execution": "ansible-playbook-invocation",
    "postExecution": ["parse-results", "optional-profile-enrichment"],
    "timeout": 3600
  }
}
```

### 9.8 Batch Execution Handler

When a workflow step targets multiple nodes and the Ansible plugin is the execution handler, Ansible manages the fan-out:

```
Workflow step: "Restart nginx on all web servers"
    │
    ├── Without Ansible: Hydra queues N individual cmd::service::restart
    │   executions, one per node. Each node's agent executes independently.
    │   No coordination, no parallel SSH.
    │
    └── With Ansible: Single cmd::ansible::run-ad-hoc invocation
        with module=service, args="name=nginx state=restarted",
        limit="hydra_tag_webserver". Ansible handles parallel SSH
        to all hosts, collects results, returns aggregate.
```

### 9.9 Tier-Specific Behavior

Ansible is an **API-local plugin**. It runs on the Hydra API host (or a designated control node). The agent tier is irrelevant because Ansible SSHes directly to target machines — it does not go through the Hydra agent. However, Hydra's agent provides value by:
- Confirming node reachability (the API knows if an agent is online before sending Ansible to SSH)
- Providing the IP/hostname Ansible should target (from node registration data)
- Enriching profiles with Ansible-gathered facts

---

## 10. Core Integrations — Terraform

### 10.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::terraform` |
| **Category** | IaC & Orchestration |
| **Classification** | Core |
| **External System** | Terraform / OpenTofu (CLI-based) |
| **API** | Terraform CLI invocation — `terraform plan`, `terraform apply`, `terraform destroy` |
| **Authentication** | Provider-specific credentials (Proxmox API token, AWS keys, etc.) stored in Terraform vars |
| **Direction** | Hydra → Terraform → Infrastructure Providers |
| **Minimum Agent Tier** | `none` (Terraform runs on API host) |
| **Primary Execution** | API-local |

### 10.2 Why Terraform Is Different

Like Ansible, Terraform is a CLI tool, not a service with a REST API. But Terraform has additional complexity:

1. **State Management.** Terraform maintains a state file that maps declared resources to real infrastructure. This state must be managed carefully — concurrent modifications can corrupt it.
2. **Plan-Apply Lifecycle.** Terraform operations have a mandatory two-phase lifecycle: `plan` (preview changes) → `apply` (execute changes). Destructive operations add `destroy`. This lifecycle must be represented in workflows.
3. **Provider Dependencies.** Terraform modules declare providers (Proxmox, Docker, Cloudflare, etc.). The Terraform plugin must manage provider credentials and know which Hydra integrations correspond to which Terraform providers.
4. **Workspace Management.** Multiple Terraform configurations may coexist, each with independent state.

### 10.3 Touchpoint Matrix

| Touchpoint | Supported | Details |
|---|---|---|
| Profile Enrichment | ✗ | Terraform doesn't profile existing infrastructure (that's Ansible's role) |
| Discovery Provider | ✓ | Can discover resources from state files (what Terraform manages → what Hydra should know about) |
| Command Provider | ✓ | `cmd::terraform::init`, `cmd::terraform::plan`, `cmd::terraform::apply`, `cmd::terraform::destroy`, `cmd::terraform::import`, `cmd::terraform::state-list`, `cmd::terraform::output` |
| Execution Handler | ✗ | Terraform doesn't handle existing commands (it creates/destroys infrastructure) |
| Topology Provider | ✓ | Resources→provider mapping, module dependency tree |
| Workflow Block Provider | ✓ | `terraform_apply` block with plan→approve→apply lifecycle and state management |

### 10.4 Configuration Schema

```json
{
  "pluginId": "plg::terraform",
  "configuration": {
    "terraformConfig": {
      "binary": "/usr/bin/terraform",
      "workspacesDir": "/etc/hydra/terraform/workspaces",
      "stateBackend": "local",
      "stateBackendConfig": {
        "path": "/etc/hydra/terraform/state"
      },
      "pluginCacheDir": "/etc/hydra/terraform/plugin-cache",
      "parallelism": 10
    },
    "providerCredentials": {
      "proxmox": {
        "source": "plg::proxmox-ve",
        "description": "Inherits credentials from Proxmox VE plugin"
      },
      "docker": {
        "source": "plg::docker",
        "description": "Inherits credentials from Docker plugin"
      },
      "cloudflare": {
        "apiToken": "encrypted::..."
      }
    },
    "workspaces": [
      {
        "name": "homelab-core",
        "path": "/etc/hydra/terraform/workspaces/homelab-core",
        "description": "Core infrastructure — Proxmox LXCs, networks",
        "autoInit": true,
        "lockTimeout": "5m"
      },
      {
        "name": "monitoring-stack",
        "path": "/etc/hydra/terraform/workspaces/monitoring-stack",
        "description": "Monitoring infrastructure — Prometheus, Grafana containers",
        "autoInit": true
      }
    ],
    "restrictions": {
      "allowDestroy": true,
      "requireApproval": true,
      "maxConcurrentApplies": 1,
      "executionTimeoutSeconds": 1800
    }
  }
}
```

### 10.5 Commands — Deep Specification

#### 10.5.1 cmd::terraform::plan

```json
{
  "commandId": "cmd::terraform::plan",
  "name": "Terraform Plan",
  "description": "Generate and show an execution plan for infrastructure changes",
  "parameters": {
    "required": ["workspace"],
    "properties": {
      "workspace": {
        "type": "string",
        "description": "Terraform workspace name"
      },
      "varFile": {
        "type": "string",
        "description": "Path to variable file"
      },
      "vars": {
        "type": "object",
        "description": "Inline variable overrides"
      },
      "target": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Target specific resources",
        "examples": [["proxmox_lxc.pihole", "proxmox_lxc.dns_secondary"]]
      },
      "destroy": {
        "type": "boolean",
        "default": false,
        "description": "Plan for destruction"
      },
      "refresh": {
        "type": "boolean",
        "default": true,
        "description": "Refresh state before planning"
      }
    }
  },
  "dangerous": false,
  "requiredRole": "admin",
  "timeout": 300
}
```

**Execution Flow:**

```
cmd::terraform::plan submitted
    │
    ├── API locks workspace state file (prevent concurrent operations)
    ├── API runs: terraform -chdir={workspace_path} plan -out=plan.tfplan
    │   -var-file={varFile} -var 'key=value' [-target=resource] [-destroy]
    │
    ├── Capture plan output:
    │   ├── Resources to add
    │   ├── Resources to change
    │   ├── Resources to destroy
    │   └── Full diff text
    │
    ├── Store plan artifact for subsequent apply:
    │   plan.tfplan saved with execution ID reference
    │
    ├── Release workspace lock
    │
    └── Return plan summary:
        {
          "planId": "plan_abc123",
          "workspace": "homelab-core",
          "add": 2,
          "change": 1,
          "destroy": 0,
          "resources": [
            {"action": "add", "type": "proxmox_lxc", "name": "new-service", "details": "..."},
            {"action": "add", "type": "proxmox_lxc", "name": "new-service-2", "details": "..."},
            {"action": "change", "type": "proxmox_lxc", "name": "pihole", "details": "memory: 512 → 1024"}
          ],
          "planFile": "/etc/hydra/terraform/plans/plan_abc123.tfplan"
        }
```

#### 10.5.2 cmd::terraform::apply

```json
{
  "commandId": "cmd::terraform::apply",
  "name": "Terraform Apply",
  "description": "Apply a previously generated plan, or apply directly",
  "parameters": {
    "required": ["workspace"],
    "properties": {
      "workspace": { "type": "string" },
      "planId": {
        "type": "string",
        "description": "Apply a specific plan (from previous cmd::terraform::plan). If omitted, runs plan+apply in one step."
      },
      "autoApprove": {
        "type": "boolean",
        "default": false,
        "description": "Skip approval confirmation (requires admin role)"
      },
      "vars": { "type": "object" },
      "target": {
        "type": "array",
        "items": { "type": "string" }
      }
    }
  },
  "dangerous": true,
  "requiredRole": "admin",
  "confirmation": true,
  "timeout": 1800
}
```

#### 10.5.3 cmd::terraform::destroy

```json
{
  "commandId": "cmd::terraform::destroy",
  "name": "Terraform Destroy",
  "description": "Destroy Terraform-managed infrastructure",
  "parameters": {
    "required": ["workspace"],
    "properties": {
      "workspace": { "type": "string" },
      "target": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Destroy specific resources only"
      },
      "autoApprove": {
        "type": "boolean",
        "default": false
      }
    }
  },
  "dangerous": true,
  "requiredRole": "admin",
  "confirmation": true,
  "doubleConfirmation": true,
  "timeout": 1800
}
```

### 10.6 Workflow Block — terraform_apply

The Terraform plugin contributes a `terraform_apply` workflow block type with a specialized lifecycle:

```json
{
  "blockType": "terraform_apply",
  "plugin": "plg::terraform",
  "displayName": "Terraform Apply",
  "description": "Deploy infrastructure changes with plan/approve/apply lifecycle",
  "icon": "terraform",
  "inputs": {
    "workspace": { "type": "select", "source": "terraform-workspaces" },
    "vars": { "type": "key-value-editor" },
    "target": { "type": "resource-picker", "source": "terraform-state" },
    "autoApprove": { "type": "boolean", "label": "Auto-Approve", "default": false }
  },
  "outputs": {
    "planSummary": {
      "type": "object",
      "schema": { "add": "integer", "change": "integer", "destroy": "integer" }
    },
    "resources": {
      "type": "array",
      "schema": { "action": "string", "type": "string", "name": "string", "id": "string" }
    },
    "outputs": {
      "type": "object",
      "description": "Terraform output values after apply"
    }
  },
  "conditionalOutputs": {
    "applied": "applyResult.success == true",
    "failed": "applyResult.success == false",
    "noop": "planSummary.add == 0 && planSummary.change == 0 && planSummary.destroy == 0"
  },
  "lifecycle": {
    "phases": [
      {
        "name": "plan",
        "description": "Generate execution plan",
        "automatic": true,
        "timeout": 300
      },
      {
        "name": "approval",
        "description": "User reviews and approves plan",
        "automatic": false,
        "skipIf": "inputs.autoApprove == true",
        "ui": "plan-diff-viewer"
      },
      {
        "name": "apply",
        "description": "Apply the approved plan",
        "automatic": true,
        "timeout": 1800
      },
      {
        "name": "verify",
        "description": "Verify resources are created/modified",
        "automatic": true,
        "timeout": 60
      }
    ],
    "rollback": {
      "supported": true,
      "method": "terraform-destroy-targeted",
      "description": "Destroy only the resources created by this apply"
    },
    "stateLocking": {
      "required": true,
      "lockTimeout": "5m",
      "preventConcurrent": true
    }
  }
}
```

**Practical Use Case — Provisioning LXC via Workflow:**

```
Workflow: "Deploy New Service"
    │
    Step 1: terraform_apply (plg::terraform)
    │   workspace: "homelab-core"
    │   vars: { hostname: "new-service", cores: 2, memory: 1024 }
    │   → Plan shows: +1 proxmox_lxc.new-service
    │   → User approves
    │   → Apply creates LXC on Proxmox
    │   → Output: { ip: "192.168.0.50", vmid: 110 }
    │
    Step 2: cmd::proxmox::snapshot (plg::proxmox-ve)
    │   vmid: 110
    │   name: "initial-state"
    │   → Creates clean-state snapshot
    │
    Step 3: cmd::ansible::run-playbook (plg::ansible)
    │   playbook: "bootstrap-node.yml"
    │   limit: "new-service"
    │   extraVars: { hydra_api_url: "...", hydra_agent_tier: "normal" }
    │   → Installs Hydra agent, configures SSH keys, sets up monitoring
    │
    Step 4: cmd::agent::collect-now (core)
        → Triggers immediate profile collection on new node
        → Node appears in Hydra topology
```

### 10.7 State Discovery

Terraform plugin can discover resources from existing state files and register them in Hydra:

```python
async def discover_nodes(self) -> list[dict]:
    discovered = []
    
    for workspace in self.config.workspaces:
        state = await self.run_terraform(workspace, "state", "list")
        
        for resource_addr in state.splitlines():
            resource_type, resource_name = parse_resource_address(resource_addr)
            
            if resource_type in COMPUTE_RESOURCE_TYPES:
                show = await self.run_terraform(workspace, "state", "show", resource_addr)
                attrs = parse_resource_attributes(show)
                
                discovered.append({
                    "source": "plg::terraform",
                    "displayName": resource_name,
                    "type": "logical" if resource_type in VM_TYPES else "physical",
                    "kind": RESOURCE_TYPE_TO_KIND.get(resource_type, "other"),
                    "metadata": {
                        "terraformWorkspace": workspace.name,
                        "resourceAddress": resource_addr,
                        "resourceType": resource_type,
                        "provider": attrs.get("provider")
                    }
                })
    
    return discovered
```

### 10.8 Tier-Specific Behavior

Terraform is an **API-local plugin**. Like Ansible, it runs on the Hydra API host. Agent tier is irrelevant for Terraform operations — the infrastructure changes happen through Terraform providers (Proxmox API, Docker API, cloud APIs), not through Hydra agents.

---

## 11. Core Integrations — Prometheus

### 11.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::prometheus` |
| **Category** | Monitoring & Health |
| **Classification** | Core |
| **External System** | Prometheus Server + node_exporter |
| **API** | Prometheus HTTP API (`/api/v1/*`) + node_exporter metrics endpoint |
| **Authentication** | Optional (basic auth or bearer token if configured) |
| **Direction** | Hydra → Prometheus (read-only) |
| **Minimum Agent Tier** | `lite` (detection), `max` (metrics proxy) |
| **Primary Execution** | API-direct (queries Prometheus server) + Agent-side (node_exporter detection/proxy) |

### 11.2 Touchpoint Matrix

| Touchpoint | Supported | Details |
|---|---|---|
| Profile Enrichment | ✓ | Metric snapshots at profile time — CPU, memory, disk, network baselines captured from Prometheus |
| Discovery Provider | ✓ | Scrape targets registered in Prometheus become candidate nodes |
| Command Provider | ✗ | Prometheus is read-only; no commands contributed |
| Execution Handler | ✗ | — |
| Topology Provider | ✓ | Target→job→instance mapping, alerting rule→target relationships |
| Workflow Block Provider | ✗ | — |

### 11.3 Configuration Schema

```json
{
  "pluginId": "plg::prometheus",
  "configuration": {
    "connection": {
      "url": "http://prometheus.home.lan:9090",
      "verifyTls": false
    },
    "credentials": {
      "type": "none"
    },
    "features": {
      "profileEnrichment": true,
      "discoveryFromTargets": true,
      "topologyMapping": true,
      "metricQueryTools": true
    },
    "enrichmentConfig": {
      "metricsToCapture": [
        "node_cpu_seconds_total",
        "node_memory_MemTotal_bytes",
        "node_memory_MemAvailable_bytes",
        "node_filesystem_size_bytes",
        "node_filesystem_avail_bytes",
        "node_network_receive_bytes_total",
        "node_network_transmit_bytes_total",
        "node_load1",
        "node_load5",
        "node_load15",
        "node_boot_time_seconds"
      ],
      "snapshotWindowSeconds": 300,
      "aggregation": "avg"
    },
    "nodeExporter": {
      "expectedPort": 9100,
      "metricsPath": "/metrics"
    }
  }
}
```

### 11.4 Profile Enrichment Data

Prometheus enriches node profiles with metric baselines — these are not real-time monitoring values but snapshots that characterize the node's typical state at profile time:

```json
{
  "pluginData": {
    "plg::prometheus": {
      "source": "prometheus-server",
      "capturedAt": "2026-02-13T12:00:00Z",
      "windowSeconds": 300,
      "metrics": {
        "cpu": {
          "coreCount": 4,
          "avgUtilizationPercent": 12.5,
          "load1": 0.5,
          "load5": 0.8,
          "load15": 0.6
        },
        "memory": {
          "totalBytes": 8589934592,
          "availableBytes": 6442450944,
          "usedPercent": 25.0
        },
        "disk": [
          {
            "mountpoint": "/",
            "totalBytes": 53687091200,
            "availableBytes": 32212254720,
            "usedPercent": 40.0
          }
        ],
        "network": {
          "interfaces": [
            {
              "name": "eth0",
              "rxBytesPerSec": 125000,
              "txBytesPerSec": 50000
            }
          ]
        },
        "uptime": {
          "bootTime": "2026-01-15T10:00:00Z",
          "uptimeSeconds": 2505600
        }
      },
      "nodeExporter": {
        "detected": true,
        "port": 9100,
        "version": "1.7.0"
      }
    }
  }
}
```

### 11.5 MCP Query Tools

When Prometheus is active, the MCP service gains a powerful metric query tool:

```json
{
  "name": "query_metrics",
  "description": "Query Prometheus metrics for nodes and services",
  "inputSchema": {
    "type": "object",
    "required": ["query"],
    "properties": {
      "query": {
        "type": "string",
        "description": "PromQL query or natural language description",
        "examples": ["node_memory_MemAvailable_bytes{instance='server-01:9100'}", "How much memory is available on server-01?"]
      },
      "timeRange": {
        "type": "object",
        "properties": {
          "start": { "type": "string" },
          "end": { "type": "string" },
          "step": { "type": "string" }
        }
      },
      "nodeId": {
        "type": "string",
        "description": "If provided, query is scoped to this node's metrics"
      }
    }
  }
}
```

The MCP service translates natural language to PromQL when the AI model provides a descriptive query rather than raw PromQL.

### 11.6 Discovery Provider

Prometheus discovers nodes from its scrape targets:

```python
async def discover_nodes(self) -> list[dict]:
    targets = await self.api.get("/api/v1/targets")
    
    discovered = []
    for target in targets["data"]["activeTargets"]:
        instance = target["labels"].get("instance", "")
        ip, port = parse_instance(instance)
        
        discovered.append({
            "source": "plg::prometheus",
            "ip": ip,
            "displayName": target["labels"].get("nodename", ip),
            "metadata": {
                "prometheusJob": target["labels"].get("job"),
                "scrapeUrl": target["scrapeUrl"],
                "health": target["health"],
                "lastScrape": target["lastScrape"]
            },
            "confidence": "medium"
        })
    
    return discovered
```

### 11.7 Tier-Specific Behavior

| Tier | Behavior |
|---|---|
| **lite** | Agent detects node_exporter process/port during detection. Reports `plg::prometheus: { available: true, port: 9100 }` in detection report. No further agent-side action. |
| **normal** | Same as lite. Prometheus queries are API-side (API queries Prometheus server directly). |
| **max** | Agent can proxy node_exporter metrics through `/plugins/prometheus/metrics` endpoint. Useful when Prometheus server can't reach the node directly but the API can reach the agent. Agent can also cache recent metric snapshots for faster profile enrichment. |

---

## 12. Default Integrations — Podman

### 12.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::podman` |
| **Category** | Container Runtime |
| **Classification** | Default |
| **External System** | Podman |
| **API** | Podman REST API (compatible with Docker API v1.40+) via Unix socket or TCP |
| **Authentication** | Socket permissions (rootless: `$XDG_RUNTIME_DIR/podman/podman.sock`) |
| **Minimum Agent Tier** | `lite` (detection), `normal` (commands), `max` (proxy) |
| **Primary Execution** | Agent-local |

### 12.2 Key Differences from Docker

While Podman's API is Docker-compatible, key differences justify a separate plugin:

- **Rootless execution.** Podman containers run as non-root by default. Socket paths differ (`/run/user/{uid}/podman/podman.sock` vs `/var/run/docker.sock`).
- **Pod support.** Podman has native pod grouping (similar to Kubernetes pods).
- **Systemd integration.** Podman generates systemd units for containers (`podman generate systemd`), blurring the service/container boundary.
- **No daemon.** Podman is daemonless — the socket is activated on demand.

### 12.3 Touchpoint Matrix

| Touchpoint | Supported | Details |
|---|---|---|
| Profile Enrichment | ✓ | Container images, pods, volumes, networks (same data shape as Docker with pod additions) |
| Discovery Provider | ✓ | Running containers and pods |
| Command Provider | ✓ | `cmd::podman::pull`, `cmd::podman::pod-create`, `cmd::podman::generate-systemd`, `cmd::podman::prune` |
| Execution Handler | ✓ | Routes `cmd::service::*` for Podman-managed containers |
| Topology Provider | ✓ | Host→pod→container, network membership |
| Workflow Block Provider | ✗ | — |

### 12.4 Commands

| Command ID | Description | Dangerous | Role |
|---|---|---|---|
| `cmd::podman::pull` | Pull container image | No | operator |
| `cmd::podman::pod-create` | Create new pod | No | admin |
| `cmd::podman::pod-start` | Start pod and all containers | No | operator |
| `cmd::podman::pod-stop` | Stop pod and all containers | No | operator |
| `cmd::podman::generate-systemd` | Generate systemd unit for container/pod | No | admin |
| `cmd::podman::prune` | Remove unused containers, images | Yes | admin |

---

## 13. Default Integrations — UniFi

### 13.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::unifi` |
| **Category** | Networking |
| **Classification** | Default |
| **External System** | UniFi Network Application (formerly Controller) |
| **API** | UniFi REST API (unofficial but well-documented) |
| **Authentication** | Username/password login (session cookies) or API key (newer firmware) |
| **Minimum Agent Tier** | `none` (API-only) |
| **Primary Execution** | API-direct |

### 13.2 Touchpoint Matrix

| Touchpoint | Supported | Details |
|---|---|---|
| Profile Enrichment | ✓ | AP/switch/gateway stats, firmware versions, PoE port status, client counts |
| Discovery Provider | ✓ | All UniFi-adopted devices + connected clients (wired and wireless) |
| Command Provider | ✓ | `cmd::unifi::restart-device`, `cmd::unifi::block-client`, `cmd::unifi::unblock-client`, `cmd::unifi::set-port-profile`, `cmd::unifi::force-provision` |
| Execution Handler | ✗ | — |
| Topology Provider | ✓ | Switch port→MAC mapping, AP→client associations, VLAN assignments, uplink topology |
| Workflow Block Provider | ✗ | — |

### 13.3 Profile Enrichment Data

```json
{
  "pluginData": {
    "plg::unifi": {
      "device": {
        "model": "USW-Pro-24-PoE",
        "firmware": "6.6.65",
        "adopted": true,
        "uptimeSeconds": 1209600,
        "portTable": [
          {
            "port": 1,
            "name": "proxmox-01",
            "speed": 1000,
            "poeEnabled": false,
            "media": "GE-TX",
            "mac": "aa:bb:cc:dd:ee:ff"
          },
          {
            "port": 2,
            "name": "AP-LivingRoom",
            "speed": 1000,
            "poeEnabled": true,
            "poeWatts": 8.5,
            "media": "GE-TX",
            "mac": "11:22:33:44:55:66"
          }
        ]
      },
      "clients": {
        "wired": 12,
        "wireless": 28,
        "total": 40
      }
    }
  }
}
```

### 13.4 Topology Edges

UniFi provides rich network topology data:

```json
[
  {
    "source": "usw-pro-24",
    "target": "proxmox-01",
    "relationship": "connected-port",
    "metadata": { "port": 1, "speed": 1000, "vlan": 10 }
  },
  {
    "source": "usw-pro-24",
    "target": "uap-living-room",
    "relationship": "connected-port",
    "metadata": { "port": 2, "speed": 1000, "poe": true, "poeWatts": 8.5 }
  },
  {
    "source": "uap-living-room",
    "target": "iphone-john",
    "relationship": "wireless-client",
    "metadata": { "ssid": "HomeNetwork", "channel": 36, "signal": -45 }
  }
]
```

---

## 14. Default Integrations — SNMP

### 14.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::snmp` |
| **Category** | Networking |
| **Classification** | Default |
| **External System** | Any SNMP-capable device (managed switches, printers, UPS, etc.) |
| **API** | SNMP v2c/v3 protocol |
| **Authentication** | Community string (v2c) or USM credentials (v3) |
| **Minimum Agent Tier** | `none` (API-direct) or `max` (agent-delegated for segmented networks) |
| **Primary Execution** | API-direct (API sends SNMP queries) |

### 14.2 Touchpoint Matrix

| Touchpoint | Supported | Details |
|---|---|---|
| Profile Enrichment | ✓ | Interface statistics, ARP tables, VLAN configuration, system description |
| Discovery Provider | ✓ | SNMP-responding devices on scanned networks |
| Command Provider | ✓ | `cmd::snmp::set` (where SNMP SET is supported by the device) |
| Execution Handler | ✗ | — |
| Topology Provider | ✓ | ARP neighbor tables, LLDP/CDP neighbor discovery, VLAN port assignments |
| Workflow Block Provider | ✗ | — |

### 14.3 Profile Enrichment Data

```json
{
  "pluginData": {
    "plg::snmp": {
      "sysDescr": "ProCurve J9728A 2920-48G-PoE+, revision WC.16.10.0012",
      "sysUptime": 8640000,
      "interfaces": [
        {
          "ifIndex": 1,
          "ifName": "1",
          "ifDescr": "Port 1",
          "ifSpeed": 1000000000,
          "ifOperStatus": "up",
          "ifAdminStatus": "up"
        }
      ],
      "vlans": [
        { "vlanId": 10, "name": "Management", "ports": [1, 2, 3] },
        { "vlanId": 20, "name": "IoT", "ports": [10, 11, 12] }
      ],
      "arpTable": [
        { "ip": "192.168.0.10", "mac": "aa:bb:cc:dd:ee:ff", "ifIndex": 1 }
      ],
      "neighbors": {
        "lldp": [
          {
            "localPort": 1,
            "remoteSystemName": "proxmox-01",
            "remoteMac": "aa:bb:cc:dd:ee:ff",
            "remotePortDesc": "eno1"
          }
        ]
      }
    }
  }
}
```

---

## 15. Default Integrations — pfSense

### 15.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::pfsense` |
| **Category** | Networking |
| **Classification** | Default |
| **External System** | pfSense Firewall |
| **API** | pfSense FauxAPI or pfSense-api (third-party REST API packages) |
| **Authentication** | API key + secret (FauxAPI) |
| **Minimum Agent Tier** | `none` (API-direct) |
| **Primary Execution** | API-direct |

### 15.2 Touchpoint Matrix

| Touchpoint | Supported | Details |
|---|---|---|
| Profile Enrichment | ✓ | Firewall rules, NAT rules, VPN tunnels, DHCP leases, interface config |
| Discovery Provider | ✓ | DHCP clients, ARP table entries |
| Command Provider | ✓ | `cmd::pfsense::reload-rules`, `cmd::pfsense::restart-service`, `cmd::pfsense::add-alias`, `cmd::pfsense::add-dhcp-static` |
| Execution Handler | ✗ | — |
| Topology Provider | ✓ | Gateway→subnet mapping, VLAN routing, VPN tunnel endpoints |
| Workflow Block Provider | ✗ | — |

### 15.3 Commands

| Command ID | Description | Dangerous | Role |
|---|---|---|---|
| `cmd::pfsense::reload-rules` | Reload firewall filter rules | Yes | admin |
| `cmd::pfsense::restart-service` | Restart pfSense service (DNS, DHCP, VPN) | Yes | admin |
| `cmd::pfsense::add-alias` | Add firewall alias entry | No | admin |
| `cmd::pfsense::add-dhcp-static` | Add static DHCP mapping | No | operator |

---

## 16. Default Integrations — OPNsense

### 16.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::opnsense` |
| **Category** | Networking |
| **Classification** | Default |
| **External System** | OPNsense Firewall |
| **API** | OPNsense REST API (native, well-documented) |
| **Authentication** | API key + secret |
| **Minimum Agent Tier** | `none` (API-direct) |
| **Primary Execution** | API-direct |

### 16.2 Key Differences from pfSense

OPNsense has a proper native REST API (unlike pfSense which requires third-party API packages). This means:
- More reliable API surface with versioned endpoints
- Better error handling and documentation
- Native plugin ecosystem support
- MVC architecture with structured JSON responses

### 16.3 Touchpoint Matrix

Same capabilities as pfSense (§15.2) but with different API implementation. Commands use `cmd::opnsense::*` prefix.

### 16.4 Commands

| Command ID | Description | Dangerous | Role |
|---|---|---|---|
| `cmd::opnsense::reload-rules` | Apply pending firewall changes | Yes | admin |
| `cmd::opnsense::restart-service` | Restart OPNsense service | Yes | admin |
| `cmd::opnsense::add-alias` | Add firewall alias | No | admin |
| `cmd::opnsense::firmware-check` | Check for firmware updates | No | operator |
| `cmd::opnsense::firmware-update` | Apply firmware update | Yes | admin |

---

## 17. Default Integrations — Traefik

### 17.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::traefik` |
| **Category** | Reverse Proxy & Ingress |
| **Classification** | Default |
| **External System** | Traefik Proxy |
| **API** | Traefik API (`/api/*`) |
| **Authentication** | Basic auth or IP whitelist on API endpoint |
| **Minimum Agent Tier** | `none` (API-direct) |
| **Primary Execution** | API-direct |

### 17.2 Touchpoint Matrix

| Touchpoint | Supported | Details |
|---|---|---|
| Profile Enrichment | ✓ | Routes, middlewares, TLS certificate status, entrypoints |
| Discovery Provider | ✓ | Auto-discovered services (from Docker labels, file provider, etc.) |
| Command Provider | ✓ | `cmd::traefik::reload` |
| Execution Handler | ✗ | — |
| Topology Provider | ✓ | Entrypoint→router→service→upstream mapping |
| Workflow Block Provider | ✗ | — |

### 17.3 Profile Enrichment Data

```json
{
  "pluginData": {
    "plg::traefik": {
      "version": "3.0.0",
      "routers": [
        {
          "name": "dashboard@docker",
          "entryPoints": ["websecure"],
          "rule": "Host(`traefik.home.lan`)",
          "service": "api@internal",
          "tls": { "certResolver": "letsencrypt" },
          "status": "enabled"
        }
      ],
      "services": [
        {
          "name": "nginx@docker",
          "loadBalancer": {
            "servers": [{ "url": "http://172.18.0.5:80" }]
          },
          "status": "enabled"
        }
      ],
      "certificates": [
        {
          "domain": "*.home.lan",
          "issuer": "Let's Encrypt",
          "expiresAt": "2026-05-13T00:00:00Z",
          "daysUntilExpiry": 89
        }
      ]
    }
  }
}
```

---

## 18. Default Integrations — Nginx Proxy Manager

### 18.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::nginx-proxy-manager` |
| **Category** | Reverse Proxy & Ingress |
| **Classification** | Default |
| **External System** | Nginx Proxy Manager |
| **API** | NPM REST API |
| **Authentication** | Username/password login (JWT session) |
| **Minimum Agent Tier** | `none` (API-direct) |
| **Primary Execution** | API-direct |

### 18.2 Touchpoint Matrix

| Touchpoint | Supported | Details |
|---|---|---|
| Profile Enrichment | ✓ | Proxy hosts, SSL certificates, access lists, redirect hosts |
| Discovery Provider | ✓ | Configured upstream targets |
| Command Provider | ✓ | `cmd::npm::enable-host`, `cmd::npm::disable-host`, `cmd::npm::renew-cert` |
| Execution Handler | ✗ | — |
| Topology Provider | ✓ | Domain→upstream service mapping |
| Workflow Block Provider | ✗ | — |

---

## 19. Default Integrations — Pi-hole

### 19.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::pihole` |
| **Category** | DNS & Ad Blocking |
| **Classification** | Default |
| **External System** | Pi-hole |
| **API** | Pi-hole Admin API |
| **Authentication** | API token (from web interface) |
| **Minimum Agent Tier** | `none` (API-direct) |
| **Primary Execution** | API-direct |

### 19.2 Touchpoint Matrix

| Touchpoint | Supported | Details |
|---|---|---|
| Profile Enrichment | ✓ | Query stats per client, blocklist count, domain counts, top queries/blocked |
| Discovery Provider | ✓ | Clients making DNS queries (with MAC and hostname when available) |
| Command Provider | ✓ | `cmd::pihole::enable`, `cmd::pihole::disable`, `cmd::pihole::flush-cache`, `cmd::pihole::update-gravity` |
| Execution Handler | ✗ | — |
| Topology Provider | ✓ | Client→query pattern mapping |
| Workflow Block Provider | ✗ | — |

### 19.3 Commands

| Command ID | Description | Dangerous | Role |
|---|---|---|---|
| `cmd::pihole::enable` | Enable Pi-hole blocking | No | operator |
| `cmd::pihole::disable` | Disable blocking (with optional duration) | No | operator |
| `cmd::pihole::flush-cache` | Flush DNS cache | No | operator |
| `cmd::pihole::update-gravity` | Update blocklists (gravity) | No | admin |

---

## 20. Default Integrations — AdGuard Home

### 20.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::adguard-home` |
| **Category** | DNS & Ad Blocking |
| **Classification** | Default |
| **External System** | AdGuard Home |
| **API** | AdGuard Home REST API (OpenAPI documented) |
| **Authentication** | Username/password (basic auth) |
| **Minimum Agent Tier** | `none` (API-direct) |
| **Primary Execution** | API-direct |

### 20.2 Key Differences from Pi-hole

AdGuard Home has a proper REST API (vs Pi-hole's PHP-based API), supports DNS-over-HTTPS/TLS natively, and has per-client settings. Commands use `cmd::adguard::*` prefix.

### 20.3 Touchpoint Matrix

Same capabilities as Pi-hole (§19.2) with different API implementation and additional features:
- Per-client blocking settings
- DNS rewrites
- DHCP server management

### 20.4 Commands

| Command ID | Description | Dangerous | Role |
|---|---|---|---|
| `cmd::adguard::enable` | Enable protection | No | operator |
| `cmd::adguard::disable` | Disable protection (with duration) | No | operator |
| `cmd::adguard::flush-cache` | Clear DNS cache | No | operator |
| `cmd::adguard::update-filters` | Update filter lists | No | admin |
| `cmd::adguard::add-rewrite` | Add DNS rewrite rule | No | admin |

---

## 21. Default Integrations — TrueNAS

### 21.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::truenas` |
| **Category** | Storage |
| **Classification** | Default |
| **External System** | TrueNAS CORE / SCALE |
| **API** | TrueNAS REST API v2.0 |
| **Authentication** | API key |
| **Minimum Agent Tier** | `none` (API-direct) |
| **Primary Execution** | API-direct |

### 21.2 Touchpoint Matrix

| Touchpoint | Supported | Details |
|---|---|---|
| Profile Enrichment | ✓ | ZFS pools, datasets, shares (SMB/NFS/iSCSI), SMART data, replication tasks |
| Discovery Provider | ✓ | Network shares and connected clients |
| Command Provider | ✓ | `cmd::truenas::create-snapshot`, `cmd::truenas::create-dataset`, `cmd::truenas::start-service`, `cmd::truenas::stop-service`, `cmd::truenas::run-scrub` |
| Execution Handler | ✗ | — |
| Topology Provider | ✓ | Pool→dataset→share hierarchy, replication source→target |
| Workflow Block Provider | ✗ | — |

### 21.3 Profile Enrichment Data

```json
{
  "pluginData": {
    "plg::truenas": {
      "system": {
        "version": "TrueNAS-SCALE-24.04",
        "hostname": "nas-01"
      },
      "pools": [
        {
          "name": "tank",
          "topology": "raidz2",
          "totalBytes": 21474836480000,
          "usedBytes": 10737418240000,
          "health": "ONLINE",
          "datasets": [
            {
              "name": "tank/media",
              "usedBytes": 5368709120000,
              "quotaBytes": null,
              "compression": "lz4",
              "shares": [
                { "type": "smb", "name": "Media", "path": "/mnt/tank/media" }
              ]
            }
          ]
        }
      ],
      "smartStatus": {
        "healthy": 8,
        "warning": 0,
        "critical": 0
      },
      "services": {
        "smb": "running",
        "nfs": "running",
        "ssh": "running"
      }
    }
  }
}
```

### 21.4 Commands

| Command ID | Description | Dangerous | Role |
|---|---|---|---|
| `cmd::truenas::create-snapshot` | Create ZFS snapshot | No | operator |
| `cmd::truenas::create-dataset` | Create new ZFS dataset | No | admin |
| `cmd::truenas::start-service` | Start TrueNAS service | No | operator |
| `cmd::truenas::stop-service` | Stop TrueNAS service | Yes | admin |
| `cmd::truenas::run-scrub` | Run ZFS scrub on pool | No | operator |
| `cmd::truenas::destroy-snapshot` | Destroy ZFS snapshot | Yes | admin |

---

## 22. Default Integrations — Uptime Kuma

### 22.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::uptime-kuma` |
| **Category** | Monitoring & Health |
| **Classification** | Default |
| **External System** | Uptime Kuma |
| **API** | Uptime Kuma Socket.IO API |
| **Authentication** | Username/password or API key |
| **Minimum Agent Tier** | `none` (API-direct) |
| **Primary Execution** | API-direct |

### 22.2 Touchpoint Matrix

| Touchpoint | Supported | Details |
|---|---|---|
| Profile Enrichment | ✓ | Monitor health status, uptime percentage, average response time |
| Discovery Provider | ✓ | Monitored endpoints as service entities |
| Command Provider | ✓ | `cmd::uptimekuma::pause`, `cmd::uptimekuma::resume`, `cmd::uptimekuma::add-monitor` |
| Execution Handler | ✗ | — |
| Topology Provider | ✓ | Monitor→service URL→node mapping |
| Workflow Block Provider | ✗ | — |

### 22.3 Profile Enrichment Data

```json
{
  "pluginData": {
    "plg::uptime-kuma": {
      "monitors": [
        {
          "id": 1,
          "name": "Proxmox Web UI",
          "type": "https",
          "url": "https://proxmox-01:8006",
          "status": "up",
          "uptimePercent24h": 99.99,
          "uptimePercent30d": 99.95,
          "avgResponseMs": 45,
          "lastCheck": "2026-02-13T12:00:00Z",
          "tags": ["infrastructure", "critical"]
        }
      ]
    }
  }
}
```

---

## 23. Default Integrations — Tailscale

### 23.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::tailscale` |
| **Category** | Networking |
| **Classification** | Default |
| **External System** | Tailscale |
| **API** | Tailscale API (`https://api.tailscale.com`) + local `tailscale status` CLI |
| **Authentication** | API key (management) + OAuth (for control plane) |
| **Minimum Agent Tier** | `lite` (detection via CLI), `none` for API-side management |
| **Primary Execution** | API-direct (management API) + Agent-local (local status) |

### 23.2 Touchpoint Matrix

| Touchpoint | Supported | Details |
|---|---|---|
| Profile Enrichment | ✓ | Tailscale IP, hostname, tailnet membership, exit node status, ACL tags |
| Discovery Provider | ✓ | Tailscale-connected devices (overlay network members) |
| Command Provider | ✓ | `cmd::tailscale::approve-device`, `cmd::tailscale::set-exit-node`, `cmd::tailscale::remove-device` |
| Execution Handler | ✗ | — |
| Topology Provider | ✓ | Overlay network topology (which devices can reach which) |
| Workflow Block Provider | ✗ | — |

### 23.3 Profile Enrichment

```json
{
  "pluginData": {
    "plg::tailscale": {
      "tailscaleIp": "100.64.0.5",
      "hostname": "proxmox-01",
      "tailnet": "homelab.ts.net",
      "online": true,
      "lastSeen": "2026-02-13T12:00:00Z",
      "exitNode": false,
      "tags": ["tag:server", "tag:infra"],
      "allowedIps": ["100.64.0.5/32"],
      "os": "linux",
      "clientVersion": "1.60.0"
    }
  }
}
```

---

## 24. Default Integrations — IPMI/Redfish

### 24.1 Overview

| Field | Value |
|---|---|
| **Plugin ID** | `plg::ipmi-redfish` |
| **Category** | Remote Management (Bare Metal) |
| **Classification** | Default |
| **External System** | IPMI BMC / Redfish-enabled BMC |
| **API** | IPMI protocol (via `ipmitool`) + Redfish REST API |
| **Authentication** | IPMI username/password or Redfish session auth |
| **Minimum Agent Tier** | `lite` (detection of `ipmitool`), `normal` (poll-exec), `max` (direct exec + proxy) |
| **Primary Execution** | Agent-local (ipmitool on the host) or API-direct (Redfish REST API to BMC) |

### 24.2 Touchpoint Matrix

| Touchpoint | Supported | Details |
|---|---|---|
| Profile Enrichment | ✓ | Hardware sensor readings (temperatures, fan speeds, voltages), PSU status, firmware version |
| Discovery Provider | ✓ | BMC endpoints on management network |
| Command Provider | ✓ | `cmd::ipmi::power-on`, `cmd::ipmi::power-off`, `cmd::ipmi::power-cycle`, `cmd::ipmi::reset-bmc`, `cmd::ipmi::sol-activate` |
| Execution Handler | ✓ | Routes `cmd::node::shutdown`, `cmd::node::reboot` for bare-metal when OS is unreachable |
| Topology Provider | ✓ | BMC→physical host mapping |
| Workflow Block Provider | ✗ | — |

### 24.3 Execution Handler — Bare Metal Power Control

When `cmd::node::reboot` targets a physical bare-metal server and the OS agent is unreachable, the IPMI plugin provides an alternative execution path:

```python
async def execute_command(self, command_id: str, target: dict, params: dict) -> dict:
    if command_id in ("cmd::node::reboot", "cmd::node::shutdown"):
        node = await get_node(target["nodeId"])
        bmc_ip = node.plugins["plg::ipmi-redfish"].bmc_address
        
        if command_id == "cmd::node::reboot":
            # Try graceful first via agent, fall back to IPMI
            result = await self.ipmi_power(bmc_ip, "cycle")
        elif command_id == "cmd::node::shutdown":
            result = await self.ipmi_power(bmc_ip, "soft")  # ACPI shutdown
        
        return {
            "success": result.success,
            "output": f"IPMI power {result.action} sent to BMC at {bmc_ip}",
            "executionMethod": "plugin-ipmi",
            "warning": "Command sent via out-of-band management (IPMI). OS agent was unreachable."
        }
```

### 24.4 Profile Enrichment Data

```json
{
  "pluginData": {
    "plg::ipmi-redfish": {
      "bmcAddress": "192.168.100.10",
      "bmcFirmware": "2.93",
      "protocol": "ipmi",
      "sensors": [
        { "name": "CPU0 Temp", "value": 42, "unit": "°C", "status": "ok", "threshold": { "upper_critical": 90 } },
        { "name": "CPU1 Temp", "value": 40, "unit": "°C", "status": "ok" },
        { "name": "System Fan 1", "value": 3200, "unit": "RPM", "status": "ok" },
        { "name": "PSU1 Status", "value": "Present", "unit": "", "status": "ok" },
        { "name": "PSU2 Status", "value": "Present", "unit": "", "status": "ok" }
      ],
      "powerStatus": "on",
      "lastPowerEvent": "2026-01-15T10:00:00Z"
    }
  }
}
```

### 24.5 Tier-Specific Behavior

| Tier | Behavior |
|---|---|
| **lite** | Detects `ipmitool` availability. Reports BMC presence. Collects sensor readings during profile cycle. |
| **normal** | Everything in lite. Picks up IPMI power commands from poll queue, executes `ipmitool` locally. |
| **max** | Everything in normal. Exposes `/plugins/ipmi-redfish/sensors` and `/plugins/ipmi-redfish/power` proxy endpoints for synchronous API calls. Can also proxy Redfish REST API calls if BMC supports Redfish. |

---

## 25. Community Plugin Development

### 25.1 Plugin Interface Specification

Community plugins must implement the same `PluginDriver` interface as core/default plugins. The minimal requirements:

1. **Manifest file** (`plugin.json`): Declares plugin metadata, touchpoints, requirements, commands.
2. **API-side driver** (Python module): Implements `PluginDriver` base class for API-side operations.
3. **Agent-side module** (optional, Rust crate): If the plugin needs agent-side execution, provide a compiled Rust module.
4. **Web UI components** (optional, React components): Custom UI for plugin configuration or workflow blocks.

### 25.2 Plugin Distribution

Community plugins are distributed through a Hydra plugin registry:

```
POST /plugins/install
{
  "source": "registry",
  "pluginId": "plg::custom-integration",
  "version": "1.0.0"
}
```

The API downloads the plugin package, validates the manifest, loads the driver module, and makes it available in the plugin registry.

### 25.3 Security Considerations

- Community plugins execute within Hydra's API process — they have access to the database and credentials store. Only install trusted plugins.
- Plugin credentials are isolated — a community plugin cannot access credentials belonging to other plugins.
- All plugin API calls are logged in the audit trail.
- Community plugins cannot modify core Hydra functionality or bypass RBAC.

---

## 26. Implementation Roadmap

### 26.1 Phase Order

Plugin system implementation should follow this dependency order:

```
Phase 2F.1: Plugin System Core (2-3 weeks)
├── Plugin registry (MongoDB collection + API CRUD)
├── Plugin manifest loader + validator
├── Plugin lifecycle management
├── Plugin health check scheduler
├── Agent plugin detection framework
├── Agent plugin config push mechanism
├── Plugin execution path resolver
└── API endpoints for plugin management

Phase 2F.2: Core Plugins — Wave 1 (3-4 weeks)
├── Docker Engine (agent-local, highest everyday use)
├── Proxmox VE (API-direct, hypervisor management)
└── Home Assistant (API-direct, IoT)

Phase 2F.3: Core Plugins — Wave 2 (3-4 weeks)
├── Prometheus (API-direct + agent detection)
├── Ansible (API-local, playbook catalog + dynamic inventory)
└── Terraform (API-local, workspace management + workflow blocks)

Phase 2F.4: Default Plugins — Wave 1 (2-3 weeks)
├── Podman
├── UniFi
├── SNMP
├── pfSense
└── OPNsense

Phase 2F.5: Default Plugins — Wave 2 (2-3 weeks)
├── Traefik
├── Nginx Proxy Manager
├── Pi-hole
├── AdGuard Home
├── TrueNAS
├── Uptime Kuma
├── Tailscale
└── IPMI/Redfish

Phase 2F.6: Community Plugin Framework (1-2 weeks)
├── Plugin package format specification
├── Plugin installation/uninstallation
├── Plugin registry client
└── Developer documentation
```

### 26.2 Total Estimated Duration

14-19 weeks for complete plugin system implementation (including all 19 integrations).

### 26.3 Dependencies

```
Plugin System Core ────────┬──→ Core Plugins Wave 1 ──→ Default Plugins Wave 1
                           │
                           └──→ Core Plugins Wave 2 ──→ Default Plugins Wave 2
                                        │
                                        └──→ Community Plugin Framework
```

Plugin system core depends on:
- Agent Architecture (Phase 2A) — for tier-aware communication
- Command Execution (Phase 2B) — for plugin command routing
- Controls Framework (Phase 2C) — for RBAC on plugin commands

---

## 27. Appendices

### 27.1 Plugin Capability Matrix (Complete)

| Plugin | Profile | Discovery | Commands | Exec Handler | Topology | Workflow Blocks | Agent Tier | Execution Location |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|---|
| **Proxmox VE** | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | lite/max | API-direct |
| **Docker** | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | lite/normal/max | Agent-local |
| **Home Assistant** | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | none | API-direct |
| **Ansible** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | none | API-local |
| **Terraform** | ✗ | ✓ | ✓ | ✗ | ✓ | ✓ | none | API-local |
| **Prometheus** | ✓ | ✓ | ✗ | ✗ | ✓ | ✗ | lite/max | API-direct + Agent |
| **Podman** | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | lite/normal/max | Agent-local |
| **UniFi** | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | none | API-direct |
| **SNMP** | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | none/max | API-direct |
| **pfSense** | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | none | API-direct |
| **OPNsense** | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | none | API-direct |
| **Traefik** | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | none | API-direct |
| **Nginx PM** | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | none | API-direct |
| **Pi-hole** | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | none | API-direct |
| **AdGuard Home** | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | none | API-direct |
| **TrueNAS** | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | none | API-direct |
| **Uptime Kuma** | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | none | API-direct |
| **Tailscale** | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | lite/none | API-direct + Agent |
| **IPMI/Redfish** | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | lite/normal/max | Agent-local + API |

### 27.2 Complete Command Registry (Plugin-Contributed)

| Command ID | Plugin | Role | Dangerous |
|---|---|---|---|
| `cmd::proxmox::create-lxc` | Proxmox VE | admin | Yes |
| `cmd::proxmox::create-vm` | Proxmox VE | admin | Yes |
| `cmd::proxmox::migrate` | Proxmox VE | admin | Yes |
| `cmd::proxmox::snapshot` | Proxmox VE | operator | No |
| `cmd::proxmox::backup` | Proxmox VE | operator | No |
| `cmd::proxmox::clone` | Proxmox VE | admin | Yes |
| `cmd::proxmox::resize-disk` | Proxmox VE | admin | Yes |
| `cmd::docker::pull` | Docker | operator | No |
| `cmd::docker::compose-up` | Docker | operator | No |
| `cmd::docker::compose-down` | Docker | operator | Yes |
| `cmd::docker::prune` | Docker | admin | Yes |
| `cmd::docker::network-create` | Docker | admin | No |
| `cmd::docker::volume-create` | Docker | admin | No |
| `cmd::docker::exec` | Docker | admin | Yes |
| `cmd::ha::turn-on` | Home Assistant | family | No |
| `cmd::ha::turn-off` | Home Assistant | family | No |
| `cmd::ha::toggle` | Home Assistant | family | No |
| `cmd::ha::set-value` | Home Assistant | family | No |
| `cmd::ha::trigger-automation` | Home Assistant | operator | No |
| `cmd::ha::trigger-scene` | Home Assistant | family | No |
| `cmd::ha::set-hvac-mode` | Home Assistant | family | No |
| `cmd::ansible::run-playbook` | Ansible | admin | Yes |
| `cmd::ansible::run-role` | Ansible | admin | Yes |
| `cmd::ansible::gather-facts` | Ansible | operator | No |
| `cmd::ansible::run-ad-hoc` | Ansible | admin | Yes |
| `cmd::terraform::init` | Terraform | admin | No |
| `cmd::terraform::plan` | Terraform | admin | No |
| `cmd::terraform::apply` | Terraform | admin | Yes |
| `cmd::terraform::destroy` | Terraform | admin | Yes |
| `cmd::terraform::import` | Terraform | admin | No |
| `cmd::terraform::state-list` | Terraform | operator | No |
| `cmd::terraform::output` | Terraform | operator | No |
| `cmd::podman::pull` | Podman | operator | No |
| `cmd::podman::pod-create` | Podman | admin | No |
| `cmd::podman::pod-start` | Podman | operator | No |
| `cmd::podman::pod-stop` | Podman | operator | No |
| `cmd::podman::generate-systemd` | Podman | admin | No |
| `cmd::podman::prune` | Podman | admin | Yes |
| `cmd::unifi::restart-device` | UniFi | admin | Yes |
| `cmd::unifi::block-client` | UniFi | admin | No |
| `cmd::unifi::unblock-client` | UniFi | admin | No |
| `cmd::unifi::set-port-profile` | UniFi | admin | No |
| `cmd::unifi::force-provision` | UniFi | admin | No |
| `cmd::snmp::set` | SNMP | admin | Yes |
| `cmd::pfsense::reload-rules` | pfSense | admin | Yes |
| `cmd::pfsense::restart-service` | pfSense | admin | Yes |
| `cmd::pfsense::add-alias` | pfSense | admin | No |
| `cmd::pfsense::add-dhcp-static` | pfSense | operator | No |
| `cmd::opnsense::reload-rules` | OPNsense | admin | Yes |
| `cmd::opnsense::restart-service` | OPNsense | admin | Yes |
| `cmd::opnsense::add-alias` | OPNsense | admin | No |
| `cmd::opnsense::firmware-check` | OPNsense | operator | No |
| `cmd::opnsense::firmware-update` | OPNsense | admin | Yes |
| `cmd::traefik::reload` | Traefik | admin | No |
| `cmd::npm::enable-host` | Nginx PM | operator | No |
| `cmd::npm::disable-host` | Nginx PM | operator | No |
| `cmd::npm::renew-cert` | Nginx PM | operator | No |
| `cmd::pihole::enable` | Pi-hole | operator | No |
| `cmd::pihole::disable` | Pi-hole | operator | No |
| `cmd::pihole::flush-cache` | Pi-hole | operator | No |
| `cmd::pihole::update-gravity` | Pi-hole | admin | No |
| `cmd::adguard::enable` | AdGuard Home | operator | No |
| `cmd::adguard::disable` | AdGuard Home | operator | No |
| `cmd::adguard::flush-cache` | AdGuard Home | operator | No |
| `cmd::adguard::update-filters` | AdGuard Home | admin | No |
| `cmd::adguard::add-rewrite` | AdGuard Home | admin | No |
| `cmd::truenas::create-snapshot` | TrueNAS | operator | No |
| `cmd::truenas::create-dataset` | TrueNAS | admin | No |
| `cmd::truenas::start-service` | TrueNAS | operator | No |
| `cmd::truenas::stop-service` | TrueNAS | admin | Yes |
| `cmd::truenas::run-scrub` | TrueNAS | operator | No |
| `cmd::truenas::destroy-snapshot` | TrueNAS | admin | Yes |
| `cmd::uptimekuma::pause` | Uptime Kuma | operator | No |
| `cmd::uptimekuma::resume` | Uptime Kuma | operator | No |
| `cmd::uptimekuma::add-monitor` | Uptime Kuma | admin | No |
| `cmd::tailscale::approve-device` | Tailscale | admin | No |
| `cmd::tailscale::set-exit-node` | Tailscale | admin | No |
| `cmd::tailscale::remove-device` | Tailscale | admin | Yes |
| `cmd::ipmi::power-on` | IPMI/Redfish | admin | No |
| `cmd::ipmi::power-off` | IPMI/Redfish | admin | Yes |
| `cmd::ipmi::power-cycle` | IPMI/Redfish | admin | Yes |
| `cmd::ipmi::reset-bmc` | IPMI/Redfish | admin | Yes |
| `cmd::ipmi::sol-activate` | IPMI/Redfish | admin | No |

### 27.3 Glossary

| Term | Definition |
|---|---|
| **Plugin** | A module that extends Hydra's capabilities by integrating with an external system. Interchangeable with "integration." |
| **Provider** | The external system a plugin connects to (e.g., Docker Engine, Proxmox VE). Each provider has exactly one plugin. |
| **Touchpoint** | One of six surfaces a plugin can extend: Profile Enrichment, Discovery, Commands, Execution Handler, Topology, Workflow Blocks. |
| **Plugin Manifest** | JSON document declaring a plugin's capabilities, requirements, commands, and configuration schema. |
| **Node Binding** | The association between a plugin and a specific node, including per-node configuration and command routing settings. |
| **Command Routing** | Per-plugin, per-command setting controlling whether a plugin handles command execution for a specific command on a specific node. |
| **Plugin Proxy** | Max-tier agent endpoint that proxies requests to local integration APIs (e.g., Docker socket). |
| **API-direct** | Plugin execution pattern where the API calls the external system's REST API directly. |
| **Agent-local** | Plugin execution pattern where the agent accesses local resources (sockets, CLIs). |
| **API-local** | Plugin execution pattern where the plugin runs CLI tools (Ansible, Terraform) on the API host. |
| **Detection** | Agent process of checking if an integration's external system is available locally. |
| **Enrichment** | Adding plugin-collected data to node profiles beyond native agent collection. |

---

_End of Hydra Integrations & Plugin Architecture Specification_
