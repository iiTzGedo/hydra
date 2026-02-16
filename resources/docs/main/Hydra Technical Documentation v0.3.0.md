
> **Version:** 0.3.0  
> **Last Updated:** 2025-12-31  
> **Status:** Comprehensive Technical Specification

---
## 1. Objective

### 1.1 High-Level Summary

Hydra is a distributed infrastructure knowledge graph system designed to make homelab (and eventually enterprise) infrastructure **queryable** and **actionable** by AI models. The system profiles network devices, compute nodes, IoT devices, and their services, storing structured snapshots that enable AI-assisted infrastructure management, capacity planning, topology visualization, and operational insights.

### 1.2 Document Purpose

This document serves as the canonical technical specification for the Hydra system, covering:

- Complete API specifications with JSON schemas
- MongoDB collection designs and indexing strategies
- Agent data collection contracts for all node classes
- Service, group, network, and topology data models
- MCP tool interfaces for AI integration
- Web service architecture and Time Machine feature
- Security, RBAC, and access control specifications
- Write operations and command execution framework
- Integration specifications (Home Assistant, monitoring)
- Deployment and operational guidelines

### 1.3 Success Criteria

|Metric|Target|Priority|
|---|---|---|
|Node registration to first profile|< 60 seconds|P0|
|Profile payload processing time|< 500ms|P0|
|Agent memory footprint|< 50MB RSS|P0|
|MCP tool response time|< 2 seconds|P0|
|Topology generation time|< 5 seconds (100 nodes)|P0|
|Time Machine state retrieval|< 1 second|P0|
|Web UI initial load|< 3 seconds|P1|
|Profile data freshness|Configurable (default: 24h)|P0|
|API availability|> 99% uptime|P1|
|Command execution acknowledgment|< 1 second|P1|

### 1.4 Core Features

|Feature|Description|Status|
|---|---|---|
|**Nodes**|Infrastructure entity registration and management|Core|
|**Profiles**|Point-in-time infrastructure snapshots|Core|
|**Services**|First-class workload tracking with runtime details|Core|
|**Groups**|Flexible logical partitioning via selectors|Core|
|**Networks**|Auto-discovered network space definitions|Core|
|**Topologies**|Generated infrastructure/network graphs|Core|
|**Time Machine**|Historical state navigation|Core|
|**Documentations**|Infrastructure knowledge base|Core|
|**RBAC**|Role-based access control|Planned|
|**Write Operations**|Controlled service/system management|Planned|
|**Home Assistant**|IoT integration|Planned|
|**Mobile Apps**|iOS/Android applications|Planned|

---

## 2. Background

### 2.1 Problem Statement

Modern homelabs and small infrastructure deployments lack unified tooling that:

1. **Provides comprehensive infrastructure visibility** — Understanding what hardware, software, services, and network configurations exist across all nodes
2. **Enables AI-assisted operations** — Making infrastructure knowledge accessible to LLM-based assistants for troubleshooting, planning, and automation
3. **Maintains historical context** — Tracking infrastructure evolution with the ability to "time travel" through states
4. **Visualizes topology** — Rendering network and infrastructure relationships in intuitive graphical formats
5. **Documents organically** — Capturing and organizing infrastructure knowledge automatically
6. **Enables controlled actions** — Taking action on infrastructure with appropriate safeguards

### 2.2 Existing Solutions & Gaps

|Solution|What It Does|What's Missing|
|---|---|---|
|**Prometheus/Grafana**|Real-time metrics and alerting|Focuses on "when" not "what"; no AI integration; no topology|
|**Ansible Facts**|Point-in-time system inventory|No persistence; no centralized querying; manual execution|
|**NetBox**|DCIM/IPAM documentation|Manual data entry; no automated profiling; no time machine|
|**Observium/LibreNMS**|Network monitoring and discovery|SNMP-centric; no compute profiling; no AI interface|
|**Home Assistant**|IoT device management|IoT-only; no compute/network profiling; no topology|

### 2.3 Hydra's Differentiation

Hydra addresses these gaps through:

- **Automated profiling** — Agents collect and push structured profiles without manual intervention
- **Service-centric model** — First-class service tracking separate from node profiles
- **Flexible grouping** — Selector-based logical partitioning for any organizational model
- **Network awareness** — Auto-discovery and mapping of network topology
- **Time Machine** — Navigate historical states at node and topology levels
- **AI-native design** — MCP interface provides structured tools for LLM interaction
- **Visual topology** — Interactive graph visualization of infrastructure relationships
- **Progressive control** — From read-only to controlled write operations

---

## 3. Requirements

### 3.1 Functional Requirements

#### FR-1: Node Management

|ID|Requirement|Priority|
|---|---|---|
|FR-1.1|System SHALL support registration of new nodes with unique identifiers|P0|
|FR-1.2|System SHALL classify nodes as `compute`, `networking`, or `iot` types|P0|
|FR-1.3|System SHALL distinguish between `physical` and `logical` compute nodes|P0|
|FR-1.4|System SHALL support node deregistration and archival|P1|
|FR-1.5|System SHALL support node metadata updates without full re-profiling|P1|
|FR-1.6|System SHALL track parent-child relationships between nodes|P0|

#### FR-2: Profile Collection

|ID|Requirement|Priority|
|---|---|---|
|FR-2.1|Agent SHALL collect hardware specifications (CPU, RAM, storage, network, graphics)|P0|
|FR-2.2|Agent SHALL collect network interface configurations for all node classes|P0|
|FR-2.3|Agent SHALL collect installed software/package inventories|P1|
|FR-2.4|Agent SHALL collect user accounts and SSH keys|P1|
|FR-2.5|Agent SHALL collect configuration files with hash tracking|P1|
|FR-2.6|Agent SHALL support scheduled and event-triggered collection|P0|
|FR-2.7|Agent SHALL NOT collect real-time usage metrics (profiling, not monitoring)|P0|
|FR-2.8|Agent SHALL collect interface/port details for networking nodes|P0|
|FR-2.9|Agent SHALL collect device capabilities for IoT nodes|P0|
|FR-2.10|Agent SHALL support three profiling levels: shallow, neutral, deep|P1|

#### FR-3: Service Management

|ID|Requirement|Priority|
|---|---|---|
|FR-3.1|System SHALL track services as first-class entities separate from profiles|P0|
|FR-3.2|System SHALL capture service runtime, status, version, and exposure|P0|
|FR-3.3|System SHALL track service resource allocations when available|P1|
|FR-3.4|System SHALL maintain service discovery origin and timestamps|P0|
|FR-3.5|System SHALL support multiple runtime types (systemd, docker, kubernetes)|P0|
|FR-3.6|System SHALL support service control operations (start/stop/restart)|P2|

#### FR-4: Group Management

|ID|Requirement|Priority|
|---|---|---|
|FR-4.1|System SHALL support user-defined groups with flexible selectors|P0|
|FR-4.2|System SHALL support group membership by ID, network, status, kind, or tags|P0|
|FR-4.3|System SHALL support hierarchical groups via parent references|P1|
|FR-4.4|System SHALL support groups scoped to nodes, services, or both|P0|
|FR-4.5|System SHALL resolve group membership dynamically|P0|

#### FR-5: Network Management

|ID|Requirement|Priority|
|---|---|---|
|FR-5.1|System SHALL auto-create network definitions from node profile data|P0|
|FR-5.2|System SHALL support manual network definition creation|P0|
|FR-5.3|System SHALL track network CIDR, gateway, and subnet relationships|P0|
|FR-5.4|System SHALL associate network nodes (routers) with network definitions|P1|
|FR-5.5|System SHALL support VLAN and overlay network types|P1|

#### FR-6: Topology Management

|ID|Requirement|Priority|
|---|---|---|
|FR-6.1|System SHALL auto-generate network topology graphs|P0|
|FR-6.2|System SHALL auto-generate infrastructure topology graphs|P0|
|FR-6.3|System SHALL maintain historical topology snapshots for Time Machine|P0|
|FR-6.4|System SHALL support topology diff between snapshots|P1|
|FR-6.5|System SHALL trigger topology regeneration on profile changes|P0|

#### FR-7: AI Integration

|ID|Requirement|Priority|
|---|---|---|
|FR-7.1|MCP service SHALL expose node, service, group, network listing tools|P0|
|FR-7.2|MCP service SHALL expose profile and topology retrieval tools|P0|
|FR-7.3|MCP service SHALL support capacity planning queries|P1|
|FR-7.4|MCP service SHALL support network topology queries|P0|
|FR-7.5|MCP service SHALL support Time Machine queries|P0|
|FR-7.6|MCP service SHALL format responses in TOON for LLM consumption|P0|

#### FR-8: Web Interface

|ID|Requirement|Priority|
|---|---|---|
|FR-8.1|Web service SHALL visualize network and infrastructure topology|P0|
|FR-8.2|Web service SHALL provide Time Machine interface|P0|
|FR-8.3|Web service SHALL display node, service, network, and group details|P0|
|FR-8.4|Web service SHALL host MCP chat interface|P0|
|FR-8.5|Web service SHALL support admin and family dashboard views|P1|
|FR-8.6|Web service SHALL support IoT device controls|P2|

#### FR-9: Security & Access Control

|ID|Requirement|Priority|
|---|---|---|
|FR-9.1|System SHALL implement role-based access control (RBAC)|P0|
|FR-9.2|System SHALL support built-in roles: admin, operator, viewer, family, agent|P0|
|FR-9.3|System SHALL support custom role definitions|P1|
|FR-9.4|System SHALL log all write operations for audit|P0|
|FR-9.5|System SHALL support API key authentication for automation|P1|

#### FR-10: Write Operations

|ID|Requirement|Priority|
|---|---|---|
|FR-10.1|System SHALL support safe metadata update operations|P1|
|FR-10.2|System SHALL support service control operations|P2|
|FR-10.3|System SHALL support package management operations|P3|
|FR-10.4|System SHALL support configuration file updates|P3|
|FR-10.5|System SHALL queue and track command execution|P2|

### 3.2 Non-Functional Requirements

