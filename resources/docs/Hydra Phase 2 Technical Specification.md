
> **Version:** 0.4.0  
> **Last Updated:** 2026-02-06  
> **Status:** Feature Specification - Network Discovery, Command Execution, Tiered Agent Architecture, Remote Installation, Controls & Integrations  
> **Revision Note:** Updated to incorporate tiered agent model (lite/normal/max), opt-in firewall management, explicit integration command routing, realistic scan performance targets, discovery lifecycle post-registration, enhanced MCP client guidance for external clients, and detailed family role MCP access.

---

## Table of Contents

1. [Document Overview](#1-document-overview)
2. [Network Discovery](#2-network-discovery)
3. [Agent Architecture: Tiered Agents & Bidirectional Communication](#3-agent-architecture-tiered-agents--bidirectional-communication)
4. [Command Execution System](#4-command-execution-system)
5. [Controls Framework](#5-controls-framework)
6. [Remote Agent Installation](#6-remote-agent-installation)
7. [Integrations Framework](#7-integrations-framework)
8. [Cross-Component Implementation](#8-cross-component-implementation)
9. [Security Architecture](#9-security-architecture)
10. [Implementation Roadmap](#10-implementation-roadmap)
11. [Appendices](#11-appendices)

---

## 1. Document Overview

### 1.1 Purpose

This document specifies six interconnected feature areas that extend Hydra's core profiling capabilities into active infrastructure management:

| Feature | Purpose | Dependencies |
|---------|---------|--------------|
| **Network Discovery** | Proactively find devices on networks before registration | Networks, Agent Architecture |
| **Agent Architecture** | Enable tiered agents (lite/normal/max) with bidirectional API ↔ Agent communication for max tier | Core Agent |
| **Command Execution** | Execute controlled operations on infrastructure | Agent Architecture, Controls |
| **Controls Framework** | Define what operations are permitted on what targets | RBAC, Command Execution |
| **Remote Agent Installation** | Deploy agents to discovered nodes automatically | Network Discovery, Agent Architecture |
| **Integrations Framework** | Connect external systems for enhanced capabilities | All components |

### 1.2 Design Principles

**API as Central Authority**
The Hydra API is the authoritative orchestrator. It manages its own network posture, coordinates all operations, and maintains the single source of truth for infrastructure state.

**Explicit Over Implicit**
All operations must be explicitly requested. No scheduled scans, no automatic actions without user initiation. Users maintain full control over when Hydra takes action.

**Security by Default**
Command execution is restricted to registered commands only. External MCP clients are read-only. Network access is allowlisted per node. Credentials are never stored in plain text.

**Graceful Degradation**
When optimal execution paths are unavailable (agent unreachable, integration down), the system falls back to alternative methods rather than failing. Users are always informed of the degraded state.

**Integration-Aware Architecture**
All four Hydra components (API, Agent, Web, MCP) are designed with integration awareness from the ground up. Integrations enhance but never replace core functionality.

### 1.3 Component Responsibility Matrix

| Feature | hydra-api | hydra-agent | hydra-web | hydra-mcp |
|---------|-----------|-------------|-----------|-----------|
| Network Discovery | Scanner, storage, orchestration | Delegated scanning (max tier only) | Scan UI, results display | Discovery tools |
| Agent Architecture | Client to agent servers (max tier) | HTTP server (max), poll executor (normal+max) | Agent status display | Agent control tools |
| Command Execution | Queue, dispatch, audit | Execute via poll (normal) or direct (max) | Command Center UI | Control tools (restricted) |
| Controls | Registry, RBAC enforcement | Execute registered commands (normal+max) | Control panels | Read-only for external clients |
| Remote Installation | SSH execution, coordination | N/A (target doesn't have agent yet) | Install wizard | Install tools |
| Integrations | Driver management, routing | Local integration proxy (max), basic detection (all) | Integration config UI | Integration-powered tools |

---

## 2. Network Discovery

### 2.1 Overview

#### 2.1.1 What

Network Discovery enables Hydra to proactively find devices (potential nodes) on networks before they are registered. It scans for IP:port combinations, fingerprints discovered devices, classifies them by type, and assesses their eligibility for registration as Hydra nodes.

#### 2.1.2 Why

The current Hydra model requires explicit node registration—users must know about a device to add it. Network Discovery inverts this: Hydra finds devices and presents them as candidates. This enables:

- **Infrastructure visibility**: "What's on my network that Hydra doesn't know about?"
- **Onboarding acceleration**: Pre-populated registration forms from fingerprint data
- **Drift detection**: Devices appearing or disappearing between scans
- **AI-assisted operations**: The MCP service can answer questions about unregistered infrastructure

#### 2.1.3 How

The API performs network scanning directly for its own L2 segment. For networks it cannot reach, it delegates scanning to agents that have interfaces on those networks. Discovered devices are stored as candidates until the user chooses to register or dismiss them.

### 2.2 Network Scannability Model

#### 2.2.1 What the API Can Discover

On startup and on-demand, the API introspects its host's network configuration:

```bash
# Interfaces and their networks
ip addr show
# → eth0: 192.168.0.5/24

# Routing table  
ip route show
# → default via 192.168.0.1 dev eth0
# → 192.168.0.0/24 dev eth0 proto kernel scope link src 192.168.0.5

# ARP cache (recently communicated devices)
ip neigh show
# → 192.168.0.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE
```

The API can directly scan any network its host has an interface on.

#### 2.2.2 What the API Cannot Discover

| Limitation | Reason | Mitigation |
|------------|--------|------------|
| VLANs not trunked to API host | L2 isolation—traffic never reaches API interface | Agent delegation or user configuration |
| Networks behind router | API only sees its gateway, not what's behind it | Query router via integration (SNMP, API) or agent delegation |
| Devices on remote subnets without routes | No network path exists | User must configure routing or use agent delegation |

#### 2.2.3 Network Scannability Status

Every network in Hydra has an explicit scannability status:

```json
{
  "networkId": "iot-vlan",
  "cidr": "192.168.10.0/24",
  "gatewayV4": "192.168.10.1",
  
  "origin": {
    "createdBy": "agent-discovery",
    "sourceNodeId": "dual-homed-server",
    "sourceProfileId": "prof_abc123",
    "createdAt": "2026-02-05T10:00:00Z"
  },
  
  "scanConfig": {
    "status": "agent-only",
    "apiReachable": false,
    "apiReachabilityTest": {
      "lastTested": "2026-02-05T10:00:05Z",
      "method": "icmp+tcp",
      "result": "timeout",
      "gatewayReachable": false,
      "sampleHostReachable": false,
      "errorDetails": "No route to 192.168.10.0/24 from API host"
    },
    "delegateAgentNodeIds": ["dual-homed-server"],
    "delegateAgentTierRequired": "max",
    "userGuidance": "This network is not reachable from the Hydra API. Scans will be delegated to max-tier agent on 'dual-homed-server' which has an interface on this network."
  }
}
```

**Status Values:**

| Status | Meaning | Scan Behavior |
|--------|---------|---------------|
| `api-direct` | API has L2 access to this network | API scans directly with ARP + TCP |
| `api-routed` | API can reach via L3 routing | API scans with TCP only (no ARP, no MAC resolution) |
| `agent-only` | API cannot reach, but registered max-tier agent(s) can | Delegate scan to max-tier agent |
| `unreachable` | Neither API nor any agent can reach | Return error with guidance |

### 2.3 Scanning Mechanics

#### 2.3.1 Scan Layers

Discovery uses a layered approach, with each layer providing progressively more information:

**Layer 1: Host Discovery**

| Method | When Used | Provides |
|--------|-----------|----------|
| ARP scan | L2 networks (API direct) | IP → MAC mapping, definitive host presence |
| ICMP echo | L3 networks, initial sweep | Host alive (if not firewalled) |
| TCP SYN | All networks, ports 22, 80, 443 | Host alive (more reliable than ICMP) |

**Layer 2: Port Fingerprinting**

Targeted port scan on discovered hosts. Ports selected for homelab/infrastructure relevance:

```
Tier 1 (always scanned, ~20 ports):
22, 80, 443, 8006, 8080, 8443, 3000, 9090, 8123, 53, 
5353, 161, 554, 1883, 8883, 9100, 3306, 5432, 6379, 27017

Tier 2 (extended scan if requested, +60 ports):
21, 23, 25, 110, 143, 993, 995, 389, 636, 3389, 5900,
8000, 8081, 8181, 9000, 9001, 10000, ... (common service ports)
```

**Port Selection Rationale:**

| Port | Service | Why Included |
|------|---------|--------------|
| 8006 | Proxmox VE | Hypervisor detection |
| 8123 | Home Assistant | IoT hub detection |
| 9100 | Node Exporter | Prometheus metrics |
| 1883/8883 | MQTT | IoT device detection |
| 161 | SNMP | Network device management |
| 554 | RTSP | IP camera detection |

**Layer 3: Service Banner Grabbing**

For open ports, retrieve service identification:

| Protocol | Method | Information Extracted |
|----------|--------|----------------------|
| SSH (22) | Banner read | SSH version, OS hints (e.g., "Debian-2+deb12u3") |
| HTTP (80, 443, 8xxx) | GET / + headers | Server header, redirects, page title |
| SNMP (161) | GET sysDescr | Full device description |
| MQTT (1883) | CONNECT attempt | Broker identification |

**Layer 4: Protocol-Specific Discovery**

Additional discovery protocols for specific device classes:

| Protocol | Target Devices | Information |
|----------|---------------|-------------|
| mDNS/Bonjour | IoT, services | Service advertisements, device model |
| SSDP/UPnP | Media devices, routers | Device description XML |
| LLDP/CDP | Managed switches | Switch identity, port info |
| ARP vendor lookup | All | Manufacturer from MAC OUI |

#### 2.3.2 IoT Device Discovery

For IoT devices specifically, Hydra employs protocols commonly used in smart home ecosystems:

**mDNS (Multicast DNS)**
```
Query: _services._dns-sd._udp.local PTR
Response: 
  _hue._tcp.local
  _homekit._tcp.local
  _matter._tcp.local
```

**SSDP (Simple Service Discovery Protocol)**
```
M-SEARCH * HTTP/1.1
HOST: 239.255.255.250:1900
MAN: "ssdp:discover"
MX: 3
ST: ssdp:all
```

**Device-Specific Probes:**

| Device Type | Detection Method |
|-------------|-----------------|
| Philips Hue | mDNS `_hue._tcp`, HTTP API on port 80 |
| Shelly | mDNS `_shelly._tcp`, HTTP on port 80 |
| ESPHome | mDNS `_esphomelib._tcp` |
| HomeKit | mDNS `_hap._tcp` |
| Matter | mDNS `_matter._tcp`, `_matterc._udp` |
| Chromecast | mDNS `_googlecast._tcp` |
| Sonos | SSDP `urn:schemas-upnp-org:device:ZonePlayer:1` |

These protocols are built into the API scanner (not integration-dependent) to ensure basic IoT discovery works out of the box.

### 2.4 Device Identity: MAC as Stable Identifier

#### 2.4.1 The Problem with IP-Based Identity

IP addresses change due to DHCP lease expiration, network reconfiguration, or device reconnection. Using IP as the primary identifier causes:
- Duplicate discovery records for the same device
- Loss of historical tracking when IP changes
- Inability to distinguish two identical devices on the same network

#### 2.4.2 MAC Address as Primary Identifier

The MAC address is the stable physical identifier. Discovery records anchor to MAC:

```
discoveryId format:
- When MAC known: disc::mac::{normalized_mac}
  Example: disc::mac::dc-a6-32-ab-cd-ef
  
- When MAC unknown (L3 scan): disc::ip::{networkId}::{ip}
  Example: disc::ip::iot-vlan::192.168.10.50
```

**MAC Normalization:** Lowercase, colon-separated → hyphen-separated
```
DC:A6:32:AB:CD:EF → dc-a6-32-ab-cd-ef
```

#### 2.4.3 MAC Resolution for L3 Scans

When the API scans a remote subnet via L3 routing, it cannot directly observe the target's MAC (ARP shows the router's MAC). Resolution strategies:

| Strategy | How It Works | When Available |
|----------|--------------|----------------|
| Router ARP query | Query router's ARP table via SNMP or API | Router is integrated node |
| Agent resolution | Agent on target L2 segment reports MAC | Agent exists on network |
| Deferred resolution | Store as IP-based, upgrade when MAC learned | Always (fallback) |

When a MAC is later resolved for an IP-only record, the record is migrated:
```
disc::ip::iot-vlan::192.168.10.50 
  → merged into → 
disc::mac::dc-a6-32-ab-cd-ef
```

### 2.5 Data Model

#### 2.5.1 Collection: `discovered_nodes`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:discovered_nodes",
  "title": "DiscoveredNode",
  "type": "object",
  "required": ["discoveryId", "identity", "networkId", "probe", "status"],
  "properties": {
    "_id": { "type": "string" },
    "discoveryId": {
      "type": "string",
      "pattern": "^disc::(mac::[a-f0-9-]+|ip::[a-z0-9-]+::[0-9.]+)$",
      "examples": ["disc::mac::dc-a6-32-ab-cd-ef", "disc::ip::iot-vlan::192.168.10.50"]
    },
    
    "identity": {
      "type": "object",
      "required": ["currentIp"],
      "properties": {
        "primaryMac": { 
          "type": ["string", "null"],
          "pattern": "^[a-f0-9]{2}(:[a-f0-9]{2}){5}$",
          "description": "Primary MAC address (null if not yet resolved)"
        },
        "observedMacs": {
          "type": "array",
          "items": { "type": "string" },
          "description": "All MACs observed for this device (multi-NIC devices)"
        },
        "macVendor": {
          "type": ["string", "null"],
          "description": "Manufacturer from OUI lookup"
        },
        "macResolved": {
          "type": "boolean",
          "description": "Whether MAC has been definitively resolved"
        },
        "currentIp": {
          "type": "string",
          "format": "ipv4"
        },
        "observedIps": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "address": { "type": "string", "format": "ipv4" },
              "seenAt": { "type": "string", "format": "date-time" },
              "seenInScan": { "type": "string" }
            }
          },
          "description": "Historical IP addresses for this device"
        },
        "hostname": {
          "type": ["string", "null"],
          "description": "Discovered hostname"
        },
        "hostnameSources": {
          "type": "array",
          "items": { 
            "type": "string",
            "enum": ["dns-reverse", "mdns", "netbios", "snmp", "http-title", "ssh-banner"]
          },
          "description": "How hostname was discovered"
        }
      }
    },
    
    "networkId": {
      "type": "string",
      "description": "Network where device was discovered"
    },
    
    "probe": {
      "type": "object",
      "required": ["scannedBy", "scannedAt", "method"],
      "properties": {
        "scannedBy": {
          "type": "string",
          "enum": ["api"],
          "description": "Always 'api' or a nodeId if delegated"
        },
        "scannedFrom": {
          "type": "string",
          "format": "ipv4",
          "description": "IP address of the scanner"
        },
        "scanId": {
          "type": "string",
          "description": "Reference to the scan that found this device"
        },
        "method": {
          "type": "string",
          "enum": ["arp", "arp+tcp", "tcp", "icmp+tcp", "mdns", "ssdp"],
          "description": "Primary discovery method used"
        },
        "scannedAt": {
          "type": "string",
          "format": "date-time"
        },
        "durationMs": {
          "type": "integer",
          "description": "Time to fully fingerprint this device"
        }
      }
    },
    
    "fingerprint": {
      "type": "object",
      "properties": {
        "openPorts": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["port", "protocol"],
            "properties": {
              "port": { "type": "integer", "minimum": 1, "maximum": 65535 },
              "protocol": { "type": "string", "enum": ["tcp", "udp"] },
              "state": { "type": "string", "enum": ["open", "filtered", "open|filtered"] },
              "service": { "type": ["string", "null"] },
              "banner": { "type": ["string", "null"], "maxLength": 1024 },
              "inference": {
                "type": "object",
                "properties": {
                  "os": { "type": "string" },
                  "arch": { "type": "string" },
                  "application": { "type": "string" },
                  "version": { "type": "string" }
                }
              }
            }
          }
        },
        "protocols": {
          "type": "object",
          "properties": {
            "mdns": {
              "type": ["object", "null"],
              "properties": {
                "services": { "type": "array", "items": { "type": "string" } },
                "hostname": { "type": "string" },
                "txtRecords": { "type": "object" }
              }
            },
            "ssdp": {
              "type": ["object", "null"],
              "properties": {
                "server": { "type": "string" },
                "location": { "type": "string" },
                "usn": { "type": "string" },
                "deviceType": { "type": "string" }
              }
            },
            "snmp": {
              "type": ["object", "null"],
              "properties": {
                "sysDescr": { "type": "string" },
                "sysName": { "type": "string" },
                "sysObjectID": { "type": "string" }
              }
            },
            "lldp": {
              "type": ["object", "null"],
              "properties": {
                "chassisId": { "type": "string" },
                "portId": { "type": "string" },
                "systemName": { "type": "string" },
                "systemDescription": { "type": "string" }
              }
            }
          }
        },
        "httpResponses": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "port": { "type": "integer" },
              "statusCode": { "type": "integer" },
              "server": { "type": "string" },
              "title": { "type": "string" },
              "redirectTo": { "type": "string" },
              "identifiedAs": { "type": "string" }
            }
          },
          "description": "HTTP responses from web ports"
        }
      }
    },
    
    "classification": {
      "type": "object",
      "properties": {
        "suggestedClass": {
          "type": "string",
          "enum": ["compute", "networking", "iot", "unknown"]
        },
        "suggestedType": {
          "type": "string",
          "enum": ["physical", "logical", "unknown"]
        },
        "suggestedKind": {
          "type": ["string", "null"],
          "description": "Specific device kind (sbc, router, switch, sensor, etc.)"
        },
        "suggestedNodeId": {
          "type": ["string", "null"],
          "description": "Auto-generated node ID suggestion"
        },
        "suggestedDisplayName": {
          "type": ["string", "null"],
          "description": "Human-friendly name suggestion"
        },
        "confidence": {
          "type": "number",
          "minimum": 0,
          "maximum": 1,
          "description": "Classification confidence (0-1)"
        },
        "signals": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Evidence supporting the classification"
        }
      }
    },
    
    "eligibility": {
      "type": "object",
      "properties": {
        "registerable": {
          "type": "boolean",
          "description": "Can this device be registered as a Hydra node?"
        },
        "agentCompatible": {
          "type": "boolean",
          "description": "Can this device run the Hydra agent?"
        },
        "agentPlatform": {
          "type": ["string", "null"],
          "enum": ["linux-x86_64", "linux-arm64", "linux-armv7", "freebsd-x86_64", "macos-arm64", null],
          "description": "Platform for agent binary if compatible"
        },
        "profilingStrategy": {
          "type": "string",
          "enum": ["agent", "snmp", "integration", "homeassistant", "manual", "none"],
          "description": "How this device would be profiled if registered"
        },
        "remoteInstallable": {
          "type": "boolean",
          "description": "Can agent be remotely installed?"
        },
        "remoteInstallMethod": {
          "type": ["string", "null"],
          "enum": ["ssh", "proxmox-exec", "docker-exec", null]
        },
        "remoteInstallBlockers": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Why remote install is not possible"
        },
        "blockers": {
          "type": "array",
          "items": { "type": "string" },
          "description": "General registration blockers"
        },
        "notes": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Additional information for the user"
        }
      }
    },
    
    "status": {
      "type": "string",
      "enum": ["pending", "registered", "dismissed"],
      "description": "Current status in discovery workflow"
    },
    "matchedNodeId": {
      "type": ["string", "null"],
      "description": "If registered, the resulting node ID"
    },
    "dismissedAt": {
      "type": ["string", "null"],
      "format": "date-time"
    },
    "dismissedBy": {
      "type": ["string", "null"]
    },
    "dismissReason": {
      "type": ["string", "null"],
      "description": "Why this discovery was dismissed"
    },
    
    "firstSeen": {
      "type": "string",
      "format": "date-time"
    },
    "lastSeen": {
      "type": "string",
      "format": "date-time"
    },
    "seenCount": {
      "type": "integer",
      "minimum": 1,
      "description": "Number of scans that found this device"
    }
  }
}
```

#### 2.5.2 Collection: `discovery_scans`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:discovery_scans",
  "title": "DiscoveryScan",
  "type": "object",
  "required": ["scanId", "triggeredBy", "targetNetworks", "status"],
  "properties": {
    "_id": { "type": "string" },
    "scanId": {
      "type": "string",
      "pattern": "^scan_[a-z0-9]+$"
    },
    "triggeredBy": {
      "type": "string",
      "description": "User ID who initiated the scan"
    },
    "triggeredVia": {
      "type": "string",
      "enum": ["api", "web", "mcp"]
    },
    "targetNetworks": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1
    },
    "scanOptions": {
      "type": "object",
      "properties": {
        "portTier": { "type": "string", "enum": ["tier1", "tier2"] },
        "includeIoTProtocols": { "type": "boolean", "default": true },
        "includeSnmp": { "type": "boolean", "default": true },
        "timeout": { "type": "integer", "default": 300 }
      }
    },
    "execution": {
      "type": "object",
      "properties": {
        "scannedBy": { "type": "string" },
        "scannedFrom": { "type": "string" },
        "method": { "type": "string" },
        "delegatedTo": { 
          "type": ["string", "null"],
          "description": "Agent nodeId if delegated"
        }
      }
    },
    "status": {
      "type": "string",
      "enum": ["pending", "running", "completed", "failed", "cancelled"]
    },
    "startedAt": { "type": ["string", "null"], "format": "date-time" },
    "completedAt": { "type": ["string", "null"], "format": "date-time" },
    "results": {
      "type": "object",
      "properties": {
        "hostsScanned": { "type": "integer" },
        "hostsAlive": { "type": "integer" },
        "newDiscoveries": { "type": "integer" },
        "returningDevices": { "type": "integer" },
        "departedSinceLast": { "type": "integer" },
        "alreadyRegistered": { "type": "integer" },
        "errors": { "type": "integer" }
      }
    },
    "error": {
      "type": ["object", "null"],
      "properties": {
        "code": { "type": "string" },
        "message": { "type": "string" },
        "details": { "type": "object" }
      }
    }
  }
}
```