|Category|Requirement|
|---|---|
|**Performance**|API response time < 300ms for single-entity queries|
|**Performance**|Topology generation < 2s per 100 nodes|
|**Scalability**|Support up to 500 nodes, 2000 services without architecture changes|
|**Availability**|API service uptime > 99% (non-HA deployment)|
|**Security**|All inter-service communication over TLS; JWT-based auth|
|**Portability**|Agent must run on x86_64 & ARM64 - Linux, macOS, BSD, Windows|
|**Observability**|Structured logging (JSON) with correlation IDs|
|**Resilience**|Graceful degradation when dependencies unavailable|

### 3.3 Constraints

- Agent must be deployable as a single static binary (no runtime dependencies)
- MongoDB is the required database (existing infrastructure)
- MCP protocol compatibility with Claude and other MCP-compatible clients
- No persistent connection requirements between agent and API (stateless HTTP)
- Web service must support modern browsers (Chrome, Firefox, Safari, Edge)
- No secrets stored in profiles (hashes only for sensitive configs)

---

## 4. System Architecture

### 4.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    HYDRA SYSTEM                                          │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│   ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│   │                              USER INTERFACES                                      │  │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │  │
│   │  │   Web App    │  │  Mobile App  │  │  Claude/LLM  │  │    CLI / Scripts     │ │  │
│   │  │  (React/TS)  │  │ (React Nat.) │  │ (MCP Client) │  │                      │ │  │
│   │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘ │  │
│   └─────────┼─────────────────┼─────────────────┼─────────────────────┼─────────────┘  │
│             │                 │                 │                     │                 │
│             ▼                 ▼                 ▼                     ▼                 │
│   ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│   │                              SERVICE LAYER                                        │  │
│   │  ┌────────────────────────────────────────┐  ┌────────────────────────────────┐  │  │
│   │  │            hydra-api                   │  │         hydra-mcp              │  │  │
│   │  │         (Python/FastAPI)               │  │      (Python/MCP SDK)          │  │  │
│   │  │                                        │  │                                │  │  │
│   │  │  • Authentication & RBAC               │  │  • MCP Server Implementation   │  │  │
│   │  │  • Node/Profile CRUD                   │  │  • AI Tools & Resources        │  │  │
│   │  │  • Service Management                  │  │  • TOON Formatting             │  │  │
│   │  │  • Topology Generation                 │  │  • Prompts Library             │  │  │
│   │  │  • Time Machine                        │  │  • API Client Wrapper          │  │  │
│   │  │  • Command Execution Queue             │  │                                │  │  │
│   │  │  • Audit Logging                       │  │                                │  │  │
│   │  └────────────────────┬───────────────────┘  └────────────────┬───────────────┘  │  │
│   └───────────────────────┼──────────────────────────────────────┼───────────────────┘  │
│                           │                                      │                      │
│                           ▼                                      │                      │
│   ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│   │                              DATA LAYER                                           │  │
│   │  ┌────────────────────────────────────────────────────────────────────────────┐  │  │
│   │  │                            MongoDB                                          │  │  │
│   │  │  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐            │  │  │
│   │  │  │  nodes  │ │ profiles │ │ services │ │ groups  │ │ networks │            │  │  │
│   │  │  └─────────┘ └──────────┘ └──────────┘ └─────────┘ └──────────┘            │  │  │
│   │  │  ┌────────────┐ ┌────────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │  │  │
│   │  │  │ topologies │ │ documentations │ │  tokens  │ │ commands │ │  users   │  │  │  │
│   │  │  └────────────┘ └────────────────┘ └──────────┘ └──────────┘ └──────────┘  │  │  │
│   │  │  ┌──────────────┐ ┌──────────────┐                                         │  │  │
│   │  │  │ profile_meta │ │  audit_log   │                                         │  │  │
│   │  │  └──────────────┘ └──────────────┘                                         │  │  │
│   │  └────────────────────────────────────────────────────────────────────────────┘  │  │
│   │                                                                                   │  │
│   │  ┌─────────────────────────┐                                                     │  │
│   │  │         Redis           │  (Command queue, caching, pub/sub)                  │  │
│   │  └─────────────────────────┘                                                     │  │
│   └──────────────────────────────────────────────────────────────────────────────────┘  │
│                                         │                                               │
│             ┌───────────────────────────┼───────────────────────────┐                  │
│             │                           │                           │                  │
│             ▼                           ▼                           ▼                  │
│   ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│   │                          INFRASTRUCTURE LAYER                                     │  │
│   │                                                                                   │  │
│   │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐               │  │
│   │  │   hydra-agent    │  │   hydra-agent    │  │   hydra-agent    │  ...          │  │
│   │  │     (Rust)       │  │     (Rust)       │  │     (Rust)       │               │  │
│   │  │                  │  │                  │  │                  │               │  │
│   │  │  Compute Node    │  │  Network Device  │  │  IoT (via HA)    │               │  │
│   │  └──────────────────┘  └──────────────────┘  └──────────────────┘               │  │
│   │                                                                                   │  │
│   │  ┌──────────────────────────────────────────────────────────────────────────┐   │  │
│   │  │                        Home Assistant                                      │   │  │
│   │  │  (IoT Device Source - REST API Integration)                               │   │  │
│   │  └──────────────────────────────────────────────────────────────────────────┘   │  │
│   └──────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Component Responsibilities

|Component|Responsibility|Technology|
|---|---|---|
|**hydra-api**|Central REST API; manage all collections; generate topologies; authenticate; execute commands|Python/FastAPI|
|**hydra-agent**|Collect node profiles, discover services, push to API, execute commands|Rust|
|**hydra-mcp**|Expose infrastructure as MCP tools/resources for AI consumption|Python/MCP SDK|
|**hydra-web**|Visual interface for topology, Time Machine, planning, MCP chat|React/TypeScript|
|**MongoDB**|Persistent storage for all collections|MongoDB 7.x|
|**Redis**|Command queue, caching, real-time pub/sub|Redis 7.x|

### 4.3 Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    DATA FLOWS                                            │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  1. PROFILE COLLECTION FLOW                                                              │
│  ═══════════════════════════                                                             │
│  ┌─────────┐      ┌─────────┐      ┌───────────────────────────────────────────────────┐│
│  │  Agent  │─────▶│   API   │─────▶│  a) Validate profile schema                      ││
│  │ collects│ POST │receives │      │  b) Compute hash fingerprints (profile_meta)      ││
│  │ profile │      │ profile │      │  c) Calculate version (diff from previous)        ││
│  └─────────┘      └─────────┘      │  d) Store profile in profiles collection          ││
│                                    │  e) Extract & upsert services                      ││
│                                    │  f) Auto-create/update networks                    ││
│                                    │  g) Trigger topology regeneration                  ││
│                                    │  h) Update node.lastProfileAt                      ││
│                                    └───────────────────────────────────────────────────┘│
│                                                                                          │
│  2. TOPOLOGY GENERATION FLOW                                                             │
│  ═══════════════════════════                                                             │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │  Triggered by: profile submission, manual request, scheduled job                  │  │
│  │                                                                                    │  │
│  │  a) Query all active nodes with latest profiles                                   │  │
│  │  b) Query all active services                                                     │  │
│  │  c) Query all networks                                                            │  │
│  │  d) Build graph nodes (nodes, services, networks)                                 │  │
│  │  e) Build graph edges (network-connection, parent-child, service-host)            │  │
│  │  f) Compute layout positions                                                      │  │
│  │  g) Calculate diff from previous topology                                         │  │
│  │  h) Store topology snapshot with validity window                                  │  │
│  │  i) Mark previous topology validUntil                                             │  │
│  └───────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
│  3. TIME MACHINE QUERY FLOW                                                              │
│  ═══════════════════════════                                                             │
│  ┌─────────┐      ┌─────────┐      ┌───────────────────────────────────────────────────┐│
│  │ Web/MCP │─────▶│   API   │─────▶│  a) Parse target timestamp T                      ││
│  │requests │ GET  │  Time   │      │  b) Find topology where validFrom <= T < validUntil│
│  │ state@T │      │ Machine │      │  c) For each node in topology:                    ││
│  └─────────┘      └─────────┘      │     - Find profile where submittedAt <= T         ││
│                                    │     - Merge topology node data with profile        ││
│                                    │  d) Return reconstructed state                     ││
│                                    └───────────────────────────────────────────────────┘│
│                                                                                          │
│  4. COMMAND EXECUTION FLOW                                                               │
│  ═════════════════════════                                                               │
│  ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────────────┐│
│  │User/MCP │─────▶│   API   │─────▶│  Redis  │─────▶│  Agent  │─────▶│ Target System   ││
│  │ request │ POST │validates│ QUEUE│  Queue  │ POLL │executes │      │ (systemd, etc)  ││
│  │ command │      │& queues │      │         │      │ command │      │                 ││
│  └─────────┘      └─────────┘      └─────────┘      └─────────┘      └─────────────────┘│
│       ▲                                                   │                              │
│       │                                                   │                              │
│       └───────────────────────────────────────────────────┘                              │
│                          Result returned                                                 │
│                                                                                          │
│  5. AI QUERY FLOW                                                                        │
│  ═════════════════                                                                       │
│  ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌───────────────────────────────────┐
│  │ Claude  │─────▶│   MCP   │─────▶│   API   │─────▶│ Query nodes/services/topologies  │
│  │  (LLM)  │ MCP  │ Service │ HTTP │         │      │ Return TOON-formatted responses   │
│  └─────────┘      └─────────┘      └─────────┘      └───────────────────────────────────┘
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Technical Implementation

### 5.1 Technology Stack

|Layer|Technology|Rationale|
|---|---|---|
|**Agent**|Rust 1.75+|Performance, single binary, safe concurrency, cross-platform|
|**API**|Python 3.11+ / FastAPI|Rapid development, async support, OpenAPI generation|
|**MCP Service**|Python 3.11+ / MCP SDK|MCP SDK availability, API integration|
|**Web Service**|React 18 / TypeScript|Component model, type safety, ecosystem|
|**Mobile**|React Native|Shared codebase for iOS/Android|
|**Visualization**|ReactFlow / D3.js|Flexible graph rendering, interactivity|
|**Database**|MongoDB 7.x|Document model fits profile data; existing infra|
|**Queue**|Redis 7.x|Command queue, caching, pub/sub|
|**Authentication**|JWT (HS256)|Stateless, widely supported|