#### 2.5.3 Indexes

```javascript
// discovered_nodes indexes
db.discovered_nodes.createIndex({ "discoveryId": 1 }, { unique: true })
db.discovered_nodes.createIndex({ "identity.primaryMac": 1 })
db.discovered_nodes.createIndex({ "identity.currentIp": 1, "networkId": 1 })
db.discovered_nodes.createIndex({ "networkId": 1, "status": 1 })
db.discovered_nodes.createIndex({ "classification.suggestedClass": 1 })
db.discovered_nodes.createIndex({ "lastSeen": 1 })
db.discovered_nodes.createIndex({ "status": 1, "lastSeen": -1 })

// discovery_scans indexes
db.discovery_scans.createIndex({ "scanId": 1 }, { unique: true })
db.discovery_scans.createIndex({ "triggeredBy": 1, "startedAt": -1 })
db.discovery_scans.createIndex({ "targetNetworks": 1 })
db.discovery_scans.createIndex({ "status": 1 })
```

### 2.6 Classification Engine

#### 2.6.1 Classification Rules

The classification engine applies deterministic rules based on fingerprint signals:

**Compute Node Detection:**

| Signal | Classification | Confidence Boost |
|--------|---------------|------------------|
| SSH open + Linux banner | compute/physical | +0.3 |
| Port 8006 + Proxmox response | compute/physical/hypervisor | +0.4 |
| MAC vendor: Raspberry Pi | compute/physical/sbc | +0.3 |
| SSH banner: "Debian", "Ubuntu", "CentOS" | compute (confirms) | +0.2 |
| mDNS model: "Raspberry Pi *" | compute/physical/sbc | +0.3 |

**Networking Device Detection:**

| Signal | Classification | Confidence Boost |
|--------|---------------|------------------|
| SNMP sysDescr contains "router" | networking/physical/router | +0.4 |
| SNMP sysDescr contains "switch" | networking/physical/switch | +0.4 |
| Port 443 + OPNsense/pfSense response | networking/physical/router | +0.4 |
| MAC vendor: Ubiquiti, Cisco, Netgear | networking (suggests) | +0.2 |
| LLDP response present | networking (confirms) | +0.3 |
| Multiple VLANs detected | networking/physical (confirms) | +0.2 |

**IoT Device Detection:**

| Signal | Classification | Confidence Boost |
|--------|---------------|------------------|
| mDNS `_hue._tcp` | iot/physical/lighting | +0.5 |
| mDNS `_homekit._tcp` | iot/physical | +0.3 |
| SSDP Sonos response | iot/physical/speaker | +0.5 |
| MAC vendor: Espressif | iot/physical/sensor | +0.3 |
| Port 1883 (MQTT) only | iot/physical | +0.2 |
| Port 8123 + Home Assistant | iot/logical/hub | +0.4 |
| mDNS `_esphomelib._tcp` | iot/physical/sensor | +0.4 |
| MAC vendor: Shelly, Sonoff | iot/physical/switch | +0.4 |

#### 2.6.2 Confidence Calculation

```python
def calculate_confidence(signals: list[ClassificationSignal]) -> float:
    """
    Confidence starts at 0.0 and accumulates from matching signals.
    Capped at 0.95 (never 100% certain from network probing alone).
    """
    confidence = 0.0
    for signal in signals:
        confidence += signal.confidence_boost
    return min(confidence, 0.95)
```

#### 2.6.3 Eligibility Assessment

**Agent Compatibility:**

```python
def assess_agent_compatibility(fingerprint: Fingerprint) -> AgentEligibility:
    # Must be compute class
    if classification.suggested_class != "compute":
        return AgentEligibility(
            compatible=False,
            reason="Only compute nodes can run the Hydra agent"
        )
    
    # Determine platform from signals
    platform = None
    if "arm64" in ssh_banner or "aarch64" in ssh_banner:
        platform = "linux-arm64"
    elif "x86_64" in ssh_banner or "amd64" in ssh_banner:
        platform = "linux-x86_64"
    elif "armv7" in ssh_banner:
        platform = "linux-armv7"
    elif mac_vendor == "Raspberry Pi":
        platform = "linux-arm64"  # Assume Pi 4/5
    
    if platform is None:
        return AgentEligibility(
            compatible=True,  # Probably compatible, just unknown platform
            platform=None,
            notes=["Platform could not be determined from fingerprint"]
        )
    
    # Check if we have binary for this platform
    if platform not in available_agent_binaries:
        return AgentEligibility(
            compatible=False,
            reason=f"No agent binary available for {platform}"
        )
    
    return AgentEligibility(
        compatible=True,
        platform=platform
    )
```

**Remote Install Eligibility:**

```python
def assess_remote_install(fingerprint: Fingerprint, parent_node: Node | None) -> RemoteInstallEligibility:
    blockers = []
    method = None
    
    # Check SSH access
    ssh_port = fingerprint.get_open_port(22)
    if ssh_port and ssh_port.state == "open":
        method = "ssh"
    
    # Check Proxmox parent (for LXC/VM)
    if parent_node and parent_node.has_integration("proxmox"):
        method = "proxmox-exec"
    
    # No method available
    if method is None:
        blockers.append("No SSH access detected")
        blockers.append("No parent hypervisor with Proxmox integration")
        return RemoteInstallEligibility(
            installable=False,
            blockers=blockers
        )
    
    return RemoteInstallEligibility(
        installable=True,
        method=method
    )
```

### 2.7 API Endpoints

#### 2.7.1 Trigger Network Scan

```
POST /discovery/scan
```

**Request Body:**

```json
{
  "networkIds": ["homenet-lan"],
  "options": {
    "portTier": "tier1",
    "includeIoTProtocols": true,
    "includeSnmp": true,
    "timeout": 300
  }
}
```

**Response (API can scan directly):** `202 Accepted`

```json
{
  "scanId": "scan_abc123",
  "status": "running",
  "networks": [
    {
      "networkId": "homenet-lan",
      "method": "direct",
      "scanner": "api"
    }
  ],
  "streamUrl": "/discovery/scan/scan_abc123/stream"
}
```

**Response (delegated to max-tier agent):** `202 Accepted`

```json
{
  "scanId": "scan_def456",
  "status": "delegating",
  "networks": [
    {
      "networkId": "iot-vlan",
      "method": "agent-delegated",
      "scanner": "dual-homed-server",
      "agentTier": "max",
      "notes": "This network is not directly reachable from the Hydra API. Scan delegated to max-tier agent on 'dual-homed-server' which has an interface on this network."
    }
  ]
}
```

> **Note:** Scan delegation requires a max-tier agent on the target network. If only lite or normal tier agents are available on that network, the scan will fail with guidance to upgrade the agent or manually configure routing.

**Response (network not scannable):** `400 Bad Request`

```json
{
  "error": "NETWORK_NOT_SCANNABLE",
  "network": "guest-vlan",
  "reason": "Network is not reachable from API and no agent has an interface on this network.",
  "guidance": [
    "Option 1: Configure router to allow traffic from API host (192.168.0.5) to 192.168.20.0/24",
    "Option 2: Install Hydra agent on a device connected to this network",
    "Option 3: Register a node on this network manually, then retry the scan"
  ]
}
```

**Required Permission:** `discovery:scan` (operator, admin)

---

#### 2.7.2 Stream Scan Results (WebSocket — API-Direct Scans Only)

This WebSocket endpoint is available only for scans executed directly by the API (`api-direct` and `api-routed` networks). For agent-delegated scans, clients should poll `GET /discovery/scan/{scanId}` instead.

```
GET /discovery/scan/{scanId}/stream
Upgrade: websocket
```

**Server Messages:**

```json
// Progress update
{
  "type": "progress",
  "scanned": 45,
  "total": 254,
  "phase": "port-scanning",
  "currentHost": "192.168.0.45"
}

// Device discovered
{
  "type": "discovery",
  "discoveryId": "disc::mac::dc-a6-32-ab-cd-ef",
  "ip": "192.168.0.47",
  "mac": "dc:a6:32:ab:cd:ef",
  "hostname": "raspberrypi",
  "classification": {
    "suggestedClass": "compute",
    "suggestedKind": "sbc",
    "confidence": 0.85
  },
  "isNew": true
}

// Scan complete
{
  "type": "complete",
  "scanId": "scan_abc123",
  "results": {
    "hostsScanned": 254,
    "hostsAlive": 23,
    "newDiscoveries": 2,
    "returningDevices": 18,
    "departedSinceLast": 1,
    "alreadyRegistered": 15
  }
}
```

---

#### 2.7.3 List Discovered Nodes

```
GET /discovery/results
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `networkId` | string | Filter by network |
| `status` | enum | `pending`, `registered`, `dismissed` |
| `class` | enum | `compute`, `networking`, `iot`, `unknown` |
| `agentCompatible` | boolean | Filter by agent compatibility |
| `remoteInstallable` | boolean | Filter by remote install capability |
| `minConfidence` | number | Minimum classification confidence (0-1) |
| `since` | datetime | Discovered after timestamp |
| `limit` | integer | Max results (default: 50) |
| `offset` | integer | Pagination offset |

**Response:** `200 OK`

```json
{
  "discoveries": [
    {
      "discoveryId": "disc::mac::dc-a6-32-ab-cd-ef",
      "identity": {
        "primaryMac": "dc:a6:32:ab:cd:ef",
        "macVendor": "Raspberry Pi Trading Ltd",
        "currentIp": "192.168.0.47",
        "hostname": "raspberrypi"
      },
      "networkId": "homenet-lan",
      "classification": {
        "suggestedClass": "compute",
        "suggestedType": "physical",
        "suggestedKind": "sbc",
        "suggestedDisplayName": "Raspberry Pi (Pi-hole)",
        "confidence": 0.85
      },
      "eligibility": {
        "registerable": true,
        "agentCompatible": true,
        "agentPlatform": "linux-arm64",
        "remoteInstallable": true,
        "remoteInstallMethod": "ssh"
      },
      "status": "pending",
      "firstSeen": "2026-01-20T08:00:00Z",
      "lastSeen": "2026-02-05T12:00:00Z",
      "seenCount": 4
    }
  ],
  "total": 8,
  "limit": 50,
  "offset": 0
}
```

**Required Permission:** `discovery:read` (viewer, operator, admin)

---

#### 2.7.4 Get Discovery Details

```
GET /discovery/results/{discoveryId}
```

**Response:** `200 OK`

Returns full `DiscoveredNode` document including complete fingerprint data.

**Required Permission:** `discovery:read`

---

#### 2.7.5 Register Discovered Node

```
POST /discovery/results/{discoveryId}/register
```

**Request Body:**

```json
{
  "nodeId": "pihole-01",
  "displayName": "Pi-hole DNS Server",
  "description": "Primary DNS server running Pi-hole",
  "class": "compute",
  "type": "physical",
  "kind": "sbc",
  "tags": ["dns", "critical"],
  "overrideClassification": false
}
```

If `overrideClassification` is false, `class`, `type`, `kind` can be omitted and will use suggested values.

**Response:** `201 Created`

```json
{
  "nodeId": "pihole-01",
  "apiKey": "hyk_node_abc123...",
  "apiKeyId": "key_node_abc123",
  "registeredBy": "user_admin001",
  "registeredAt": "2026-02-05T12:30:00Z",
  "status": "active",
  "fromDiscovery": "disc::mac::dc-a6-32-ab-cd-ef"
}
```

**Required Permission:** `nodes:create` (operator, admin)

---

#### 2.7.6 Dismiss Discovery

```
POST /discovery/results/{discoveryId}/dismiss
```

**Request Body:**

```json
{
  "reason": "Personal device - not infrastructure",
  "permanent": false
}
```

If `permanent` is true, the device will be added to an exclusion list and won't appear in future scans.

**Response:** `200 OK`

```json
{
  "discoveryId": "disc::mac::aa-bb-cc-dd-ee-ff",
  "status": "dismissed",
  "dismissedAt": "2026-02-05T12:35:00Z",
  "dismissedBy": "user_admin001",
  "permanent": false
}
```

**Required Permission:** `discovery:dismiss` (operator, admin)

---

#### 2.7.7 Scan Diff (Compare Scans)

```
GET /discovery/diff
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `networkId` | string | Required: Network to compare |
| `fromScan` | string | Earlier scan ID (default: previous scan) |
| `toScan` | string | Later scan ID (default: latest scan) |

**Response:** `200 OK`

```json
{
  "network": "homenet-lan",
  "fromScan": {
    "scanId": "scan_abc123",
    "completedAt": "2026-02-04T12:00:00Z"
  },
  "toScan": {
    "scanId": "scan_def456",
    "completedAt": "2026-02-05T12:00:00Z"
  },
  "diff": {
    "arrived": [
      {
        "discoveryId": "disc::mac::11-22-33-44-55-66",
        "ip": "192.168.0.99",
        "hostname": "new-device",
        "classification": { "suggestedClass": "compute" }
      }
    ],
    "departed": [
      {
        "discoveryId": "disc::mac::aa-bb-cc-dd-ee-ff",
        "lastIp": "192.168.0.50",
        "lastSeen": "2026-02-04T12:00:00Z"
      }
    ],
    "changed": [
      {
        "discoveryId": "disc::mac::dc-a6-32-ab-cd-ef",
        "changes": {
          "ip": { "from": "192.168.0.47", "to": "192.168.0.52" },
          "openPorts": { "added": [8080], "removed": [] }
        }
      }
    ],
    "unchanged": 18
  }
}
```

**Required Permission:** `discovery:read`

---

#### 2.7.8 Manage Exclusions

```
GET /discovery/exclusions
POST /discovery/exclusions
DELETE /discovery/exclusions/{exclusionId}
```

**POST Request Body:**

```json
{
  "type": "mac",
  "value": "aa:bb:cc:dd:ee:ff",
  "label": "Wife's laptop",
  "reason": "Personal device"
}
```

or

```json
{
  "type": "ip-range",
  "value": "192.168.0.200-192.168.0.254",
  "label": "DHCP guest range",
  "reason": "Transient devices"
}
```

**Required Permission:** `discovery:configure` (admin)

### 2.9 Discovery Lifecycle: Post-Registration Behavior

#### 2.9.1 Compute Nodes (Agent-Managed)

Once a discovered compute node has been fully registered and its agent is running, the agent becomes the authoritative source for all profiling data. The discovery record is **retained** in the `discovered_nodes` collection with `status: "registered"` and `matchedNodeId` set, but subsequent network scans **skip** this device for fingerprinting purposes.

```python
def should_fingerprint_discovered_device(discovery: DiscoveredNode) -> bool:
    """
    Determine if a previously discovered device needs re-fingerprinting during a scan.
    """
    if discovery.status == "registered" and discovery.matched_node_id:
        node = get_node(discovery.matched_node_id)
        if node and node.agent and node.agent.installed:
            # Agent handles all profiling — no need to re-fingerprint
            # Just update lastSeen timestamp for presence tracking
            return False
    
    return True
```

Rationale: For compute nodes, the agent collects far richer data than a network fingerprint ever could (hardware details, software inventory, service enumeration, etc.). Re-scanning a registered compute node during discovery adds no value and wastes scan time. The discovery record persists as a historical artifact of how the node was originally found.

#### 2.9.2 IoT and Networking Nodes (No Agent)

IoT and networking devices cannot run the Hydra agent. For these node classes, network discovery remains the **only mechanism** Hydra has to detect changes. When a scan encounters a device that is already registered as an IoT or networking node, Hydra **does** re-fingerprint it and compares the new fingerprint against the stored discovery data for drift detection.

```python
def process_returning_registered_device(discovery: DiscoveredNode, new_fingerprint: Fingerprint) -> DriftReport | None:
    """
    For registered IoT/networking nodes, compare current fingerprint to stored data.
    """
    node = get_node(discovery.matched_node_id)
    
    if node.node_class in ("iot", "networking"):
        # Compare fingerprints for drift
        drift = compare_fingerprints(discovery.fingerprint, new_fingerprint)
        
        if drift.has_changes:
            # Update stored fingerprint
            discovery.fingerprint = new_fingerprint
            discovery.last_seen = now()
            discovery.seen_count += 1
            save(discovery)
            
            return DriftReport(
                node_id=node.node_id,
                discovery_id=discovery.discovery_id,
                changes=drift.changes,
                # e.g., "Port 8123 no longer open", "New mDNS service: _matter._tcp"
                severity=drift.severity
            )
        
        # No changes — just update presence
        discovery.last_seen = now()
        discovery.seen_count += 1
        save(discovery)
    
    return None
```

Drift examples for IoT/networking nodes:

| Change Type | Example | Severity |
|-------------|---------|----------|
| Port appeared | Smart plug now exposing port 80 (firmware update added web UI) | info |
| Port disappeared | Switch management port 443 no longer responding | warning |
| New protocol | Device now advertising `_matter._tcp` via mDNS | info |
| IP changed | Device moved from 192.168.10.50 to 192.168.10.55 | info |
| MAC changed | Device at same IP now has different MAC (possible replacement) | warning |
| Service version changed | SNMP sysDescr shows new firmware version | info |

#### 2.9.3 Summary: Discovery Data Retention

| Node Class | Agent Installed | Re-Fingerprint on Scan | Discovery Record | Primary Data Source |
|------------|----------------|----------------------|------------------|-------------------|
| compute | Yes | No (skip, just update lastSeen) | Retained, `status: "registered"` | Agent profiles |
| compute | No (pending install) | Yes | Active, `status: "pending"` | Discovery fingerprint |
| iot | N/A (cannot run agent) | Yes (drift detection) | Active, `status: "registered"` | Discovery fingerprint + integration (HA) |
| networking | N/A (cannot run agent) | Yes (drift detection) | Active, `status: "registered"` | Discovery fingerprint + integration (SNMP) |

### 2.8 MCP Tools

#### 2.8.1 scan_network

```json
{
  "name": "scan_network",
  "description": "Trigger a network discovery scan to find devices not yet registered in Hydra",
  "inputSchema": {
    "type": "object",
    "properties": {
      "networkIds": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Network IDs to scan. If omitted, scans API's own network."
      },
      "portTier": {
        "type": "string",
        "enum": ["tier1", "tier2"],
        "default": "tier1",
        "description": "Port scan depth: tier1 (~20 ports) or tier2 (~80 ports)"
      }
    }
  }
}
```

#### 2.8.2 list_discoveries

```json
{
  "name": "list_discoveries",
  "description": "List devices discovered on the network that are not yet registered as Hydra nodes",
  "inputSchema": {
    "type": "object",
    "properties": {
      "networkId": { "type": "string" },
      "status": { "type": "string", "enum": ["pending", "all"] },
      "class": { "type": "string", "enum": ["compute", "networking", "iot"] },
      "agentCompatible": { "type": "boolean" }
    }
  }
}
```

#### 2.8.3 assess_discovery

```json
{
  "name": "assess_discovery",
  "description": "Get detailed analysis of a discovered device including fingerprint, classification signals, and eligibility",
  "inputSchema": {
    "type": "object",
    "required": ["discoveryId"],
    "properties": {
      "discoveryId": { "type": "string" }
    }
  }
}
```

#### 2.8.4 register_discovery

```json
{
  "name": "register_discovery",
  "description": "Register a discovered device as a Hydra node",
  "inputSchema": {
    "type": "object",
    "required": ["discoveryId"],
    "properties": {
      "discoveryId": { "type": "string" },
      "nodeId": { "type": "string", "description": "Override suggested node ID" },
      "displayName": { "type": "string", "description": "Override suggested display name" },
      "tags": { "type": "array", "items": { "type": "string" } }
    }
  }
}
```

### 2.9 Implementation Notes

#### 2.9.1 Recommended Libraries (Python)

| Library | Purpose | Notes |
|---------|---------|-------|
| `scapy` | ARP scanning, packet crafting | Requires root/CAP_NET_RAW |
| `python-nmap` | Port scanning (wraps nmap) | Requires nmap binary |
| `asyncio` + `socket` | TCP connect scanning | No special privileges needed |
| `aiodns` | Async DNS resolution | For reverse DNS lookups |
| `zeroconf` | mDNS/Bonjour discovery | Pure Python, no deps |
| `async-upnp-client` | SSDP/UPnP discovery | Async compatible |
| `pysnmp` | SNMP queries | For network device profiling |
| `mac-vendor-lookup` | OUI database lookup | Offline MAC vendor resolution |
| `httpx` | Async HTTP client | For banner grabbing |

#### 2.9.2 Privilege Requirements

The API process needs network scanning capabilities:

| Capability | Required For | Alternative |
|------------|--------------|-------------|
| `CAP_NET_RAW` | ARP scanning | Use TCP-only scanning (loses MAC resolution) |
| `CAP_NET_ADMIN` | Firewall management | Run firewall commands via sudo |

**Container Configuration (Docker):**

```yaml
services:
  hydra-api:
    cap_add:
      - NET_RAW
      - NET_ADMIN
    network_mode: host  # Required for L2 access
```

**Alternative: Unprivileged Mode**

If running without elevated privileges, the API falls back to TCP-only scanning. Users are informed of reduced capability:

```json
{
  "scanCapabilities": {
    "arp": false,
    "tcp": true,
    "note": "Running without CAP_NET_RAW. MAC addresses cannot be resolved for local network. Consider running with elevated privileges for full discovery capabilities."
  }
}
```

#### 2.9.3 Scan Performance Targets

Discovery uses a phased approach. Targets below represent the full pipeline (host discovery → port scan → fingerprinting → classification):

**Host Discovery Phase (ARP/ICMP/TCP SYN):**

| Network Size | Target Duration | Concurrency |
|--------------|-----------------|-------------|
| /24 (254 hosts) | < 15 seconds | 50 concurrent probes |
| /16 (65,534 hosts) | < 10 minutes | 100 concurrent probes |

**Full Fingerprinting Phase (port scan + banner grab + protocol probes):**

| Network Size | Target Duration | Concurrency | Notes |
|--------------|-----------------|-------------|-------|
| /24 (254 hosts) | 2-5 minutes | 50 concurrent probes | mDNS/SSDP listeners require 3-5s dwell time |
| /16 (65,534 hosts) | 45-90 minutes | 100 concurrent probes | Full /16 scans should be rare in homelab use |

Host discovery results are streamed to the client as they are found (within seconds), while full fingerprinting completes in the background. This means the user sees hosts appear quickly, with classification details populating progressively.

**SNMP Query Overhead:** SNMP queries add 2-5 seconds per responding device due to timeout windows. For networks with many SNMP-capable devices, this is the dominant cost in the fingerprinting phase.

#### 2.9.4 Scan Streaming Scope

**WebSocket streaming (`/discovery/scan/{scanId}/stream`) is for API-executed scans only.** This includes:

- Scans the API performs directly on its own L2/L3-reachable networks
- Networks where the API has `api-direct` or `api-routed` scannability status

**For agent-delegated scans** (networks with `agent-only` scannability status), the max-tier agent performs the scan locally and reports results back to the API via the standard API endpoints (the agent POSTs discovered nodes to the API). The API then stores the results in `discovered_nodes` and `discovery_scans` collections. The web UI polls the scan status via `GET /discovery/scan/{scanId}` rather than receiving a WebSocket stream. This is because:

1. The agent is on a different network segment — maintaining a WebSocket relay through the API adds unnecessary complexity
2. Agent-delegated scans may take longer due to constrained hardware
3. The API already has the polling infrastructure for agent communication

The web UI handles both cases transparently: it connects to the WebSocket for API-direct scans and falls back to polling for agent-delegated scans, showing a progress indicator in both cases.

---

## 3. Agent Architecture: Tiered Agents & Bidirectional Communication

### 3.1 Overview

#### 3.1.1 What

The agent architecture is extended to support three deployment tiers—**lite**, **normal**, and **max**—each offering progressively more capabilities. The **max** tier introduces bidirectional communication where agents expose an HTTP server that the API can call directly to execute commands, trigger scans, and check health.

#### 3.1.2 Why

Not all nodes need the same agent capabilities. A Raspberry Pi Zero running Pi-hole doesn't need a built-in HTTP server and network scanner. A Proxmox hypervisor managing 20 LXCs does. Tiered agents allow Hydra to:

- **Right-size the footprint**: Minimal resource usage on constrained devices
- **Match capability to role**: Only nodes that need bidirectional communication get it
- **Simplify deployment**: Users install what they need, nothing more
- **Enable instant command execution** (max tier): API calls agent directly, gets result in seconds
- **Support delegated scanning** (max tier): API can ask agents to scan their local networks immediately

#### 3.1.3 How

Agents are compiled as a single binary with feature-gated capabilities. The tier is set at install time and determines which features are active. The API tracks each agent's tier and routes commands accordingly—direct call for max-tier agents, poll-based for normal-tier, profile-only for lite-tier.

#### 3.1.4 Agent Tiers

The agent ships in three tiers. Each tier is a superset of the previous:

| Tier | Binary Size Target | Capabilities | Ideal For |
|------|-------------------|--------------|-----------|
| **lite** | ~5 MB | Profile collection, profile submission, minimal integration detection | SBCs, low-resource nodes, single-purpose devices |
| **normal** | ~10 MB | Everything in lite + poll-based command execution, standard integration support (Docker, systemd) | General compute nodes, VMs, LXCs |
| **max** | ~15 MB | Everything in normal + HTTP server for synchronous execution, delegated network probing/scanning, deep integration support (Docker socket proxy, metrics proxy) | Hypervisors, multi-homed servers, infrastructure hubs |

**Capability Matrix:**

| Capability                                      | lite | normal | max |
| ----------------------------------------------- | ---- | ------ | --- |
| Profile collection & submission                 | ✓    | ✓      | ✓   |
| Scheduled collection (cron)                     | ✓    | ✓      | ✓   |
| Event-triggered collection (inotify)            | ✓    | ✓      | ✓   |
| Integration detection (basic)                   | ✓    | ✓      | ✓   |
| Poll-based command execution                    | ✗    | ✓      | ✓   |
| Command executors (systemd, docker, podman)     | ✗    | ✓      | ✓   |
| Self-update via polling                         | ✗    | ✓      | ✓   |
| HTTP server (axum + TLS)                        | ✗    | ✗      | ✓   |
| Synchronous command execution                   | ✗    | ✗      | ✓   |
| Delegated network probing/scanning              | ✗    | ✗      | ✓   |
| Deep integration proxy (Docker socket, metrics) | ✗    | ✗      | ✓   |
| Config push endpoint                            | ✗    | ✗      | ✓   |
| Self-update via direct push                     | ✗    | ✗      | ✓   |