### 5.2 Version Format

Hydra uses a hexadecimal versioning format for profiles that reflects the magnitude of infrastructure changes:

```
Format: Ex-W.X.Y.Z

E = Epoch (0-9, then 10+) — Manual increment for breaking changes
W = Massive (0-F) — >75% of sections changed
X = Major (0-F) — >50% of sections changed
Y = Moderate (0-F) — >25% of sections changed
Z = Minor (0-F) — Any section changed

Overflow behavior:
- When Z > F → Y++, Z=0
- When Y > F → X++, Y=0
- When X > F → W++, X=0
- When W > F → E++, W=X=Y=Z=0

Examples:
- E0-0.0.0.1  → First profile (initial submission)
- E0-0.0.0.F  → 15 minor changes
- E0-0.0.1.0  → Moderate change after Z overflow
- E0-0.1.2.3  → Mix of changes over time
- E1-0.0.0.0  → New epoch (breaking schema change)
```

### 5.3 Hash-Based Diff Calculation

Profile versioning uses pre-computed hash fingerprints for O(1) diff detection:

```python
# Stored in profile_meta collection
{
  "profileId": "prof-abc123",
  "nodeId": "node-server-01",
  "version": "E0-1.2.A.5",
  "sectionFingerprints": {
    "network": ["a3f2e1...", "b8c4d5...", "e7f9a2..."],
    "hardware": ["c5d6e7...", "f8a9b1..."],
    "software": ["d2e3f4...", "g9h1i2..."],
    "storage": ["e4f5g6..."],
    "configs": ["f6g7h8..."]
  },
  "profileHash": "1a2b3c4d..."  # Overall identity hash
}
```

**Diff Algorithm:**

1. Compare `profileHash` — if identical, profiles are 100% identical (no new version)
2. For each section, compute Jaccard distance between hash sets
3. Weight sections (hardware: 30%, configs: 25%, software: 20%, storage: 15%, network: 10%)
4. Determine increment position based on weighted diff percentage

---

## 6. Data Models & MongoDB Schema

### 6.1 Collection: `nodes`

**Purpose:** Store registered node metadata (lightweight, not profile data).

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:nodes",
  "title": "Node",
  "type": "object",
  "required": ["nodeId", "class", "type", "displayName", "status"],
  "properties": {
    "_id": { "type": "string" },
    "nodeId": {
      "type": "string",
      "pattern": "^[a-z0-9][a-z0-9.-]{2,63}$",
      "description": "Unique node identifier",
      "examples": ["proxmox-01", "opnsense.gw", "ha-core"]
    },
    "class": {
      "type": "string",
      "enum": ["compute", "networking", "iot"]
    },
    "type": {
      "type": "string",
      "enum": ["physical", "logical"]
    },
    "kind": {
      "type": "string",
      "enum": [
        "bare-metal", "vm", "lxc", "docker", "kubernetes-pod",
        "router", "switch", "access-point", "firewall", "load-balancer",
        "sensor", "actuator", "controller", "hub", "bridge", "appliance",
        "other"
      ]
    },
    "displayName": { "type": "string", "maxLength": 128 },
    "description": { "type": "string", "maxLength": 1024 },
    "tags": {
      "type": "array",
      "items": { "type": "string", "pattern": "^[a-z0-9]+[_:-]?[a-z0-9]*$" }
    },
    "parentNodeId": { "type": ["string", "null"] },
    "networkIds": { "type": "array", "items": { "type": "string" } },
    "location": {
      "type": "object",
      "properties": {
        "site": { "type": "string" },
        "building": { "type": "string" },
        "room": { "type": "string" },
        "rack": { "type": "string" },
        "position": { "type": "integer" }
      }
    },
    "registeredBy": {
      "type": ["string", "null"],
      "description": "User ID of the user who registered this node"
    },
    "registeredAt": { "type": "string", "format": "date-time" },
    "lastUpdated": { "type": "string", "format": "date-time" },
    "lastProfileAt": { "type": ["string", "null"], "format": "date-time" },
    "status": {
      "type": "string",
      "enum": ["active", "inactive", "archived", "pending"]
    }
  }
}
```

**Indexes:**

```javascript
db.nodes.createIndexes([
  { key: { "nodeId": 1 }, unique: true },
  { key: { "class": 1, "type": 1, "status": 1 } },
  { key: { "tags": 1 } },
  { key: { "parentNodeId": 1 } },
  { key: { "networkIds": 1 } },
  { key: { "lastProfileAt": -1 } },
  { key: { "displayName": "text", "description": "text" } }
])
```

### 6.2 Collection: `profiles`

**Purpose:** Store timestamped node profile snapshots (append-only, historical).

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:profiles",
  "title": "Profile",
  "type": "object",
  "required": ["profileId", "nodeId", "version", "collectedAt", "submittedAt"],
  "properties": {
    "_id": { "type": "string" },
    "profileId": { "type": "string" },
    "nodeId": { "type": "string" },
    "version": {
      "type": "string",
      "pattern": "^E([0-9]|[1-9][0-9]+)-([0-9A-F]\\.){3}[0-9A-F]$"
    },
    "collectedAt": { "type": "string", "format": "date-time" },
    "submittedAt": { "type": "string", "format": "date-time" },
    "agentVersion": { "type": "string" },
    "collectionLevel": {
      "type": "string",
      "enum": ["shallow", "neutral", "deep"],
      "default": "neutral"
    },
    "serviceIds": { "type": "array", "items": { "type": "string" } },
    "hardware": { "$ref": "#/definitions/hardwareProfile" },
    "network": { "$ref": "#/definitions/networkProfile" },
    "storage": { "$ref": "#/definitions/storageProfile" },
    "software": { "$ref": "#/definitions/softwareProfile" },
    "virtualization": { "$ref": "#/definitions/virtualizationProfile" },
    "users": { "$ref": "#/definitions/usersProfile" },
    "configs": { "$ref": "#/definitions/configsProfile" },
    "iot": { "$ref": "#/definitions/iotProfile" },
    "networking": { "$ref": "#/definitions/networkingDeviceProfile" },
    "metadata": { "type": "object" }
  }
}
```

**Indexes:**

```javascript
db.profiles.createIndexes([
  { key: { "profileId": 1 }, unique: true },
  { key: { "nodeId": 1, "submittedAt": -1 } },
  { key: { "nodeId": 1, "version": 1 }, unique: true },
  { key: { "submittedAt": -1 } },
  { key: { "serviceIds": 1 } }
])
```

### 6.3 Collection: `profile_meta`

**Purpose:** Store pre-computed hashes for fast profile diff calculations.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:profile_meta",
  "title": "ProfileMeta",
  "type": "object",
  "required": ["profileId", "nodeId", "version", "sectionFingerprints", "profileHash"],
  "properties": {
    "_id": { "type": "string" },
    "profileId": { "type": "string" },
    "nodeId": { "type": "string" },
    "version": { "type": "string" },
    "sectionFingerprints": {
      "type": "object",
      "additionalProperties": {
        "type": "array",
        "items": { "type": "string" }
      }
    },
    "profileHash": { "type": "string" },
    "computedAt": { "type": "string", "format": "date-time" }
  }
}
```

### 6.4 Collection: `services`

**Purpose:** Store first-class service entities discovered on nodes.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:services",
  "title": "Service",
  "type": "object",
  "required": ["serviceId", "runtime", "name", "status", "nodeId", "origin"],
  "properties": {
    "_id": { "type": "string" },
    "serviceId": {
      "type": "string",
      "pattern": "^svc::[a-z0-9-]+::[a-z0-9-_.]+$",
      "examples": ["svc::docker::mongodb", "svc::systemd::nginx"]
    },
    "runtime": {
      "type": "string",
      "enum": ["systemd", "rc", "openrc", "docker", "podman", "containerd", 
               "kubernetes", "lxc", "supervisord", "pm2", "winservice", "launchd", "unknown"]
    },
    "name": { "type": "string" },
    "displayName": { "type": "string" },
    "description": { "type": "string", "maxLength": 1024 },
    "status": {
      "type": "string",
      "enum": ["running", "stopped", "paused", "exited", "failed", "restarting", "unknown"]
    },
    "version": { "type": ["string", "null"] },
    "image": { "type": ["string", "null"] },
    "profileId": { "type": "string" },
    "nodeId": { "type": "string" },
    "exposure": {
      "type": "object",
      "properties": {
        "ports": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "port": { "type": "integer" },
              "protocol": { "type": "string", "enum": ["tcp", "udp"] },
              "hostPort": { "type": ["integer", "null"] }
            }
          }
        },
        "endpoints": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "url": { "type": "string" },
              "type": { "type": "string", "enum": ["http", "https", "grpc", "tcp", "udp"] },
              "internal": { "type": "boolean" }
            }
          }
        }
      }
    },
    "resources": {
      "type": "object",
      "properties": {
        "cpuCores": { "type": ["number", "null"] },
        "cpuShares": { "type": ["integer", "null"] },
        "memoryBytes": { "type": ["integer", "null"] },
        "memoryLimitBytes": { "type": ["integer", "null"] }
      }
    },
    "attachments": {
      "type": "object",
      "properties": {
        "volumes": { "type": "array" },
        "networks": { "type": "array", "items": { "type": "string" } }
      }
    },
    "dependencies": { "type": "array", "items": { "type": "string" } },
    "origin": {
      "type": "object",
      "required": ["nativeId", "discoveredBy", "collectedAt"],
      "properties": {
        "nativeId": { "type": "string" },
        "discoveredBy": { "type": "string", "enum": ["agent", "api", "manual"] },
        "collectedAt": { "type": "string", "format": "date-time" }
      }
    },
    "health": {
      "type": "object",
      "properties": {
        "status": { "type": "string", "enum": ["healthy", "unhealthy", "unknown"] },
        "lastCheck": { "type": "string", "format": "date-time" }
      }
    },
    "tags": { "type": "array", "items": { "type": "string" } },
    "firstSeen": { "type": "string", "format": "date-time" },
    "lastSeen": { "type": "string", "format": "date-time" }
  }
}
```

### 6.5 Collection: `groups`