**Tier Selection During Installation:**

```bash
# Lite - profiling only
curl -sSL https://hydra-api/install/agent | \
  HYDRA_AGENT_TIER=lite HYDRA_API_URL=... HYDRA_NODE_ID=... bash

# Normal - profiling + poll-based commands
curl -sSL https://hydra-api/install/agent | \
  HYDRA_AGENT_TIER=normal HYDRA_API_URL=... HYDRA_NODE_ID=... bash

# Max - full capabilities
curl -sSL https://hydra-api/install/agent | \
  HYDRA_AGENT_TIER=max HYDRA_API_URL=... HYDRA_NODE_ID=... bash
```

**Single-Instance Enforcement:**

Only one agent instance of any tier is permitted per machine. The agent enforces this at startup:

```rust
fn enforce_single_instance() -> Result<(), AgentError> {
    // 1. Check for PID file at /var/run/hydra-agent.pid
    if let Ok(pid) = read_pid_file("/var/run/hydra-agent.pid") {
        if process_is_running(pid) {
            return Err(AgentError::AlreadyRunning {
                pid,
                message: "Another Hydra agent instance is already running. \
                          Only one agent of any tier is permitted per machine."
            });
        }
        // Stale PID file - remove and continue
        remove_pid_file("/var/run/hydra-agent.pid")?;
    }
    
    // 2. Write our PID
    write_pid_file("/var/run/hydra-agent.pid", std::process::id())?;
    
    // 3. Additionally check systemd for any hydra-agent service
    if systemd_service_active("hydra-agent") {
        return Err(AgentError::AlreadyRunning {
            pid: 0,
            message: "Hydra agent is running as a systemd service. \
                      Stop it first: systemctl stop hydra-agent"
        });
    }
    
    Ok(())
}
```

The API also validates at registration time that no other agent is reporting for the same machine (based on machine-id or MAC address).

**Tier Upgrade Path:**

Users can upgrade an agent's tier in-place without re-registration:

1. Stop the current agent
2. Replace the binary with the higher-tier version
3. Update the tier in `/etc/hydra/agent.toml`: `tier = "max"`
4. Restart the agent

The agent reports its tier to the API on first contact after upgrade, and the API updates the node's capabilities accordingly. Downgrading follows the same process.

### 3.2 Agent Server Specification (Max Tier Only)

The HTTP server is exclusive to the **max** tier agent. Lite and normal tier agents do not expose any inbound endpoints.

#### 3.2.1 Server Configuration

```toml
# /etc/hydra/agent.toml

[server]
enabled = true
bind_address = "0.0.0.0"
port = 9100
tls_enabled = true
tls_cert_file = "/etc/hydra/certs/agent.crt"
tls_key_file = "/etc/hydra/certs/agent.key"

[server.auth]
# API must present this secret to authenticate
api_secret_file = "/etc/hydra/credentials/api_secret.json"
```

#### 3.2.2 Authentication

The API and agent authenticate to each other using secrets established during registration:

**During Node Registration:**

```json
// POST /node/register response now includes:
{
  "nodeId": "proxmox-01",
  "apiKey": "hyk_node_abc123...",          // Agent uses to call API (all tiers)
  "apiKeyId": "key_node_abc123",
  "agentServerSecret": "hsk_api_xyz789...", // API uses to call agent (max tier only, null for lite/normal)
  "agentTier": "max",
  "registeredBy": "user_admin001",
  "registeredAt": "2026-02-05T10:00:00Z"
}
```

**Agent Request to API:**
```http
POST /nodes/proxmox-01/profiles HTTP/1.1
Authorization: Bearer hyk_node_abc123...
```

**API Request to Agent:**
```http
POST /execute HTTP/1.1
Host: 192.168.0.10:9100
Authorization: Bearer hsk_api_xyz789...
```

Both secrets are stored securely:
- Agent stores both in `/etc/hydra/credentials/`
- API stores `agentServerSecret` in `nodes` collection (encrypted at rest)

#### 3.2.3 Agent Server Endpoints

**POST /execute**

Execute a registered command on this node.

```http
POST /execute HTTP/1.1
Authorization: Bearer hsk_api_xyz789...
Content-Type: application/json

{
  "commandId": "cmd_abc123",
  "registryId": "reg::service::restart",
  "target": {
    "serviceId": "svc::docker::nginx"
  },
  "parameters": {
    "gracePeriod": 30
  },
  "timeout": 60
}
```

**Response:**

```json
{
  "commandId": "cmd_abc123",
  "status": "completed",
  "result": {
    "success": true,
    "output": "nginx restarted successfully",
    "exitCode": 0,
    "executionTime": 2340
  }
}
```

---

**POST /probe**

Execute a network discovery scan on the agent's local network.

```http
POST /probe HTTP/1.1
Authorization: Bearer hsk_api_xyz789...
Content-Type: application/json

{
  "scanId": "scan_abc123",
  "network": "192.168.10.0/24",
  "options": {
    "portTier": "tier1",
    "includeIoTProtocols": true
  }
}
```

**Response (chunked transfer — results streamed back to API, not to end users):**

```json
{"type": "progress", "scanned": 10, "total": 254}
{"type": "discovery", "ip": "192.168.10.50", "mac": "aa:bb:cc:dd:ee:ff", ...}
{"type": "discovery", "ip": "192.168.10.51", "mac": "11:22:33:44:55:66", ...}
{"type": "complete", "hostsAlive": 12, "newDiscoveries": 3}
```

---

**GET /health**

Return agent health and status.

```http
GET /health HTTP/1.1
Authorization: Bearer hsk_api_xyz789...
```

**Response:**

```json
{
  "status": "healthy",
  "tier": "max",
  "version": "0.4.0",
  "uptime": 86400,
  "lastProfileCollection": "2026-02-05T11:00:00Z",
  "lastProfileSubmission": "2026-02-05T11:00:05Z",
  "pendingCommands": 0,
  "capabilities": ["profile", "poll-execute", "direct-execute", "probe", "update", "config", "integration-proxy"],
  "integrations": {
    "docker": { "available": true, "status": "connected" },
    "nodeExporter": { "available": true, "port": 9100 }
  }
}
```

---

**POST /config**

Update agent configuration (admin only).

```http
POST /config HTTP/1.1
Authorization: Bearer hsk_api_xyz789...
Content-Type: application/json

{
  "operation": "merge",
  "config": {
    "collection": {
      "schedule": "0 */6 * * *"
    }
  }
}
```

---

**POST /update**

Trigger agent self-update.

```http
POST /update HTTP/1.1
Authorization: Bearer hsk_api_xyz789...
Content-Type: application/json

{
  "targetVersion": "0.4.1",
  "source": "https://hydra-api.home.lan/agent/binaries/linux-x86_64/0.4.1/hydra-agent"
}
```

### 3.3 Tier-Aware Command Dispatch

The API routes commands based on the agent's tier:

```
API wants to send command to agent
    │
    ├── Agent tier = "lite"
    │   └── REJECT: "Agent tier 'lite' does not support command execution. 
    │                Upgrade to 'normal' or 'max' tier."
    │
    ├── Agent tier = "normal"
    │   └── Queue command for poll-based execution
    │       ├── Set command status = "queued"
    │       └── Return 202 Accepted with commandId
    │       │
    │       │   Agent picks up on next poll
    │       │   Agent executes and reports result
    │       │   API updates command status
    │
    ├── Agent tier = "max"
    │   ├── Try direct call to agent server
    │   │   │
    │   │   ├── SUCCESS → Return synchronous result (200 OK)
    │   │   │
    │   │   └── FAILURE (timeout, refused, unreachable)
    │   │       │
    │   │       ├── Queue command for poll-based execution (fallback)
    │   │       ├── Set command status = "queued"
    │   │       └── Return 202 Accepted with commandId
    │   │
    │   │   Agent picks up on next poll
    │   │   Agent executes and reports result
    │   │   API updates command status
```

For max-tier agents, the API tracks reachability:

```json
// In node document
{
  "nodeId": "proxmox-01",
  "agent": {
    "tier": "max",
    "version": "0.4.0",
    "serverAddress": "192.168.0.10",
    "serverPort": 9100,
    "serverReachable": true,
    "lastDirectContact": "2026-02-05T12:00:00Z",
    "lastPollContact": "2026-02-05T11:55:00Z",
    "failedDirectAttempts": 0,
    "status": "online"
  }
}
```

After 3 consecutive failed direct contact attempts, the API marks the agent as `serverReachable: false` and stops trying direct calls until the next successful poll (at which point it retries direct contact).

### 3.4 Data Model Updates

#### 3.4.1 Node Schema: Agent Section

```json
{
  "agent": {
    "type": "object",
    "properties": {
      "installed": { "type": "boolean" },
      "tier": {
        "type": "string",
        "enum": ["lite", "normal", "max"],
        "description": "Agent deployment tier determining available capabilities"
      },
      "version": { "type": "string" },
      "platform": { 
        "type": "string",
        "enum": ["linux-x86_64", "linux-arm64", "linux-armv7", "freebsd-x86_64", "macos-arm64"]
      },
      "serverConfig": {
        "type": ["object", "null"],
        "description": "Only present for max-tier agents",
        "properties": {
          "enabled": { "type": "boolean" },
          "address": { "type": "string" },
          "port": { "type": "integer" },
          "tlsEnabled": { "type": "boolean" }
        }
      },
      "serverStatus": {
        "type": ["object", "null"],
        "description": "Only present for max-tier agents",
        "properties": {
          "reachable": { "type": "boolean" },
          "lastDirectContact": { "type": "string", "format": "date-time" },
          "lastPollContact": { "type": "string", "format": "date-time" },
          "failedDirectAttempts": { "type": "integer" },
          "lastError": { "type": ["string", "null"] }
        }
      },
      "capabilities": {
        "type": "array",
        "items": { 
          "type": "string",
          "enum": ["profile", "poll-execute", "direct-execute", "probe", "update", "config", "integration-proxy"]
        },
        "description": "Capabilities are derived from tier: lite=[profile], normal=[profile, poll-execute, update], max=[all]"
      },
      "status": {
        "type": "string",
        "enum": ["online", "degraded", "offline", "unknown"]
      },
      "lastSeen": { "type": "string", "format": "date-time" }
    }
  }
}
```

#### 3.4.2 Credentials Schema

```json
{
  "$id": "hydra:agent_credentials",
  "type": "object",
  "properties": {
    "nodeId": { "type": "string" },
    "apiKey": { 
      "type": "string",
      "description": "Agent's key for calling API (hashed in storage)"
    },
    "apiKeyId": { "type": "string" },
    "agentServerSecret": {
      "type": "string",
      "description": "API's secret for calling agent (encrypted in storage)"
    },
    "agentServerSecretId": { "type": "string" },
    "createdAt": { "type": "string", "format": "date-time" },
    "rotatedAt": { "type": ["string", "null"], "format": "date-time" }
  }
}
```

### 3.5 Implementation Notes

#### 3.5.1 Recommended Libraries (Rust Agent)

| Library | Purpose |
|---------|---------|
| `axum` | HTTP server framework |
| `tokio` | Async runtime |
| `tokio-rustls` | TLS support |
| `tower` | Middleware (auth, logging) |
| `serde` | JSON serialization |

#### 3.5.2 Agent Server Code Structure

```rust
// src/server/mod.rs

use axum::{
    routing::{get, post},
    Router,
    middleware,
};

pub fn create_router(state: AppState) -> Router {
    Router::new()
        .route("/health", get(handlers::health))
        .route("/execute", post(handlers::execute))
        .route("/probe", post(handlers::probe))
        .route("/config", post(handlers::config))
        .route("/update", post(handlers::update))
        .layer(middleware::from_fn_with_state(
            state.clone(),
            auth::verify_api_secret
        ))
        .with_state(state)
}
```

#### 3.5.3 Security Considerations

| Concern | Mitigation |
|---------|------------|
| Unauthorized access | Require valid API secret on all endpoints |
| Man-in-the-middle | TLS required; validate API's certificate |
| Credential theft | Secrets stored with restrictive permissions (600) |
| Replay attacks | Include timestamp and nonce in requests |
| Command injection | Only execute registered commands; no arbitrary shell |

---

## 4. Command Execution System

### 4.1 Overview

#### 4.1.1 What

The Command Execution System provides a secure, audited mechanism for executing operations on infrastructure. It consists of a command registry (allowed operations), a queue (pending commands), and execution paths (direct to agent or via polling).

#### 4.1.2 Why

Direct shell access to infrastructure is powerful but dangerous. The command execution system provides:

- **Security**: Only pre-registered commands can run; no arbitrary execution
- **Auditability**: Every command is logged with who, what, when, result
- **Visibility**: Users see queue status, can cancel pending commands
- **Reliability**: Fallback to polling when direct path unavailable

#### 4.1.3 How

Commands are defined in a registry. Users or MCP tools submit command requests referencing registry entries. The API validates, queues, and dispatches. The agent executes and reports results.

### 4.2 Command Registry

#### 4.2.1 Registry Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:command_registry",
  "title": "CommandRegistryEntry",
  "type": "object",
  "required": ["registryId", "category", "action", "displayName", "execution", "rbac"],
  "properties": {
    "_id": { "type": "string" },
    "registryId": {
      "type": "string",
      "pattern": "^reg::(service|node|agent)::[a-z][a-z0-9-]*$",
      "examples": ["reg::service::restart", "reg::node::reboot", "reg::agent::update"]
    },
    "category": {
      "type": "string",
      "enum": ["service", "node", "agent"]
    },
    "action": {
      "type": "string",
      "pattern": "^[a-z][a-z0-9-]*$"
    },
    "displayName": {
      "type": "string",
      "maxLength": 64
    },
    "description": {
      "type": "string",
      "maxLength": 512
    },
    "targetSchema": {
      "type": "object",
      "description": "JSON Schema for required target fields"
    },
    "parametersSchema": {
      "type": "object",
      "description": "JSON Schema for command parameters"
    },
    "execution": {
      "type": "object",
      "required": ["timeout"],
      "properties": {
        "runtimes": {
          "type": "object",
          "description": "Command templates per runtime (systemd, docker, etc.)",
          "additionalProperties": { "type": "string" }
        },
        "handler": {
          "type": "string",
          "description": "For agent/node commands: internal handler name"
        },
        "timeout": {
          "type": "integer",
          "minimum": 1,
          "maximum": 3600,
          "description": "Timeout in seconds"
        },
        "retryable": { "type": "boolean", "default": false },
        "maxRetries": { "type": "integer", "default": 0 }
      }
    },
    "rbac": {
      "type": "object",
      "required": ["minimumRole"],
      "properties": {
        "minimumRole": {
          "type": "string",
          "enum": ["viewer", "operator", "admin"]
        },
        "requiresConfirmation": {
          "type": "boolean",
          "default": false,
          "description": "Require explicit confirmation before execution"
        },
        "confirmationMessage": {
          "type": "string",
          "description": "Message shown when confirmation required"
        }
      }
    },
    "audit": {
      "type": "object",
      "properties": {
        "logLevel": {
          "type": "string",
          "enum": ["minimal", "standard", "verbose"],
          "default": "standard"
        },
        "captureOutput": {
          "type": "boolean",
          "default": true
        },
        "sensitiveParameters": {
          "type": "array",
          "items": { "type": "string" },
          "description": "Parameter names to redact in logs"
        }
      }
    },
    "metadata": {
      "type": "object",
      "properties": {
        "version": { "type": "string" },
        "addedAt": { "type": "string", "format": "date-time" },
        "builtIn": { "type": "boolean" },
        "deprecated": { "type": "boolean", "default": false },
        "deprecationMessage": { "type": "string" }
      }
    }
  }
}
```

#### 4.2.2 Built-In Commands

**Service Commands:**

| Registry ID             | Action  | Role     | Confirmation | Description                           |
| ----------------------- | ------- | -------- | ------------ | ------------------------------------- |
| `reg::service::start`   | start   | operator | No           | Start a stopped service               |
| `reg::service::stop`    | stop    | operator | No           | Stop a running service                |
| `reg::service::restart` | restart | operator | No           | Restart a service                     |
| `reg::service::reload`  | reload  | operator | No           | Reload service configuration          |
| `reg::service::logs`    | logs    | operator | No           | Retrieve service logs                 |
| `reg::service::inspect` | inspect | operator | No           | Get detailed service info             |
| `reg::service::update`  | update  | admin    | Yes          | Update service (pull new image, etc.) |


**Node Commands:**

| Registry ID | Action | Role | Confirmation | Description |
|-------------|--------|------|--------------|-------------|
| `reg::node::reboot` | reboot | admin | Yes | Reboot the node |
| `reg::node::shutdown` | shutdown | admin | Yes | Shutdown the node |
| `reg::node::update-system` | update-system | admin | Yes | Run system updates |
| `reg::node::set-hostname` | set-hostname | admin | No | Change node hostname |

**Agent Commands:**

| Registry ID | Action | Role | Confirmation | Description |
|-------------|--------|------|--------------|-------------|
| `reg::agent::restart` | restart | admin | No | Restart the Hydra agent |
| `reg::agent::update` | update | admin | Yes | Update agent to new version |
| `reg::agent::config-reload` | config-reload | operator | No | Reload agent configuration |
| `reg::agent::collect-now` | collect-now | operator | No | Trigger immediate profile collection |
| `reg::agent::probe-network` | probe-network | operator | No | Run network discovery scan |
| `reg::agent::status` | status | viewer | No | Get agent status |

### 4.3 Command Lifecycle

#### 4.3.1 States

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           COMMAND LIFECYCLE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐    ┌──────────┐    ┌───────────┐    ┌───────────┐            │
│  │ pending  │───▶│  queued  │───▶│ executing │───▶│ completed │            │
│  └──────────┘    └──────────┘    └───────────┘    └───────────┘            │
│       │               │               │                                      │
│       │               ▼               ▼                                      │
│       │          ┌──────────┐   ┌──────────┐                                │
│       │          │cancelled │   │  failed  │                                │
│       │          └──────────┘   └──────────┘                                │
│       │                              ▲                                       │
│       │                              │                                       │
│       │                         ┌──────────┐                                │
│       │                         │ timeout  │                                │
│       │                         └──────────┘                                │
│       ▼                                                                      │
│  ┌──────────┐                                                               │
│  │ rejected │                                                               │
│  └──────────┘                                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

| State | Description | User Actions |
|-------|-------------|--------------|
| `pending` | Created, awaiting validation | Cancel |
| `rejected` | Validation failed (not registered, unauthorized, invalid target) | View error |
| `queued` | Validated, waiting for execution | Cancel |
| `executing` | Agent acknowledged, running | Monitor (cancel if supported) |
| `completed` | Finished successfully | View result |
| `failed` | Finished with error | View error, retry |
| `timeout` | Execution exceeded timeout | View partial result, retry |
| `cancelled` | User cancelled before completion | - |

#### 4.3.2 Command Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:commands",
  "title": "Command",
  "type": "object",
  "required": ["commandId", "registryId", "target", "status", "requestedBy"],
  "properties": {
    "_id": { "type": "string" },
    "commandId": {
      "type": "string",
      "pattern": "^cmd_[a-z0-9]+$"
    },
    "registryId": { "type": "string" },
    "target": {
      "type": "object",
      "required": ["nodeId"],
      "properties": {
        "nodeId": { "type": "string" },
        "serviceId": { "type": ["string", "null"] }
      }
    },
    "action": { "type": "string" },
    "parameters": { "type": "object" },
    
    "status": {
      "type": "string",
      "enum": ["pending", "rejected", "queued", "executing", "completed", "failed", "timeout", "cancelled"]
    },
    "queuePosition": {
      "type": ["integer", "null"],
      "description": "Position in queue (null if not queued)"
    },
    "executionMethod": {
      "type": "string",
      "enum": ["agent-direct", "agent-poll", "integration"],
      "description": "How the command will be/was executed"
    },
    
    "result": {
      "type": ["object", "null"],
      "properties": {
        "success": { "type": "boolean" },
        "output": { "type": "string" },
        "exitCode": { "type": ["integer", "null"] },
        "error": { "type": ["string", "null"] },
        "data": { "type": "object", "description": "Structured result data" }
      }
    },
    "error": {
      "type": ["object", "null"],
      "properties": {
        "code": { "type": "string" },
        "message": { "type": "string" },
        "details": { "type": "object" }
      }
    },
    
    "requestedBy": {
      "type": "object",
      "required": ["userId", "source"],
      "properties": {
        "userId": { "type": "string" },
        "source": { 
          "type": "string",
          "enum": ["web", "mcp-internal", "api"]
        },
        "clientId": { "type": ["string", "null"] }
      }
    },
    
    "chain": {
      "type": ["object", "null"],
      "properties": {
        "chainId": { "type": "string" },
        "sequence": { "type": "integer" },
        "dependsOn": { 
          "type": "array",
          "items": { "type": "string" }
        }
      }
    },
    
    "timeoutSeconds": { "type": "integer" },
    "retryCount": { "type": "integer", "default": 0 },
    
    "createdAt": { "type": "string", "format": "date-time" },
    "queuedAt": { "type": ["string", "null"], "format": "date-time" },
    "startedAt": { "type": ["string", "null"], "format": "date-time" },
    "completedAt": { "type": ["string", "null"], "format": "date-time" },
    "cancelledAt": { "type": ["string", "null"], "format": "date-time" },
    "cancelledBy": { "type": ["string", "null"] }
  }
}
```

### 4.4 Command Chains (Workflows)

#### 4.4.1 Chain Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:command_chains",
  "title": "CommandChain",
  "type": "object",
  "required": ["chainId", "name", "steps", "createdBy"],
  "properties": {
    "_id": { "type": "string" },
    "chainId": {
      "type": "string",
      "pattern": "^chain_[a-z0-9]+$"
    },
    "name": { "type": "string", "maxLength": 128 },
    "description": { "type": "string", "maxLength": 1024 },
    
    "steps": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["stepId", "registryId", "target"],
        "properties": {
          "stepId": { "type": "string" },
          "registryId": { "type": "string" },
          "target": {
            "type": "object",
            "description": "Target with optional template variables"
          },
          "parameters": { "type": "object" },
          "dependsOn": {
            "type": "array",
            "items": { "type": "string" }
          },
          "onSuccess": {
            "type": "string",
            "description": "Next step ID or 'complete'"
          },
          "onFailure": {
            "type": "string",
            "enum": ["abort", "continue", "retry"],
            "default": "abort"
          },
          "condition": {
            "type": ["string", "null"],
            "description": "Expression to evaluate before running"
          }
        }
      }
    },
    
    "inputs": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "type": { "type": "string" },
          "required": { "type": "boolean" },
          "default": {},
          "description": { "type": "string" }
        }
      }
    },
    
    "createdBy": { "type": "string" },
    "createdAt": { "type": "string", "format": "date-time" },
    "updatedAt": { "type": "string", "format": "date-time" }
  }
}
```

#### 4.4.2 Cascade Cancellation

When cancelling a command that has dependents:

```python
def cancel_command(command_id: str, user_id: str, confirm_cascade: bool = False) -> CancelResult:
    command = get_command(command_id)
    
    if command.status not in ["pending", "queued"]:
        raise CommandNotCancellable(f"Cannot cancel command in {command.status} state")
    
    # Find dependent commands
    dependents = find_commands_depending_on(command_id)
    
    if dependents and not confirm_cascade:
        return CancelResult(
            requires_confirmation=True,
            affected_commands=dependents,
            message=f"Cancelling will also cancel {len(dependents)} dependent commands"
        )
    
    # Cancel this command and all dependents
    cancelled = [command_id]
    for dep in dependents:
        dep.status = "cancelled"
        dep.cancelled_at = now()
        dep.cancelled_by = user_id
        dep.cancel_reason = f"cascade:parent:{command_id}"
        cancelled.append(dep.command_id)
    
    command.status = "cancelled"
    command.cancelled_at = now()
    command.cancelled_by = user_id
    
    return CancelResult(cancelled_commands=cancelled)
```

### 4.5 Source Restriction

Commands can only be executed from the Hydra web interface (Command Center or integrated MCP chat). External MCP clients are read-only.

#### 4.5.1 Implementation: Token Scopes

```json
// Token for hydra-web integrated MCP
{
  "sub": "user_admin001",
  "client_type": "internal",
  "client_id": "hydra-web",
  "scopes": ["*:read", "commands:execute", "discovery:scan"]
}

// Token for external MCP client (Claude Desktop, VS Code, etc.)
{
  "sub": "user_admin001",
  "client_type": "external",
  "client_id": "claude-desktop-abc123",
  "scopes": ["*:read"],
  "restrictions": ["commands:execute"]
}
```

#### 4.5.2 Implementation: MCP Client Registration

```json
// Collection: mcp_clients
{
  "clientId": "hydra-web",
  "name": "Hydra Web Integrated Chat",
  "type": "internal",
  "trusted": true,
  "capabilities": ["read", "execute", "scan"],
  "registeredAt": "2026-01-01T00:00:00Z"
}

{
  "clientId": "claude-desktop-abc123",
  "name": "Claude Desktop (Admin Laptop)",
  "type": "external",
  "trusted": false,
  "capabilities": ["read"],
  "registeredAt": "2026-02-01T00:00:00Z",
  "registeredBy": "user_admin001"
}
```

When an MCP tool call is received:

```python
def authorize_tool_call(tool_name: str, client: MCPClient, user: User) -> bool:
    # Read-only tools always allowed
    if tool_name in READ_ONLY_TOOLS:
        return True
    
    # Execute tools require internal client
    if tool_name in EXECUTE_TOOLS:
        if client.type != "internal" or not client.trusted:
            raise MCPAuthorizationError(
                f"Tool '{tool_name}' is only available from the Hydra web interface",
                error_code="CLIENT_NOT_AUTHORIZED"
            )
    
    # Check user RBAC
    return user.has_permission(tool_to_permission(tool_name))
```

### 4.6 API Endpoints

#### 4.6.1 Submit Command

```
POST /commands
```

**Request Body:**

```json
{
  "registryId": "reg::service::restart",
  "target": {
    "nodeId": "docker-host-01",
    "serviceId": "svc::docker::nginx"
  },
  "parameters": {
    "gracePeriod": 30
  }
}
```

**Response (synchronous execution):** `200 OK`

```json
{
  "commandId": "cmd_abc123",
  "status": "completed",
  "executionMethod": "agent-direct",
  "result": {
    "success": true,
    "output": "nginx restarted successfully",
    "exitCode": 0
  },
  "createdAt": "2026-02-05T12:00:00Z",
  "completedAt": "2026-02-05T12:00:03Z"
}
```

**Response (queued for polling):** `202 Accepted`

```json
{
  "commandId": "cmd_abc123",
  "status": "queued",
  "queuePosition": 1,
  "executionMethod": "agent-poll",
  "note": "Agent server unreachable; command queued for next poll",
  "createdAt": "2026-02-05T12:00:00Z",
  "queuedAt": "2026-02-05T12:00:01Z"
}
```

**Required Permission:** `commands:execute` (operator, admin depending on command)  
**Source Restriction:** Hydra web only

---

#### 4.6.2 Get Command Status

```
GET /commands/{commandId}
```

**Response:** `200 OK`

Full command document including result if completed.

**Required Permission:** `commands:read`

---

#### 4.6.3 List Commands (History)

```
GET /commands
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `nodeId` | string | Filter by target node |
| `status` | enum | Filter by status |
| `registryId` | string | Filter by command type |
| `since` | datetime | Commands after timestamp |
| `limit` | integer | Max results (default: 50) |
| `offset` | integer | Pagination offset |

**Required Permission:** `commands:read`

---

#### 4.6.4 Cancel Command

```
POST /commands/{commandId}/cancel
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `confirmCascade` | boolean | Confirm cascade cancellation (default: false) |

**Response (cascade required):** `200 OK`

```json
{
  "requiresConfirmation": true,
  "commandId": "cmd_abc123",
  "affectedCommands": [
    { "commandId": "cmd_def456", "reason": "depends on cmd_abc123" },
    { "commandId": "cmd_ghi789", "reason": "depends on cmd_def456" }
  ],
  "message": "Cancelling will also cancel 2 dependent commands. Retry with confirmCascade=true to proceed."
}
```

**Response (cancelled):** `200 OK`

```json
{
  "cancelled": [
    { "commandId": "cmd_abc123", "status": "cancelled" },
    { "commandId": "cmd_def456", "status": "cancelled", "reason": "cascade" }
  ]
}
```

**Required Permission:** `commands:execute`

---

#### 4.6.5 View Queue

```
GET /commands/queue
```

**Response:** `200 OK`

```json
{
  "queue": [
    {
      "commandId": "cmd_abc123",
      "registryId": "reg::service::restart",
      "target": { "nodeId": "docker-host-01" },
      "status": "queued",
      "position": 1,
      "queuedAt": "2026-02-05T12:00:00Z",
      "executionMethod": "agent-poll"
    }
  ],
  "stats": {
    "totalQueued": 3,
    "totalExecuting": 1,
    "oldestQueuedAt": "2026-02-05T11:55:00Z"
  }
}
```

**Required Permission:** `commands:read`

---

#### 4.6.6 Flush Queue

```
POST /commands/queue/flush
```

**Request Body:**

```json
{
  "scope": "all",
  "confirm": true
}
```

`scope` can be:
- `"all"` — Flush entire queue
- `"node:proxmox-01"` — Flush commands for specific node
- `"user:user_admin001"` — Flush commands from specific user

**Required Permission:** `commands:admin` (admin only)

### 4.7 MCP Tools

#### 4.7.1 control_service

```json
{
  "name": "control_service",
  "description": "Control a service (start, stop, restart, etc.)",
  "inputSchema": {
    "type": "object",
    "required": ["serviceId", "action"],
    "properties": {
      "serviceId": { "type": "string" },
      "action": { 
        "type": "string",
        "enum": ["start", "stop", "restart", "reload", "logs", "inspect"]
      },
      "parameters": { "type": "object" }
    }
  }
}
```

**Note:** This tool is restricted to hydra-web MCP client. External MCP clients will receive a structured guidance response:

```json
{
  "error": "CLIENT_NOT_AUTHORIZED",
  "message": "Service control is only available from the Hydra web interface",
  "context": {
    "requestedAction": "restart",
    "targetService": "svc::docker::nginx",
    "targetNode": "docker-host-01",
    "currentServiceStatus": "running",
    "guidance": "You can perform this action from the Hydra Command Center at https://hydra-web/command-center, or use the integrated chat in the Hydra web interface which has full control permissions.",
    "alternativeActions": [
      "I can show you the current status of this service",
      "I can list recent commands executed on this service",
      "I can describe what this service does based on its profile"
    ]
  }
}
```

This structured response enables external LLM clients (Claude Desktop, VS Code, etc.) to provide helpful guidance to the user rather than a bare error. The LLM can relay the available alternative actions and direct the user to the web interface for write operations.

#### 4.7.2 control_node

```json
{
  "name": "control_node",
  "description": "Control a node (reboot, shutdown, etc.)",
  "inputSchema": {
    "type": "object",
    "required": ["nodeId", "action"],
    "properties": {
      "nodeId": { "type": "string" },
      "action": { 
        "type": "string",
        "enum": ["reboot", "shutdown", "update-system"]
      },
      "confirm": { "type": "boolean", "default": false }
    }
  }
}
```

#### 4.7.3 control_agent

```json
{
  "name": "control_agent",
  "description": "Control the Hydra agent on a node",
  "inputSchema": {
    "type": "object",
    "required": ["nodeId", "action"],
    "properties": {
      "nodeId": { "type": "string" },
      "action": { 
        "type": "string",
        "enum": ["restart", "update", "config-reload", "collect-now", "status"]
      }
    }
  }
}
```

#### 4.7.4 get_command_status

```json
{
  "name": "get_command_status",
  "description": "Get the status and result of a command",
  "inputSchema": {
    "type": "object",
    "required": ["commandId"],
    "properties": {
      "commandId": { "type": "string" }
    }
  }
}
```

This tool is available to all MCP clients (read-only).

---

## 5. Controls Framework

### 5.1 Overview

The Controls Framework defines what operations are permitted on what targets, organized into three domains: Service Controls, Node Controls, and Agent Controls.

### 5.2 Control Domains

#### 5.2.1 Service Controls

Operations targeting services running on nodes.

| Action | Description | Runtime Support | Role |
|--------|-------------|-----------------|------|
| `start` | Start a stopped service | systemd, docker, podman | operator |
| `stop` | Stop a running service | systemd, docker, podman | operator |
| `restart` | Restart a service | systemd, docker, podman | operator |
| `reload` | Reload configuration without restart | systemd (where supported) | operator |
| `logs` | Retrieve service logs | systemd, docker, podman | operator |
| `inspect` | Get detailed service information | systemd, docker, podman | operator |
| `update` | Update service (pull new image, etc.) | docker, podman | admin |

**Runtime Command Mapping:**

```yaml
service::restart:
  systemd: "systemctl restart {serviceName}"
  docker: "docker restart {containerId}"
  podman: "podman restart {containerId}"
  