**Purpose:** Store user-defined logical groupings of nodes and/or services.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:groups",
  "title": "Group",
  "type": "object",
  "required": ["groupId", "name", "types", "selectors"],
  "properties": {
    "_id": { "type": "string" },
    "groupId": {
      "type": "string",
      "pattern": "^[a-z0-9][a-z0-9-]{2,63}$"
    },
    "name": { "type": "string", "maxLength": 128 },
    "description": { "type": "string", "maxLength": 1024 },
    "parentGroupIds": { "type": "array", "items": { "type": "string" } },
    "types": {
      "type": "array",
      "items": { "type": "string", "enum": ["node", "service"] },
      "minItems": 1
    },
    "selectors": {
      "type": "object",
      "properties": {
        "id": {
          "type": "object",
          "properties": {
            "isAll": { "type": "array", "items": { "type": "string" } }
          }
        },
        "network": {
          "type": "object",
          "properties": {
            "isAny": { "type": "array", "items": { "type": "string" } }
          }
        },
        "status": {
          "type": "object",
          "properties": {
            "isAny": { "type": "array", "items": { "type": "string" } }
          }
        },
        "kind": {
          "type": "object",
          "properties": {
            "isAny": { "type": "array", "items": { "type": "string" } }
          }
        },
        "tags": {
          "type": "object",
          "properties": {
            "isAny": { "type": "array", "items": { "type": "string" } },
            "isAll": { "type": "array", "items": { "type": "string" } }
          }
        },
        "runtime": {
          "type": "object",
          "properties": {
            "isAny": { "type": "array", "items": { "type": "string" } }
          }
        },
        "location": {
          "type": "object",
          "properties": {
            "site": { "type": "string" },
            "rack": { "type": "string" }
          }
        }
      }
    },
    "memberCount": {
      "type": "object",
      "properties": {
        "nodes": { "type": "integer" },
        "services": { "type": "integer" },
        "lastComputed": { "type": "string", "format": "date-time" }
      }
    },
    "tags": { "type": "array", "items": { "type": "string" } },
    "createdAt": { "type": "string", "format": "date-time" },
    "updatedAt": { "type": "string", "format": "date-time" }
  }
}
```

**Selector Resolution Logic:**

```
For each entity (node or service):
  1. Check if entity type is in group.types
  2. For each selector in group.selectors:
     - id.isAll: entity ID must be in list
     - network.isAny: entity must be in at least one network
     - status.isAny: entity status must match at least one
     - kind.isAny: node class must match at least one
     - tags.isAny: entity must have at least one matching tag
     - tags.isAll: entity must have ALL listed tags
     - runtime.isAny: (services only) runtime must match
     - location: site AND rack must match if specified
  3. Entity is member if ANY selector rule matches (OR logic)
```

### 6.6 Collection: `networks`

**Purpose:** Store network space definitions.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:networks",
  "title": "Network",
  "type": "object",
  "required": ["networkId", "type", "name"],
  "properties": {
    "_id": { "type": "string" },
    "networkId": {
      "type": "string",
      "pattern": "^[a-z0-9][a-z0-9-]*(-net)?$"
    },
    "type": {
      "type": "string",
      "enum": ["physical", "virtual", "overlay", "vlan", "vxlan"]
    },
    "name": { "type": "string", "maxLength": 128 },
    "description": { "type": "string", "maxLength": 1024 },
    "cidr": {
      "type": ["string", "null"],
      "pattern": "^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$"
    },
    "cidrV6": { "type": ["string", "null"] },
    "gatewayV4": { "type": ["string", "null"] },
    "gatewayV6": { "type": ["string", "null"] },
    "vlanId": { "type": ["integer", "null"], "minimum": 1, "maximum": 4094 },
    "subnetIds": { "type": "array", "items": { "type": "string" } },
    "parentNetworkId": { "type": ["string", "null"] },
    "routerNodeId": { "type": ["string", "null"] },
    "dhcp": {
      "type": "object",
      "properties": {
        "enabled": { "type": "boolean" },
        "rangeStart": { "type": "string" },
        "rangeEnd": { "type": "string" },
        "serverNodeId": { "type": ["string", "null"] }
      }
    },
    "dns": {
      "type": "object",
      "properties": {
        "servers": { "type": "array", "items": { "type": "string" } },
        "domain": { "type": "string" },
        "searchDomains": { "type": "array", "items": { "type": "string" } }
      }
    },
    "nodeCount": { "type": "integer" },
    "origin": {
      "type": "object",
      "properties": {
        "createdBy": { "type": "string", "enum": ["auto", "manual", "import"] },
        "sourceNodeId": { "type": ["string", "null"] },
        "sourceProfileId": { "type": ["string", "null"] }
      }
    },
    "tags": { "type": "array", "items": { "type": "string" } },
    "createdAt": { "type": "string", "format": "date-time" },
    "updatedAt": { "type": "string", "format": "date-time" }
  }
}
```

**Auto-Creation Logic:**

```
On profile submission:
  1. Extract network information from profile.network.interfaces
  2. For each interface with IPv4/IPv6:
     a. Calculate network CIDR from IP + netmask
     b. Check if network with matching CIDR exists
     c. If not exists:
        - Create network with auto-generated networkId
        - Set gatewayV4 from defaultGateway or route table
        - Set origin.createdBy = "auto"
     d. If exists:
        - Update nodeCount
  3. Update node.networkIds with all detected networks
```

### 6.7 Collection: `topologies`

**Purpose:** Store auto-generated topology snapshots.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:topologies",
  "title": "Topology",
  "type": "object",
  "required": ["topologyId", "mode", "version", "generatedAt", "graph"],
  "properties": {
    "_id": { "type": "string" },
    "topologyId": {
      "type": "string",
      "pattern": "^topo::[a-z]+::[0-9]{8}T[0-9]{6}Z$",
      "examples": ["topo::network::20251216T120000Z"]
    },
    "mode": { "type": "string", "enum": ["network", "infrastructure"] },
    "version": { "type": "integer" },
    "scope": {
      "type": ["object", "null"],
      "properties": {
        "networkIds": { "type": "array", "items": { "type": "string" } },
        "groupIds": { "type": "array", "items": { "type": "string" } },
        "nodeIds": { "type": "array", "items": { "type": "string" } }
      }
    },
    "generatedAt": { "type": "string", "format": "date-time" },
    "validFrom": { "type": "string", "format": "date-time" },
    "validUntil": { "type": ["string", "null"], "format": "date-time" },
    "graph": {
      "type": "object",
      "required": ["nodes", "edges"],
      "properties": {
        "nodes": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["id", "type", "data"],
            "properties": {
              "id": { "type": "string" },
              "type": {
                "type": "string",
                "enum": ["compute-physical", "compute-logical", "networking", 
                         "iot", "service", "network", "group"]
              },
              "label": { "type": "string" },
              "data": { "type": "object" },
              "position": {
                "type": "object",
                "properties": {
                  "x": { "type": "number" },
                  "y": { "type": "number" },
                  "layer": { "type": "integer" }
                }
              }
            }
          }
        },
        "edges": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["id", "source", "target", "type"],
            "properties": {
              "id": { "type": "string" },
              "source": { "type": "string" },
              "target": { "type": "string" },
              "type": {
                "type": "string",
                "enum": ["network-connection", "parent-child", "service-host",
                         "service-dependency", "network-gateway", "vlan-trunk", "group-member"]
              },
              "data": { "type": "object" }
            }
          }
        }
      }
    },
    "stats": {
      "type": "object",
      "properties": {
        "nodeCount": { "type": "integer" },
        "edgeCount": { "type": "integer" },
        "networkCount": { "type": "integer" },
        "serviceCount": { "type": "integer" },
        "computeTime": { "type": "integer" }
      }
    },
    "previousTopologyId": { "type": ["string", "null"] },
    "diff": {
      "type": "object",
      "properties": {
        "nodesAdded": { "type": "array", "items": { "type": "string" } },
        "nodesRemoved": { "type": "array", "items": { "type": "string" } },
        "nodesModified": { "type": "array", "items": { "type": "string" } },
        "edgesAdded": { "type": "array", "items": { "type": "string" } },
        "edgesRemoved": { "type": "array", "items": { "type": "string" } }
      }
    }
  }
}
```

### 6.8 Collection: `users`

**Purpose:** Store user accounts for authentication and RBAC.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:users",
  "title": "User",
  "type": "object",
  "required": ["userId", "username", "email", "role", "status"],
  "properties": {
    "_id": { "type": "string" },
    "userId": { "type": "string" },
    "username": { "type": "string", "pattern": "^[a-z0-9_-]{3,32}$" },
    "email": { "type": "string", "format": "email" },
    "passwordHash": { "type": "string" },
    "role": {
      "type": "string",
      "enum": ["admin", "operator", "viewer", "family"]
    },
    "permissions": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Additional permissions beyond role"
    },
    "resourcePermissions": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "resource": { "type": "string" },
          "resourceId": { "type": "string" },
          "permissions": { "type": "array", "items": { "type": "string" } }
        }
      }
    },
    "preferences": {
      "type": "object",
      "properties": {
        "dashboardType": { "type": "string", "enum": ["admin", "home"] },
        "theme": { "type": "string", "enum": ["light", "dark", "system"] },
        "notifications": { "type": "object" }
      }
    },
    "status": { "type": "string", "enum": ["active", "inactive", "locked"] },
    "lastLogin": { "type": ["string", "null"], "format": "date-time" },
    "createdAt": { "type": "string", "format": "date-time" },
    "updatedAt": { "type": "string", "format": "date-time" }
  }
}
```

### 6.9 Collection: `commands`

**Purpose:** Store command execution queue and history.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:commands",
  "title": "Command",
  "type": "object",
  "required": ["commandId", "type", "target", "action", "status", "requestedBy"],
  "properties": {
    "_id": { "type": "string" },
    "commandId": { "type": "string" },
    "type": {
      "type": "string",
      "enum": ["service", "package", "config", "system", "custom"]
    },
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
      "enum": ["pending", "queued", "executing", "completed", "failed", "timeout", "cancelled"]
    },
    "result": {
      "type": ["object", "null"],
      "properties": {
        "success": { "type": "boolean" },
        "output": { "type": "string" },
        "exitCode": { "type": ["integer", "null"] },
        "error": { "type": ["string", "null"] }
      }
    },
    "requestedBy": {
      "type": "object",
      "properties": {
        "userId": { "type": ["string", "null"] },
        "source": { "type": "string", "enum": ["web", "api", "mcp", "automation"] }
      }
    },
    "timeoutSeconds": { "type": "integer", "default": 60 },
    "createdAt": { "type": "string", "format": "date-time" },
    "queuedAt": { "type": ["string", "null"], "format": "date-time" },
    "startedAt": { "type": ["string", "null"], "format": "date-time" },
    "completedAt": { "type": ["string", "null"], "format": "date-time" }
  }
}
```

### 6.10 Collection: `audit_log`

**Purpose:** Immutable audit trail of all significant operations.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:audit_log",
  "title": "AuditEntry",
  "type": "object",
  "required": ["entryId", "timestamp", "action", "resource"],
  "properties": {
    "_id": { "type": "string" },
    "entryId": { "type": "string" },
    "timestamp": { "type": "string", "format": "date-time" },
    "action": {
      "type": "string",
      "enum": ["create", "read", "update", "delete", "execute", "login", "logout", "error"]
    },
    "resource": {
      "type": "object",
      "properties": {
        "type": { "type": "string" },
        "id": { "type": "string" }
      }
    },
    "actor": {
      "type": "object",
      "properties": {
        "type": { "type": "string", "enum": ["user", "agent", "system", "mcp"] },
        "id": { "type": "string" },
        "ip": { "type": "string" }
      }
    },
    "details": { "type": "object" },
    "result": {
      "type": "object",
      "properties": {
        "success": { "type": "boolean" },
        "error": { "type": ["string", "null"] }
      }
    },
    "correlationId": { "type": "string" }
  }
}
```

### 6.11 Collection: `tokens`

**Purpose:** Store registration tokens for user and node registration.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:tokens",
  "title": "RegistrationToken",
  "type": "object",
  "required": ["token", "type", "scope", "createdBy", "createdAt"],
  "properties": {
    "_id": { "type": "string" },
    "token": {
      "type": "string",
      "pattern": "^reg_[A-Za-z0-9_-]{32,}$",
      "description": "Registration token value (reg_ prefix + 32+ char random)"
    },
    "type": {
      "type": "string",
      "enum": ["registration"],
      "description": "Token type (always 'registration' for this collection)"
    },
    "scope": {
      "type": "string",
      "enum": ["user", "node"],
      "description": "Token scope - 'user' for user registration, 'node' for node registration"
    },
    "description": { "type": ["string", "null"], "maxLength": 256 },
    "expiresAt": { "type": "string", "format": "date-time" },
    "maxUses": { "type": ["integer", "null"], "description": "Max uses (null = unlimited)" },
    "usedCount": { "type": "integer", "default": 0 },
    "usedBy": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "entityId": { "type": "string", "description": "Node ID or User ID" },
          "entityType": { "type": "string", "enum": ["node", "user"] },
          "usedAt": { "type": "string", "format": "date-time" }
        }
      },
      "description": "History of token usage"
    },
    "allowedRoles": {
      "type": ["array", "null"],
      "items": { "type": "string", "enum": ["admin", "operator", "viewer", "family"] },
      "description": "Roles allowed for user scope tokens (null = any)"
    },
    "createdBy": { "type": "string", "description": "User ID of token creator" },
    "creatorRole": { "type": "string", "description": "Role of creator at time of creation" },
    "maxRoleLevel": { "type": "integer", "description": "Numeric role level of creator" },
    "createdAt": { "type": "string", "format": "date-time" }
  }
}
```

**Indexes:**

```javascript
db.tokens.createIndexes([
  { key: { "token": 1 }, unique: true },
  { key: { "type": 1, "scope": 1 } },
  { key: { "createdBy": 1 } },
  { key: { "expiresAt": 1 } }
])
```

### 6.12 Collection: `api_keys`

**Purpose:** Store API keys for users and nodes.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:api_keys",
  "title": "ApiKey",
  "type": "object",
  "required": ["keyId", "keyHash", "name", "type", "ownerId", "ownerType"],
  "properties": {
    "_id": { "type": "string" },
    "keyId": { "type": "string", "pattern": "^key_(node_)?[A-Za-z0-9_-]+$" },
    "keyHash": { "type": "string", "description": "Bcrypt hash of the API key" },
    "name": { "type": "string", "maxLength": 128 },
    "type": { "type": "string", "enum": ["user", "node"] },
    "ownerId": { "type": "string", "description": "User ID who owns this key" },
    "ownerType": { "type": "string", "enum": ["user"] },
    "nodeId": { "type": ["string", "null"], "description": "Node ID (for node API keys)" },
    "roles": {
      "type": ["array", "null"],
      "items": { "type": "string" }
    },
    "permissions": {
      "type": "array",
      "items": { "type": "string" }
    },
    "expiresAt": { "type": ["string", "null"], "format": "date-time" },
    "lastUsedAt": { "type": ["string", "null"], "format": "date-time" },
    "createdAt": { "type": "string", "format": "date-time" },
    "revokedAt": { "type": ["string", "null"], "format": "date-time" }
  }
}
```

**Indexes:**

```javascript
db.api_keys.createIndexes([
  { key: { "keyId": 1 }, unique: true },
  { key: { "ownerId": 1, "type": 1 } },
  { key: { "nodeId": 1 }, sparse: true },
  { key: { "revokedAt": 1 } }
])
```

---

## 7. Profile Schemas by Node Class

### 7.1 Compute Node Profile

```json
{
  "nodeId": "proxmox-01",
  "version": "E0-0.1.2.3",
  "collectedAt": "2025-12-16T06:00:00Z",
  "collectionLevel": "neutral",
  
  "hardware": {
    "system": {
      "manufacturer": "Dell Inc.",
      "productName": "PowerEdge R630",
      "serialNumber": "ABC1234",
      "uuid": "4c4c4544-...",
      "isVirtual": false,
      "virtualizationType": null
    },
    "cpu": {
      "model": "Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz",
      "vendor": "GenuineIntel",
      "architecture": "x86_64",
      "physicalCores": 28,
      "logicalCores": 56,
      "sockets": 2,
      "maxFrequencyMHz": 3300,
      "flags": ["vmx", "aes", "avx2"]
    },
    "memory": {
      "totalBytes": 137438953472,
      "slots": [
        { "slot": "DIMM_A1", "sizeBytes": 17179869184, "type": "DDR4", "speedMHz": 2400 }
      ]
    },
    "graphics": [
      { "vendor": "ASPEED", "model": "AST2400", "driver": "ast" }
    ],
    "firmware": {
      "biosVendor": "Dell Inc.",
      "biosVersion": "2.14.0",
      "uefiEnabled": true,
      "secureBootEnabled": false
    }
  },

  "network": {
    "hostname": "proxmox-01",
    "fqdn": "proxmox-01.home.lan",
    "domain": "home.lan",
    "interfaces": [
      {
        "name": "eno1",
        "type": "ethernet",
        "mac": "aa:bb:cc:dd:ee:01",
        "state": "up",
        "speedMbps": 1000,
        "mtu": 1500,
        "driver": "igb",
        "ipv4": [
          { "address": "192.168.0.10", "netmask": "255.255.255.0", "gateway": "192.168.0.1" }
        ]
      }
    ],
    "dns": {
      "servers": ["192.168.0.1", "1.1.1.1"],
      "searchDomains": ["home.lan"]
    },
    "routes": [
      { "destination": "0.0.0.0/0", "gateway": "192.168.0.1", "interface": "eno1" }
    ],
    "defaultGateway": "192.168.0.1"
  },

  "storage": {
    "blockDevices": [
      {
        "name": "sda",
        "type": "disk",
        "sizeBytes": 960197124096,
        "model": "SAMSUNG MZ7LH960",
        "serial": "S456NY0MA00001",
        "transport": "SATA",
        "rotational": false,
        "partitions": [
          { "name": "sda1", "sizeBytes": 1073741824, "fstype": "vfat", "mountpoint": "/boot/efi" }
        ]
      }
    ],
    "filesystems": [
      { "device": "/dev/sda2", "mountpoint": "/", "fstype": "ext4", "sizeBytes": 959122284544 }
    ],
    "lvm": {
      "volumeGroups": [
        { "name": "pve", "sizeBytes": 2000398934016, "freeBytes": 500000000000 }
      ]
    }
  },

  "software": {
    "os": {
      "id": "debian",
      "name": "Debian GNU/Linux",
      "version": "12",
      "codename": "bookworm",
      "kernel": "6.5.11-7-pve",
      "architecture": "x86_64"
    },
    "packages": {
      "manager": "apt",
      "count": 1247,
      "notable": [
        { "name": "proxmox-ve", "version": "8.1.4" }
      ]
    }
  },

  "virtualization": {
    "role": "host",
    "hypervisor": {
      "type": "proxmox",
      "version": "8.1.4",
      "capabilities": ["kvm", "lxc"]
    },
    "guests": [
      {
        "guestId": "100",
        "name": "docker-host",
        "type": "lxc",
        "status": "running",
        "nodeId": "docker-host-01"
      }
    ]
  },

  "users": {
    "accounts": [
      {
        "username": "admin",
        "uid": 1000,
        "home": "/home/admin",
        "shell": "/bin/bash",
        "groups": ["admin", "sudo", "docker"],
        "lastLogin": "2025-12-16T05:45:00Z"
      }
    ],
    "sshKeys": [
      {
        "username": "admin",
        "keyType": "ssh-ed25519",
        "fingerprint": "SHA256:abcdef..."
      }
    ],
    "sudoers": ["admin"]
  },

  "configs": {
    "files": [
      {
        "path": "/etc/network/interfaces",
        "hash": "sha256:abc123...",
        "sizeBytes": 1024,
        "modifiedAt": "2025-12-01T00:00:00Z"
      }
    ],
    "trackedPaths": ["/etc/network/", "/etc/pve/"]
  }
}
```

### 7.2 Networking Node Profile