service::logs:
  systemd: "journalctl -u {serviceName} -n {lines} --no-pager"
  docker: "docker logs {containerId} --tail {lines}"
  podman: "podman logs {containerId} --tail {lines}"
```

#### 5.2.2 Node Controls

Operations targeting the node itself.

| Action | Description | Dangerous | Role | Confirmation |
|--------|-------------|-----------|------|--------------|
| `reboot` | Reboot the operating system | Yes | admin | Yes |
| `shutdown` | Shutdown the operating system | Yes | admin | Yes |
| `suspend` | Suspend to RAM | No | admin | No |
| `update-system` | Run system package updates | Yes | admin | Yes |
| `set-hostname` | Change system hostname | No | admin | No |

**Execution Methods:**

| Node Type | Method |
|-----------|--------|
| Physical with agent | Agent executes locally |
| VM/LXC with Proxmox parent | Proxmox API (preferred) or agent |
| VM/LXC without integration | Agent only |

#### 5.2.3 Agent Controls

Operations targeting the Hydra agent process.

| Action | Description | Role |
|--------|-------------|------|
| `status` | Get agent health and status | viewer |
| `restart` | Restart the agent process | admin |
| `update` | Update agent to new version | admin |
| `config-reload` | Reload configuration file | operator |
| `config-update` | Push new configuration values | admin |
| `collect-now` | Trigger immediate profile collection | operator |
| `probe-network` | Run network discovery on local segment | operator |
| `uninstall` | Stop and remove the agent | admin |

### 5.3 RBAC Mapping

#### 5.3.1 Role Definitions

| Role | Description | Control Access |
|------|-------------|----------------|
| `viewer` | Read-only access | Agent status only |
| `family` | IoT controls | IoT device controls via Home Assistant |
| `operator` | Infrastructure management | Basic service controls, agent read + collect |
| `admin` | Full access | All controls including destructive operations |

#### 5.3.2 Permission Matrix

| Permission | viewer | family | operator | admin |
|------------|--------|--------|----------|-------|
| `services:control:start` | ✗ | ✗ | ✓ | ✓ |
| `services:control:stop` | ✗ | ✗ | ✓ | ✓ |
| `services:control:restart` | ✗ | ✗ | ✓ | ✓ |
| `services:control:reload` | ✗ | ✗ | ✓ | ✓ |
| `services:control:update` | ✗ | ✗ | ✗ | ✓ |
| `nodes:control:reboot` | ✗ | ✗ | ✗ | ✓ |
| `nodes:control:shutdown` | ✗ | ✗ | ✗ | ✓ |
| `nodes:control:update-system` | ✗ | ✗ | ✗ | ✓ |
| `agent:control:status` | ✓ | ✗ | ✓ | ✓ |
| `agent:control:restart` | ✗ | ✗ | ✗ | ✓ |
| `agent:control:collect-now` | ✗ | ✗ | ✓ | ✓ |
| `agent:control:probe` | ✗ | ✗ | ✓ | ✓ |
| `iot:control` | ✗ | ✓ | ✓ | ✓ |
| `discovery:scan` | ✗ | ✗ | ✓ | ✓ |
| `commands:execute` | ✗ | ✗ | ✓ | ✓ |
| `commands:admin` | ✗ | ✗ | ✗ | ✓ |

### 5.4 Safety Controls

#### 5.4.1 Confirmation Requirements

Destructive operations require explicit confirmation:

```json
// First request (no confirmation)
POST /commands
{
  "registryId": "reg::node::reboot",
  "target": { "nodeId": "proxmox-01" }
}

// Response
{
  "requiresConfirmation": true,
  "commandId": "cmd_pending_abc123",
  "confirmationMessage": "This will reboot proxmox-01, causing all VMs and containers to restart. 7 child nodes will be affected.",
  "affectedNodes": ["vm-01", "vm-02", "lxc-01", ...],
  "confirmUrl": "POST /commands/cmd_pending_abc123/confirm"
}

// Confirmation request
POST /commands/cmd_pending_abc123/confirm

// Response: command executes
{
  "commandId": "cmd_abc123",
  "status": "executing",
  ...
}
```

#### 5.4.2 Rate Limiting

| Scope | Limit | Window |
|-------|-------|--------|
| Per user | 60 commands | 1 minute |
| Per node | 30 commands | 1 minute |
| Destructive commands (per user) | 5 | 5 minutes |

#### 5.4.3 Timeout Enforcement

All commands have timeouts. If execution exceeds the timeout:

1. Command status → `timeout`
2. If the operation is interruptible, send cancel signal to agent
3. Log the timeout event
4. Alert user

Default timeouts by command type:

| Command Type | Default Timeout | Max Configurable |
|--------------|-----------------|------------------|
| Service restart | 60s | 300s |
| Service logs | 30s | 120s |
| Node reboot | 300s | 600s |
| System update | 1800s | 3600s |
| Agent update | 180s | 300s |

---

## 6. Remote Agent Installation

### 6.1 Overview

Remote Agent Installation allows Hydra to deploy the agent binary to discovered compute nodes without manual intervention.

### 6.2 Prerequisites

#### 6.2.1 API Host Requirements

The API host must have:
- SSH client installed
- SSH key pair at a known path (configurable, default: `/etc/hydra/ssh/id_ed25519`)
- Network connectivity to target node's SSH port

```toml
# /etc/hydra/api.toml

[remote_install]
enabled = true
ssh_key_path = "/etc/hydra/ssh/id_ed25519"
ssh_timeout = 30
known_hosts_file = "/etc/hydra/ssh/known_hosts"
strict_host_key_checking = false  # Set to true for production
```

#### 6.2.2 Target Node Requirements

The target node must:
- Have SSH server running and accessible
- Accept connections with the API's SSH key (user must add public key to target) OR
- Be a logical node under an integrated hypervisor (Proxmox)

### 6.3 Eligibility Assessment

Separate from general registration eligibility, remote install eligibility is specific:

```python
def assess_remote_install_eligibility(discovery: DiscoveredNode) -> RemoteInstallEligibility:
    blockers = []
    method = None
    
    # Must be compute class
    if discovery.classification.suggested_class != "compute":
        return RemoteInstallEligibility(
            eligible=False,
            blockers=["Only compute nodes can have agents installed"]
        )
    
    # Must have compatible platform
    if not discovery.eligibility.agent_compatible:
        return RemoteInstallEligibility(
            eligible=False,
            blockers=[f"No agent binary available for detected platform"]
        )
    
    # Check SSH access
    ssh_port = discovery.fingerprint.get_open_port(22)
    if ssh_port and ssh_port.state == "open":
        method = "ssh"
    
    # Check Proxmox parent (for LXC/VM)
    parent = find_parent_node(discovery)
    if parent and parent.has_integration("proxmox"):
        # Proxmox exec is preferred over SSH when available
        method = "proxmox-exec"
    
    if method is None:
        blockers.append("No SSH access detected")
        blockers.append("No parent hypervisor with Proxmox integration")
        return RemoteInstallEligibility(
            eligible=False,
            blockers=blockers
        )
    
    return RemoteInstallEligibility(
        eligible=True,
        method=method,
        requirements=get_requirements_for_method(method)
    )
```

### 6.4 Installation Flow

#### 6.4.1 SSH-Based Installation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SSH-BASED AGENT INSTALLATION                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. User triggers: POST /discovery/{id}/remote-install                      │
│     Body: { "sshUser": "pi", "nodeId": "pihole-01" }                        │
│                                                                              │
│  2. API validates:                                                           │
│     - Discovery exists and is eligible                                       │
│     - SSH key is configured                                                  │
│     - Platform is supported                                                  │
│                                                                              │
│  3. API tests SSH connectivity:                                              │
│     ssh -o ConnectTimeout=10 pi@192.168.0.47 "echo hydra-test"              │
│                                                                              │
│  4. API registers the node (internally):                                     │
│     POST /node/register { nodeId, class, type, ... }                        │
│     → Returns apiKey for the new node                                        │
│                                                                              │
│  5. API executes remote installation:                                        │
│     ssh pi@192.168.0.47 'curl -sSL https://hydra-api/install/agent |        │
│       HYDRA_API_URL=https://hydra-api HYDRA_NODE_ID=pihole-01               │
│       HYDRA_API_KEY=hyk_node_... bash'                                      │
│                                                                              │
│  6. API waits for agent check-in:                                           │
│     Poll GET /nodes/pihole-01 until agent.status = "online"                 │
│     Timeout: 120 seconds                                                     │
│                                                                              │
│  7. Return result to user                                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 6.4.2 Proxmox-Based Installation

For VMs and LXCs under an integrated Proxmox host:

```
1. User triggers: POST /discovery/{id}/remote-install
   Body: { "nodeId": "ubuntu-lxc-01", "parentNodeId": "proxmox-01" }

2. API validates:
   - Parent node has Proxmox integration
   - Discovery is a logical node (VM/LXC)
   - VMID is known from parent's profile

3. API registers the node

4. API executes via Proxmox:
   POST /api2/json/nodes/pve/lxc/{vmid}/exec
   Body: { "command": ["bash", "-c", "curl ... | bash"] }

5. Wait for agent check-in

6. Return result
```

### 6.5 API Endpoints

#### 6.5.1 Initiate Remote Installation

```
POST /discovery/results/{discoveryId}/remote-install
```

**Request Body:**

```json
{
  "nodeId": "pihole-01",
  "displayName": "Pi-hole DNS Server",
  "class": "compute",
  "type": "physical",
  "kind": "sbc",
  "tags": ["dns"],
  
  "sshUser": "pi",
  "sshPort": 22,
  
  "installOptions": {
    "agentTier": "normal",
    "startAgent": true,
    "enableSystemd": true,
    "collectImmediately": true
  }
}
```

The `agentTier` field determines which agent binary is installed. Defaults to `"normal"` if omitted. For nodes intended as scanning delegates or infrastructure hubs, use `"max"`.

**Response (success):** `201 Created`

```json
{
  "nodeId": "pihole-01",
  "status": "installed",
  "agent": {
    "tier": "normal",
    "version": "0.4.0",
    "status": "online",
    "firstProfile": "2026-02-05T12:35:00Z"
  },
  "apiKey": "hyk_node_abc123...",
  "installLog": [
    { "step": "ssh_connect", "status": "ok", "duration": 1.2 },
    { "step": "register_node", "status": "ok", "duration": 0.3 },
    { "step": "download_agent", "status": "ok", "duration": 5.4 },
    { "step": "install_agent", "status": "ok", "duration": 2.1 },
    { "step": "start_agent", "status": "ok", "duration": 0.8 },
    { "step": "verify_checkin", "status": "ok", "duration": 12.3 }
  ]
}
```

**Response (SSH key not authorized):** `400 Bad Request`

```json
{
  "error": "SSH_AUTH_FAILED",
  "message": "SSH authentication failed. The API's public key may not be authorized on the target.",
  "guidance": [
    "1. Copy the API's public key to the target:",
    "   ssh-copy-id -i /etc/hydra/ssh/id_ed25519.pub pi@192.168.0.47",
    "2. Or manually add to ~/.ssh/authorized_keys on the target",
    "3. Retry the installation"
  ],
  "apiPublicKey": "ssh-ed25519 AAAA... hydra-api"
}
```

**Required Permission:** `nodes:create` + `agent:install` (operator, admin)

---

#### 6.5.2 Get API Public Key

```
GET /install/ssh-key
```

**Response:** `200 OK`

```json
{
  "publicKey": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... hydra-api",
  "fingerprint": "SHA256:abcdef123456...",
  "instructions": "Add this key to ~/.ssh/authorized_keys on target nodes to enable remote agent installation"
}
```

**Required Permission:** Public (no auth required)

---

#### 6.5.3 Get Agent Installer Script

```
GET /install/agent
```

**Response:** `200 OK`

Returns the agent installer bash script. The script:
- Detects platform (OS, architecture)
- Downloads appropriate agent binary
- Creates configuration directory
- Writes configuration file
- Installs systemd service (if requested)
- Starts agent

**Required Permission:** Public (no auth required, but API key required for actual registration)

### 6.6 MCP Tools

#### 6.6.1 remote_install_agent

```json
{
  "name": "remote_install_agent",
  "description": "Install the Hydra agent on a discovered compute node",
  "inputSchema": {
    "type": "object",
    "required": ["discoveryId"],
    "properties": {
      "discoveryId": { "type": "string" },
      "nodeId": { "type": "string" },
      "displayName": { "type": "string" },
      "sshUser": { 
        "type": "string",
        "description": "SSH username (default: root)"
      },
      "tags": { 
        "type": "array",
        "items": { "type": "string" }
      }
    }
  }
}
```

**Note:** Restricted to hydra-web MCP client.

---

## 7. Integrations Framework

### 7.1 Overview

Integrations connect Hydra to external systems for enhanced capabilities. All Hydra components (API, Agent, Web, MCP) are integration-aware.

### 7.2 Design Principles

1. **Integration-Aware Architecture**: Every component checks for and uses relevant integrations
2. **Optional Per Node**: Integration usage is configurable at the node level
3. **Graceful Degradation**: Core functionality works without integrations
4. **Secure Credentials**: Integration secrets stored encrypted, never in plain text
5. **Health Monitoring**: Integrations are health-checked; failures are surfaced to users
6. **Explicit Command Routing**: Each integration has an explicit setting to control whether it is allowed to execute commands on behalf of Hydra. This is off by default and must be explicitly enabled per integration. Additionally, command routing can be toggled at the per-command-type level, allowing fine-grained control (e.g., allow Docker integration to restart containers but not delete them)

### 7.3 Integration Categories

#### 7.3.1 Core Integrations (Built-In)

| Integration | Purpose | Direction |
|-------------|---------|-----------|
| **Home Assistant** | IoT device management and control | Bidirectional |
| **Proxmox VE** | Hypervisor management, VM/LXC control | Hydra → Proxmox |
| **Docker** | Container management | Hydra → Docker |

#### 7.3.2 Observability Integrations

| Integration | Purpose | Direction |
|-------------|---------|-----------|
| **Prometheus** | Metrics collection and querying | Hydra → Prometheus |
| **Grafana** | Dashboard provisioning | Hydra → Grafana |
| **Alertmanager** | Alert context enrichment | Bidirectional |
| **Elasticsearch** | Centralized log search | Hydra → ES |

#### 7.3.3 Infrastructure-as-Code Integrations

| Integration | Purpose | Direction |
|-------------|---------|-----------|
| **Ansible** | Mass configuration, dynamic inventory | Hydra → Ansible |
| **Terraform** | Infrastructure provisioning | Bidirectional |

### 7.4 Data Model

#### 7.4.1 Integration Registry

```json
{
  "$id": "hydra:integrations",
  "type": "object",
  "required": ["integrationId", "type", "name", "status"],
  "properties": {
    "_id": { "type": "string" },
    "integrationId": {
      "type": "string",
      "pattern": "^int::[a-z]+::[a-z0-9-]+$",
      "examples": ["int::proxmox::proxmox-01", "int::homeassistant::main"]
    },
    "type": {
      "type": "string",
      "enum": ["proxmox", "docker", "homeassistant", "prometheus", "grafana", 
               "alertmanager", "elasticsearch", "ansible", "terraform"]
    },
    "name": { "type": "string", "maxLength": 128 },
    "status": {
      "type": "string",
      "enum": ["connected", "disconnected", "error", "disabled"]
    },
    
    "connection": {
      "type": "object",
      "properties": {
        "endpoint": { "type": "string", "format": "uri" },
        "authMethod": { 
          "type": "string",
          "enum": ["api-token", "basic", "oauth2", "certificate"]
        },
        "credentialRef": { 
          "type": "string",
          "description": "Reference to credentials collection"
        },
        "verifySsl": { "type": "boolean", "default": true },
        "timeoutSeconds": { "type": "integer", "default": 30 }
      }
    },
    
    "linkedNodeId": {
      "type": ["string", "null"],
      "description": "Node this integration is associated with (e.g., Proxmox host)"
    },
    "linkedNetworkIds": {
      "type": "array",
      "items": { "type": "string" }
    },
    
    "capabilities": {
      "type": "array",
      "items": { "type": "string" },
      "description": "What this integration can do"
    },
    
    "syncConfig": {
      "type": "object",
      "properties": {
        "autoDiscover": { "type": "boolean", "default": true },
        "syncOnDemandOnly": { "type": "boolean", "default": true }
      }
    },
    
    "health": {
      "type": "object",
      "properties": {
        "lastCheck": { "type": "string", "format": "date-time" },
        "status": { "type": "string", "enum": ["healthy", "degraded", "unhealthy"] },
        "latencyMs": { "type": "integer" },
        "errorMessage": { "type": ["string", "null"] }
      }
    },
    
    "createdBy": { "type": "string" },
    "createdAt": { "type": "string", "format": "date-time" },
    "updatedAt": { "type": "string", "format": "date-time" }
  }
}
```

#### 7.4.2 Per-Node Integration Configuration

```json
// In node document
{
  "nodeId": "docker-host-01",
  "integrations": {
    "docker": {
      "enabled": true,
      "connectionMethod": "agent-proxy",
      "commandRouting": {
        "enabled": true,
        "description": "Allow Docker integration to execute commands instead of agent",
        "allowedCommands": {
          "reg::service::start": true,
          "reg::service::stop": true,
          "reg::service::restart": true,
          "reg::service::logs": true,
          "reg::service::inspect": true,
          "reg::service::update": false
        }
      },
      "status": "connected",
      "lastCheck": "2026-02-05T12:00:00Z"
    },
    "prometheus": {
      "enabled": true,
      "exporterPort": 9100,
      "scrapeEndpoint": "http://192.168.0.20:9100/metrics",
      "commandRouting": {
        "enabled": false,
        "description": "Prometheus is read-only; no command routing applicable"
      },
      "status": "healthy"
    },
    "elasticsearch": {
      "enabled": false,
      "reason": "User disabled - logs not exported"
    }
  }
}
```

**Command Routing Decision Logic:**

When a command targets a node with an integration that supports the requested action, the API uses this priority chain:

```python
async def resolve_execution_path(node: Node, command: Command) -> ExecutionPath:
    """
    Determine how to execute a command on a node.
    Priority: integration-direct → agent-direct (max tier) → agent-poll (normal/max) → error
    """
    
    # 1. Check for integration that can handle this command
    for integration_id, config in node.integrations.items():
        if not config.enabled:
            continue
        if not config.command_routing.enabled:
            continue
        if not config.command_routing.allowed_commands.get(command.registry_id, False):
            continue
        
        driver = get_integration_driver(integration_id)
        if driver and await driver.health_check() == "healthy":
            return ExecutionPath(
                method="integration-direct",
                integration=integration_id,
                fallback=resolve_agent_path(node)
            )
    
    # 2. Try agent-direct (max tier only)
    if node.agent.tier == "max" and node.agent.server_status.reachable:
        return ExecutionPath(
            method="agent-direct",
            fallback=ExecutionPath(method="agent-poll")
        )
    
    # 3. Try agent-poll (normal and max tiers)
    if node.agent.tier in ("normal", "max"):
        return ExecutionPath(method="agent-poll")
    
    # 4. Lite tier or no agent
    return ExecutionPath(
        method="error",
        reason=f"Node '{node.node_id}' agent tier '{node.agent.tier}' does not support command execution"
    )