```json
{
  "nodeId": "opnsense-gw",
  "version": "E0-0.0.1.5",
  
  "hardware": {
    "system": {
      "manufacturer": "Protectli",
      "productName": "VP2420"
    },
    "cpu": {
      "model": "Intel(R) Celeron(R) J6412",
      "physicalCores": 4
    },
    "memory": { "totalBytes": 8589934592 }
  },

  "network": {
    "hostname": "opnsense-gw",
    "interfaces": [
      { "name": "igb0", "role": "wan", "state": "up" },
      { "name": "igb1", "role": "lan", "state": "up", "ipv4": [{ "address": "192.168.0.1" }] },
      { "name": "igb1_vlan10", "role": "iot", "vlanId": 10, "ipv4": [{ "address": "192.168.10.1" }] }
    ]
  },

  "networking": {
    "deviceType": "router",
    "platform": {
      "os": "OPNsense",
      "version": "24.1.1",
      "basedOn": "FreeBSD"
    },
    "routing": {
      "ipForwarding": true,
      "staticRoutes": [],
      "nat": { "enabled": true }
    },
    "switching": {
      "vlans": [
        { "vlanId": 1, "name": "default", "ipAddress": "192.168.0.1/24" },
        { "vlanId": 10, "name": "IoT", "ipAddress": "192.168.10.1/24" }
      ]
    },
    "firewall": {
      "enabled": true,
      "defaultPolicy": "deny",
      "zones": [
        { "name": "wan", "interfaces": ["igb0"], "policy": "deny" },
        { "name": "lan", "interfaces": ["igb1"], "policy": "allow" }
      ],
      "ruleCount": 42
    },
    "services": {
      "dhcp": { "enabled": true },
      "dns": { "enabled": true, "type": "unbound" },
      "vpn": {
        "servers": [
          { "type": "wireguard", "port": 51820, "peers": 3 }
        ]
      }
    }
  }
}
```

### 7.3 IoT Node Profile

```json
{
  "nodeId": "living-room-thermostat",
  "version": "E0-0.0.0.3",

  "network": {
    "hostname": "nest-thermostat-living",
    "interfaces": [
      {
        "name": "wlan0",
        "type": "wifi",
        "mac": "aa:bb:cc:dd:ee:ff",
        "ipv4": [{ "address": "192.168.10.45" }]
      }
    ]
  },

  "iot": {
    "device": {
      "manufacturer": "Google",
      "model": "Nest Thermostat (4th gen)",
      "firmwareVersion": "5.9.3"
    },
    "category": "climate",
    "subcategory": "thermostat",
    "connectivity": {
      "protocol": "wifi",
      "band": "2.4GHz",
      "signalStrength": -45
    },
    "capabilities": {
      "sensors": [
        { "type": "temperature", "unit": "celsius" },
        { "type": "humidity", "unit": "percent" }
      ],
      "actuators": [
        { "type": "hvac", "modes": ["heat", "cool", "auto", "off"] }
      ],
      "controls": [
        { "name": "target_temperature", "type": "number", "min": 10, "max": 32 }
      ]
    },
    "integration": {
      "homeAssistant": {
        "entityIds": ["climate.nest_living_room"],
        "integration": "nest"
      }
    },
    "power": {
      "source": "wired",
      "battery": { "present": true, "level": 100, "backup": true }
    },
    "status": { "online": true },
    "state": {
      "currentTemperature": 21.5,
      "targetTemperature": 22.0,
      "hvacMode": "heat"
    }
  }
}
```

---

## 8. API Service (hydra-api)

### 8.1 Service Configuration

```yaml
# config/hydra-api.yaml
server:
  host: "0.0.0.0"
  port: 8080
  workers: 4
  
database:
  mongodb_uri: "${MONGODB_URI}"
  database_name: "hydra"
  
redis:
  url: "${REDIS_URL}"
  
auth:
  jwt_secret: "${JWT_SECRET}"
  jwt_algorithm: "HS256"
  access_token_expire_minutes: 60
  refresh_token_expire_days: 30
  
features:
  require_registration_token: true
  auto_create_networks: true
  rbac_enabled: true
  write_operations_enabled: false  # Enable in phases
  topology_generation:
    enabled: true
    interval_minutes: 60
    on_profile_change: true
    
rate_limits:
  auth: "10/minute"
  profile_submit: "100/minute"
  read: "300/minute"
  write: "30/minute"
  
logging:
  level: "INFO"
  format: "json"
  include_request_id: true
```

### 8.2 API Endpoints Overview

|Category|Method|Endpoint|Description|
|---|---|---|---|
|**Health**|GET|`/health`|Health check (no auth)|
||GET|`/info`|Service info|
|**Auth**|POST|`/auth/register`|Register node|
||POST|`/auth/login`|User login|
||POST|`/auth/refresh`|Refresh token|
||POST|`/auth/tokens`|Create registration token|
||GET|`/auth/me`|Current user info|
|**Users**|GET|`/users`|List users (admin)|
||POST|`/users`|Create user (admin)|
||GET|`/users/{userId}`|Get user|
||PATCH|`/users/{userId}`|Update user|
||DELETE|`/users/{userId}`|Delete user (admin)|
|**Nodes**|GET|`/nodes`|List nodes|
||GET|`/nodes/{nodeId}`|Get node|
||PATCH|`/nodes/{nodeId}`|Update node|
||DELETE|`/nodes/{nodeId}`|Archive node|
|**Profiles**|POST|`/profiles`|Submit profile|
||GET|`/profiles`|Query profiles|
||GET|`/profiles/{profileId}`|Get profile|
||GET|`/nodes/{nodeId}/profiles/latest`|Latest profile|
||GET|`/nodes/{nodeId}/profiles/diff`|Diff profiles|
|**Services**|GET|`/services`|List services|
||GET|`/services/{serviceId}`|Get service|
||PATCH|`/services/{serviceId}`|Update service|
||DELETE|`/services/{serviceId}`|Archive service|
||POST|`/services/{serviceId}/control`|Control service|
|**Groups**|GET|`/groups`|List groups|
||POST|`/groups`|Create group|
||GET|`/groups/{groupId}`|Get group|
||PUT|`/groups/{groupId}`|Update group|
||DELETE|`/groups/{groupId}`|Delete group|
||GET|`/groups/{groupId}/members`|Get members|
||POST|`/groups/{groupId}/resolve`|Resolve membership|
|**Networks**|GET|`/networks`|List networks|
||POST|`/networks`|Create network|
||GET|`/networks/{networkId}`|Get network|
||PUT|`/networks/{networkId}`|Update network|
||DELETE|`/networks/{networkId}`|Delete network|
|**Topologies**|GET|`/topologies`|List topologies|
||GET|`/topologies/latest`|Latest topology|
||GET|`/topologies/{topologyId}`|Get topology|
||POST|`/topologies/generate`|Trigger generation|
||GET|`/topologies/diff`|Diff topologies|
|**Time Machine**|GET|`/timemachine/node/{nodeId}`|Node at time|
||GET|`/timemachine/topology`|Topology at time|
||GET|`/timemachine/timeline`|Timeline events|
|**Commands**|POST|`/commands`|Queue command|
||GET|`/commands/{commandId}`|Get command status|
||POST|`/commands/{commandId}/cancel`|Cancel command|
|**Docs**|GET|`/docs`|List documentation|
||POST|`/docs`|Create documentation|
||GET|`/docs/{docId}`|Get documentation|
||PUT|`/docs/{docId}`|Update documentation|
||DELETE|`/docs/{docId}`|Delete documentation|
|**Query**|POST|`/query`|Execute query|
||GET|`/capacity`|Capacity summary|
|**Home Assistant**|GET|`/ha/devices`|List HA devices|
||POST|`/ha/sync`|Sync from HA|
||POST|`/ha/control`|Control HA device|

### 8.3 Error Codes

|HTTP|Code|Description|
|---|---|---|
|400|`INVALID_REQUEST`|Malformed request|
|400|`VALIDATION_ERROR`|Schema validation failed|
|401|`AUTH_INVALID_TOKEN`|Invalid/expired token|
|401|`AUTH_MISSING_TOKEN`|No authorization header|
|403|`AUTH_INSUFFICIENT_PERMISSIONS`|Lacks required permission|
|404|`RESOURCE_NOT_FOUND`|Resource doesn't exist|
|409|`RESOURCE_ALREADY_EXISTS`|Duplicate resource|
|422|`OPERATION_NOT_ALLOWED`|Business logic violation|
|429|`RATE_LIMIT_EXCEEDED`|Too many requests|
|500|`INTERNAL_ERROR`|Server error|
|503|`SERVICE_UNAVAILABLE`|Dependency unavailable|

---

## 9. Agent Service (hydra-agent)

### 9.1 Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              hydra-agent                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐ │
│  │    Scheduler    │    │  Event Watcher  │    │      Collectors         │ │
│  │     (cron)      │    │   (inotify)     │    │                         │ │
│  └────────┬────────┘    └────────┬────────┘    │  • Hardware             │ │
│           │                      │             │  • Network              │ │
│           └──────────┬───────────┘             │  • Storage              │ │
│                      │                         │  • Software             │ │
│                      ▼                         │  • Services             │ │
│           ┌─────────────────────┐              │  • Virtualization       │ │
│           │ Profile Orchestrator│◀────────────▶│  • Users                │ │
│           └──────────┬──────────┘              │  • Configs              │ │
│                      │                         └─────────────────────────┘ │
│                      ▼                                                      │
│           ┌─────────────────────┐                                          │
│           │  Service Discovery  │                                          │
│           │  (systemd, docker)  │                                          │
│           └──────────┬──────────┘                                          │
│                      │                                                      │
│                      ▼                                                      │
│           ┌─────────────────────┐              ┌─────────────────────────┐ │
│           │     API Client      │              │   Command Executor      │ │
│           │      (HTTPS)        │◀────────────▶│   (via Redis queue)     │ │
│           └──────────┬──────────┘              └─────────────────────────┘ │
│                      │                                                      │
│                      ▼                                                      │
│           ┌─────────────────────┐                                          │
│           │      hydra-api      │                                          │
│           └─────────────────────┘                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Configuration

```toml
# /etc/hydra/agent.toml

[agent]
node_id = "proxmox-01"
node_class = "compute"  # compute, networking, iot
node_type = "physical"  # physical, logical

[api]
base_url = "https://hydra-api.home.lan"
registration_token = ""
credentials_file = "/etc/hydra/credentials.json"
timeout_seconds = 30
retry_attempts = 3
verify_ssl = true

[schedule]
cron = "0 */6 * * *"
events = ["boot", "network_change", "package_change"]

[collection]
level = "neutral"  # shallow, neutral, deep

[collectors]
hardware = true
network = true
storage = true
software = true
virtualization = true
users = true
services = true
configs = true

[collectors.software]
include_packages = true  # Only in 'deep' mode
service_include = ["docker.*", "nginx", "ssh.*"]
service_exclude = ["snapd"]

[collectors.users]
include_system_accounts = false
include_ssh_keys = true

[collectors.configs]
tracked_paths = [
  "/etc/network/",
  "/etc/hostname",
  "/etc/hosts"
]

[commands]
enabled = false  # Enable for write operations
allowed_types = ["service"]  # Whitelist command types
poll_interval_seconds = 5

[logging]
level = "info"
format = "json"
file = "/var/log/hydra/agent.log"
```

### 9.3 Collection Levels

|Level|Hardware|Network|Storage|Software|Services|Users|Configs|Packages|
|---|---|---|---|---|---|---|---|---|
|**shallow**|Basic|Interfaces|Filesystems|OS only|Running|None|None|None|
|**neutral**|Full|Full|Full + LVM|OS + notable|All|Non-system|Tracked|Notable|
|**deep**|Full|Full + routes|Full + ZFS|Full|All + deps|All|All|All|

### 9.4 Collector Data Sources

|Collector|Linux Sources|
|---|---|
|**Hardware**|`/sys/class/dmi/id/*`, `/proc/cpuinfo`, `/proc/meminfo`, `dmidecode`|
|**Network**|`/sys/class/net/*/`, `/proc/net/route`, `/etc/resolv.conf`, `ip addr`|
|**Storage**|`/sys/block/*/`, `/proc/mounts`, `lsblk`, `vgs/lvs`, `zpool list`|
|**Software**|`/etc/os-release`, `/proc/version`, `dpkg-query`/`rpm -qa`/`pacman -Q`|
|**Services**|`systemctl list-units`, `docker ps`, `docker inspect`, `podman ps`|
|**Virtualization**|`systemd-detect-virt`, `qm list`, `pct list`, `virsh list`|
|**Users**|`/etc/passwd`, `/etc/shadow`, `/etc/group`, `~/.ssh/authorized_keys`|
|**Configs**|File stat, SHA-256 hash, inotify watch|

### 9.5 Agent Installation Flow

The hydra-agent installation script now uses user credentials instead of registration tokens:

```bash
# Linux one-liner with user credentials
curl -sSL https://hydra.local/api/v1/install | bash -s -- \
  --register \
  -u <username> \
  -p <password>

# Manual installation
wget https://hydra.local/api/v1/install/hydra-agent-linux-amd64
chmod +x hydra-agent-linux-amd64

# Register with credentials (password prompt if -p omitted)
./hydra-agent-linux-amd64 register -u <username> -p <password>

# Or with explicit node configuration
./hydra-agent-linux-amd64 register \
  -u <username> \
  -p <password> \
  --node-id "custom-node-01" \
  --display-name "Custom Node" \
  --tags "production,web"

# Install as systemd service
./hydra-agent-linux-amd64 install
```

**Installation Process:**

1. User provides their Hydra credentials
2. Agent authenticates user via `POST /auth/login`
3. Agent calls `POST /nodes/register` with user's access token
4. Agent receives node-specific API key
5. Agent stores API key in `/etc/hydra/credentials.json`
6. All subsequent agent operations use the node API key

---

## 10. MCP Service (hydra-mcp)

### 10.1 Tools

|Tool|Description|Parameters|
|---|---|---|
|`list_nodes`|List infrastructure nodes|`class`, `type`, `status`, `tags`, `limit`|
|`get_node`|Get node details|`nodeId`, `includeChildren`, `includeServices`|
|`get_node_profile`|Get latest profile|`nodeId`, `sections[]`|
|`list_services`|List services|`nodeId`, `runtime`, `status`, `limit`|
|`get_service`|Get service details|`serviceId`|
|`list_groups`|List groups|`types[]`, `tags`, `limit`|
|`get_group`|Get group with members|`groupId`, `resolveMembers`|
|`list_networks`|List networks|`type`, `limit`|
|`get_network`|Get network details|`networkId`, `includeNodes`|
|`get_topology`|Get topology graph|`mode`, `scope`|
|`search_infrastructure`|Search across entities|`query`, `types[]`, `limit`|
|`compare_profiles`|Diff two profiles|`nodeId`, `fromVersion`, `toVersion`|
|`get_capacity`|Capacity summary|`groupBy`, `includeLogical`|
|`time_machine_node`|Node state at time|`nodeId`, `timestamp`|
|`time_machine_topology`|Topology at time|`mode`, `timestamp`|
|`query_infrastructure`|Raw query|`collection`, `filter`, `projection`|
|`control_service`|Control service|`serviceId`, `action`|
|`control_device`|Control IoT device|`nodeId`, `command`, `parameters`|

### 10.2 Resources

|Resource URI|Description|
|---|---|
|`infrastructure://overview`|High-level summary|
|`infrastructure://nodes`|All nodes list|
|`infrastructure://services`|All services list|
|`infrastructure://networks`|All networks list|
|`infrastructure://topology/network`|Network topology|
|`infrastructure://topology/infrastructure`|Infrastructure topology|
|`infrastructure://node/{nodeId}`|Specific node|
|`infrastructure://service/{serviceId}`|Specific service|

### 10.3 Prompts

|Prompt|Description|
|---|---|
|`capacity_planning`|Analyze capacity for new workloads|
|`troubleshoot_network`|Network diagnostics|
|`infrastructure_audit`|Security and config audit|
|`service_dependency_map`|Map service dependencies|
|`migration_planning`|Plan infrastructure migration|
|`documentation_generator`|Generate docs for entities|

### 10.4 TOON Response Format

```
INFRASTRUCTURE OVERVIEW
=======================

Nodes: 12 total (11 active, 1 inactive)
├── Compute: 10 (3 physical, 7 logical)
├── Networking: 1
└── IoT: 1

Services: 47 total (42 running, 5 stopped)
├── systemd: 15
├── docker: 28
└── kubernetes: 4

Networks: 3
├── homenet-lan (192.168.0.0/24) - 12 nodes
├── iot-vlan (192.168.10.0/24) - 8 nodes
└── guest-vlan (192.168.20.0/24) - 2 nodes

Last Profile: 2 minutes ago (proxmox-01)
```

---

## 11. Web Service (hydra-web)

### 11.1 Technology Stack

|Component|Technology|
|---|---|
|Framework|React 18 + TypeScript|
|State Management|Zustand|
|Routing|React Router v6|
|UI Components|shadcn/ui|
|Graph Visualization|ReactFlow + D3.js|
|API Client|TanStack Query|
|Styling|Tailwind CSS|
|Build|Vite|

### 11.2 Key Features

**Dashboard**

- Infrastructure health summary
- Capacity overview (CPU, RAM, Storage)
- Recent activity feed
- Alert summary
- Mini topology view

**Topology Viewer**

- Network mode: L2/L3 topology
- Infrastructure mode: Node hierarchy
- Interactive zoom/pan/drag
- Filter by class, status, network
- Click for detail panel
- Export as SVG/PNG

**Time Machine**

- Timeline scrubber
- Event markers (node added, service changed, etc.)
- Historical topology view
- Node state at any point
- Compare two points in time

**MCP Chat**

- Natural language queries
- Tool call visualization
- Context-aware suggestions
- Query history

**Admin Dashboard**

- User management
- Token management
- Audit log viewer
- System settings

**Home Dashboard**

- Simplified IoT controls
- Room-by-room view
- Scene activation
- Temperature/lighting controls

---

## 12. Authentication & Security

### 12.1 Token Types

| Type         | Lifetime     | Purpose                     |
| ------------ | ------------ | --------------------------- |
| Registration | 7 days       | One-time user registration  |
| Access (JWT) | 1 hour       | API authentication          |
| Refresh      | 30 days      | Renew access tokens         |
| API Key      | Configurable | Automation/service accounts |

### 12.2 JWT Claims

```json
{
  "sub": "user_abc123",
  "type": "user",
  "role": "operator",
  "permissions": ["nodes:read", "services:*"],
  "iat": 1703851200,
  "exp": 1703854800
}
```

### 12.3 Security Layers

|Layer|Implementation|
|---|---|
|**Network**|TLS 1.3 for all external traffic|
|**Authentication**|JWT with HS256, bcrypt for passwords|
|**Authorization**|RBAC with permission checks|
|**Data**|No secrets in profiles, hash-only configs|
|**Audit**|All write operations logged|

---

## 13. Access Control (RBAC)

### 13.1 Built-in Roles

|Role|Description|Permissions|
|---|---|---|
|**admin**|Full access|`*:*`|
|**operator**|Manage infrastructure|`nodes:*`, `services:*`, `groups:*`, `networks:*`, `topologies:read`, `commands:execute`|
|**viewer**|Read-only access|`nodes:read`, `services:read`, `groups:read`, `networks:read`, `topologies:read`|
|**family**|Smart home controls|`iot:read`, `iot:control`, `ha:control`|
|**agent**|Agent-only|`profiles:write` (own node), `commands:poll`|

### 13.2 Permission Format

```
resource:action

Resources: nodes, profiles, services, groups, networks, topologies, 
           docs, users, tokens, commands, iot, ha, audit

Actions: read, write, create, delete, execute, control, *

Examples:
- nodes:read       → Read nodes
- services:*       → All service operations
- commands:execute → Execute commands
- *:*              → Full access
```

### 13.3 Resource-Level Permissions

```json
{
  "userId": "user_family_01",
  "role": "viewer",
  "resourcePermissions": [
    {
      "resource": "nodes",
      "resourceId": "living-room-*",
      "permissions": ["read", "control"]
    }
  ]
}
```

---

## 14. Write Operations & Command Execution

### 14.1 Command Types