```

### 7.5 Home Assistant Integration (Core)

Home Assistant is a core integration for IoT device management.

#### 7.5.1 Capabilities

| Capability | Description |
|------------|-------------|
| Device Discovery | Enumerate all HA entities and devices |
| State Sync | Pull current state of IoT devices |
| Device Control | Control lights, switches, climate, locks, etc. |
| Automation Trigger | Trigger HA automations from Hydra |
| Event Subscription | Receive state change events via webhook |

#### 7.5.2 Configuration

```json
{
  "integrationId": "int::homeassistant::main",
  "type": "homeassistant",
  "name": "Home Assistant",
  "connection": {
    "endpoint": "http://homeassistant.local:8123",
    "authMethod": "api-token",
    "credentialRef": "cred::ha-token"
  },
  "capabilities": ["device-discovery", "state-sync", "device-control", "automation-trigger"],
  "syncConfig": {
    "autoDiscover": true,
    "entityFilter": {
      "include": ["light.*", "switch.*", "climate.*", "sensor.*", "lock.*"],
      "exclude": ["sensor.*_battery"]
    }
  }
}
```

#### 7.5.3 IoT Node Creation from HA

When HA integration syncs, discovered devices become Hydra IoT nodes:

```json
{
  "nodeId": "iot-living-room-light",
  "class": "iot",
  "type": "physical",
  "kind": "lighting",
  "displayName": "Living Room Light",
  "source": {
    "integration": "int::homeassistant::main",
    "entityId": "light.living_room",
    "deviceId": "abc123"
  },
  "capabilities": ["on_off", "brightness", "color_temp"],
  "currentState": {
    "state": "on",
    "brightness": 255,
    "color_temp": 370,
    "lastUpdated": "2026-02-05T12:00:00Z"
  }
}
```

#### 7.5.4 Family Role and IoT Controls

The `family` role specifically enables IoT control without infrastructure access:

```yaml
family:
  permissions:
    - iot:read
    - iot:control
    - ha:control
  restrictions:
    - nodes:*
    - services:*
    - commands:*
    - discovery:*
```

**Family Role MCP Tool Access:**

Family members have access to the MCP chat interface (both via hydra-web and external clients like Claude Desktop) with a restricted tool set:

| MCP Tool | Available to Family | Description |
|----------|-------------------|-------------|
| `list_iot_devices` | ✓ | List all IoT devices and their current state |
| `control_iot_device` | ✓ | Control lights, switches, climate, locks, etc. |
| `get_iot_device_status` | ✓ | Get detailed status of a specific IoT device |
| `list_nodes` | ✗ | Infrastructure visibility not permitted |
| `get_node_profile` | ✗ | Infrastructure details not permitted |
| `scan_network` | ✗ | Discovery not permitted |
| `control_service` | ✗ | Infrastructure control not permitted |
| `control_node` | ✗ | Infrastructure control not permitted |
| `control_agent` | ✗ | Agent management not permitted |

This enables natural language IoT interaction for family members:

```
Family member: "Turn off the living room lights"
→ MCP calls control_iot_device(entityId="light.living_room", action="turn_off")

Family member: "What's the temperature in the bedroom?"
→ MCP calls get_iot_device_status(entityId="climate.bedroom")

Family member: "Show me all the lights that are on"
→ MCP calls list_iot_devices(class="lighting", stateFilter="on")
```

Family members **cannot** see infrastructure nodes, network topology, service status, or any data outside the IoT domain. The MCP service enforces this by filtering available tools based on the authenticated user's role before presenting the tool list to the LLM.

### 7.6 Integration Driver Architecture

```python
from abc import ABC, abstractmethod

class IntegrationDriver(ABC):
    """Base class for all integration drivers."""
    
    @abstractmethod
    async def connect(self, config: ConnectionConfig) -> bool:
        """Establish connection to the external system."""
        pass
    
    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """Check integration health."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up connection."""
        pass
    
    # Optional capability methods - implement based on integration type
    
    async def list_child_nodes(self) -> list[DiscoveredNode]:
        """For integrations that manage child nodes (Proxmox, HA)."""
        raise NotImplementedError()
    
    async def execute_on_node(self, node_id: str, command: Command) -> Result:
        """For integrations that support remote execution (Proxmox)."""
        raise NotImplementedError()
    
    async def control_entity(self, entity_id: str, action: str, params: dict) -> Result:
        """For integrations that control devices (HA, Docker)."""
        raise NotImplementedError()
    
    async def query_metrics(self, query: str, time_range: TimeRange) -> MetricResult:
        """For observability integrations (Prometheus)."""
        raise NotImplementedError()
    
    async def search_logs(self, query: str, time_range: TimeRange) -> LogResult:
        """For logging integrations (Elasticsearch)."""
        raise NotImplementedError()
```

### 7.7 Component Integration Awareness

#### 7.7.1 hydra-api

- Maintains integration registry
- Routes control commands through integrations when appropriate
- Health-checks integrations periodically
- Aggregates data from integrations

```python
async def execute_service_control(service: Service, action: str, params: dict) -> Result:
    node = get_node(service.node_id)
    command = Command(registry_id=f"reg::service::{action}", target={"serviceId": service.service_id}, parameters=params)
    
    # Resolve execution path using priority chain
    path = await resolve_execution_path(node, command)
    
    if path.method == "integration-direct":
        try:
            driver = get_integration_driver(path.integration)
            return await driver.control_entity(service.service_id, action, params)
        except IntegrationError:
            # Fall back to agent if integration fails
            if path.fallback:
                return await execute_via_path(path.fallback, node, command)
            raise
    
    elif path.method == "agent-direct":
        try:
            return await send_direct_to_agent(node, command)
        except AgentUnreachableError:
            if path.fallback:
                return await execute_via_path(path.fallback, node, command)
            raise
    
    elif path.method == "agent-poll":
        return await queue_for_polling(node, command)
    
    else:
        raise CommandExecutionError(path.reason)
```

#### 7.7.2 hydra-agent

- Reports available local integrations (Docker socket, node_exporter, etc.)
- Can proxy integration calls on API's behalf
- Reports integration status in health checks

```json
// In agent health response
{
  "integrations": {
    "docker": {
      "available": true,
      "socketPath": "/var/run/docker.sock",
      "version": "24.0.7"
    },
    "nodeExporter": {
      "available": true,
      "port": 9100,
      "version": "1.7.0"
    }
  }
}
```

#### 7.7.3 hydra-web

- Displays integration status per node and globally
- Shows integration-specific UI panels
- Surfaces integration capabilities in Command Center

```
┌─────────────────────────────────────────────────────────────────┐
│  Node: docker-host-01                                           │
├─────────────────────────────────────────────────────────────────┤
│  Integrations:                                                  │
│    Docker ✓ Connected  │  Prometheus ✓ Healthy                 │
│    Elasticsearch ✗ Disabled                                     │
│                                                                 │
│  [Configure Integrations]                                       │
└─────────────────────────────────────────────────────────────────┘
```

#### 7.7.4 hydra-mcp

- Exposes integration-powered tools when integrations available
- Provides integration context in tool descriptions
- Adjusts tool behavior based on integration status

```json
// Tool availability depends on integrations
{
  "name": "query_metrics",
  "available": true,
  "requires": "prometheus",
  "description": "Query Prometheus metrics for nodes and services"
}

{
  "name": "search_logs",
  "available": false,
  "requires": "elasticsearch",
  "unavailableReason": "Elasticsearch integration not configured"
}
```

### 7.8 API Endpoints (Summary)

```
GET    /integrations                    — List all integrations
POST   /integrations                    — Create integration
GET    /integrations/{id}               — Get integration details
PUT    /integrations/{id}               — Update integration
DELETE /integrations/{id}               — Remove integration
POST   /integrations/{id}/test          — Test connection
GET    /integrations/{id}/health        — Health check

GET    /nodes/{nodeId}/integrations     — Node's integration config
PUT    /nodes/{nodeId}/integrations     — Update node's integration config
```

### 7.9 MCP Tools (Integration-Powered)

| Tool | Required Integration | Min Role | Description |
|------|---------------------|----------|-------------|
| `query_metrics` | Prometheus | operator | Query metrics for nodes/services |
| `search_logs` | Elasticsearch | operator | Search centralized logs |
| `control_iot_device` | Home Assistant | family | Control IoT devices (lights, switches, climate, etc.) |
| `list_iot_devices` | Home Assistant | family | List HA entities and their current state |
| `get_iot_device_status` | Home Assistant | family | Get detailed status of a specific IoT device |
| `create_vm` | Proxmox | admin | Create new VM/LXC |
| `snapshot_node` | Proxmox | admin | Create VM/LXC snapshot |
| `run_playbook` | Ansible | admin | Execute Ansible playbook |

**Role-Based Tool Filtering:** The MCP service presents only tools that the authenticated user has permission to call. A `family` role user's LLM will only see IoT tools in its available tool list, preventing it from even attempting infrastructure operations.

---

## 8. Cross-Component Implementation

### 8.1 hydra-api Implementation Summary

#### 8.1.1 New Modules

```
hydra-api/
├── src/
│   ├── discovery/
│   │   ├── __init__.py
│   │   ├── scanner.py          # Network scanning logic
│   │   ├── fingerprint.py      # Service/device fingerprinting
│   │   ├── classifier.py       # Classification engine
│   │   ├── iot_protocols.py    # mDNS, SSDP, etc.
│   │   └── routes.py           # API endpoints
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── registry.py         # Command registry management
│   │   ├── executor.py         # Command dispatch and execution
│   │   ├── queue.py            # Queue management
│   │   ├── chains.py           # Workflow/chain management
│   │   └── routes.py           # API endpoints
│   ├── agent_client/
│   │   ├── __init__.py
│   │   ├── client.py           # HTTP client to agent servers
│   │   ├── auth.py             # Agent authentication
│   │   └── fallback.py         # Polling fallback logic
│   ├── remote_install/
│   │   ├── __init__.py
│   │   ├── ssh.py              # SSH-based installation
│   │   ├── proxmox.py          # Proxmox-based installation
│   │   └── routes.py           # API endpoints
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── base.py             # Base driver class
│   │   ├── registry.py         # Integration management
│   │   ├── drivers/
│   │   │   ├── homeassistant.py
│   │   │   ├── proxmox.py
│   │   │   ├── docker.py
│   │   │   ├── prometheus.py
│   │   │   └── ...
│   │   └── routes.py           # API endpoints
│   └── security/
│       ├── firewall.py         # API host firewall management
│       └── allowlist.py        # Per-node allowlisting
```

#### 8.1.2 Dependencies

```toml
# pyproject.toml additions

[tool.poetry.dependencies]
# Scanning
scapy = "^2.5"           # ARP scanning, packet crafting
python-nmap = "^0.7"     # Port scanning (optional, wraps nmap)
zeroconf = "^0.131"      # mDNS/Bonjour
async-upnp-client = "^0.38"  # SSDP/UPnP
pysnmp = "^5.0"          # SNMP queries
mac-vendor-lookup = "^0.1"   # OUI database

# SSH
asyncssh = "^2.14"       # Async SSH client

# HTTP client
httpx = "^0.27"          # Async HTTP client for agent/integration calls

# Queue
redis = "^5.0"           # Command queue backend
```

### 8.2 hydra-agent Implementation Summary

#### 8.2.1 New Modules

Modules are feature-gated by tier. The build system produces three binaries (or one binary with runtime tier selection):

```
hydra-agent/
├── src/
│   ├── core/                    # All tiers
│   │   ├── mod.rs               # Core module
│   │   ├── config.rs            # Configuration loading
│   │   ├── tier.rs              # Tier detection and enforcement
│   │   └── singleton.rs         # Single-instance enforcement (PID file)
│   ├── server/                  # Max tier only [feature = "server"]
│   │   ├── mod.rs               # Server module
│   │   ├── router.rs            # Axum router setup
│   │   ├── handlers.rs          # Request handlers
│   │   ├── auth.rs              # API secret verification
│   │   └── tls.rs               # TLS configuration
│   ├── commands/                # Normal + Max tiers [feature = "commands"]
│   │   ├── mod.rs               # Command execution
│   │   ├── registry.rs          # Local command registry
│   │   ├── poll.rs              # Poll-based command fetch (normal + max)
│   │   ├── executors/
│   │   │   ├── service.rs       # Service control executor
│   │   │   ├── node.rs          # Node control executor
│   │   │   └── agent.rs         # Agent self-control
│   │   └── safety.rs            # Safety checks
│   ├── probe/                   # Max tier only [feature = "probe"]
│   │   ├── mod.rs               # Network probing
│   │   ├── arp.rs               # ARP scanning
│   │   ├── tcp.rs               # TCP port scanning
│   │   ├── fingerprint.rs       # Service fingerprinting
│   │   └── protocols.rs         # mDNS, SSDP handlers
│   └── integrations/
│       ├── mod.rs               # Local integration detection (all tiers: basic)
│       ├── docker.rs            # Docker socket proxy (max tier) [feature = "deep-integrations"]
│       └── metrics.rs           # Local metrics collection (max tier) [feature = "deep-integrations"]
```

**Cargo Feature Gates:**

```toml
[features]
default = ["lite"]
lite = []                                          # Profile collection only
normal = ["commands"]                               # + poll-based execution
max = ["commands", "server", "probe", "deep-integrations"]  # Full capabilities
commands = []
server = ["dep:axum", "dep:tokio-rustls", "dep:tower", "dep:tower-http"]
probe = ["dep:socket2", "dep:pnet", "dep:mdns-sd"]
deep-integrations = []
```

#### 8.2.2 Dependencies

```toml
# Cargo.toml additions

[dependencies]
# Core (all tiers)
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tokio = { version = "1", features = ["full"] }

# HTTP server (max tier only)
axum = { version = "0.7", optional = true }
tower = { version = "0.4", optional = true }
tower-http = { version = "0.5", features = ["trace", "cors"], optional = true }

# TLS (max tier only)
tokio-rustls = { version = "0.25", optional = true }
rustls = { version = "0.22", optional = true }
rustls-pemfile = { version = "2", optional = true }

# Networking / probing (max tier only)
socket2 = { version = "0.5", optional = true }    # Raw sockets for ARP
pnet = { version = "0.34", optional = true }       # Network packet construction
mdns-sd = { version = "0.10", optional = true }    # mDNS service discovery

# Command execution (normal + max tiers)
tokio-process = "0.2"     # Async process spawning
```

### 8.3 hydra-web Implementation Summary

#### 8.3.1 New Components

```
hydra-web/
├── src/
│   ├── pages/
│   │   ├── discovery/
│   │   │   ├── ScanPage.tsx         # Trigger and view scans
│   │   │   ├── ResultsPage.tsx      # List discovered nodes
│   │   │   ├── DetailPage.tsx       # Discovery details
│   │   │   └── components/
│   │   │       ├── ScanProgress.tsx
│   │   │       ├── DiscoveryCard.tsx
│   │   │       └── ClassificationBadge.tsx
│   │   ├── command-center/
│   │   │   ├── CommandCenterPage.tsx  # Main workflow builder
│   │   │   ├── QueuePage.tsx          # Queue visibility
│   │   │   ├── HistoryPage.tsx        # Command history
│   │   │   └── components/
│   │   │       ├── WorkflowCanvas.tsx   # Drag-drop canvas
│   │   │       ├── CommandPalette.tsx   # Available commands
│   │   │       ├── CommandBlock.tsx     # Individual command
│   │   │       ├── QueueList.tsx
│   │   │       └── CommandResult.tsx
│   │   └── integrations/
│   │       ├── IntegrationsPage.tsx
│   │       ├── ConfigurePage.tsx
│   │       └── components/
│   │           ├── IntegrationCard.tsx
│   │           └── HealthIndicator.tsx
│   ├── components/
│   │   ├── controls/
│   │   │   ├── ServiceControlPanel.tsx
│   │   │   ├── NodeControlPanel.tsx
│   │   │   └── AgentControlPanel.tsx
│   │   └── common/
│   │       └── ConfirmationDialog.tsx
│   └── hooks/
│       ├── useDiscovery.ts
│       ├── useCommands.ts
│       └── useIntegrations.ts
```

### 8.4 hydra-mcp Implementation Summary

#### 8.4.1 New Tools

```python
# Discovery tools
DISCOVERY_TOOLS = [
    "scan_network",              # operator+, hydra-web only
    "list_discoveries",          # viewer+
    "assess_discovery",          # viewer+
    "register_discovery",        # operator+, hydra-web only
    "remote_install_agent",      # operator+, hydra-web only
]

# Control tools
CONTROL_TOOLS = [
    "control_service",           # operator+, hydra-web only
    "control_node",              # admin, hydra-web only
    "control_agent",             # varies by action, hydra-web only
    "get_command_status",        # viewer+ (read-only, available to all clients)
    "list_commands",             # viewer+ (read-only, available to all clients)
]

# Integration-powered tools
INTEGRATION_TOOLS = [
    "query_metrics",             # operator+, requires Prometheus
    "search_logs",               # operator+, requires Elasticsearch
    "control_iot_device",        # family+, requires Home Assistant
    "list_iot_devices",          # family+, requires Home Assistant
    "get_iot_device_status",     # family+, requires Home Assistant
]
```

**Tool Availability Logic:**

```python
def get_available_tools(user: User, client: MCPClient) -> list[Tool]:
    """
    Return only tools the user has permission to call and the client is authorized for.
    """
    available = []
    for tool in ALL_TOOLS:
        # Check user role permission
        if not user.has_permission(tool.required_permission):
            continue
        # Check client authorization (internal vs external)
        if tool.requires_internal_client and client.type != "internal":
            continue
        # Check integration availability
        if tool.required_integration and not is_integration_healthy(tool.required_integration):
            continue
        available.append(tool)
    return available
```

---

## 9. Security Architecture

### 9.1 API Host Firewall Management (Opt-In — Advanced Feature)

The API can optionally manage its own host's firewall for network security. **This feature is disabled by default** and should only be enabled by users who understand the implications of programmatic firewall management.

> **⚠️ Important:** Enabling firewall management gives the Hydra API process the ability to add and remove iptables rules on its host. This can conflict with other firewall managers (Docker, UFW, firewalld) and misconfiguration can result in network lockout. This feature is intended for advanced users running Hydra on a dedicated host or in a container with host networking. Most users should manage their firewall manually and consult the [Firewall Configuration Guide](#) in the Hydra documentation portal for recommended rules.

**Enabling Firewall Management:**

```toml
# /etc/hydra/api.toml

[security]
manage_firewall = false  # DEFAULT: disabled
# Only enable if you understand the risks:
# manage_firewall = true
allowlist_registered_nodes = false  # Auto-add firewall rules for registered nodes
```

When enabled, the web UI configuration page will display a prominent notice:

```
┌─────────────────────────────────────────────────────────────────┐
│  ⚠️  Firewall Management is ENABLED                             │
│                                                                 │
│  Hydra is actively managing iptables rules on the API host.     │
│  Ensure no other firewall manager (UFW, firewalld, Docker) is   │
│  conflicting with these rules.                                  │
│                                                                 │
│  [View Current Rules]  [Disable]  [Documentation]               │
└─────────────────────────────────────────────────────────────────┘
```

#### 9.1.1 Default Posture

```
INBOUND:
  - ALLOW from localhost
  - ALLOW from hydra-web host IP on API port
  - ALLOW from hydra-mcp host IP on API port
  - DROP all other inbound

OUTBOUND:
  - ALLOW to any (API needs to scan and probe)
```

#### 9.1.2 Per-Node Allowlisting

When a node is registered:

```
INBOUND:
  - ALLOW from {node_ip} on API port
  
OUTBOUND (when agent server enabled):
  - ALLOW to {node_ip}:{agent_port}
```

#### 9.1.3 Implementation

```python
# Using iptables via subprocess or python-iptables

async def allowlist_node(node: Node):
    """Add firewall rules for a newly registered node."""
    
    node_ip = node.agent.server_config.address
    agent_port = node.agent.server_config.port
    api_port = config.api.port
    
    # Allow inbound from node to API
    await run_iptables([
        "-A", "INPUT",
        "-s", node_ip,
        "-p", "tcp",
        "--dport", str(api_port),
        "-j", "ACCEPT",
        "-m", "comment",
        "--comment", f"hydra:node:{node.node_id}:inbound"
    ])
    
    # Allow outbound to agent server
    if agent_port:
        await run_iptables([
            "-A", "OUTPUT",
            "-d", node_ip,
            "-p", "tcp",
            "--dport", str(agent_port),
            "-j", "ACCEPT",
            "-m", "comment",
            "--comment", f"hydra:node:{node.node_id}:outbound"
        ])
```

### 9.2 Credential Management

#### 9.2.1 Storage

All credentials stored encrypted at rest:

```json
// credentials collection
{
  "credentialId": "cred::proxmox-01",
  "type": "api-token",
  "scope": "integration",
  "linkedId": "int::proxmox::proxmox-01",
  "encryptedPayload": "<AES-256-GCM encrypted>",
  "encryptionKeyId": "key_master_001",
  "createdBy": "user_admin001",
  "createdAt": "2026-01-15T10:00:00Z",
  "rotatedAt": null,
  "expiresAt": null
}
```

#### 9.2.2 Key Hierarchy

```
Master Key (from environment or secrets manager)
    │
    ├── Integration Credentials Key
    │   └── Encrypts: API tokens, passwords for integrations
    │
    ├── Agent Secrets Key
    │   └── Encrypts: Agent server secrets
    │
    └── SSH Keys Key
        └── Encrypts: Private SSH keys for remote install
```

### 9.3 MCP Client Authorization

```python
def authorize_mcp_request(client: MCPClient, tool: str, user: User) -> bool:
    """
    Authorize an MCP tool call.
    
    Rules:
    1. Read-only tools: Any authenticated client with appropriate role
    2. Write/execute tools: Internal clients only (hydra-web)
    3. User must have required RBAC permission
    4. External clients receive structured guidance (not bare errors) for restricted tools
    """
    
    tool_config = get_tool_config(tool)
    
    # Check user permission first
    required_permission = tool_config.required_permission
    if not user.has_permission(required_permission):
        raise MCPAuthorizationError(
            f"User lacks permission '{required_permission}'",
            code="PERMISSION_DENIED"
        )
    
    # Check client authorization
    if tool_config.requires_internal_client:
        if client.type != "internal":
            # Provide structured guidance for the LLM to relay to the user
            raise MCPAuthorizationError(
                f"Tool '{tool}' is only available from the Hydra web interface",
                code="CLIENT_NOT_AUTHORIZED",
                guidance={
                    "webUrl": f"https://hydra-web/command-center",
                    "alternativeActions": get_read_only_alternatives(tool),
                    "message": "You can perform this action from the Hydra Command Center "
                               "or use the integrated chat in the Hydra web interface."
                }
            )
    
    return True
```

---

## 10. Implementation Roadmap

### 10.1 Phase Order

The features should be implemented in this order due to dependencies:

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2A: Agent Architecture (Tiered + Bidirectional)           │
│  - Agent tier system (lite, normal, max)                         │
│  - Single-instance enforcement                                   │
│  - Agent HTTP server (max tier)                                  │
│  - API-to-agent client                                           │
│  - Authentication between API and agent                          │
│  - Poll-based command fetch (normal tier)                        │
│  - Fallback to polling (max tier)                                │
│  Duration: 3-4 weeks                                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2B: Command Execution System                             │
│  - Command registry                                             │
│  - Queue management                                             │
│  - Execution dispatch                                           │
│  - Command chains/workflows                                     │
│  Duration: 2-3 weeks                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2C: Controls Framework                                   │
│  - Service controls                                             │
│  - Node controls                                                │
│  - Agent controls                                               │
│  - RBAC enforcement                                             │
│  Duration: 1-2 weeks                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2D: Network Discovery                                    │
│  - Scanner implementation                                       │
│  - Fingerprinting and classification                            │
│  - IoT protocol support (mDNS, SSDP)                            │
│  - Discovery API and MCP tools                                  │
│  Duration: 3-4 weeks                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2E: Remote Agent Installation                            │
│  - SSH-based installation                                       │
│  - Proxmox-based installation                                   │
│  - Installation UI                                              │
│  Duration: 1-2 weeks                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2F: Integrations Framework                               │
│  - Driver architecture                                          │
│  - Home Assistant integration (core)                            │
│  - Proxmox integration                                          │
│  - Docker integration                                           │
│  Duration: 3-4 weeks                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2G: Web UI - Command Center                              │
│  - Workflow builder canvas                                      │
│  - Queue visualization                                          │
│  - Integration configuration UI                                 │
│  Duration: 2-3 weeks                                            │
└─────────────────────────────────────────────────────────────────┘
```

### 10.2 Total Estimated Duration

15-23 weeks for complete Phase 2 implementation.

### 10.3 Feature Dependencies

```
Agent Architecture ─────┬───▶ Command Execution ───▶ Controls
                        │
                        └───▶ Network Discovery ───▶ Remote Installation
                                     │
                                     └───▶ Integrations (Home Assistant for IoT)
```

---

## 11. Appendices

### 11.1 Glossary

| Term | Definition |
|------|------------|
| **Discovery** | Process of finding devices on a network |
| **Candidate Node** | Discovered device not yet registered |
| **Fingerprint** | Collected data about a device (ports, banners, protocols) |
| **Classification** | Determining device type from fingerprint |
| **Eligibility** | Assessment of whether a device can be registered/installed |
| **Agent Tier** | Deployment level of the agent: lite (profile-only), normal (+ poll execution), max (+ server + probe) |
| **Agent Server** | HTTP server exposed by max-tier agent for API-to-agent calls |
| **Command Registry** | Database of allowed operations |
| **Command Chain** | Sequence of dependent commands (workflow) |
| **Command Routing** | Per-integration, per-command setting controlling whether an integration handles command execution |
| **Integration** | Connection to external system |
| **Driver** | Code module implementing integration interface |
| **Drift Detection** | Comparing current scan fingerprint to stored data for IoT/networking nodes |

### 11.2 Error Codes

| Code | Description |
|------|-------------|
| `NETWORK_NOT_SCANNABLE` | Network exists but cannot be scanned |
| `DISCOVERY_NOT_FOUND` | Discovery ID doesn't exist |
| `ALREADY_REGISTERED` | Device is already a registered node |
| `COMMAND_NOT_REGISTERED` | Command not in registry |
| `COMMAND_NOT_CANCELLABLE` | Command in non-cancellable state |
| `CLIENT_NOT_AUTHORIZED` | MCP client lacks permission |
| `AGENT_UNREACHABLE` | Cannot connect to agent server |
| `SSH_AUTH_FAILED` | SSH authentication failed |
| `INTEGRATION_UNHEALTHY` | Integration health check failed |
| `CONFIRMATION_REQUIRED` | Destructive operation needs confirmation |

### 11.3 Configuration Reference

#### 11.3.1 API Configuration

```toml
# /etc/hydra/api.toml

[discovery]
enabled = true
default_port_tier = "tier1"
scan_timeout = 300
iot_protocols = ["mdns", "ssdp", "upnp"]

[discovery.capabilities]
arp_scanning = true  # Requires CAP_NET_RAW
snmp_queries = true

[commands]
queue_backend = "redis"
redis_url = "redis://localhost:6379/0"
default_timeout = 60
max_queue_size = 1000

[agent_client]
connection_timeout = 10
request_timeout = 60
retry_failed_direct = 3
fallback_to_poll = true

[remote_install]
enabled = true
ssh_key_path = "/etc/hydra/ssh/id_ed25519"
ssh_timeout = 30

[security]
manage_firewall = false   # Opt-in only — see Security Architecture section
allowlist_registered_nodes = false  # Requires manage_firewall = true
```

#### 11.3.2 Agent Configuration

```toml
# /etc/hydra/agent.toml

[agent]
tier = "max"  # "lite", "normal", or "max"

[server]
# Only applicable for max tier; ignored by lite/normal
enabled = true
bind_address = "0.0.0.0"
port = 9100
tls_enabled = true
tls_cert_file = "/etc/hydra/certs/agent.crt"
tls_key_file = "/etc/hydra/certs/agent.key"

[server.auth]
api_secret_file = "/etc/hydra/credentials/api_secret.json"

[commands]
# Only applicable for normal and max tiers; ignored by lite
allowed_commands = ["reg::service::*", "reg::agent::*"]

[probe]
# Only applicable for max tier; ignored by lite/normal
enabled = true
max_concurrent_scans = 1
```

---

*End of Phase 2 Technical Specification*