|Type|Operations|Role Required|
|---|---|---|
|**metadata**|Update node/service tags, descriptions|operator|
|**service**|start, stop, restart, reload|operator|
|**package**|install, update, remove|admin|
|**config**|Edit configuration files|admin|
|**system**|Reboot, shutdown|admin|

### 14.2 Command Execution Flow

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌──────────┐
│  User   │────▶│   API   │────▶│  Redis  │────▶│  Agent  │────▶│  System  │
│ Request │     │ Validate│     │  Queue  │     │ Execute │     │          │
└─────────┘     └────┬────┘     └─────────┘     └────┬────┘     └──────────┘
                     │                               │
                     │     ┌─────────────────────────┘
                     │     │
                     ▼     ▼
              ┌─────────────────┐
              │   commands      │
              │   collection    │
              └─────────────────┘
```

### 14.3 Command Request

```json
{
  "type": "service",
  "target": {
    "nodeId": "docker-host-01",
    "serviceId": "svc::docker::nginx"
  },
  "action": "restart",
  "parameters": {},
  "timeoutSeconds": 60
}
```

### 14.4 Safety Controls

- Permission check before queuing
- Timeout enforcement
- Rate limiting per user/node
- Audit logging
- Confirmation for destructive operations
- Rollback support (where applicable)

---

## 15. Home Assistant Integration

### 15.1 Integration Modes

|Mode|Direction|Description|
|---|---|---|
|**Pull**|Hydra ← HA|Hydra queries HA REST API|
|**Push**|HA → Hydra|HA webhooks to Hydra|
|**Control**|Hydra → HA|Hydra sends commands to HA|

### 15.2 Configuration

```yaml
# hydra-api config
home_assistant:
  enabled: true
  url: "http://homeassistant.local:8123"
  token: "${HA_LONG_LIVED_TOKEN}"
  sync_interval_minutes: 15
  webhook_secret: "${HA_WEBHOOK_SECRET}"
  
  entity_mapping:
    climate.*: { class: "iot", category: "climate" }
    light.*: { class: "iot", category: "lighting" }
    switch.*: { class: "iot", category: "switch" }
    lock.*: { class: "iot", category: "security" }
    sensor.*: { class: "iot", category: "sensor" }
```

### 15.3 Device Mapping

```
HA Entity: climate.living_room_thermostat
                    ↓
Hydra Node: {
  nodeId: "ha-climate-living-room-thermostat",
  class: "iot",
  type: "logical",
  kind: "controller",
  displayName: "Living Room Thermostat",
  iot: {
    category: "climate",
    integration: { homeAssistant: { entityId: "climate.living_room_thermostat" } }
  }
}
```

### 15.4 Control API

```
POST /api/v1/ha/control
{
  "entityId": "climate.living_room_thermostat",
  "service": "set_temperature",
  "data": {
    "temperature": 22
  }
}
```

---

## 16. Mobile Application

### 16.1 Technology

- **Framework:** React Native
- **State:** Zustand + TanStack Query
- **Navigation:** React Navigation
- **Push Notifications:** Firebase Cloud Messaging

### 16.2 Key Screens

|Screen|Features|
|---|---|
|**Home**|Status cards, quick actions, alerts|
|**Nodes**|Searchable list, basic details|
|**IoT**|Room controls, scenes|
|**Chat**|MCP interface with voice input|
|**Notifications**|Alert history, settings|

### 16.3 Notification Types

- Node offline
- Service failed
- Profile collection failed
- Security alerts
- Custom threshold alerts

---

## 17. Monitoring & Observability

### 17.1 Metrics (Prometheus)

```
# Node metrics
hydra_nodes_total{class, type, status}
hydra_nodes_last_profile_age_seconds{node_id}

# Service metrics
hydra_services_total{runtime, status}
hydra_services_by_node{node_id, runtime}

# Profile metrics
hydra_profiles_submitted_total{node_id}
hydra_profile_processing_duration_seconds

# API metrics
hydra_api_requests_total{method, endpoint, status}
hydra_api_request_duration_seconds{method, endpoint}

# Command metrics
hydra_commands_total{type, status}
hydra_command_execution_duration_seconds{type}
```

### 17.2 Structured Logging

```json
{
  "timestamp": "2025-12-16T10:00:00Z",
  "level": "info",
  "message": "Profile submitted",
  "service": "hydra-api",
  "request_id": "req-abc123",
  "node_id": "proxmox-01",
  "version": "E0-0.1.2.4",
  "duration_ms": 125
}
```

### 17.3 Health Checks

```json
GET /health

{
  "status": "healthy",
  "version": "0.3.0",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "disk": "ok"
  },
  "uptime_seconds": 86400
}
```

---

## 18. Deployment

### 18.1 Docker Compose (Production)

```yaml
version: '3.8'

services:
  mongodb:
    image: mongo:7
    volumes:
      - mongo_data:/data/db
    restart: unless-stopped
    healthcheck:
      test: mongosh --eval "db.runCommand('ping').ok"
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped
    healthcheck:
      test: redis-cli ping
      interval: 10s
      timeout: 5s
      retries: 5

  hydra-api:
    image: hydra/api:0.3.0
    ports:
      - "8080:8080"
    environment:
      - MONGODB_URI=mongodb://mongodb:27017/hydra
      - REDIS_URL=redis://redis:6379
      - JWT_SECRET=${JWT_SECRET}
    depends_on:
      mongodb:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

  hydra-mcp:
    image: hydra/mcp:0.3.0
    ports:
      - "3000:3000"
    environment:
      - HYDRA_API_URL=http://hydra-api:8080
    depends_on:
      - hydra-api
    restart: unless-stopped

  hydra-web:
    image: hydra/web:0.3.0
    ports:
      - "80:80"
    environment:
      - API_URL=http://hydra-api:8080
      - MCP_URL=ws://hydra-mcp:3000
    depends_on:
      - hydra-api
      - hydra-mcp
    restart: unless-stopped

volumes:
  mongo_data:
  redis_data:
```

### 18.2 Production Checklist

- [ ] TLS certificates configured
- [ ] JWT secret generated and secured
- [ ] MongoDB authentication enabled
- [ ] Redis password set
- [ ] Backup strategy configured
- [ ] Log aggregation set up
- [ ] Monitoring dashboards created
- [ ] Alert rules configured
- [ ] Rate limits tuned
- [ ] Resource limits set

---

## 19. Testing Strategy

### 19.1 Test Pyramid

|Level|Coverage|Tools|
|---|---|---|
|Unit|80%|pytest, cargo test|
|Integration|70%|pytest-asyncio, testcontainers|
|E2E|10%|Playwright|

### 19.2 Critical Path Tests

1. **Authentication Flow:** Register → Login → Refresh → Access
2. **Profile Flow:** Submit → Validate → Version → Store → Services
3. **Time Machine:** Generate topology → Query at time → Verify state
4. **Command Execution:** Queue → Agent poll → Execute → Result

---

## 20. Technical Concerns & Mitigations

### 20.1 Security Concerns

|Concern|Risk|Mitigation|
|---|---|---|
|Agent as attack surface|Compromised agent = system access|Minimal agent permissions, command whitelisting, audit logging|
|JWT secret compromise|Full API access|Secret rotation capability, short token lifetime|
|Sensitive data in profiles|Data leakage|No secrets in profiles, hash-only for configs|
|Write operation abuse|System damage|RBAC, rate limiting, audit logging, confirmation for destructive ops|

### 20.2 Reliability Concerns

|Concern|Risk|Mitigation|
|---|---|---|
|MongoDB single point of failure|Data loss, downtime|Replica set for production, regular backups|
|Agent connectivity issues|Stale profiles|Offline queue, retry logic, staleness indicators|
|Topology generation overhead|API slowdown|Background job queue, incremental updates|
|Large profile payloads|Memory pressure|Streaming processing, size limits, compression|

### 20.3 Scalability Concerns

|Concern|Threshold|Mitigation|
|---|---|---|
|Profile storage growth|100+ nodes, years of history|TTL indexes, archival strategy, compression|
|Topology complexity|500+ nodes|Scoped generation, caching, lazy loading|
|Concurrent agent submissions|100+ simultaneous|Rate limiting, queue processing, horizontal scaling|
|MCP query volume|High AI usage|Caching, query optimization, resource limits|

---

## 21. Appendices

### 21.1 Collection Summary

|Collection|Purpose|Key Fields|
|---|---|---|
|`nodes`|Node metadata|nodeId, class, type, status|
|`profiles`|Profile snapshots|nodeId, version, hardware, network|
|`profile_meta`|Hash fingerprints|profileId, sectionFingerprints|
|`services`|Service entities|serviceId, runtime, nodeId, exposure|
|`groups`|Logical groupings|groupId, types, selectors|
|`networks`|Network definitions|networkId, cidr, gatewayV4|
|`topologies`|Topology snapshots|topologyId, mode, graph|
|`documentations`|Documentation|docId, type, linkedEntities|
|`users`|User accounts|userId, role, permissions|
|`tokens`|Auth tokens|token, type, expiresAt|
|`commands`|Command queue|commandId, type, status|
|`audit_log`|Audit trail|action, resource, actor|

### 21.2 ID Formats

|Entity|Format|Example|
|---|---|---|
|Node|`[a-z0-9][a-z0-9.-]{2,63}`|`proxmox-01`|
|Service|`svc::<runtime>::<name>`|`svc::docker::mongodb`|
|Group|`[a-z0-9][a-z0-9-]{2,63}`|`production-servers`|
|Network|`[a-z0-9][a-z0-9-]*(-net)?`|`homenet-lan`|
|Topology|`topo::<mode>::<timestamp>`|`topo::network::20251216T120000Z`|
|Profile|`prof-<nodeId>-<timestamp>`|`prof-proxmox-01-1703851200`|
|Command|`cmd-<uuid>`|`cmd-abc12345`|

### 21.3 Version History

|Version|Date|Changes|
|---|---|---|
|0.1.0|2025-12-15|Initial design|
|0.2.0|2025-12-29|Services, groups, networks, topologies|
|0.3.0|2025-12-31|RBAC, write ops, HA integration, mobile, monitoring|

---

_This document is the canonical technical reference for Hydra. For API details, see the API Reference. For product context, see the Product Documentation._