# Hydra Technical Documentation

> **Version:** 0.5.0  
> **Last Updated:** 2026-02-25  
> **Status:** Comprehensive Technical Specification — Phase 2 Complete  
> **Supersedes:** Technical Documentation v0.3.0, Phase 2 Technical Specification v0.4.0, Dashboard Framework v0.5.0, Documentation System v0.5.0

---

## Table of Contents

1. [Objective](#1-objective)
2. [Background](#2-background)
3. [Requirements](#3-requirements)
4. [System Architecture](#4-system-architecture)
5. [Technical Implementation](#5-technical-implementation)
6. [Data Layer Architecture](#6-data-layer-architecture)
7. [MongoDB Data Models](#7-mongodb-data-models)
8. [PostgreSQL Data Models](#8-postgresql-data-models)
9. [Profile Schemas by Node Class](#9-profile-schemas-by-node-class)
10. [Service Discovery](#10-service-discovery)
11. [Group Management](#11-group-management)
12. [Network Management](#12-network-management)
13. [Topology Generation](#13-topology-generation)
14. [Time Machine](#14-time-machine)
15. [Network Discovery](#15-network-discovery)
16. [Agent Architecture](#16-agent-architecture)
17. [Commands, Executions & Workflows](#17-commands-executions--workflows)
18. [Controls & Safety](#18-controls--safety)
19. [Remote Agent Installation](#19-remote-agent-installation)
20. [Plugin & Integration Architecture](#20-plugin--integration-architecture)
21. [Dashboard Framework](#21-dashboard-framework)
22. [Living Documentation System](#22-living-documentation-system)
23. [Embedding & Semantic Search Pipeline](#23-embedding--semantic-search-pipeline)
24. [MCP Service](#24-mcp-service)
25. [Web Service Architecture](#25-web-service-architecture)
26. [Authentication & RBAC](#26-authentication--rbac)
27. [Notification System](#27-notification-system)
28. [AI Configuration & Chat](#28-ai-configuration--chat)
29. [Known Services](#29-known-services)
30. [Settings Management](#30-settings-management)
31. [Deployment](#31-deployment)
32. [Testing Strategy](#32-testing-strategy)
33. [Technical Concerns & Mitigations](#33-technical-concerns--mitigations)
34. [Appendices](#34-appendices)

---

## 1. Objective

### 1.1 High-Level Summary

Hydra is a distributed infrastructure knowledge graph system designed to make homelab (and eventually enterprise) infrastructure **queryable** and **actionable** by AI models. The system profiles network devices, compute nodes, IoT devices, and their services, storing structured snapshots that enable AI-assisted infrastructure management, capacity planning, topology visualization, and operational control.

Phase 2 expands Hydra from a read-only profiling system into a comprehensive infrastructure management platform with network discovery, tiered agent architecture, a three-layer command execution system, a provider-scoped plugin framework with 19 integrations, customizable dashboards, and a living documentation system — all underpinned by a dual-database architecture (MongoDB + PostgreSQL/pgvector) that enables both document-model storage and semantic AI search.

### 1.2 Document Purpose

This document is the **canonical technical specification** for the Hydra system. It absorbs and supersedes all Phase 2 feature specifications into a single authoritative reference covering:

- Dual-database architecture (MongoDB + PostgreSQL/pgvector) with domain-specific split rationale
- Complete MongoDB collection designs and PostgreSQL table schemas with indexing strategies
- Agent data collection contracts for all node classes across three agent tiers
- Service, group, network, topology, and discovery data models
- Three-layer command execution system (Commands → Executions → Workflows)
- Provider-scoped plugin architecture with six integration touchpoints
- Dashboard framework with widget system, data binding, and layout engine
- Living documentation system with auto-generation pipeline and hybrid authoring
- Embedding pipeline for semantic search across all infrastructure knowledge
- MCP tool interfaces for AI integration with source-aware permissions
- Web service architecture with 55+ pages/panels and role-adapted navigation
- Security, RBAC, and access control specifications including MCP client scoping
- Deployment and operational guidelines for the three-database stack

### 1.3 Success Criteria

| Metric | Target | Priority |
|---|---|---|
| Node registration to first profile | < 60 seconds | P0 |
| Profile payload processing time | < 500ms | P0 |
| Agent memory footprint | < 50MB RSS (all tiers) | P0 |
| MCP tool response time | < 2 seconds | P0 |
| Semantic search (pgvector) response time | < 500ms | P0 |
| Topology generation time | < 5 seconds (100 nodes) | P0 |
| Time Machine state retrieval | < 1 second | P0 |
| Web UI initial load | < 3 seconds | P1 |
| Profile data freshness | Configurable (default: 24h) | P0 |
| API availability | > 99% uptime | P1 |
| Command execution acknowledgment | < 1 second (max-tier) | P1 |
| Dashboard widget render time | < 200ms per widget | P1 |
| Document auto-generation | < 10 seconds per document | P1 |
| Global search (Cmd+K) response | < 100ms | P1 |
| Network scan (/24 host discovery) | < 15 seconds | P1 |

### 1.4 Core Features

| Feature | Description | Status |
|---|---|---|
| **Nodes** | Infrastructure entity registration and management | Core |
| **Profiles** | Point-in-time infrastructure snapshots | Core |
| **Services** | First-class workload tracking with runtime details | Core |
| **Groups** | Flexible logical partitioning via selectors | Core |
| **Networks** | Auto-discovered network space definitions | Core |
| **Topologies** | Generated infrastructure/network graphs | Core |
| **Time Machine** | Historical state navigation | Core |
| **Network Discovery** | Proactive device scanning and classification | Phase 2 |
| **Agent Architecture** | Three-tier agents (lite/normal/max) with bidirectional comms | Phase 2 |
| **Command Center** | Three-layer command execution (Commands → Executions → Workflows) | Phase 2 |
| **Controls & Safety** | RBAC enforcement, confirmation, rate limiting for operations | Phase 2 |
| **Remote Installation** | Deploy agents to discovered nodes via SSH/Proxmox | Phase 2 |
| **Plugin System** | 19 provider-scoped integrations across six touchpoints | Phase 2 |
| **Dashboard Framework** | Customizable boards with 75+ widget types | Phase 2 |
| **Living Documentation** | Auto-generated + manually-authored infrastructure docs | Phase 2 |
| **Semantic Search** | pgvector-powered AI search across all infrastructure knowledge | Phase 2 |
| **RBAC** | Role-based access control with source-aware MCP permissions | Core |
| **Write Operations** | Controlled service/system management via command catalog | Phase 2 |
| **Home Assistant** | IoT integration via plugin | Core |
| **Notifications** | 5-tier real-time notification system with dedup, escalation, auto-resolve | Core |
| **AI Chat** | Multi-provider LLM configuration + web MCP chat | Core |
| **Known Services** | Service registry and allow-listing | Core |
| **Mobile Apps** | iOS/Android applications | Phase 3 |

---

## 2. Background

### 2.1 Problem Statement

Modern homelabs and small infrastructure deployments lack unified tooling that:

1. **Provides comprehensive infrastructure visibility** — Understanding what hardware, software, services, and network configurations exist across all nodes
2. **Enables AI-assisted operations** — Making infrastructure knowledge accessible to LLM-based assistants for troubleshooting, planning, and automation
3. **Discovers proactively** — Finding devices on the network before they are manually registered
4. **Maintains historical context** — Tracking infrastructure evolution with the ability to "time travel" through states
5. **Visualizes topology** — Rendering network and infrastructure relationships in intuitive graphical formats
6. **Documents organically** — Capturing and organizing infrastructure knowledge automatically with living documentation
7. **Enables controlled actions** — Taking action on infrastructure with appropriate safeguards through a composable command system
8. **Extends via integrations** — Connecting to the heterogeneous tools that homelabbers actually run (Proxmox, Docker, Home Assistant, Pi-hole, etc.)
9. **Understands semantically** — Going beyond keyword search to truly understand user intent when querying infrastructure knowledge

### 2.2 Existing Solutions & Gaps

| Solution | What It Does | What's Missing |
|---|---|---|
| **Prometheus/Grafana** | Real-time metrics and alerting | Focuses on "when" not "what"; no AI integration; no topology; no semantic search |
| **Ansible Facts** | Point-in-time system inventory | No persistence; no centralized querying; manual execution |
| **NetBox** | DCIM/IPAM documentation | Manual data entry; no automated profiling; no time machine; no AI |
| **Observium/LibreNMS** | Network monitoring and discovery | SNMP-centric; no compute profiling; no AI interface; no command execution |
| **Home Assistant** | IoT device management | IoT-only; no compute/network profiling; no topology |
| **Portainer** | Container management UI | Docker-only; no bare-metal; no network discovery; no historical state |
| **Homarr/Glance** | Dashboard aggregation | Scrapes external URLs; no unified data layer; no AI integration |

### 2.3 Hydra's Differentiation

Hydra addresses these gaps through:

- **Automated profiling** — Agents collect and push structured profiles without manual intervention
- **Service-centric model** — First-class service tracking separate from node profiles
- **Proactive discovery** — Network scanning finds devices before manual registration
- **Flexible grouping** — Selector-based logical partitioning for any organizational model
- **Network awareness** — Auto-discovery and mapping of network topology
- **Time Machine** — Navigate historical states at node and topology levels
- **AI-native design** — MCP interface provides structured tools for LLM interaction
- **Semantic search** — pgvector embeddings enable natural language infrastructure queries
- **Visual topology** — Interactive graph visualization of infrastructure relationships
- **Composable control** — Three-layer command system (Commands → Executions → Workflows) with safety guardrails
- **Plugin ecosystem** — 19 provider-scoped integrations extending every operational surface
- **Living documentation** — Auto-generated docs that stay current with infrastructure state
- **Customizable dashboards** — 75+ widget types with role-aware, multi-surface rendering
- **Dual-database intelligence** — MongoDB for document storage + PostgreSQL/pgvector for relational docs, semantic search, and audit

---

## 3. Requirements

### 3.1 Functional Requirements

#### FR-1: Node Management

| ID | Requirement | Priority |
|---|---|---|
| FR-1.1 | System SHALL support registration of new nodes with unique identifiers | P0 |
| FR-1.2 | System SHALL classify nodes as `compute`, `networking`, or `iot` types | P0 |
| FR-1.3 | System SHALL distinguish between `physical` and `logical` compute nodes | P0 |
| FR-1.4 | System SHALL support node deregistration and archival | P1 |
| FR-1.5 | System SHALL support node metadata updates without full re-profiling | P1 |
| FR-1.6 | System SHALL track parent-child relationships between nodes | P0 |

#### FR-2: Profile Collection

| ID | Requirement | Priority |
|---|---|---|
| FR-2.1 | Agent SHALL collect hardware specifications (CPU, RAM, storage, network, graphics) | P0 |
| FR-2.2 | Agent SHALL collect network interface configurations for all node classes | P0 |
| FR-2.3 | Agent SHALL collect installed software/package inventories | P1 |
| FR-2.4 | Agent SHALL collect user accounts and SSH keys | P1 |
| FR-2.5 | Agent SHALL collect configuration files with hash tracking | P1 |
| FR-2.6 | Agent SHALL support scheduled and event-triggered collection | P0 |
| FR-2.7 | Agent SHALL NOT collect real-time usage metrics (profiling, not monitoring) | P0 |
| FR-2.8 | Agent SHALL collect interface/port details for networking nodes | P0 |
| FR-2.9 | Agent SHALL collect device capabilities for IoT nodes | P0 |
| FR-2.10 | Agent SHALL support three profiling levels: shallow, neutral, deep | P1 |

#### FR-3: Service Management

| ID | Requirement | Priority |
|---|---|---|
| FR-3.1 | System SHALL track services as first-class entities separate from profiles | P0 |
| FR-3.2 | System SHALL capture service runtime, status, version, and exposure | P0 |
| FR-3.3 | System SHALL track service resource allocations when available | P1 |
| FR-3.4 | System SHALL maintain service discovery origin and timestamps | P0 |
| FR-3.5 | System SHALL support multiple runtime types (systemd, docker, kubernetes) | P0 |
| FR-3.6 | System SHALL support service control operations (start/stop/restart) | P1 |

#### FR-4: Group Management

| ID | Requirement | Priority |
|---|---|---|
| FR-4.1 | System SHALL support user-defined groups with flexible selectors | P0 |
| FR-4.2 | System SHALL support group membership by ID, network, status, kind, or tags | P0 |
| FR-4.3 | System SHALL support hierarchical groups via parent references | P1 |
| FR-4.4 | System SHALL support groups scoped to nodes, services, or both | P0 |
| FR-4.5 | System SHALL resolve group membership dynamically | P0 |

#### FR-5: Network Management

| ID | Requirement | Priority |
|---|---|---|
| FR-5.1 | System SHALL auto-create network definitions from node profile data | P0 |
| FR-5.2 | System SHALL support manual network definition creation | P0 |
| FR-5.3 | System SHALL track network CIDR, gateway, and subnet relationships | P0 |
| FR-5.4 | System SHALL associate network nodes (routers) with network definitions | P1 |
| FR-5.5 | System SHALL support VLAN and overlay network types | P1 |

#### FR-6: Topology Management

| ID | Requirement | Priority |
|---|---|---|
| FR-6.1 | System SHALL auto-generate network topology graphs | P0 |
| FR-6.2 | System SHALL auto-generate infrastructure topology graphs | P0 |
| FR-6.3 | System SHALL maintain historical topology snapshots for Time Machine | P0 |
| FR-6.4 | System SHALL support topology diff between snapshots | P1 |
| FR-6.5 | System SHALL trigger topology regeneration on profile changes | P0 |
| FR-6.6 | System SHALL accept topology edge contributions from plugins | P1 |

#### FR-7: AI Integration

| ID | Requirement | Priority |
|---|---|---|
| FR-7.1 | MCP service SHALL expose node, service, group, network listing tools | P0 |
| FR-7.2 | MCP service SHALL expose profile and topology retrieval tools | P0 |
| FR-7.3 | MCP service SHALL support capacity planning queries | P1 |
| FR-7.4 | MCP service SHALL support network topology queries | P0 |
| FR-7.5 | MCP service SHALL support Time Machine queries | P0 |
| FR-7.6 | MCP service SHALL format responses in TOON for LLM consumption | P0 |
| FR-7.7 | MCP service SHALL support semantic search via pgvector embeddings | P1 |
| FR-7.8 | MCP service SHALL enforce source-aware permissions (internal vs external clients) | P0 |

#### FR-8: Web Interface

| ID | Requirement | Priority |
|---|---|---|
| FR-8.1 | Web service SHALL visualize network and infrastructure topology | P0 |
| FR-8.2 | Web service SHALL provide Time Machine interface | P0 |
| FR-8.3 | Web service SHALL display node, service, network, and group details | P0 |
| FR-8.4 | Web service SHALL host MCP chat interface with full control permissions | P0 |
| FR-8.5 | Web service SHALL support customizable dashboard framework with 75+ widget types | P1 |
| FR-8.6 | Web service SHALL support IoT device controls | P2 |
| FR-8.7 | Web service SHALL provide Command Center with visual workflow builder | P1 |
| FR-8.8 | Web service SHALL host living documentation portal | P1 |
| FR-8.9 | Web service SHALL provide network discovery scan UI | P1 |
| FR-8.10 | Web service SHALL provide global search and command palette (Cmd+K) | P1 |

#### FR-9: Security & Access Control

| ID | Requirement | Priority |
|---|---|---|
| FR-9.1 | System SHALL implement role-based access control (RBAC) | P0 |
| FR-9.2 | System SHALL support built-in roles: admin, operator, viewer, family, agent | P0 |
| FR-9.3 | System SHALL support custom role definitions | P1 |
| FR-9.4 | System SHALL log all write operations to PostgreSQL audit log | P0 |
| FR-9.5 | System SHALL support API key authentication for automation | P1 |
| FR-9.6 | System SHALL enforce source restrictions for MCP clients (internal vs external) | P0 |
| FR-9.7 | System SHALL support per-command RBAC with confirmation for dangerous operations | P0 |

#### FR-10: Write Operations

| ID | Requirement | Priority |
|---|---|---|
| FR-10.1 | System SHALL define immutable system commands as verified building blocks | P0 |
| FR-10.2 | System SHALL support bound executions (command + target + parameters) | P0 |
| FR-10.3 | System SHALL support composable workflows (DAGs of building blocks) | P1 |
| FR-10.4 | System SHALL queue and track command execution with full lifecycle | P0 |
| FR-10.5 | System SHALL support OS-aware command translations per platform/runtime | P0 |

#### FR-11: Network Discovery

| ID | Requirement | Priority |
|---|---|---|
| FR-11.1 | System SHALL scan networks to discover unregistered devices | P0 |
| FR-11.2 | System SHALL fingerprint discovered devices (ports, protocols, banners) | P0 |
| FR-11.3 | System SHALL classify discovered devices by node class and kind | P0 |
| FR-11.4 | System SHALL assess agent compatibility and remote install eligibility | P1 |
| FR-11.5 | System SHALL delegate scanning to max-tier agents for unreachable networks | P1 |
| FR-11.6 | System SHALL track drift for registered IoT/networking nodes across scans | P1 |

#### FR-12: Agent Architecture

| ID | Requirement | Priority |
|---|---|---|
| FR-12.1 | Agent SHALL support three deployment tiers: lite, normal, max | P0 |
| FR-12.2 | Lite agent SHALL support profile collection and submission only | P0 |
| FR-12.3 | Normal agent SHALL add poll-based command execution | P0 |
| FR-12.4 | Max agent SHALL add HTTP server for synchronous execution and scanning | P1 |
| FR-12.5 | Agent SHALL enforce single-instance per machine | P0 |
| FR-12.6 | Agent SHALL support in-place tier upgrade without re-registration | P1 |

#### FR-13: Plugin System

| ID | Requirement | Priority |
|---|---|---|
| FR-13.1 | System SHALL support provider-scoped plugins with six integration touchpoints | P0 |
| FR-13.2 | Plugins SHALL support: Profile Enrichment, Discovery Provider, Command Provider, Execution Handler, Topology Provider, Workflow Block Provider | P0 |
| FR-13.3 | System SHALL ship with 6 Core and 13 Default integrations | P1 |
| FR-13.4 | Plugins SHALL have lifecycle: available → enabled → configured → active → error | P0 |
| FR-13.5 | Agent SHALL detect locally available integrations and report to API | P0 |

#### FR-14: Dashboard Framework

| ID | Requirement | Priority |
|---|---|---|
| FR-14.1 | System SHALL support multi-board dashboards per user | P0 |
| FR-14.2 | System SHALL provide 75+ widget types from core and plugin sources | P1 |
| FR-14.3 | System SHALL support grid-based layout with responsive breakpoints | P0 |
| FR-14.4 | System SHALL support pre-built templates and board sharing | P1 |
| FR-14.5 | System SHALL enforce role-based widget library filtering | P0 |

#### FR-15: Living Documentation

| ID | Requirement | Priority |
|---|---|---|
| FR-15.1 | System SHALL auto-generate infrastructure documentation from profiles and topology | P0 |
| FR-15.2 | System SHALL support hybrid authoring (auto-generated + manual sections) | P0 |
| FR-15.3 | System SHALL detect staleness when linked entities change | P0 |
| FR-15.4 | System SHALL store documentation in PostgreSQL with full-text and vector search | P0 |
| FR-15.5 | System SHALL expose documentation as MCP knowledge base | P1 |

#### FR-16: Semantic Search

| ID | Requirement | Priority |
|---|---|---|
| FR-16.1 | System SHALL embed documentation, profile summaries, and service descriptions | P0 |
| FR-16.2 | System SHALL support configurable embedding providers (OpenAI, Ollama, Anthropic) | P0 |
| FR-16.3 | System SHALL provide combined keyword + semantic search via PostgreSQL | P0 |
| FR-16.4 | System SHALL maintain embedding freshness via content hashing | P0 |

### 3.2 Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Performance** | API response time < 300ms for single-entity queries |
| **Performance** | Topology generation < 2s per 100 nodes |
| **Performance** | Semantic search < 500ms including embedding generation |
| **Scalability** | Support up to 500 nodes, 2000 services without architecture changes |
| **Availability** | API service uptime > 99% (non-HA deployment) |
| **Security** | All inter-service communication over TLS; JWT-based auth |
| **Portability** | Agent must run on x86_64 & ARM64 - Linux, macOS, BSD, Windows |
| **Observability** | Structured logging (JSON) with correlation IDs |
| **Resilience** | Graceful degradation when dependencies unavailable |
| **Data Integrity** | PostgreSQL for ACID-critical data (audit, docs); MongoDB for flexible schemas |

### 3.3 Constraints

- Agent must be deployable as a single static binary (no runtime dependencies)
- MongoDB is the primary database for infrastructure data (existing infrastructure)
- PostgreSQL with pgvector is required for documentation, semantic search, and audit
- MCP protocol compatibility with Claude and other MCP-compatible clients
- No persistent connection requirements between agent and API (stateless HTTP)
- Web service must support modern browsers (Chrome, Firefox, Safari, Edge)
- No secrets stored in profiles (hashes only for sensitive configs)
- Embedding model provider must be configurable (OpenAI, Ollama, Anthropic)

---

## 4. System Architecture

### 4.1 High-Level Architecture

```mermaid
graph TB
    subgraph UI["🖥️ User Interfaces"]
        WebApp["Web App (React/TS)<br/>• Dashboards<br/>• Cmd Center<br/>• Doc Portal<br/>• Discovery"]
        MobileApp["Mobile App (React Native)<br/>• Monitoring<br/>• IoT Ctrl<br/>• Notifications<br/>• Chat"]
        LLM["Claude/LLM (MCP Client)<br/>• Internal (Web Chat)<br/>• External (Desktop)"]
        CLI["CLI / Scripts<br/>• Profile<br/>• Execute<br/>• Report"]
    end

    subgraph SVC["⚙️ Service Layer"]
        API["hydra-api (Python/FastAPI)<br/>• Authentication & RBAC<br/>• Node/Profile CRUD<br/>• Service Management<br/>• Network Discovery Scanner<br/>• Topology Generation<br/>• Time Machine<br/>• Command Execution Engine<br/>• Workflow Orchestrator<br/>• Plugin Registry & Drivers<br/>• Dashboard/Board CRUD<br/>• Doc Generation Pipeline<br/>• Embedding Pipeline<br/>• Notification System<br/>• Audit Logging (→ PostgreSQL)"]
        MCP["hydra-mcp (Python/MCP SDK)<br/>• MCP Server Implementation<br/>• AI Tools & Resources<br/>• TOON Formatting<br/>• Prompts Library<br/>• API Client Wrapper<br/>• Semantic Search Client<br/>• Source-Aware Permissions"]
    end

    subgraph DATA["💾 Data Layer"]
        Mongo["MongoDB (~35 collections)<br/><br/>Core: nodes · profiles · profile_meta · services · groups<br/>networks · topologies<br/><br/>Ops: executions · workflows · workflow_runs<br/>discovered_nodes · discovery_scans · discovery_exclusions<br/><br/>Content: boards · board_templates · chat_sessions<br/>chat_messages · chat_projects · notifications · notification_reads<br/><br/>System: users · users_pending · tokens · api_keys<br/>password_reset_tokens · integrations · integration_configs<br/>mcp_servers · mcp_clients · ai_models · global_api_keys<br/>known_services · user_settings · system_settings"]
        PG["PostgreSQL + pgvector (7 tables)<br/><br/>Search: embeddings · search_index<br/>Docs: documents · document_sections<br/>document_entity_links · document_versions<br/>Audit: audit_log (time-partitioned)"]
        Redis["Redis<br/><br/>Execution queue<br/>Caching<br/>Pub/Sub<br/>WebSocket"]
    end

    subgraph INFRA["🏗️ Infrastructure Layer"]
        Agent1["hydra-agent (Rust, tiered)<br/>lite | normal<br/>Compute Node"]
        Agent2["hydra-agent (Rust, tiered)<br/>max<br/>Hypervisor"]
        Agent3["hydra-agent (Rust, tiered)<br/>lite | normal<br/>IoT (via HA)"]
        AgentN["..."]
        HA["Home Assistant<br/>(IoT Device Source - REST API Integration via Plugin)"]
    end

    WebApp --> API
    MobileApp --> API
    LLM --> MCP
    CLI --> API

    MCP --> API

    API --> Mongo
    API --> PG
    API --> Redis

    API --> Agent1
    API --> Agent2
    API --> Agent3

    Agent3 --> HA

    style UI fill:#E8F4FD,stroke:#2196F3,color:#000
    style SVC fill:#FFF3E0,stroke:#FF9800,color:#000
    style DATA fill:#E8F5E9,stroke:#4CAF50,color:#000
    style INFRA fill:#FCE4EC,stroke:#E91E63,color:#000
```

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
│   │  │              │  │              │  │              │  │                      │ │  │
│   │  │ • Dashboards │  │ • Monitoring │  │ • Internal   │  │ • Profile            │ │  │
│   │  │ • Cmd Center │  │ • IoT Ctrl   │  │   (Web Chat) │  │ • Execute            │ │  │
│   │  │ • Doc Portal │  │ • Notif.     │  │ • External   │  │ • Report             │ │  │
│   │  │ • Discovery  │  │ • Chat       │  │   (Desktop)  │  │                      │ │  │
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
│   │  │  • Network Discovery Scanner           │  │  • Prompts Library             │  │  │
│   │  │  • Topology Generation                 │  │  • API Client Wrapper          │  │  │
│   │  │  • Time Machine                        │  │  • Semantic Search Client      │  │  │
│   │  │  • Command Execution Engine            │  │  • Source-Aware Permissions    │  │  │
│   │  │  • Workflow Orchestrator               │  │                                │  │  │
│   │  │  • Plugin Registry & Drivers           │  │                                │  │  │
│   │  │  • Dashboard/Board CRUD                │  │                                │  │  │
│   │  │  • Doc Generation Pipeline             │  │                                │  │  │
│   │  │  • Embedding Pipeline                  │  │                                │  │  │
│   │  │  • Notification System                 │  │                                │  │  │
│   │  │  • Audit Logging (→ PostgreSQL)        │  │                                │  │  │
│   │  └────────────────────┬───────────────────┘  └────────────────┬───────────────┘  │  │
│   └───────────────────────┼──────────────────────────────────────┼───────────────────┘  │
│                           │                                      │                      │
│                           ▼                                      │                      │
│   ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│   │                              DATA LAYER                                           │  │
│   │                                                                                   │  │
│   │  ┌────────────────────────────────────────────────────────────────────────────┐  │  │
│   │  │                     MongoDB (~35 collections)                               │  │  │
│   │  │                                                                              │  │  │
│   │  │  Core:  nodes · profiles · profile_meta · services · groups                 │  │  │
│   │  │         networks · topologies                                                │  │  │
│   │  │                                                                              │  │  │
│   │  │  Ops:   executions · workflows · workflow_runs                               │  │  │
│   │  │         discovered_nodes · discovery_scans · discovery_exclusions            │  │  │
│   │  │                                                                              │  │  │
│   │  │  Content: boards · board_templates · chat_sessions · chat_messages           │  │  │
│   │  │           chat_projects · notifications · notification_reads                 │  │  │
│   │  │                                                                              │  │  │
│   │  │  System: users · users_pending · tokens · api_keys · password_reset_tokens  │  │  │
│   │  │          integrations · integration_configs · mcp_servers · mcp_clients      │  │  │
│   │  │          ai_models · global_api_keys · known_services                        │  │  │
│   │  │          user_settings · system_settings                                     │  │  │
│   │  └────────────────────────────────────────────────────────────────────────────┘  │  │
│   │                                                                                   │  │
│   │  ┌────────────────────────────────────────────────────────────────────────────┐  │  │
│   │  │                PostgreSQL + pgvector (7 tables)                              │  │  │
│   │  │                                                                              │  │  │
│   │  │  Search:  embeddings · search_index                                         │  │  │
│   │  │  Docs:    documents · document_sections · document_entity_links             │  │  │
│   │  │           document_versions                                                  │  │  │
│   │  │  Audit:   audit_log (time-partitioned)                                      │  │  │
│   │  └────────────────────────────────────────────────────────────────────────────┘  │  │
│   │                                                                                   │  │
│   │  ┌─────────────────────────┐                                                     │  │
│   │  │         Redis           │  (Execution queue, caching, pub/sub, WebSocket)     │  │
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
│   │  │  (Rust, tiered)  │  │  (Rust, tiered)  │  │  (Rust, tiered)  │               │  │
│   │  │                  │  │                  │  │                  │               │  │
│   │  │  lite | normal   │  │      max         │  │  lite | normal   │               │  │
│   │  │  Compute Node    │  │  Hypervisor      │  │  IoT (via HA)    │               │  │
│   │  └──────────────────┘  └──────────────────┘  └──────────────────┘               │  │
│   │                                                                                   │  │
│   │  ┌──────────────────────────────────────────────────────────────────────────┐   │  │
│   │  │                        Home Assistant                                      │   │  │
│   │  │  (IoT Device Source - REST API Integration via Plugin)                    │   │  │
│   │  └──────────────────────────────────────────────────────────────────────────┘   │  │
│   └──────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Component Responsibilities

| Component | Responsibility | Technology |
|---|---|---|
| **hydra-agent** | Data collection, profile assembly, command execution, integration detection | Rust 1.75+ (tiered: lite/normal/max) |
| **hydra-api** | Central authority: CRUD, topology, discovery, execution engine, plugin registry, doc generation, embedding pipeline | Python 3.11+ / FastAPI |
| **hydra-mcp** | AI interface: MCP tools, resources, prompts, TOON formatting, semantic search | Python 3.11+ / MCP SDK |
| **hydra-web** | User interface: dashboards, command center, doc portal, topology, discovery UI | React 18 / TypeScript / Vite |
| **MongoDB** | Primary datastore for infrastructure entities, operations, UI content, system config | MongoDB 7.x |
| **PostgreSQL** | Relational docs, semantic search (pgvector), full-text search, audit log | PostgreSQL 16 + pgvector |
| **Redis** | Execution queue, caching, pub/sub, WebSocket session state, rate limiting | Redis 7.x |

### 4.3 Design Principles

**API as Central Authority**
The Hydra API is the authoritative orchestrator. It manages its own network posture, coordinates all operations, and maintains the single source of truth for infrastructure state.

**Explicit Over Implicit**
All operations must be explicitly requested. No scheduled scans, no automatic actions without user initiation. Users maintain full control over when Hydra takes action.

**Security by Default**
Command execution is restricted to registered commands only. External MCP clients are read-only for direct executions. Network access is allowlisted per node. Credentials are never stored in plain text.

**Graceful Degradation**
When optimal execution paths are unavailable (agent unreachable, integration down, PostgreSQL offline), the system falls back to alternative methods rather than failing. Users are always informed of the degraded state. MongoDB services continue independently of PostgreSQL availability.

**Integration-Aware Architecture**
All four Hydra components (API, Agent, Web, MCP) are designed with integration awareness from the ground up. Integrations enhance but never replace core functionality.

**Right Database for the Job**
MongoDB stores variable-schema infrastructure data (profiles, topologies, commands). PostgreSQL stores relational data that benefits from joins, full-text search, vector similarity, and ACID guarantees (documentation, audit logs, search indexes, embeddings). Redis handles ephemeral operational state (queues, caches, pub/sub).

### 4.4 Data Flow Diagrams

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                    DATA FLOWS                                            │
│                                                                                          │
│  1. PROFILE SUBMISSION FLOW                                                              │
│  ═════════════════════════                                                               │
│  ┌─────────┐      ┌─────────┐      ┌───────────────────────────────────────────────────┐│
│  │  Agent  │─────▶│   API   │─────▶│  a) Validate profile payload                      ││
│  │profiles │ POST │receives │      │  b) Compute section hashes (profile_meta)          ││
│  │  node   │      │ payload │      │  c) Compare profileHash → skip if identical        ││
│  └─────────┘      └─────────┘      │  d) Calculate hex version increment                ││
│                                    │  e) Store profile + meta in MongoDB                ││
│                                    │  f) Extract/upsert services                        ││
│                                    │  g) Update node.lastProfileAt                      ││
│                                    │  h) Trigger topology regeneration                   ││
│                                    │  i) Queue embedding generation (→ PostgreSQL)       ││
│                                    │  j) Check doc staleness (→ PostgreSQL)              ││
│                                    │  k) Log audit entry (→ PostgreSQL)                  ││
│                                    └───────────────────────────────────────────────────┘│
│                                                                                          │
│  2. TOPOLOGY GENERATION FLOW                                                             │
│  ════════════════════════════                                                            │
│  ┌─────────┐      ┌─────────┐      ┌───────────────────────────────────────────────────┐│
│  │Trigger: │─────▶│   API   │─────▶│  a) Load all active nodes from MongoDB             ││
│  │profile  │      │generates│      │  b) Load latest profiles for each node             ││
│  │submitted│      │topology │      │  c) Query enabled plugins for topology edges       ││
│  └─────────┘      └─────────┘      │  d) Build graph nodes (nodes, services, networks)  ││
│                                    │  e) Build graph edges (network, parent, service)   ││
│                                    │  f) Compute layout positions                        ││
│                                    │  g) Calculate diff from previous topology           ││
│                                    │  h) Store topology snapshot in MongoDB              ││
│                                    │  i) Mark previous topology validUntil               ││
│                                    └───────────────────────────────────────────────────┘│
│                                                                                          │
│  3. COMMAND EXECUTION FLOW                                                               │
│  ═════════════════════════                                                               │
│  ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌───────────────┐│
│  │User/MCP │─────▶│   API   │─────▶│  Redis  │─────▶│  Agent  │─────▶│ Target System ││
│  │ request │ POST │validates│ QUEUE│  Queue  │ POLL │executes │      │(systemd, etc) ││
│  │execution│      │& queues │      │(normal) │ or   │ command │      │               ││
│  └─────────┘      └─────────┘      └─────────┘ DIRECT└─────────┘      └───────────────┘│
│       ▲                │                         (max) │                                 │
│       │                │                               │                                 │
│       └────────────────┼───────────────────────────────┘                                │
│                        │        Result returned                                          │
│                        ▼                                                                 │
│                   ┌─────────┐                                                            │
│                   │PostgreSQL│  Audit log entry written                                  │
│                   └─────────┘                                                            │
│                                                                                          │
│  4. SEMANTIC SEARCH FLOW                                                                 │
│  ═══════════════════════                                                                │
│  ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌───────────────────────────────┐  │
│  │ MCP/Web │─────▶│hydra-mcp│─────▶│hydra-api│─────▶│ PostgreSQL:                   │  │
│  │ query:  │      │ embeds  │      │ queries │      │  1. Embed query via provider  │  │
│  │"capacity│      │ query   │      │ pgvector│      │  2. Vector similarity search  │  │
│  │ for ML" │      │ text    │      │         │      │  3. Combine with FTS ranking  │  │
│  └─────────┘      └─────────┘      └─────────┘      │  4. Return ranked results     │  │
│                                                       └───────────────────────────────┘  │
│                                                                                          │
│  5. DOCUMENT AUTO-GENERATION FLOW                                                        │
│  ════════════════════════════════                                                        │
│  ┌─────────┐      ┌─────────┐      ┌───────────────────────────────────────────────────┐│
│  │Trigger: │─────▶│   API   │─────▶│  a) Resolve template for doc type                  ││
│  │profile  │      │doc gen  │      │  b) Gather data from MongoDB (profiles, topology)  ││
│  │change   │      │pipeline │      │  c) Gather plugin contributions                    ││
│  └─────────┘      └─────────┘      │  d) Render template sections into markdown         ││
│                                    │  e) Preserve manual override sections               ││
│                                    │  f) Store doc + sections in PostgreSQL              ││
│                                    │  g) Update entity links in PostgreSQL               ││
│                                    │  h) Queue embedding generation for new content      ││
│                                    │  i) Update search_index in PostgreSQL               ││
│                                    └───────────────────────────────────────────────────┘│
│                                                                                          │
│  6. NETWORK DISCOVERY FLOW                                                               │
│  ═════════════════════════                                                               │
│  ┌─────────┐      ┌─────────┐      ┌───────────────────────────────────────────────────┐│
│  │User/MCP │─────▶│   API   │─────▶│  a) Determine network scannability                 ││
│  │triggers │ POST │ scanner │      │  b) API-direct or delegate to max-tier agent       ││
│  │  scan   │      │         │      │  c) ARP scan → host discovery                      ││
│  └─────────┘      └─────────┘      │  d) Port scan → service fingerprinting             ││
│                                    │  e) Protocol probes (mDNS, SSDP, SNMP)             ││
│                                    │  f) Classify devices by type/kind                   ││
│                                    │  g) Assess agent compatibility & install eligibility││
│                                    │  h) Store discoveries in MongoDB                    ││
│                                    │  i) Stream results via WebSocket (API-direct)       ││
│                                    └───────────────────────────────────────────────────┘│
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.5 Component Responsibility Matrix

| Feature | hydra-api | hydra-agent | hydra-web | hydra-mcp |
|---|---|---|---|---|
| Node/Profile CRUD | Storage, validation, versioning | Collection, submission | Detail views, lists | Query tools |
| Service Management | CRUD, discovery coordination | Detection, reporting | Service views, controls | Service tools |
| Network Discovery | Scanner, storage, orchestration | Delegated scanning (max) | Scan UI, results | Discovery tools |
| Agent Architecture | Client to agent servers (max) | HTTP server (max), poll (normal+max) | Agent status display | Agent control tools |
| Commands & Executions | Command catalog, execution dispatch | Execute via poll or direct | Command Center | Control tools |
| Workflows | Orchestrator, run tracking | Execute individual steps | Visual Workflow Builder | Workflow invocation |
| Controls & Safety | RBAC, rate limiting, confirmation | Execute registered commands | Confirmation dialogs | Read-only (external) |
| Remote Installation | SSH execution, coordination | N/A (target has no agent) | Install wizard | Install tools |
| Plugin System | Driver management, routing | Integration detection/proxy | Plugin config UI | Integration tools |
| Dashboard Framework | Board CRUD, data resolution | N/A | Editor, widget rendering | Board creation tools |
| Living Documentation | Template engine, generation pipeline | N/A (indirect via profiles) | Portal, editor | Doc tools, knowledge base |
| Semantic Search | Embedding pipeline, pgvector queries | N/A | Global search UI | Semantic query tools |
| Topology Generation | Graph construction, snapshot storage | N/A | Visualization | Topology tools |
| Time Machine | State reconstruction | N/A | Timeline UI, compare mode | Time Machine tools |
| Audit Logging | Write to PostgreSQL | N/A | Audit log viewer | N/A |
| Notifications | Event processing, dispatch | N/A | Toast/drawer UI | N/A |

---

## 5. Technical Implementation

### 5.1 Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Agent** | Rust 1.75+ | Performance, single binary, safe concurrency, cross-platform |
| **API** | Python 3.11+ / FastAPI | Rapid development, async support, OpenAPI generation |
| **MCP Service** | Python 3.11+ / MCP SDK | MCP SDK availability, API integration |
| **Web Service** | React 18 / TypeScript / Vite | Component model, type safety, ecosystem |
| **Mobile** | React Native | Shared codebase for iOS/Android |
| **Visualization** | ReactFlow / D3.js | Flexible graph rendering, interactivity |
| **Primary DB** | MongoDB 7.x | Document model fits variable-schema profile data; existing infra |
| **Relational DB** | PostgreSQL 16 + pgvector | Relational docs, vector search, FTS, ACID audit log |
| **Queue/Cache** | Redis 7.x | Execution queue, caching, pub/sub, WebSocket state |
| **Authentication** | JWT (HS256) | Stateless, widely supported |
| **Embedding** | Configurable (OpenAI / Ollama / Anthropic) | Provider flexibility for self-hosted and cloud deployments |
| **DB Migrations** | Alembic (PostgreSQL) | Schema versioning for relational tables |
| **MongoDB ODM** | Motor (async) | Non-blocking MongoDB access |
| **PostgreSQL Driver** | asyncpg | High-performance async PostgreSQL access |

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
# Stored in profile_meta collection (MongoDB)
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

### 5.4 Embedding Provider Abstraction

The embedding pipeline supports multiple providers through a common interface:

```python
class EmbeddingProvider(ABC):
    """Abstract base for embedding providers."""
    
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        ...
    
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        ...

class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI text-embedding-ada-002 or text-embedding-3-small."""
    model: str = "text-embedding-3-small"
    dimension: int = 1536

class OllamaEmbeddingProvider(EmbeddingProvider):
    """Local Ollama instance (e.g., nomic-embed-text, mxbai-embed-large)."""
    model: str = "nomic-embed-text"
    base_url: str = "http://localhost:11434"
    dimension: int = 768

class AnthropicEmbeddingProvider(EmbeddingProvider):
    """Anthropic Voyage embeddings (voyage-3, voyage-code-3)."""
    model: str = "voyage-3"
    dimension: int = 1024
```

Configuration is stored in `system_settings` (MongoDB) and referenced by the embedding pipeline:

```json
{
  "embedding": {
    "provider": "ollama",
    "model": "nomic-embed-text",
    "baseUrl": "http://ollama:11434",
    "dimension": 768,
    "batchSize": 32,
    "maxRetries": 3
  }
}
```

The `embeddings` table in PostgreSQL uses `vector(N)` where N matches the configured provider's dimension. Changing providers requires re-embedding all content (a background migration job).

---

## 6. Data Layer Architecture

### 6.1 Dual-Database Rationale

Hydra uses a purpose-specific split between MongoDB and PostgreSQL rather than forcing all data into a single engine. The split is driven by access patterns, schema variability, and capability requirements:

| Criterion | MongoDB | PostgreSQL |
|---|---|---|
| **Schema variability** | High — profiles, commands, widgets have deeply nested, variable structures per type | Low — documents, audit logs, search indexes have stable relational schemas |
| **Query patterns** | Document lookups, nested field queries, append-only histories | Joins (entity links → docs), full-text search, vector similarity, time-range aggregations |
| **ACID requirements** | Eventual consistency acceptable for profiles and topologies | ACID required for audit log integrity and document versioning |
| **Search capabilities** | Basic text index (keyword matching) | `tsvector` full-text search with ranking + `pgvector` semantic similarity |
| **Analytical queries** | Poor — no window functions, no partitioning | Excellent — partitioned audit tables, aggregation functions, GROUP BY |

**Practical consequence:** If PostgreSQL goes down, Hydra's core profiling, topology, command execution, and dashboard features continue working (MongoDB-backed). Only documentation portal, semantic search, global search, and audit log viewing degrade. Conversely, MongoDB outage affects all infrastructure operations but PostgreSQL-backed docs remain readable.

### 6.2 Domain-to-Database Mapping

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       DATA DOMAIN MAPPING                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  MONGODB (Primary — ~35 collections)                                        │
│  ════════════════════════════════════                                       │
│                                                                             │
│  Infrastructure Core          Operations              Content & UI         │
│  ─────────────────           ──────────              ──────────────        │
│  nodes                       executions              boards               │
│  profiles                    workflows               board_templates      │
│  profile_meta                workflow_runs            chat_projects        │
│  services                    discovered_nodes         chat_sessions        │
│  groups                      discovery_scans          chat_messages        │
│  networks                    discovery_exclusions     notifications        │
│  topologies                                           notification_reads   │
│                                                                             │
│  System & Auth               Plugins & AI                                  │
│  ──────────────              ────────────                                  │
│  users                       integrations                                  │
│  users_pending               integration_configs                           │
│  tokens                      ai_models                                     │
│  api_keys                    global_api_keys                                │
│  password_reset_tokens       mcp_servers                                   │
│  known_services              mcp_clients                                   │
│  user_settings                                                              │
│  system_settings                                                            │
│                                                                             │
│  POSTGRESQL + pgvector (Intelligence — 7 tables)                           │
│  ═══════════════════════════════════════════════                            │
│                                                                             │
│  Search & Intelligence       Documentation            Compliance           │
│  ────────────────────       ─────────────             ──────────           │
│  embeddings                  documents                audit_log            │
│  search_index                document_sections        (time-partitioned)   │
│                              document_entity_links                          │
│                              document_versions                              │
│                                                                             │
│  REDIS (Ephemeral — operational state)                                     │
│  ═════════════════════════════════════                                      │
│  execution_queue · command_polling · cache · pub/sub · websocket_state     │
│  rate_limit_counters · session_cache                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Connection Management

The API maintains separate connection pools for each database:

```python
# hydra-api startup
from motor.motor_asyncio import AsyncIOMotorClient
import asyncpg
import redis.asyncio as aioredis

class DatabaseManager:
    """Manages connections to all three data stores."""
    
    def __init__(self, config: AppConfig):
        # MongoDB — primary infrastructure data
        self.mongo = AsyncIOMotorClient(config.mongodb_uri)
        self.mongo_db = self.mongo[config.mongodb_database]
        
        # PostgreSQL — docs, search, audit
        self.pg_pool: asyncpg.Pool = None  # initialized async
        
        # Redis — queue, cache, pub/sub
        self.redis = aioredis.from_url(config.redis_url)
    
    async def connect(self):
        self.pg_pool = await asyncpg.create_pool(
            dsn=self.config.postgresql_dsn,
            min_size=5,
            max_size=20,
            command_timeout=30
        )
    
    async def health_check(self) -> dict:
        """Returns health status per database."""
        return {
            "mongodb": await self._check_mongo(),      # Core — critical
            "postgresql": await self._check_pg(),       # Intelligence — degraded mode ok
            "redis": await self._check_redis()          # Operations — degraded mode ok
        }
```

### 6.4 Migration Strategy

| Database | Migration Tool | Approach |
|---|---|---|
| MongoDB | Application-level | Schema changes handled by the API at startup (create indexes, seed commands). No formal migration tool — MongoDB's schemaless nature handles evolution. |
| PostgreSQL | Alembic | Versioned migrations in `hydra-api/migrations/`. Run automatically on API startup. Supports rollback. |
| Redis | None needed | Ephemeral data — no schema to migrate. Key namespaces documented in code. |

---

## 7. MongoDB Data Models

### 7.1 Collection: `nodes`

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
    "agent": {
      "type": ["object", "null"],
      "description": "Agent deployment and connectivity details",
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
          "enum": ["linux-x86_64", "linux-arm64", "linux-armv7", "freebsd-x86_64", "macos-arm64", "windows-x86_64"]
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
          "description": "Derived from tier: lite=[profile], normal=[profile, poll-execute, update], max=[all]"
        },
        "detectedIntegrations": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "pluginId": { "type": "string" },
              "available": { "type": "boolean" },
              "version": { "type": ["string", "null"] },
              "detectedAt": { "type": "string", "format": "date-time" }
            }
          },
          "description": "Integrations the agent detected locally (e.g., Docker socket, Proxmox API)"
        },
        "status": {
          "type": "string",
          "enum": ["online", "degraded", "offline", "unknown"]
        },
        "lastSeen": { "type": "string", "format": "date-time" }
      }
    },
    "registeredBy": {
      "type": ["string", "null"],
      "description": "User ID of the user who registered this node"
    },
    "fromDiscovery": {
      "type": ["string", "null"],
      "description": "Discovery ID if registered from network discovery"
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
  { key: { "agent.tier": 1, "agent.status": 1 } },
  { key: { "displayName": "text", "description": "text" } }
])
```

### 7.2 Collection: `profiles`

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
    "agentTier": { "type": "string", "enum": ["lite", "normal", "max"] },
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
    "pluginData": {
      "type": "object",
      "description": "Plugin-enriched data keyed by pluginId (e.g., 'plg::docker': {...})",
      "additionalProperties": { "type": "object" }
    },
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

### 7.3 Collection: `profile_meta`

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

### 7.4 Collection: `services`

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
      "pattern": "^svc-[a-z0-9-_]+-[a-zA-Z0-9]{4}$",
      "description": "Format: svc-<sanitized_name>-<4 char hash>",
      "examples": ["svc-mongodb-a1b2", "svc-nginx-c3d4"]
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
        "discoveredBy": { "type": "string", "enum": ["agent", "api", "manual", "plugin"] },
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

### 7.5 Collection: `groups`

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
    "groupId": { "type": "string", "pattern": "^[a-z0-9][a-z0-9-]{2,63}$" },
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
        "id": { "type": "object", "properties": { "isAll": { "type": "array", "items": { "type": "string" } } } },
        "network": { "type": "object", "properties": { "isAny": { "type": "array", "items": { "type": "string" } } } },
        "status": { "type": "object", "properties": { "isAny": { "type": "array", "items": { "type": "string" } } } },
        "kind": { "type": "object", "properties": { "isAny": { "type": "array", "items": { "type": "string" } } } },
        "tags": {
          "type": "object",
          "properties": {
            "isAny": { "type": "array", "items": { "type": "string" } },
            "isAll": { "type": "array", "items": { "type": "string" } }
          }
        },
        "runtime": { "type": "object", "properties": { "isAny": { "type": "array", "items": { "type": "string" } } } },
        "location": { "type": "object", "properties": { "site": { "type": "string" }, "rack": { "type": "string" } } }
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
     - kind.isAny: node kind must match at least one
     - tags.isAny: entity must have at least one matching tag
     - tags.isAll: entity must have ALL listed tags
     - runtime.isAny: (services only) runtime must match
     - location: site AND rack must match if specified
  3. Entity is member if ANY selector rule matches (OR logic)
```

### 7.6 Collection: `networks`

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
    "networkId": { "type": "string", "pattern": "^[a-z0-9][a-z0-9-]*(-net)?$" },
    "type": { "type": "string", "enum": ["physical", "virtual", "overlay", "vlan", "vxlan", "bridge", "tunnel"] },
    "name": { "type": "string", "maxLength": 128 },
    "description": { "type": "string", "maxLength": 1024 },
    "cidr": { "type": ["string", "null"], "pattern": "^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$" },
    "cidrV6": { "type": ["string", "null"] },
    "gatewayV4": { "type": ["string", "null"] },
    "gatewayV6": { "type": ["string", "null"] },
    "vlanId": { "type": ["integer", "null"], "minimum": 1, "maximum": 4094 },
    "subnetIds": { "type": "array", "items": { "type": "string" } },
    "parentNetworkId": { "type": ["string", "null"] },
    "routerNodeId": { "type": ["string", "null"] },
    "scannability": {
      "type": "object",
      "description": "How the API can reach this network for discovery scanning",
      "properties": {
        "status": { "type": "string", "enum": ["api-direct", "api-routed", "agent-only", "unreachable"] },
        "scannerNodeId": { "type": ["string", "null"], "description": "Max-tier agent that can scan this network" },
        "lastAssessedAt": { "type": "string", "format": "date-time" }
      }
    },
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

### 7.7 Collection: `topologies`

**Purpose:** Store auto-generated topology snapshots (see Section 13 for generation logic).

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:topologies",
  "title": "Topology",
  "type": "object",
  "required": ["topologyId", "mode", "version", "generatedAt", "graph"],
  "properties": {
    "_id": { "type": "string" },
    "topologyId": { "type": "string", "pattern": "^topo-[a-z]+-[0-9]{8}T[0-9]{6}Z$" },
    "mode": { "type": "string", "enum": ["network", "infrastructure", "service"] },
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
              "type": { "type": "string", "enum": ["compute-physical", "compute-logical", "networking", "iot", "service", "network", "group"] },
              "label": { "type": "string" },
              "data": { "type": "object" },
              "position": {
                "type": "object",
                "properties": { "x": { "type": "number" }, "y": { "type": "number" }, "layer": { "type": "integer" } }
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
              "type": { "type": "string", "enum": ["network-connection", "parent-child", "service-host", "service-dependency", "network-gateway", "vlan-trunk", "group-member", "plugin-relationship"] },
              "data": { "type": "object" },
              "pluginSource": { "type": ["string", "null"], "description": "Plugin ID that contributed this edge" }
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
        "pluginEdgeCount": { "type": "integer" },
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

### 7.8 Collection: `discovered_nodes`

**Purpose:** Store devices found via network discovery scanning, before or after registration.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:discovered_nodes",
  "title": "DiscoveredNode",
  "type": "object",
  "required": ["discoveryId", "identity", "networkId", "status"],
  "properties": {
    "_id": { "type": "string" },
    "discoveryId": {
      "type": "string",
      "pattern": "^disc::mac::[a-f0-9-]+$",
      "description": "MAC-based stable identifier",
      "examples": ["disc::mac::dc-a6-32-ab-cd-ef"]
    },
    "identity": {
      "type": "object",
      "required": ["primaryMac"],
      "properties": {
        "primaryMac": { "type": "string" },
        "macVendor": { "type": ["string", "null"] },
        "currentIp": { "type": "string" },
        "hostname": { "type": ["string", "null"] },
        "mdnsName": { "type": ["string", "null"] }
      }
    },
    "networkId": { "type": "string" },
    "fingerprint": {
      "type": "object",
      "properties": {
        "openPorts": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "port": { "type": "integer" },
              "protocol": { "type": "string" },
              "state": { "type": "string" },
              "service": { "type": ["string", "null"] },
              "banner": { "type": ["string", "null"] },
              "version": { "type": ["string", "null"] }
            }
          }
        },
        "protocols": {
          "type": "object",
          "properties": {
            "mdns": { "type": "object" },
            "ssdp": { "type": "object" },
            "snmp": { "type": "object" },
            "http": { "type": "object" }
          }
        },
        "osHints": { "type": "array", "items": { "type": "string" } },
        "ttl": { "type": ["integer", "null"] }
      }
    },
    "classification": {
      "type": "object",
      "properties": {
        "suggestedClass": { "type": "string", "enum": ["compute", "networking", "iot", "unknown"] },
        "suggestedType": { "type": "string", "enum": ["physical", "logical", "unknown"] },
        "suggestedKind": { "type": ["string", "null"] },
        "suggestedDisplayName": { "type": ["string", "null"] },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
        "signals": { "type": "array", "items": { "type": "string" } }
      }
    },
    "eligibility": {
      "type": "object",
      "properties": {
        "registerable": { "type": "boolean" },
        "agentCompatible": { "type": "boolean" },
        "agentPlatform": { "type": ["string", "null"] },
        "remoteInstallable": { "type": "boolean" },
        "remoteInstallMethod": { "type": ["string", "null"], "enum": ["ssh", "proxmox-exec", null] },
        "blockers": { "type": "array", "items": { "type": "string" } }
      }
    },
    "status": {
      "type": "string",
      "enum": ["pending", "registered", "dismissed"]
    },
    "matchedNodeId": { "type": ["string", "null"], "description": "Set when device is registered as a Hydra node" },
    "dismissedReason": { "type": ["string", "null"] },
    "permanent": { "type": "boolean", "default": false },
    "firstSeen": { "type": "string", "format": "date-time" },
    "lastSeen": { "type": "string", "format": "date-time" },
    "seenCount": { "type": "integer" },
    "lastScanId": { "type": "string" }
  }
}
```

**Indexes:**

```javascript
db.discovered_nodes.createIndexes([
  { key: { "discoveryId": 1 }, unique: true },
  { key: { "networkId": 1, "status": 1 } },
  { key: { "identity.primaryMac": 1 } },
  { key: { "identity.currentIp": 1 } },
  { key: { "matchedNodeId": 1 } },
  { key: { "classification.suggestedClass": 1, "classification.confidence": -1 } },
  { key: { "lastSeen": -1 } }
])
```

### 7.9 Collection: `discovery_scans`

**Purpose:** Store scan execution history.

```json
{
  "$id": "hydra:discovery_scans",
  "type": "object",
  "properties": {
    "scanId": { "type": "string", "pattern": "^scan_[a-z0-9]+$" },
    "networkIds": { "type": "array", "items": { "type": "string" } },
    "status": { "type": "string", "enum": ["running", "completed", "failed", "cancelled"] },
    "method": { "type": "string", "enum": ["api-direct", "agent-delegated", "mixed"] },
    "scannerNodeId": { "type": ["string", "null"], "description": "Max-tier agent if delegated" },
    "options": {
      "type": "object",
      "properties": {
        "portTier": { "type": "string", "enum": ["tier1", "tier2"] },
        "includeIoTProtocols": { "type": "boolean" },
        "includeSnmp": { "type": "boolean" },
        "timeout": { "type": "integer" }
      }
    },
    "results": {
      "type": "object",
      "properties": {
        "hostsScanned": { "type": "integer" },
        "hostsAlive": { "type": "integer" },
        "newDiscoveries": { "type": "integer" },
        "returningDevices": { "type": "integer" },
        "departedSinceLast": { "type": "integer" },
        "alreadyRegistered": { "type": "integer" }
      }
    },
    "triggeredBy": { "type": "string" },
    "startedAt": { "type": "string", "format": "date-time" },
    "completedAt": { "type": ["string", "null"], "format": "date-time" }
  }
}
```

### 7.10 Collection: `discovery_exclusions`

**Purpose:** Store MAC/IP exclusion lists for network discovery.

```json
{
  "$id": "hydra:discovery_exclusions",
  "type": "object",
  "properties": {
    "exclusionId": { "type": "string" },
    "type": { "type": "string", "enum": ["mac", "ip", "ip-range"] },
    "value": { "type": "string" },
    "label": { "type": "string" },
    "reason": { "type": "string" },
    "createdBy": { "type": "string" },
    "createdAt": { "type": "string", "format": "date-time" }
  }
}
```

### 7.11 Collection: `executions`

**Purpose:** Store bound command actions — a command + specific target + parameters. This is the atomic unit of infrastructure action in the Command Center.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:executions",
  "title": "Execution",
  "description": "A command bound to a target — the atomic unit of infrastructure action",
  "type": "object",
  "required": ["executionId", "commandId", "target", "status", "requestedBy"],
  "properties": {
    "_id": { "type": "string" },
    "executionId": { "type": "string", "pattern": "^exec_[a-z0-9]+$" },
    "commandId": { "type": "string", "description": "Reference to command building block (e.g., cmd::service::restart)" },
    "target": {
      "type": "object",
      "required": ["nodeId"],
      "properties": {
        "nodeId": { "type": "string" },
        "serviceId": { "type": ["string", "null"] },
        "entityId": { "type": ["string", "null"], "description": "For IoT targets (Home Assistant entity ID)" }
      }
    },
    "parameters": { "type": "object", "description": "User-provided parameters matching command's io.parameters schema" },
    "resolvedTranslation": {
      "type": "object",
      "description": "The actual machine-level instruction resolved at execution time",
      "properties": {
        "method": { "type": "string", "enum": ["agent-direct", "agent-poll", "integration"] },
        "shell": { "type": ["string", "null"] },
        "handler": { "type": ["string", "null"] },
        "integrationId": { "type": ["string", "null"] },
        "platform": { "type": "string" },
        "runtime": { "type": ["string", "null"] }
      }
    },
    "status": {
      "type": "string",
      "enum": ["pending", "rejected", "queued", "executing", "completed", "failed", "timeout", "cancelled"]
    },
    "queuePosition": { "type": ["integer", "null"] },
    "executionMethod": { "type": "string", "enum": ["agent-direct", "agent-poll", "integration"] },
    "result": {
      "type": ["object", "null"],
      "properties": {
        "success": { "type": "boolean" },
        "output": { "type": "string" },
        "exitCode": { "type": ["integer", "null"] },
        "error": { "type": ["string", "null"] },
        "data": { "type": "object" }
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
        "source": { "type": "string", "enum": ["web", "mcp-internal", "workflow", "api"] },
        "clientId": { "type": ["string", "null"] },
        "workflowId": { "type": ["string", "null"] },
        "workflowRunId": { "type": ["string", "null"] }
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

**Indexes:**

```javascript
db.executions.createIndexes([
  { key: { "executionId": 1 }, unique: true },
  { key: { "status": 1, "createdAt": -1 } },
  { key: { "target.nodeId": 1, "createdAt": -1 } },
  { key: { "commandId": 1, "status": 1 } },
  { key: { "requestedBy.workflowRunId": 1 } },
  { key: { "requestedBy.userId": 1, "createdAt": -1 } }
])
```

### 7.12 Collection: `workflows`

**Purpose:** Store saved, reusable sequences of building blocks for infrastructure automation.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:workflows",
  "title": "Workflow",
  "type": "object",
  "required": ["workflowId", "name", "blocks", "createdBy"],
  "properties": {
    "_id": { "type": "string" },
    "workflowId": { "type": "string", "pattern": "^wf_[a-z0-9_]+$" },
    "name": { "type": "string", "maxLength": 128 },
    "description": { "type": "string", "maxLength": 2048 },
    "blocks": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["blockId", "blockType"],
        "properties": {
          "blockId": { "type": "string" },
          "blockType": { "type": "string", "enum": ["execution", "conditional", "delay", "input_formatter", "output_formatter", "parallel_gate", "loop", "note"] },
          "label": { "type": "string" },
          "commandId": { "type": "string", "description": "For execution blocks" },
          "target": { "type": "object" },
          "parameters": { "type": "object" },
          "evaluate": { "type": "object", "description": "For conditional blocks" },
          "branches": { "type": "object", "description": "For conditional blocks" },
          "durationSeconds": { "type": "integer", "description": "For delay blocks" },
          "transform": { "type": "object", "description": "For formatter blocks" },
          "parallelBlocks": { "type": "array", "items": { "type": "string" }, "description": "For parallel gate blocks" },
          "loopOver": { "type": "string", "description": "For loop blocks" },
          "loopBlock": { "type": "string", "description": "For loop blocks" },
          "nextBlock": { "type": ["string", "null"] },
          "onFailure": { "type": "string", "enum": ["abort", "continue", "skip_to"], "default": "abort" },
          "skipTo": { "type": ["string", "null"] }
        }
      }
    },
    "inputs": {
      "type": "object",
      "description": "Workflow-level inputs users provide when running",
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
    "integrationRequirements": { "type": "array", "items": { "type": "string" } },
    "rbac": {
      "type": "object",
      "properties": {
        "minimumRole": { "type": "string" },
        "mcpCallable": { "type": "boolean", "default": true }
      }
    },
    "createdBy": { "type": "string" },
    "createdAt": { "type": "string", "format": "date-time" },
    "updatedAt": { "type": "string", "format": "date-time" },
    "version": { "type": "integer", "default": 1 }
  }
}
```

### 7.13 Collection: `workflow_runs`

**Purpose:** Track workflow execution instances.

```json
{
  "$id": "hydra:workflow_runs",
  "type": "object",
  "properties": {
    "runId": { "type": "string", "pattern": "^wfr_[a-z0-9]+$" },
    "workflowId": { "type": "string" },
    "workflowVersion": { "type": "integer" },
    "status": { "type": "string", "enum": ["running", "completed", "failed", "cancelled", "timeout"] },
    "inputs": { "type": "object" },
    "currentBlock": { "type": "string" },
    "blockResults": { "type": "object", "additionalProperties": { "type": "object" } },
    "executionIds": { "type": "array", "items": { "type": "string" } },
    "triggeredBy": {
      "type": "object",
      "properties": {
        "userId": { "type": "string" },
        "source": { "type": "string", "enum": ["web", "mcp-internal", "mcp-external", "api", "schedule"] }
      }
    },
    "startedAt": { "type": "string", "format": "date-time" },
    "completedAt": { "type": ["string", "null"], "format": "date-time" }
  }
}
```

### 7.14 Collection: `integrations`

**Purpose:** Store plugin registry and configuration. Each document represents one integration provider.

```json
{
  "$id": "hydra:integrations",
  "type": "object",
  "properties": {
    "pluginId": { "type": "string", "pattern": "^plg::[a-z-]+$", "examples": ["plg::docker", "plg::proxmox", "plg::home-assistant"] },
    "name": { "type": "string" },
    "classification": { "type": "string", "enum": ["core", "default", "community"] },
    "version": { "type": "string" },
    "status": { "type": "string", "enum": ["available", "enabled", "configured", "active", "error", "disabled"] },
    "touchpoints": {
      "type": "array",
      "items": { "type": "string", "enum": ["profile-enrichment", "discovery-provider", "command-provider", "execution-handler", "topology-provider", "workflow-block-provider"] }
    },
    "configSchema": { "type": "object", "description": "JSON Schema for this plugin's configuration" },
    "config": { "type": "object", "description": "Actual configuration values" },
    "healthStatus": {
      "type": "object",
      "properties": {
        "healthy": { "type": "boolean" },
        "lastCheck": { "type": "string", "format": "date-time" },
        "error": { "type": ["string", "null"] }
      }
    },
    "enabledBy": { "type": "string" },
    "enabledAt": { "type": ["string", "null"], "format": "date-time" }
  }
}
```

### 7.15 Collection: `integration_configs`

**Purpose:** Per-node plugin bindings — which plugins are active on which nodes.

```json
{
  "$id": "hydra:integration_configs",
  "type": "object",
  "properties": {
    "nodeId": { "type": "string" },
    "pluginId": { "type": "string" },
    "enabled": { "type": "boolean" },
    "config": { "type": "object", "description": "Node-specific plugin config overrides" },
    "commandRoutingEnabled": { "type": "boolean", "default": false, "description": "Whether commands should route through this plugin's execution handler" },
    "detectedByAgent": { "type": "boolean" },
    "lastSyncAt": { "type": "string", "format": "date-time" }
  }
}
```

### 7.16 Collection: `boards`

**Purpose:** Store customizable dashboard definitions.

```json
{
  "$id": "hydra:boards",
  "type": "object",
  "properties": {
    "boardId": { "type": "string", "pattern": "^board_[a-z0-9]+$" },
    "name": { "type": "string", "maxLength": 128 },
    "description": { "type": "string" },
    "ownerId": { "type": "string" },
    "visibility": { "type": "string", "enum": ["private", "shared", "public"] },
    "layout": {
      "type": "object",
      "properties": {
        "columns": { "type": "integer", "enum": [6, 8, 12] },
        "rowHeight": { "type": "integer", "default": 80 }
      }
    },
    "widgets": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["widgetId", "widgetType", "position", "dataSource"],
        "properties": {
          "widgetId": { "type": "string" },
          "widgetType": { "type": "string" },
          "title": { "type": "string" },
          "position": {
            "type": "object",
            "properties": { "x": { "type": "integer" }, "y": { "type": "integer" }, "w": { "type": "integer" }, "h": { "type": "integer" } }
          },
          "dataSource": {
            "type": "object",
            "properties": {
              "type": { "type": "string", "enum": ["api-query", "static", "embed"] },
              "endpoint": { "type": "string" },
              "params": { "type": "object" },
              "refreshInterval": { "type": "integer" }
            }
          },
          "config": { "type": "object", "description": "Widget-type-specific configuration" },
          "pluginSource": { "type": ["string", "null"], "description": "Plugin that contributed this widget type" }
        }
      }
    },
    "templateId": { "type": ["string", "null"] },
    "tags": { "type": "array", "items": { "type": "string" } },
    "isDefault": { "type": "boolean", "default": false },
    "kioskMode": { "type": "boolean", "default": false },
    "version": { "type": "integer", "default": 1 },
    "createdAt": { "type": "string", "format": "date-time" },
    "updatedAt": { "type": "string", "format": "date-time" }
  }
}
```

### 7.17 Collection: `mcp_clients`

**Purpose:** Track registered MCP client applications for source-aware permission enforcement.

```json
{
  "$id": "hydra:mcp_clients",
  "type": "object",
  "properties": {
    "clientId": { "type": "string" },
    "name": { "type": "string" },
    "type": { "type": "string", "enum": ["internal", "external"] },
    "trusted": { "type": "boolean" },
    "capabilities": {
      "type": "array",
      "items": { "type": "string", "enum": ["read", "execute", "workflow-build", "workflow-run", "scan"] }
    },
    "registeredBy": { "type": ["string", "null"] },
    "registeredAt": { "type": "string", "format": "date-time" }
  }
}
```

### 7.18–7.30 Remaining MongoDB Collections

The following collections retain the same schemas as defined in Technical Documentation v0.3.0 with no structural changes for v0.5.0:

| Collection | Purpose | Key Fields |
|---|---|---|
| `users` | User accounts for auth and RBAC | userId, role, status, temporaryRoles |
| `users_pending` | Pending registrations (TTL 7d) | userId, username, email, role, requestedAt |
| `tokens` | Auth tokens (access, refresh, registration) | token, type, expiresAt |
| `api_keys` | API keys for user and node authentication | keyId, keyHash, type, ownerId, nodeId, permissions |
| `password_reset_tokens` | Password reset tokens | token, userId, expiresAt, used |
| `known_services` | Service registry/allow-list | knownServiceId, runtime, name, tags |
| `ai_models` | LLM provider configurations | configId, type, model, apiKeyEncrypted |
| `global_api_keys` | Provider-level API keys | providerType, apiKeyEncrypted, scopes |
| `mcp_servers` | External MCP server configs | serverId, name, endpoint, category |
| `chat_projects` | Chat workspace projects | projectId, name, ownerId |
| `chat_sessions` | Chat conversation sessions | sessionId, projectId, llmProviderId |
| `chat_messages` | Individual chat messages | messageId, sessionId, role, content, toolCalls |
| `user_settings` | Per-user preferences | userId, ui, views, notifications |
| `system_settings` | Global system config (singleton) | smtp, objectStorage, defaults, embedding |
| `notifications` | Notification records | notificationId, type, tier, source, status, groupKey |
| `notification_reads` | Read/acknowledge tracking | notificationId, userId, readAt |
| `board_templates` | Pre-built dashboard templates | templateId, name, widgets, category |

---

## 8. PostgreSQL Data Models

### 8.1 Table: `embeddings`

**Purpose:** Store vector embeddings for semantic search across all infrastructure knowledge.

```sql
CREATE TABLE embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(50) NOT NULL,
    source_id VARCHAR(255) NOT NULL,
    source_section VARCHAR(255),
    chunk_index INTEGER DEFAULT 0,
    content_text TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    embedding vector(1536) NOT NULL,  -- dimension matches configured provider
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_source_chunk UNIQUE (source_type, source_id, source_section, chunk_index)
);

CREATE INDEX idx_embeddings_vector ON embeddings
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_embeddings_source ON embeddings (source_type, source_id);
CREATE INDEX idx_embeddings_metadata ON embeddings USING GIN (metadata);
CREATE INDEX idx_embeddings_hash ON embeddings (content_hash);
```

**Source types and their chunking strategies:**

| source_type | source_id | Chunking | Example |
|---|---|---|---|
| `doc_section` | docId | Per-section (~500 tokens) | Documentation content |
| `profile_summary` | nodeId | Per-node natural language summary | "proxmox-01 is a Dell PowerEdge R630 with 56 cores..." |
| `service` | serviceId | Per-service description | "nginx running as Docker container on port 80/443" |
| `topology` | networkId | Per-network/cluster description | "homenet-lan: 192.168.0.0/24, 15 nodes, gateway OPNsense" |
| `workflow` | workflowId | Per-workflow description | "Safe Service Restart: checks health, captures logs..." |
| `change_journal` | entryId | Per-journal entry | "2026-02-05: proxmox-01 profile updated, 3 new containers" |

### 8.2 Table: `search_index`

**Purpose:** Materialized global search index powering the Cmd+K command palette.

```sql
CREATE TABLE search_index (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    title VARCHAR(512) NOT NULL,
    subtitle VARCHAR(512),
    body TEXT,
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    route VARCHAR(512) NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(subtitle, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(body, '')), 'C') ||
        setweight(to_tsvector('english', array_to_string(tags, ' ')), 'B')
    ) STORED,
    
    CONSTRAINT unique_entity UNIQUE (entity_type, entity_id)
);

CREATE INDEX idx_search_vector ON search_index USING GIN (search_vector);
CREATE INDEX idx_search_entity_type ON search_index (entity_type);
```

**Indexed entity types:** `node`, `service`, `network`, `group`, `document`, `workflow`, `command`, `integration`, `board`

### 8.3 Table: `documents`

**Purpose:** Store document metadata, staleness tracking, and full-text search for the living documentation system.

```sql
CREATE TABLE documents (
    doc_id VARCHAR(255) PRIMARY KEY,
    title VARCHAR(512) NOT NULL,
    description TEXT,
    doc_type VARCHAR(50) NOT NULL,
    category VARCHAR(100),
    generation_mode VARCHAR(20) NOT NULL,
    template_set_id VARCHAR(255),
    status VARCHAR(20) DEFAULT 'published',
    staleness VARCHAR(20) DEFAULT 'current',
    staleness_reason TEXT,
    tags TEXT[] DEFAULT '{}',
    current_version INTEGER DEFAULT 1,
    author_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
        setweight(to_tsvector('english', array_to_string(tags, ' ')), 'C')
    ) STORED
);

CREATE INDEX idx_documents_search ON documents USING GIN (search_vector);
CREATE INDEX idx_documents_type ON documents (doc_type, category);
CREATE INDEX idx_documents_staleness ON documents (staleness) WHERE staleness = 'stale';
CREATE INDEX idx_documents_status ON documents (status);
```

**Document types:** `runbook`, `architecture`, `service-catalog`, `change-journal`, `capacity-report`, `integration-doc`, `dr-analysis`, `guide`, `reference`, `troubleshooting`, `changelog`, `custom`

**Generation modes:** `auto` (fully generated from templates), `manual` (user-authored), `hybrid` (auto-generated with manual section overrides)

### 8.4 Table: `document_sections`

**Purpose:** Section-level content supporting hybrid authoring (auto-generated + manual overrides).

```sql
CREATE TABLE document_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id VARCHAR(255) NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    section_id VARCHAR(255) NOT NULL,
    title VARCHAR(512) NOT NULL,
    content TEXT NOT NULL,
    authoring_mode VARCHAR(20) NOT NULL,
    template_id VARCHAR(255),
    section_order INTEGER NOT NULL,
    data_hash VARCHAR(64),
    metadata JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(content, '')), 'B')
    ) STORED,
    
    CONSTRAINT unique_doc_section UNIQUE (doc_id, section_id)
);

CREATE INDEX idx_doc_sections_search ON document_sections USING GIN (search_vector);
CREATE INDEX idx_doc_sections_doc ON document_sections (doc_id, section_order);
```

**Authoring modes:** `auto` (generated from template, regenerated on staleness), `manual` (user-written, preserved during regeneration), `override` (user replaced an auto-generated section, preserved during regeneration)

### 8.5 Table: `document_entity_links`

**Purpose:** Relational links between documents and the infrastructure entities they describe. Enables staleness detection via foreign key relationships.

```sql
CREATE TABLE document_entity_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id VARCHAR(255) NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    link_type VARCHAR(50) DEFAULT 'describes',
    
    CONSTRAINT unique_doc_entity UNIQUE (doc_id, entity_type, entity_id)
);

CREATE INDEX idx_doc_entity_links ON document_entity_links (entity_type, entity_id);
CREATE INDEX idx_doc_entity_doc ON document_entity_links (doc_id);
```

**Link types:** `describes` (primary relationship), `references` (mentioned but not primary), `depends_on` (doc depends on entity for generation)

**Staleness detection pattern:**

```sql
-- When node 'proxmox-01' gets a new profile, flag all describing docs as stale
UPDATE documents SET staleness = 'stale',
    staleness_reason = 'Linked entity proxmox-01 updated (new profile submitted)',
    updated_at = NOW()
WHERE doc_id IN (
    SELECT doc_id FROM document_entity_links
    WHERE entity_type = 'node' AND entity_id = 'proxmox-01'
)
AND generation_mode IN ('auto', 'hybrid')
AND staleness = 'current';
```

### 8.6 Table: `document_versions`

**Purpose:** Version history with section snapshots for diff viewing.

```sql
CREATE TABLE document_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id VARCHAR(255) NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    sections_snapshot JSONB NOT NULL,
    changed_sections TEXT[] DEFAULT '{}',
    change_summary TEXT,
    generation_trigger VARCHAR(100),
    created_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_doc_version UNIQUE (doc_id, version)
);

CREATE INDEX idx_doc_versions ON document_versions (doc_id, version DESC);
```

### 8.7 Table: `audit_log`

**Purpose:** Time-partitioned audit trail of all write operations across the system. ACID guarantees ensure audit integrity.

```sql
CREATE TABLE audit_log (
    id BIGSERIAL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(255) NOT NULL,
    actor_id VARCHAR(255) NOT NULL,
    actor_role VARCHAR(50) NOT NULL,
    source VARCHAR(50) NOT NULL,
    details JSONB DEFAULT '{}',
    result VARCHAR(20) NOT NULL,
    ip_address INET,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Monthly partitions (auto-created by maintenance job)
CREATE TABLE audit_log_2026_01 PARTITION OF audit_log
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE audit_log_2026_02 PARTITION OF audit_log
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE audit_log_2026_03 PARTITION OF audit_log
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

CREATE INDEX idx_audit_timestamp ON audit_log (timestamp DESC);
CREATE INDEX idx_audit_actor ON audit_log (actor_id, timestamp DESC);
CREATE INDEX idx_audit_resource ON audit_log (resource_type, resource_id, timestamp DESC);
CREATE INDEX idx_audit_action ON audit_log (action, timestamp DESC);
```

**Partition management:** A background job in hydra-api creates next month's partition automatically and optionally detaches partitions older than the configured retention period (default: 12 months).

---

## 9. Profile Schemas by Node Class

### 9.1 Compute Node — Physical

Physical compute nodes represent bare-metal hardware. The profile captures the complete hardware specification, network interfaces, storage devices, installed software, user accounts, and configuration files.

**Profile sections and their data contracts:**

| Section | Key Fields | Notes |
|---|---|---|
| `hardware.cpu` | model, architecture, cores (physical + logical), threads, sockets, flags, cache | Static — changes only on hardware swap |
| `hardware.memory` | totalBytes, type (DDR4/5), speed, slots (used/total), modules[] | Physical DIMM enumeration |
| `hardware.gpu` | model, vendor, vramBytes, driver, busId, capabilities | Per-GPU entry; includes iGPU |
| `hardware.motherboard` | vendor, model, serial, bios (vendor, version, date) | Firmware tracking |
| `hardware.chassis` | type (desktop/server/laptop), vendor, model, serial | Physical form factor |
| `network.interfaces[]` | name, type (ethernet/wifi/bridge/bond), mac, ipv4[], ipv6[], speed, mtu, state, driver | All interfaces enumerated |
| `network.routing` | defaultGatewayV4, defaultGatewayV6, routes[] | Routing table snapshot |
| `network.dns` | nameservers[], searchDomains[], resolverConfig | DNS configuration |
| `network.connections[]` | localAddr, remoteAddr, protocol, state, pid, process | Listening + established (deep only) |
| `storage.blockDevices[]` | name, type (disk/part/lvm/raid), size, model, serial, mountpoint, fsType, transport | Block device tree |
| `storage.filesystems[]` | device, mountpoint, fsType, totalBytes, usedBytes, options | Mounted filesystem inventory |
| `storage.pools[]` | name, type (zfs/lvm/btrfs), totalBytes, members[] | Storage pool aggregation |
| `software.os` | name, id, version, kernel, arch, family | OS identification |
| `software.packages[]` | name, version, manager (apt/yum/pacman/brew), installedAt | Package inventory |
| `software.runtimes[]` | name (python/node/java/go/rust), version, path | Language runtime detection |
| `users.accounts[]` | username, uid, gid, home, shell, groups[], lastLogin, hasAuthorizedKeys | User enumeration |
| `users.sshKeys[]` | username, keyType, fingerprint, comment | SSH authorized_keys (fingerprints only) |
| `configs.files[]` | path, hash, sizeBytes, modifiedAt, tracked | Tracked config file hashes |
| `configs.sysctl` | key-value pairs of active sysctl settings | Kernel tuning (deep only) |

**Source paths (Linux):**

| Data | Source |
|---|---|
| CPU | `/proc/cpuinfo`, `/sys/devices/system/cpu/`, `lscpu` |
| Memory | `/proc/meminfo`, `dmidecode -t memory` |
| GPU | `/sys/class/drm/`, `lspci -nn`, `/proc/driver/nvidia/` |
| Network interfaces | `/sys/class/net/`, `/proc/net/if_inet6`, `ip addr` |
| Block devices | `/sys/block/`, `lsblk -J`, `/proc/mdstat` |
| Packages | `dpkg-query -W` / `rpm -qa` / `pacman -Q` |
| Services | `systemctl list-units --type=service` |
| Users | `/etc/passwd`, `/etc/shadow` (hash presence only), `~/.ssh/authorized_keys` |

### 9.2 Compute Node — Logical

Logical nodes (VMs, LXCs, containers) share the same profile structure as physical nodes with additions:

| Section | Additional Fields | Notes |
|---|---|---|
| `virtualization.type` | vm, lxc, docker, kubernetes-pod | Virtualization technology |
| `virtualization.hypervisor` | parentNodeId, hypervisorType (kvm/xen/vmware/lxc/docker) | Parent reference |
| `virtualization.resources` | allocatedCores, allocatedMemoryBytes, allocatedDiskBytes | Resource allocation from hypervisor |
| `virtualization.config` | vmId, template, privileged, nestingEnabled | VM/LXC-specific config |

**Key difference:** Logical nodes report `hardware.cpu.cores` as what the OS sees (vCPUs), while `virtualization.resources.allocatedCores` reflects the hypervisor allocation. The parent-child relationship enables Hydra to map resource allocation across the infrastructure.

### 9.3 IoT Node

IoT nodes are profiled via the Home Assistant plugin integration, not by running an agent directly. The profile structure differs significantly:

| Section | Key Fields | Notes |
|---|---|---|
| `iot.source` | provider (home-assistant), sourceUrl, areaId, areaName | Integration source |
| `iot.device` | manufacturer, model, swVersion, hwVersion, viaDeviceId | Device metadata from HA |
| `iot.capabilities` | entities[], each with entityId, domain, deviceClass, unitOfMeasurement, supportedFeatures | What the device can do |
| `iot.connectivity` | connectionType (wifi/zigbee/zwave/bluetooth/thread/matter), signalStrength, lastSeen | Connection details |
| `iot.categories` | domains[] (light, switch, sensor, climate, media_player, etc.) | HA domain classification |
| `network.interfaces[]` | Simplified: mac, ipv4 (if available from HA) | Limited network info |

### 9.4 Networking Node

Networking devices (switches, routers, APs, firewalls) use specialized profile sections:

| Section | Key Fields | Notes |
|---|---|---|
| `networking.type` | router, managed-switch, unmanaged-switch, access-point, firewall | Device function |
| `networking.ports[]` | portId, type (ethernet/sfp/sfp+), speed, status (up/down), vlanMode, pvid, taggedVlans[], connectedMac | Per-port detail |
| `networking.vlans[]` | vlanId, name, tagged[], untagged[] | VLAN configuration |
| `networking.routingTable[]` | destination, gateway, interface, metric, protocol | Routing entries (routers only) |
| `networking.protocols` | stp (enabled, rootBridge), lldp (enabled, neighbors[]), lacp (bonds[]) | Protocol configuration |
| `networking.firmware` | current, available, lastUpdated | Firmware tracking |
| `hardware` | Simplified: model, vendor, serial, portCount, managementIp | Basic hardware ID |
| `network.interfaces[]` | management interface + uplinks | Management and uplink interfaces |

**Profiling methods by device type:**

| Device Type | Method | Source |
|---|---|---|
| Managed switch (SNMP) | SNMP polling via Discovery Provider plugin | SNMP MIBs (IF-MIB, BRIDGE-MIB, Q-BRIDGE-MIB) |
| Router (SSH) | SSH command execution | CLI output parsing (show interfaces, show vlans, etc.) |
| UniFi devices | UniFi Controller API via plugin | REST API |
| pfSense/OPNsense | REST API via plugin | Configuration API |

---

## 10. Service Discovery

### 10.1 Discovery Mechanism

Services are discovered by the agent during profile collection. The agent detects services from multiple runtime sources and reports them as part of the profile payload. The API extracts services from profiles and upserts them as first-class entities.

```
Agent collects profile
  └── Discovers services from:
       ├── systemd:     systemctl list-units --type=service --state=running
       ├── docker:      docker ps --format json (or Docker socket API)
       ├── podman:      podman ps --format json
       ├── containerd:  ctr tasks ls
       ├── kubernetes:  kubectl get pods (if kubeconfig available)
       ├── supervisord: supervisorctl status
       ├── pm2:         pm2 jlist
       ├── launchd:     launchctl list (macOS)
       └── winservice:  Get-Service (Windows)
  └── For each service:
       ├── Collect runtime-specific metadata
       ├── Detect exposed ports (ss -tlnp / docker port)
       ├── Generate serviceId: svc-<sanitized_name>-<4char_hash>
       └── Include in profile.serviceIds[]
```

### 10.2 Service Lifecycle

```
             Agent discovers              API extracts
Profile ──────────────────────▶ API ─────────────────────▶ services collection
                                 │
                                 ├── New service? → INSERT with firstSeen
                                 ├── Known service? → UPDATE lastSeen, status, version
                                 └── Missing service? → Mark status = "stopped" (not deleted)
```

Services are never automatically deleted. If a service disappears from subsequent profiles, its status changes to `stopped` but the record persists for historical tracking.

### 10.3 Service-to-Known-Service Matching

When a service is discovered, the API attempts to match it against the `known_services` registry:

```
For each discovered service:
  1. Check known_services for matching (runtime + name) or (runtime + image)
  2. If matched:
     - Apply displayName, description, tags from known_services
     - Set origin.knownServiceId
  3. If not matched:
     - Use raw name from runtime
     - Flag as "unmatched" for user review
```

---

## 11. Group Management

### 11.1 Group Types

Groups provide flexible logical partitioning of infrastructure entities. Unlike physical groupings (networks, parent-child), groups are user-defined organizational overlays.

**Common use cases:**

| Group | Types | Selectors | Purpose |
|---|---|---|---|
| "Production" | [node, service] | `tags.isAll: ["production"]` | All production infrastructure |
| "Docker Hosts" | [node] | `kind.isAny: ["bare-metal", "vm"]`, `tags.isAny: ["docker"]` | Nodes running Docker |
| "Server Rack" | [node] | `location.rack: "rack-01"` | Physical rack grouping |
| "Media Stack" | [service] | `tags.isAll: ["media"]` | Plex, Sonarr, Radarr, etc. |
| "Monitoring" | [node, service] | `tags.isAny: ["monitoring", "observability"]` | Prometheus, Grafana, etc. |

### 11.2 Group Resolution

Group membership is computed dynamically on request (not stored). When `GET /groups/{groupId}/members` is called, the API evaluates all selectors against current node/service state and returns matching entities.

For performance, `memberCount` is periodically recomputed and cached on the group document (every 5 minutes or on profile submission).

---

## 12. Network Management

### 12.1 Auto-Creation from Profiles

When a profile is submitted, the API extracts network interface information and auto-creates or updates network definitions:

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

### 12.2 Scannability Assessment

Each network is assessed for how the API can reach it for discovery scanning:

| Status | Meaning | Scan Method |
|---|---|---|
| `api-direct` | API server has an interface on this network | API runs scan directly |
| `api-routed` | API can route to this network | API runs scan through gateway |
| `agent-only` | Only reachable by a max-tier agent on the network | Delegated scan via agent |
| `unreachable` | No scan path available | Manual registration only |

Scannability is reassessed when profiles update network information or agent tiers change.

---

## 13. Topology Generation

### 13.1 Generation Triggers

Topology snapshots are regenerated when:

- A new profile is submitted
- A node is registered or deregistered
- A network is created, updated, or deleted
- A manual regeneration is requested
- A plugin reports topology edge changes

### 13.2 Topology Modes

| Mode | Nodes in Graph | Edges in Graph | Use Case |
|---|---|---|---|
| `network` | compute, networking, iot nodes | network-connection, network-gateway, vlan-trunk | Network-centric view |
| `infrastructure` | All node types + services | parent-child, service-host, network-connection, plugin-relationship | Full infrastructure map |
| `service` | Services + host nodes | service-host, service-dependency | Service dependency map |

### 13.3 Edge Construction

```
Core edges (always computed):
  ├── network-connection: Nodes sharing a network CIDR
  ├── parent-child: node.parentNodeId relationships
  ├── service-host: service.nodeId → hosting node
  ├── service-dependency: service.dependencies[] references
  ├── network-gateway: network.routerNodeId → network
  └── vlan-trunk: Ports carrying multiple VLANs

Plugin-contributed edges:
  ├── Proxmox: cluster → node, node → VM/LXC (HA groups)
  ├── Docker: host → container, container → network
  ├── Home Assistant: hub → device, device → entity
  └── Custom: Any plugin implementing TopologyProvider touchpoint
```

### 13.4 Diff Calculation

Each topology stores a diff from its predecessor:

```python
def compute_topology_diff(current: Topology, previous: Topology) -> TopologyDiff:
    current_node_ids = {n.id for n in current.graph.nodes}
    previous_node_ids = {n.id for n in previous.graph.nodes}
    
    return TopologyDiff(
        nodesAdded=list(current_node_ids - previous_node_ids),
        nodesRemoved=list(previous_node_ids - current_node_ids),
        nodesModified=[n.id for n in current.graph.nodes 
                       if n.id in previous_node_ids and n.data != prev_map[n.id].data],
        edgesAdded=list(current_edge_ids - previous_edge_ids),
        edgesRemoved=list(previous_edge_ids - current_edge_ids)
    )
```

---

## 14. Time Machine

### 14.1 Concept

Time Machine enables navigation through historical infrastructure states at both individual node and topological levels. It answers questions like "What did my infrastructure look like last Thursday?" and "When did this service first appear?"

### 14.2 State Reconstruction

**Node-level Time Machine:**

```
GET /nodes/{nodeId}/profiles?asOf=2026-01-15T00:00:00Z

Algorithm:
  1. Find the latest profile for nodeId WHERE submittedAt <= asOf
  2. Return that profile with its version, services, and metadata
  3. If no profile exists before asOf, return 404
```

**Topology-level Time Machine:**

```
GET /topologies?mode=network&asOf=2026-01-15T00:00:00Z

Algorithm:
  1. Find topology WHERE mode=network AND validFrom <= asOf AND (validUntil > asOf OR validUntil IS NULL)
  2. Return the topology snapshot with its graph
  3. If no topology covers asOf, return the earliest available
```

### 14.3 Compare Mode

The web UI supports side-by-side comparison of two time points:

```
GET /compare/node/{nodeId}?from=2026-01-01T00:00:00Z&to=2026-02-01T00:00:00Z

Returns:
  - Profile at "from" timestamp
  - Profile at "to" timestamp
  - Section-level diff (which sections changed, what changed)
  - Service diff (added, removed, changed services)
```

### 14.4 Integration with Documentation

Documents support Time Machine via PostgreSQL versioning:

```sql
-- "What did the proxmox-01 runbook look like on Jan 15?"
SELECT dv.sections_snapshot FROM document_versions dv
JOIN documents d ON d.doc_id = dv.doc_id
WHERE d.doc_id = 'doc::runbook::proxmox-01'
  AND dv.created_at <= '2026-01-15T00:00:00Z'
ORDER BY dv.version DESC LIMIT 1;
```

---

## 15. Network Discovery

### 15.1 Scanning Model

Network discovery proactively finds devices on the network before they are registered as Hydra nodes. Scanning is always user-initiated (explicit over implicit — no automated scans without user action).

**Scan execution paths:**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         DISCOVERY SCAN FLOW                              │
│                                                                          │
│  User triggers scan for network(s)                                       │
│         │                                                                │
│         ▼                                                                │
│  ┌─────────────────┐                                                     │
│  │ API evaluates    │                                                     │
│  │ scannability    │                                                     │
│  └────────┬────────┘                                                     │
│           │                                                              │
│    ┌──────┼──────────────────┐                                          │
│    ▼      ▼                  ▼                                          │
│  API-Direct   API-Routed   Agent-Delegated                              │
│  (same net)   (routable)   (remote net)                                 │
│    │           │                │                                        │
│    │           │                ▼                                        │
│    │           │         POST to max-tier                                │
│    │           │         agent HTTP server                               │
│    │           │                │                                        │
│    ▼           ▼                ▼                                        │
│  ┌─────────────────────────────────────────┐                            │
│  │           SCAN PIPELINE                   │                            │
│  │  1. ARP scan → host discovery            │                            │
│  │  2. Cross-ref with known nodes            │                            │
│  │  3. Port scan (tier1: common ports)       │                            │
│  │  4. Protocol probes (mDNS, SSDP, SNMP)   │                            │
│  │  5. Banner grabbing                       │                            │
│  │  6. Device classification                 │                            │
│  │  7. Eligibility assessment                │                            │
│  └─────────────────────────────────────────┘                            │
│           │                                                              │
│           ▼                                                              │
│  Store/update discovered_nodes                                          │
│  Stream results via WebSocket (API-direct)                              │
│  Return results via HTTP (agent-delegated)                              │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 15.2 Device Fingerprinting

Fingerprinting uses multiple signal sources to classify discovered devices:

| Signal | Source | Classification Contribution |
|---|---|---|
| Open ports | Port scan | SSH (22) → compute; 80/443 → web service; 8123 → Home Assistant |
| MAC OUI | ARP table | Vendor identification (Raspberry Pi, Synology, Ubiquiti, etc.) |
| mDNS | Multicast query | Service advertisement (_http._tcp, _ssh._tcp, _hap._tcp) |
| SSDP | UPnP discovery | Device type (MediaServer, InternetGateway, etc.) |
| SNMP | SNMP community probe | sysDescr, sysObjectID → networking device identification |
| HTTP headers | Port 80/443 probe | Server headers, title tags (e.g., "Pi-hole Admin Console") |
| Banner strings | TCP banner grab | SSH version, SMTP greeting, etc. |
| TTL | ICMP/TCP | OS family hint (64=Linux, 128=Windows, 255=networking) |

### 15.3 Classification Logic

```python
def classify_device(fingerprint: Fingerprint) -> Classification:
    signals = []
    
    # MAC vendor analysis
    if fingerprint.identity.macVendor in NETWORKING_VENDORS:
        signals.append(("networking", 0.8, "MAC vendor is networking manufacturer"))
    
    # Port-based classification
    if has_port(22) and has_port(80):
        signals.append(("compute", 0.6, "SSH + HTTP suggests compute device"))
    if has_port(161):  # SNMP
        signals.append(("networking", 0.7, "SNMP suggests managed networking device"))
    if has_port(8123):  # Home Assistant
        signals.append(("compute", 0.9, "Port 8123 = Home Assistant controller"))
    
    # Protocol analysis
    if fingerprint.protocols.ssdp and "InternetGateway" in ssdp.device_type:
        signals.append(("networking", 0.9, "UPnP IGD = router"))
    if fingerprint.protocols.mdns and "_hap._tcp" in mdns.services:
        signals.append(("iot", 0.8, "HomeKit Accessory Protocol"))
    
    # Aggregate signals with weighted confidence
    return aggregate_classification(signals)
```

### 15.4 Post-Discovery Actions

Each discovered device has three possible paths:

| Action | Description | Result |
|---|---|---|
| **Register** | User registers the device as a Hydra node | Creates node, sets `matchedNodeId` on discovery record |
| **Register + Install Agent** | Register and deploy agent via SSH/Proxmox | Creates node, installs agent, triggers first profile |
| **Dismiss** | User marks device as not interesting | Sets `status = "dismissed"`, optionally `permanent = true` |

---

## 16. Agent Architecture

### 16.1 Three-Tier Model

The agent ships as a single Rust binary with feature-gated compilation for three deployment tiers:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AGENT TIER CAPABILITIES                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  LITE                    NORMAL                   MAX                    │
│  ─────                   ──────                   ───                    │
│  • Profile collection    • Everything in Lite     • Everything in Normal │
│  • Profile submission    • Poll-based command     • HTTP server (axum)   │
│  • Schedule-based        • In-place update        • Synchronous execute  │
│  • < 20MB memory         • < 30MB memory          • Network scanning     │
│                                                   • Integration proxy    │
│  Use case:               Use case:                • Plugin local agent   │
│  Low-power devices,      Standard compute nodes   • < 50MB memory        │
│  NAS, embedded           that need command         │
│                          execution                Use case:              │
│                                                   Hypervisors, main     │
│                                                   servers, network      │
│                                                   gateways              │
└─────────────────────────────────────────────────────────────────────────┘
```

### 16.2 Capability Matrix

| Capability | Lite | Normal | Max | Description |
|---|---|---|---|---|
| `profile` | Yes | Yes | Yes | Collect and submit profiles |
| `poll-execute` | No | Yes | Yes | Poll Redis queue for commands |
| `direct-execute` | No | No | Yes | Receive commands via HTTP |
| `probe` | No | No | Yes | Network scanning/probing |
| `update` | No | Yes | Yes | Self-update binary |
| `config` | No | No | Yes | Accept runtime config changes |
| `integration-proxy` | No | No | Yes | Proxy API calls to local integrations |

### 16.3 Agent-API Communication

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     COMMUNICATION PATTERNS                               │
│                                                                          │
│  LITE AGENT:                                                             │
│  Agent ────POST /profiles────▶ API     (push profiles, one-way)         │
│                                                                          │
│  NORMAL AGENT:                                                           │
│  Agent ────POST /profiles────▶ API     (push profiles)                  │
│  Agent ────GET /commands/poll─▶ API     (poll for pending commands)      │
│  Agent ────POST /executions──▶ API      (return execution results)       │
│                                                                          │
│  MAX AGENT:                                                              │
│  Agent ────POST /profiles────▶ API     (push profiles)                  │
│  Agent ────GET /commands/poll─▶ API     (poll — fallback path)          │
│  API ──────POST /execute─────▶ Agent   (direct HTTP — preferred path)   │
│  API ──────POST /scan────────▶ Agent   (delegated network scan)         │
│  API ──────POST /proxy───────▶ Agent   (integration proxy)              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 16.4 Max-Tier HTTP Server

Max-tier agents run an axum HTTP server enabling synchronous API-to-agent communication:

```
Agent HTTP Server Endpoints:
  POST /execute       — Execute a command synchronously (< timeout)
  POST /scan          — Run network scan on agent's local network
  POST /proxy/{pluginId}/{path}  — Proxy request to local integration
  GET  /health        — Agent health check
  GET  /capabilities  — Report current capabilities
```

The API tracks agent reachability via `node.agent.serverStatus`:
- On successful direct contact → update `lastDirectContact`, reset `failedDirectAttempts`
- On failed direct contact → increment `failedDirectAttempts`
- After 3 consecutive failures → fall back to poll-based execution
- Continue attempting direct contact every 5 minutes

### 16.5 Agent Registration Flow

```
1. User installs agent on target machine
2. Agent reads configuration (API URL, registration token)
3. Agent sends POST /nodes/register with:
   - hostname, platform, tier
   - Registration token (validates permission to register)
4. API creates node record with:
   - Generated nodeId
   - role = "agent"
   - API key for subsequent authentication
5. API returns nodeId + API key to agent
6. Agent stores credentials and begins profile collection
7. First profile submitted → node transitions from "pending" to "active"
```

---

## 17. Commands, Executions & Workflows

### 17.1 Three-Layer Model

Hydra's operational control uses a three-layer architecture separating what, who-where-when, and composed sequences:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    COMMAND EXECUTION THREE-LAYER MODEL                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Layer 1: COMMANDS (Building Blocks)                                     │
│  System-defined, immutable command definitions.                          │
│  Seeded into MongoDB at API startup. NOT user-created.                   │
│  Define: what can be done, on what, with what parameters.               │
│  Example: cmd::service::restart                                          │
│                                                                          │
│  Layer 2: EXECUTIONS (Bound Actions)                                     │
│  A command bound to a specific target with specific parameters.          │
│  Created when a user/MCP/workflow triggers an action.                    │
│  Tracked through lifecycle: pending → queued → executing → completed.    │
│  Example: exec_a1b2c3 = restart nginx-proxy on proxmox-01              │
│                                                                          │
│  Layer 3: WORKFLOWS (Composed Sequences)                                 │
│  Saved, reusable DAGs of building blocks.                               │
│  Created by users via visual builder or MCP.                            │
│  Run as workflow_runs, spawning executions for each step.               │
│  Example: wf_safe_restart = check health → capture logs → restart →    │
│           wait 10s → verify health                                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 17.2 Command Catalog

Commands are system-defined building blocks seeded at API startup. They define what operations are available and how they translate to machine-level instructions per platform/runtime.

**Command categories:**

| Category | Examples | Target |
|---|---|---|
| `service` | restart, stop, start, enable, disable, logs | serviceId on nodeId |
| `node` | reboot, shutdown, update-packages | nodeId |
| `agent` | upgrade, reconfigure, restart-agent | nodeId (with agent) |
| `iot` | turn-on, turn-off, set-brightness, set-temperature | entityId via HA |

**Command definition structure:**

```json
{
  "commandId": "cmd::service::restart",
  "category": "service",
  "name": "Restart Service",
  "description": "Restart a service on a target node",
  "dangerLevel": "medium",
  "requiresConfirmation": true,
  "rbac": {
    "minimumRole": "operator",
    "mcpExternalAllowed": false
  },
  "io": {
    "parameters": {
      "graceful": { "type": "boolean", "default": true, "description": "Attempt graceful restart" },
      "timeout": { "type": "integer", "default": 30, "description": "Restart timeout in seconds" }
    },
    "expectedOutput": {
      "type": "object",
      "properties": {
        "previousState": { "type": "string" },
        "currentState": { "type": "string" },
        "restartTime": { "type": "number" }
      }
    }
  },
  "translations": {
    "systemd": {
      "method": "agent",
      "shell": "bash",
      "template": "systemctl restart {{service.origin.nativeId}}",
      "gracefulTemplate": "systemctl reload-or-restart {{service.origin.nativeId}}"
    },
    "docker": {
      "method": "integration",
      "integrationId": "plg::docker",
      "handler": "container_restart",
      "parameters": { "timeout": "{{parameters.timeout}}" }
    },
    "launchd": {
      "method": "agent",
      "shell": "bash",
      "template": "launchctl kickstart -k system/{{service.origin.nativeId}}"
    }
  }
}
```

### 17.3 Execution Lifecycle

```
┌─────────┐     ┌──────────┐     ┌──────────┐     ┌───────────┐     ┌───────────┐
│ PENDING  │────▶│ REJECTED │     │  QUEUED  │────▶│ EXECUTING │────▶│ COMPLETED │
│         │     │ (RBAC,   │     │ (Redis   │     │ (agent    │     │ (success) │
│ Created │     │  target  │     │  queue)  │     │  running) │     │           │
└─────────┘     │  invalid)│     └──────────┘     └───────────┘     └───────────┘
    │           └──────────┘          ▲                  │                        
    │                                 │                  ├────▶ FAILED (error)    
    ├── RBAC check                    │                  ├────▶ TIMEOUT           
    ├── Target validation             │                  └────▶ CANCELLED         
    ├── Translation resolution        │                                           
    └── Confirmation (if required) ───┘                                           
```

**Resolution flow:**

```python
async def create_execution(request: ExecutionRequest) -> Execution:
    # 1. Validate command exists
    command = await get_command(request.commandId)
    
    # 2. RBAC check
    if not user_has_permission(request.user, command.rbac):
        return Execution(status="rejected", error="Insufficient permissions")
    
    # 3. Source restriction (external MCP clients cannot execute directly)
    if request.source == "mcp-external" and not command.rbac.mcpExternalAllowed:
        return Execution(status="rejected", error="External MCP clients cannot execute this command")
    
    # 4. Resolve target
    node = await get_node(request.target.nodeId)
    service = await get_service(request.target.serviceId) if request.target.serviceId else None
    
    # 5. Resolve translation (which platform/runtime instruction to use)
    translation = resolve_translation(command, node, service)
    
    # 6. Determine execution method
    method = determine_method(node)  # agent-direct, agent-poll, or integration
    
    # 7. Create execution record
    execution = Execution(
        executionId=generate_id("exec"),
        commandId=command.commandId,
        target=request.target,
        parameters=request.parameters,
        resolvedTranslation=translation,
        executionMethod=method,
        status="pending",
        requestedBy=request.user
    )
    
    # 8. If confirmation required → wait for user confirm
    if command.requiresConfirmation:
        await send_confirmation_request(execution)
        return execution  # status stays "pending" until confirmed
    
    # 9. Queue for execution
    await queue_execution(execution)
    return execution
```

### 17.4 Workflow Block Types

| Block Type | Purpose | Properties |
|---|---|---|
| `execution` | Run a command on a target | commandId, target, parameters |
| `conditional` | Branch based on previous result | evaluate (expression), branches (true/false paths) |
| `delay` | Wait between steps | durationSeconds |
| `input_formatter` | Transform data between steps | transform (jmespath/template expression) |
| `output_formatter` | Format final workflow output | transform |
| `parallel_gate` | Run multiple blocks concurrently | parallelBlocks[], waitStrategy (all/any) |
| `loop` | Iterate over a list | loopOver (data path), loopBlock (block to repeat) |
| `note` | Documentation/comment block | text (no execution) |

### 17.5 Workflow Execution (Workflow Runs)

When a workflow is triggered, a `workflow_run` is created that orchestrates block-by-block execution:

```
1. Create workflow_run with status = "running"
2. Start at first block
3. For each block:
   a. If execution block → create Execution, wait for completion
   b. If conditional → evaluate expression against previous results
   c. If delay → wait durationSeconds
   d. If parallel → launch all parallelBlocks concurrently, wait per strategy
   e. If loop → iterate loopOver data, execute loopBlock per iteration
4. On block completion:
   a. Store result in blockResults[blockId]
   b. Advance to nextBlock (or branch for conditionals)
   c. On failure: check onFailure (abort/continue/skip_to)
5. On workflow completion → set status, calculate total duration
```

### 17.6 MCP Client Source Restrictions

| Source | Can Execute | Can Run Workflows | Can Build Workflows |
|---|---|---|---|
| Web UI | Yes (with confirmation) | Yes | Yes |
| MCP Internal (web chat) | Yes (with confirmation) | Yes | Yes |
| MCP External (Claude Desktop) | No (read-only for executions) | Saved workflows only | No |
| API (direct) | Yes (with API key permissions) | Yes | Yes |

External MCP clients can invoke **saved workflows** (pre-approved by an admin/operator) but cannot create ad-hoc executions. This provides a controlled path for AI-assisted operations without unrestricted access.

---

## 18. Controls & Safety

### 18.1 Control Domains

Every operational action in Hydra is governed by a layered safety model:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SAFETY LAYERS                                    │
│                                                                          │
│  Layer 1: RBAC              Does the user's role permit this action?    │
│  Layer 2: Source Restriction Is the request from an allowed source?     │
│  Layer 3: Target Validation  Is the target node/service valid + online? │
│  Layer 4: Rate Limiting      Has the user exceeded action frequency?    │
│  Layer 5: Confirmation       Does this action require user confirmation?│
│  Layer 6: Timeout            Automatic cancellation after timeout       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 18.2 RBAC Permission Matrix for Commands

| Command Category | admin | operator | viewer | family | agent | MCP-external |
|---|---|---|---|---|---|---|
| `service:restart` | Yes | Yes | No | No | No | Saved workflows only |
| `service:stop` | Yes | Yes | No | No | No | No |
| `service:start` | Yes | Yes | No | No | No | Saved workflows only |
| `service:logs` | Yes | Yes | Yes (read) | No | No | Yes |
| `node:reboot` | Yes | No | No | No | No | No |
| `node:shutdown` | Yes | No | No | No | No | No |
| `node:update-packages` | Yes | Yes | No | No | No | Saved workflows only |
| `agent:upgrade` | Yes | Yes | No | No | No | No |
| `iot:turn-on/off` | Yes | Yes | No | Yes | No | Saved workflows only |
| `iot:set-*` | Yes | Yes | No | Yes | No | No |

### 18.3 Danger Levels & Confirmation

| Danger Level | Confirmation Required | Examples |
|---|---|---|
| `safe` | No | service:logs, agent:health |
| `low` | No | iot:turn-on, iot:turn-off |
| `medium` | Yes (single click) | service:restart, service:start |
| `high` | Yes (type to confirm) | node:reboot, service:stop |
| `critical` | Yes (type exact resource name) | node:shutdown, bulk operations |

### 18.4 Rate Limiting

```python
RATE_LIMITS = {
    "per_user": {
        "executions_per_minute": 10,
        "executions_per_hour": 100,
    },
    "per_node": {
        "executions_per_minute": 5,      # Prevent command flooding a single node
    },
    "per_command": {
        "node:reboot": {"per_hour": 3},  # Prevent reboot loops
        "node:shutdown": {"per_hour": 1},
    }
}
```

Rate limit counters are tracked in Redis with automatic expiration.

---

## 19. Remote Agent Installation

### 19.1 Installation Methods

| Method | Mechanism | Requirements | Best For |
|---|---|---|---|
| SSH | SSH connection from API server | Target has SSH, API has credentials | VMs, LXCs, physical servers |
| Proxmox exec | `pct exec` / `qm guest exec` via Proxmox API | Proxmox plugin active, target is VM/LXC | Proxmox-managed containers/VMs |
| Manual | User downloads binary and runs install script | Physical access or existing SSH session | Air-gapped, restricted access |

### 19.2 SSH Installation Flow

```
1. User selects discovered device → "Install Agent"
2. UI prompts for: SSH credentials (or key), target tier, install path
3. API initiates SSH connection to target
4. Steps executed:
   a. Detect platform: uname -m, uname -s → select binary
   b. Download agent binary from Garage object storage
   c. Create /opt/hydra-agent/ directory
   d. Write configuration file (API URL, registration token)
   e. Install systemd service (or equivalent for target OS)
   f. Start agent service
   g. Verify agent contacts API (registration handshake)
5. Stream progress via WebSocket to install wizard UI
6. On success: discovered_node.matchedNodeId set, node created
```

### 19.3 Proxmox Exec Installation Flow

```
1. User selects Proxmox VM/LXC → "Install Agent"
2. API routes through Proxmox plugin driver
3. Plugin calls Proxmox API:
   - For LXC: POST /nodes/{pve_node}/lxc/{vmid}/exec
   - For VM:  POST /nodes/{pve_node}/qemu/{vmid}/agent/exec
4. Same installation steps as SSH but via Proxmox exec channel
5. No SSH credentials needed — uses Proxmox API authentication
```

---

## 20. Plugin & Integration Architecture

### 20.1 Design Philosophy

Integrations are **provider-scoped** — each integration targets a specific tool/platform rather than grouping by behavior category. Docker ≠ Podman. pfSense ≠ OPNsense. This creates cleaner driver implementations and avoids behavioral abstraction leaks.

### 20.2 Six Integration Touchpoints

Every plugin can implement one or more of these touchpoints:

| # | Touchpoint | Purpose | Example |
|---|---|---|---|
| 1 | **Profile Enrichment** | Add data to node profiles during collection | Docker adds container inventory to profile |
| 2 | **Discovery Provider** | Contribute to network discovery scanning | UniFi provides connected client list |
| 3 | **Command Provider** | Add commands to the command catalog | Proxmox adds `vm:snapshot`, `container:migrate` |
| 4 | **Execution Handler** | Handle command execution via integration API | Docker restarts container via Docker API |
| 5 | **Topology Provider** | Contribute edges/nodes to topology graphs | Proxmox adds cluster→node relationships |
| 6 | **Workflow Block Provider** | Add custom block types for workflows | Ansible adds `run-playbook` block type |

### 20.3 Plugin Lifecycle

```
available ──▶ enabled ──▶ configured ──▶ active ──▶ error
    │              │           │            │          │
    │              │           │            │          └── Health check failed
    │              │           │            └── Config valid + health check passed
    │              │           └── User provided required configuration
    │              └── User enabled the plugin
    └── Plugin registered in system (shipped or installed)
```

### 20.4 Integration Registry (19 Integrations)

| Plugin ID | Name | Classification | Touchpoints | Tier Required |
|---|---|---|---|---|
| `plg::proxmox` | Proxmox VE | Core | 1,2,3,4,5,6 | max |
| `plg::docker` | Docker | Core | 1,3,4,5 | normal+ |
| `plg::home-assistant` | Home Assistant | Core | 1,2,3,4,5 | any (API) |
| `plg::ansible` | Ansible | Core | 3,4,6 | normal+ |
| `plg::terraform` | Terraform | Core | 3,4 | normal+ |
| `plg::prometheus` | Prometheus | Core | 1,2 | any (API) |
| `plg::podman` | Podman | Default | 1,3,4,5 | normal+ |
| `plg::unifi` | UniFi | Default | 1,2,5 | any (API) |
| `plg::pfsense` | pfSense | Default | 1,2,3,5 | any (API) |
| `plg::opnsense` | OPNsense | Default | 1,2,3,5 | any (API) |
| `plg::pihole` | Pi-hole | Default | 1,2 | any (API) |
| `plg::adguard` | AdGuard Home | Default | 1,2 | any (API) |
| `plg::portainer` | Portainer | Default | 1,3,4 | any (API) |
| `plg::truenas` | TrueNAS | Default | 1,3,5 | any (API) |
| `plg::synology` | Synology DSM | Default | 1,3 | any (API) |
| `plg::nginx-proxy-manager` | Nginx Proxy Manager | Default | 1,2 | any (API) |
| `plg::traefik` | Traefik | Default | 1,2 | any (API) |
| `plg::grafana` | Grafana | Default | 1 | any (API) |
| `plg::uptime-kuma` | Uptime Kuma | Default | 1 | any (API) |

> **For complete plugin specifications including driver implementations, configuration schemas, command contributions, and cross-plugin interactions, see the Plugin Architecture v0.4.0 and Plugin Deep Dive v0.4.1 specifications.**

### 20.5 Agent Plugin Awareness

Agents detect locally available integrations and report them to the API:

```
Agent startup:
  1. Scan for integration indicators:
     - Docker: /var/run/docker.sock exists
     - Podman: podman --version succeeds
     - Proxmox: /etc/pve exists
     - etc.
  2. Report detectedIntegrations[] in node.agent
  3. API matches detections against enabled integrations
  4. API creates integration_configs for matched node+plugin pairs
```

Max-tier agents additionally serve as **integration proxies** — the API can route requests through the agent to reach locally-accessible integration APIs:

```
API ──POST /proxy/plg::docker/containers/json──▶ Max-Tier Agent ──▶ Docker Socket
                                                     ◀── Response ──◀
```

---

## 21. Dashboard Framework

### 21.1 Board Model

Dashboards consist of boards (the canvas) containing widgets (data-bound visual components). Each user can have multiple boards with different layouts.

### 21.2 Widget System

**Widget categories (75+ types):**

| Category | Widget Examples | Source |
|---|---|---|
| **Infrastructure** | Node status card, service list, network summary, storage gauge, CPU/memory bars | Core |
| **Topology** | Mini topology graph, network map, parent-child tree | Core |
| **Operations** | Execution queue, workflow status, recent commands | Core |
| **Discovery** | Last scan summary, unregistered devices count | Core |
| **Documentation** | Stale docs count, recent changes, doc link card | Core |
| **Time Machine** | Version timeline, change sparkline | Core |
| **IoT** | Entity control card, area summary, sensor reading | Core |
| **Notification** | Alert list, notification count badge | Core |
| **Plugin** | Docker container grid, Proxmox VM list, HA area card | Plugin-contributed |
| **Custom** | Markdown card, iframe embed, static text | Core |

### 21.3 Widget Data Binding

Each widget declares a `dataSource` that specifies how to fetch its data:

```json
{
  "widgetType": "node-status-card",
  "dataSource": {
    "type": "api-query",
    "endpoint": "/nodes/{nodeId}",
    "params": { "nodeId": "proxmox-01" },
    "refreshInterval": 60
  }
}
```

The dashboard framework resolves data sources at render time. Widgets with real-time needs subscribe via WebSocket channels.

### 21.4 Layout Engine

Boards use `react-grid-layout` with a configurable column grid (6, 8, or 12 columns). Widget positions are stored as `{x, y, w, h}` grid coordinates. Responsive breakpoints adapt layouts for different screen sizes.

### 21.5 Templates

Board templates provide pre-built dashboard configurations:

| Template | Description | Widgets |
|---|---|---|
| `Infrastructure Overview` | Full infrastructure health at a glance | Node grid, service summary, network map, alerts |
| `Homelab Status` | Focused on homelab use case | Docker containers, Proxmox VMs, storage, uptime |
| `IoT Home` | Smart home dashboard | Area cards, entity controls, sensor readings |
| `Operations` | Command center focus | Execution queue, recent workflows, agent status |
| `Network` | Network-centric view | Topology mini, discovery summary, VLAN table |

> **For complete dashboard framework specifications including widget registry, lifecycle management, RBAC widget filtering, kiosk mode, and real-time data binding, see the Dashboard Framework v0.5.0 specification.**

---

## 22. Living Documentation System

### 22.1 Concept

The living documentation system auto-generates 80% of infrastructure documentation from data Hydra already has (profiles, topology, services, plugins), with the remaining 20% (operational notes, recovery procedures, architecture decisions) filled in by human authoring.

All documentation is stored in **PostgreSQL** (see Section 8.3-8.6) for relational entity linking, full-text search, and vector similarity search.

### 22.2 Document Types

| Type | Generation Mode | Triggered By | Content |
|---|---|---|---|
| `runbook` | Auto/Hybrid | Node registration, profile update | Hardware specs, services, config, network, recovery |
| `architecture` | Auto | Network/topology change | Network layout, VLANs, gateways, segmentation |
| `service-catalog` | Auto | Service discovery | Service inventory per node, ports, versions, dependencies |
| `change-journal` | Auto (scheduled) | Daily/weekly cron | Profile diffs, topology changes, new services, alerts |
| `capacity-report` | Auto (scheduled) | Weekly cron | Storage trends, memory utilization, CPU headroom |
| `integration-doc` | Auto | Plugin activation | Plugin configuration, managed resources, status |
| `dr-analysis` | Auto | Topology change | Blast radius per node, dependency chains, recovery order |
| `guide` | Manual | User creates | Setup guides, procedures, notes |
| `reference` | Manual | User creates | Architecture decisions, standards, conventions |
| `troubleshooting` | Manual/Hybrid | User creates (AI assist) | Common issues, resolution steps |

### 22.3 Auto-Generation Pipeline

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   TRIGGER    │────▶│  GATHER DATA │────▶│   RENDER     │────▶│    STORE     │
│              │     │              │     │              │     │              │
│ Profile      │     │ MongoDB:     │     │ Template     │     │ PostgreSQL:  │
│ submitted    │     │ profiles,    │     │ engine       │     │ documents,   │
│ Topology     │     │ topology,    │     │ processes    │     │ sections,    │
│ changed      │     │ services     │     │ sections     │     │ entity_links │
│ Schedule     │     │              │     │              │     │              │
│ User/MCP     │     │ Plugins:     │     │ Preserves    │     │ Embedding:   │
│ request      │     │ enrichment   │     │ manual       │     │ queue new    │
│              │     │ data         │     │ overrides    │     │ content      │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

### 22.4 Hybrid Authoring

Documents support section-level authoring modes:

- **Auto sections:** Generated from templates, regenerated when source data changes
- **Manual sections:** User-written, preserved during regeneration
- **Override sections:** User replaced an auto-generated section — preserved during regeneration but flagged when source data diverges significantly

```
Example: Node runbook for proxmox-01
┌─────────────────────────────────────────────────┐
│ Section: Hardware Overview          [AUTO]       │  ← Regenerates from profile
│ Section: Network Configuration      [AUTO]       │  ← Regenerates from profile
│ Section: Services                   [AUTO]       │  ← Regenerates from services
│ Section: Docker Environment         [AUTO/PLUGIN]│  ← Docker plugin contributes
│ Section: Recovery Procedures        [MANUAL]     │  ← User-written, always kept
│ Section: Operational Notes          [MANUAL]     │  ← User-written, always kept
│ Section: Dependencies               [OVERRIDE]   │  ← User replaced auto-generated
└─────────────────────────────────────────────────┘
```

### 22.5 Staleness Detection

When a linked entity changes (profile submitted, topology updated), the API runs the staleness detection query (see Section 8.5) to flag affected documents. The web UI shows a visual indicator, and the user can trigger regeneration or wait for scheduled regeneration.

### 22.6 MCP Knowledge Base Integration

The documentation system serves double duty as the MCP service's knowledge base:

| User Query via MCP | Resolution Path |
|---|---|
| "What's my network setup?" | `search_docs(query="network architecture VLAN")` → reads network architecture doc |
| "What breaks if proxmox-01 goes down?" | `get_blast_radius(nodeId="proxmox-01")` → reads DR analysis doc |
| "What changed last week?" | `get_change_journal(period="weekly")` → reads change journal |
| "How do I recover my NAS?" | `search_docs(query="recovery NAS")` → reads runbook recovery section |

> **For complete documentation system specifications including template engine, portal experience, rich content rendering, versioning, export, and RBAC, see the Documentation System v0.5.0 specification.**

---

## 23. Embedding & Semantic Search Pipeline

### 23.1 Architecture

The embedding pipeline generates vector representations of infrastructure knowledge for semantic similarity search. It runs as a background task within hydra-api, processing content changes asynchronously.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     EMBEDDING PIPELINE                                   │
│                                                                          │
│  Content Sources (triggers)          Embedding Process                  │
│  ──────────────────────────         ─────────────────                   │
│  Profile submitted ──────┐                                               │
│  Doc generated/updated ──┤         ┌──────────────────┐                 │
│  Service discovered ─────┼────────▶│ 1. Extract text   │                 │
│  Topology changed ───────┤         │ 2. Chunk content  │                 │
│  Workflow created ───────┤         │ 3. Hash chunks    │                 │
│  Change journal entry ───┘         │ 4. Skip unchanged │                 │
│                                    │ 5. Embed via      │                 │
│                                    │    provider       │                 │
│                                    │ 6. Upsert to PG   │                 │
│                                    └──────────────────┘                 │
│                                            │                             │
│                                            ▼                             │
│                                    ┌──────────────────┐                 │
│                                    │   PostgreSQL      │                 │
│                                    │   embeddings      │                 │
│                                    │   table           │                 │
│                                    └──────────────────┘                 │
│                                                                          │
│  Query Path                                                              │
│  ──────────                                                              │
│  User/MCP query ──▶ Embed query text ──▶ pgvector similarity search    │
│                                          + optional FTS filtering       │
│                                          ──▶ Ranked results              │
└─────────────────────────────────────────────────────────────────────────┘
```

### 23.2 Content Extraction & Chunking

| Source Type | Extraction | Chunking Strategy | Typical Chunks |
|---|---|---|---|
| `doc_section` | Section markdown content | Per-section, split at ~500 tokens if too long | 3-10 per document |
| `profile_summary` | Auto-generated natural language summary from profile data | Single chunk per node | 1 per node |
| `service` | Service name + runtime + description + ports + host | Single chunk per service | 1 per service |
| `topology` | Network description + node list + edge summary | Per-network cluster | 1-5 per topology |
| `workflow` | Workflow name + description + block summaries | Single chunk per workflow | 1 per workflow |
| `change_journal` | Journal entry text | Per-entry | 1 per entry |

**Profile summary generation example:**

```python
def generate_profile_summary(node: Node, profile: Profile) -> str:
    """Generate a natural language summary of a node for embedding."""
    parts = [
        f"{node.displayName} ({node.nodeId}) is a {node.kind} {node.class_} node",
    ]
    
    if profile.hardware:
        cpu = profile.hardware.cpu
        mem = profile.hardware.memory
        parts.append(
            f"with {cpu.model} ({cpu.logicalCores} cores), "
            f"{format_bytes(mem.totalBytes)} RAM"
        )
    
    if profile.network:
        ips = [iface.ipv4[0].address for iface in profile.network.interfaces 
               if iface.ipv4]
        if ips:
            parts.append(f"on networks {', '.join(ips)}")
    
    if profile.serviceIds:
        service_names = await get_service_names(profile.serviceIds[:10])
        parts.append(f"running services: {', '.join(service_names)}")
    
    if profile.pluginData:
        for plugin_id, data in profile.pluginData.items():
            parts.append(f"with {plugin_id} integration active")
    
    return ". ".join(parts) + "."
    
# Output: "proxmox-01 (proxmox-01) is a bare-metal compute node with Intel Xeon 
# E5-2680 v4 (56 cores), 128GB RAM on networks 192.168.0.10, 10.0.0.1 running 
# services: plex-media-server, nginx-proxy-manager, pihole-dns, grafana, 
# prometheus. with plg::proxmox integration active. with plg::docker integration active."
```

### 23.3 Content Hashing (Skip Unchanged)

Each chunk is hashed before embedding. If the hash matches the existing `content_hash` in the `embeddings` table, the embedding is skipped — avoiding unnecessary API calls to the embedding provider.

```python
import hashlib

def content_hash(text: str) -> str:
    return hashlib.blake2b(text.encode(), digest_size=32).hexdigest()

async def upsert_embedding(source_type: str, source_id: str, 
                           section: str, chunk_idx: int, text: str):
    new_hash = content_hash(text)
    
    # Check if unchanged
    existing = await pg.fetchrow(
        "SELECT content_hash FROM embeddings WHERE source_type=$1 AND source_id=$2 "
        "AND source_section=$3 AND chunk_index=$4",
        source_type, source_id, section, chunk_idx
    )
    
    if existing and existing['content_hash'] == new_hash:
        return  # Content unchanged, skip embedding
    
    # Generate embedding
    vector = await embedding_provider.embed([text])
    
    # Upsert
    await pg.execute("""
        INSERT INTO embeddings (source_type, source_id, source_section, chunk_index,
                               content_text, content_hash, embedding, metadata)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (source_type, source_id, source_section, chunk_index)
        DO UPDATE SET content_text=$5, content_hash=$6, embedding=$7, 
                      metadata=$8, updated_at=NOW()
    """, source_type, source_id, section, chunk_idx, text, new_hash, vector[0], metadata)
```

### 23.4 Query Pipeline

Semantic search supports two modes:

**Pure semantic search:**
```sql
-- "Which machine could handle ML training?"
SELECT source_type, source_id, content_text,
       1 - (embedding <=> $1) AS similarity
FROM embeddings
WHERE 1 - (embedding <=> $1) > 0.7  -- similarity threshold
ORDER BY embedding <=> $1
LIMIT 10;
```

**Hybrid search (semantic + keyword):**
```sql
-- Combine vector similarity with full-text relevance
WITH semantic AS (
    SELECT source_type, source_id, content_text,
           1 - (embedding <=> $1) AS semantic_score
    FROM embeddings
    WHERE 1 - (embedding <=> $1) > 0.5
    ORDER BY embedding <=> $1 LIMIT 50
),
keyword AS (
    SELECT 'doc_section' AS source_type, doc_id AS source_id,
           ts_rank(search_vector, plainto_tsquery('english', $2)) AS keyword_score
    FROM document_sections
    WHERE search_vector @@ plainto_tsquery('english', $2)
)
SELECT s.source_type, s.source_id, s.content_text,
       (0.7 * s.semantic_score + 0.3 * COALESCE(k.keyword_score, 0)) AS combined_score
FROM semantic s
LEFT JOIN keyword k ON s.source_type = k.source_type AND s.source_id = k.source_id
ORDER BY combined_score DESC
LIMIT 10;
```

### 23.5 Provider Configuration

Embedding provider is configured in `system_settings` (MongoDB):

```json
{
  "settingsId": "global",
  "embedding": {
    "provider": "ollama",
    "model": "nomic-embed-text",
    "baseUrl": "http://ollama:11434",
    "dimension": 768,
    "batchSize": 32,
    "maxRetries": 3,
    "rateLimitPerMinute": 100
  }
}
```

**Provider-specific configuration:**

| Provider | Config Fields | Dimension Options |
|---|---|---|
| `openai` | model, apiKey | 1536 (ada-002), 256/512/1536/3072 (text-embedding-3-*) |
| `ollama` | model, baseUrl | 768 (nomic-embed-text), 1024 (mxbai-embed-large) |
| `anthropic` | model, apiKey | 1024 (voyage-3), 1536 (voyage-code-3) |

**Provider change migration:** When the provider or model changes, a background job re-embeds all content. The `embeddings` table is rebuilt in-place (old embeddings are overwritten as new ones are generated). During migration, search falls back to keyword-only mode.

---

## 24. MCP Service

### 24.1 Overview

hydra-mcp exposes Hydra's infrastructure knowledge as MCP tools, resources, and prompts for consumption by AI models. It connects to hydra-api for data and PostgreSQL for semantic search.

### 24.2 Tool Catalog

**Infrastructure Query Tools:**

| Tool | Description | Source |
|---|---|---|
| `list_nodes` | List nodes with filters (class, type, status, tags) | MongoDB |
| `get_node` | Get detailed node info including agent status | MongoDB |
| `get_profile` | Get latest or specific version profile for a node | MongoDB |
| `compare_profiles` | Compare two profiles (Time Machine) | MongoDB |
| `list_services` | List services with filters (runtime, status, node) | MongoDB |
| `get_service` | Get detailed service info | MongoDB |
| `list_networks` | List network definitions | MongoDB |
| `get_topology` | Get current or historical topology | MongoDB |
| `get_timeline` | Get event timeline for a node | MongoDB |
| `search_infrastructure` | Semantic search across all infrastructure knowledge | PostgreSQL (pgvector) |

**Documentation Tools:**

| Tool | Description | Source |
|---|---|---|
| `search_docs` | Search documentation (keyword + semantic) | PostgreSQL |
| `get_doc` | Retrieve a specific document | PostgreSQL |
| `get_doc_section` | Retrieve a specific section | PostgreSQL |
| `generate_doc` | Trigger auto-generation | PostgreSQL + MongoDB |
| `create_doc` | Create manual document | PostgreSQL |
| `update_doc_section` | Update a manual/override section | PostgreSQL |
| `list_stale_docs` | List documents with stale sections | PostgreSQL |
| `get_blast_radius` | Get blast radius analysis for a node | PostgreSQL |
| `get_change_journal` | Get change journal for a period | PostgreSQL |

**Control Tools (internal MCP only):**

| Tool | Description | Source |
|---|---|---|
| `execute_command` | Submit a command execution | MongoDB + Redis |
| `run_workflow` | Trigger a saved workflow | MongoDB + Redis |
| `get_execution_status` | Check execution progress | MongoDB |
| `cancel_execution` | Cancel a pending/running execution | MongoDB + Redis |
| `scan_network` | Trigger network discovery scan | MongoDB |
| `list_discoveries` | List discovered devices | MongoDB |
| `register_discovered` | Register a discovered device as a node | MongoDB |

**Dashboard Tools:**

| Tool | Description | Source |
|---|---|---|
| `list_boards` | List dashboard boards | MongoDB |
| `create_board` | Create a new board with widgets | MongoDB |
| `get_board` | Get board configuration | MongoDB |

### 24.3 TOON Format

MCP responses use TOON (Textual Object-Oriented Notation) for LLM-friendly output:

```
=== NODE: proxmox-01 ===
Class: compute | Type: physical | Kind: bare-metal
Status: active | Agent: max (online, v0.3.0)

Hardware:
  CPU: Intel Xeon E5-2680 v4, 2× sockets, 56 logical cores
  RAM: 128 GB DDR4-2400 ECC
  Storage: 480 GB SSD (INTEL SSDSC2BB48)

Network:
  Primary IP: 192.168.0.10/24 (vmbr0)
  Gateway: 192.168.0.1
  Networks: homenet-lan

Children (3 LXCs, 1 VM):
  • pihole (LXC 100) — running, 1 CPU, 512 MB
  • nginx-proxy (LXC 101) — running, 2 CPU, 1 GB
  • monitoring (LXC 102) — running, 2 CPU, 2 GB
  • dev-vm (VM 200) — running, 8 CPU, 16 GB

Services (5):
  • pveproxy (systemd, :8006)
  • sshd (systemd, :22)
  • pihole-FTL (systemd on pihole, :53, :80)
  • nginx (docker on nginx-proxy, :80, :443)
  • prometheus (docker on monitoring, :9090)
```

### 24.4 Source-Aware Permissions

MCP clients are classified as internal (web chat) or external (Claude Desktop, VS Code):

| Capability | Internal | External |
|---|---|---|
| All read operations | ✓ | ✓ |
| Semantic search | ✓ | ✓ |
| Documentation CRUD | ✓ | ✓ |
| Direct command execution | ✓ | ✗ |
| Saved workflow execution | ✓ | ✓ (if mcpCallable) |
| Network scanning | ✓ | ✗ |
| Workflow building | ✓ | ✗ |

### 24.5 MCP Resources

| Resource URI | Content | Type |
|---|---|---|
| `hydra://nodes` | List of all active nodes | JSON |
| `hydra://nodes/{nodeId}` | Node detail with latest profile | JSON |
| `hydra://topology/network` | Current network topology | JSON |
| `hydra://topology/infrastructure` | Current infrastructure topology | JSON |
| `hydra://docs/{docId}` | Document content | Markdown |
| `hydra://services` | Service catalog | JSON |
| `hydra://networks` | Network definitions | JSON |

### 24.6 MCP Prompts

| Prompt | Description | Parameters |
|---|---|---|
| `infrastructure_overview` | Complete infrastructure summary | None |
| `capacity_planning` | Analyze capacity across nodes | nodeIds (optional), resource_type |
| `dependency_analysis` | Analyze dependencies for a node/service | entityId |
| `network_analysis` | Analyze network topology and segmentation | networkId (optional) |
| `troubleshoot` | Guided troubleshooting for a node/service | entityId, symptom |

---

## 25. Web Service Architecture

### 25.1 Overview

hydra-web is a React 18 / TypeScript application providing the complete user interface for Hydra. Phase 2 introduces a full UI remodel to support the expanded feature set.

### 25.2 Technology Stack

| Concern | Technology |
|---|---|
| Framework | React 18 with TypeScript |
| Build | Vite |
| Styling | Tailwind CSS |
| Components | shadcn/ui |
| State | Zustand (global) + TanStack Query (server) |
| Routing | React Router v6 |
| Visualization | ReactFlow (topology), D3.js (charts) |
| Layout | react-grid-layout (dashboards) |
| Real-time | WebSocket (native) |
| Rich Text | MDX-based renderer (documentation portal) |

### 25.3 Navigation Architecture

```
Primary Navigation (Sidebar):
├── Dashboard         → /dashboard (default board or board selector)
├── Infrastructure    → /infrastructure
│   ├── Nodes         → /infrastructure/nodes
│   ├── Services      → /infrastructure/services
│   ├── Networks      → /infrastructure/networks
│   └── Groups        → /infrastructure/groups
├── Topology          → /topology
├── Discovery         → /discovery
├── Command Center    → /commands
│   ├── Executions    → /commands/executions
│   └── Workflows     → /commands/workflows
├── Documentation     → /docs
├── Time Machine      → /time-machine
├── Integrations      → /integrations
├── Home              → /home (family/IoT - role-restricted)
└── Administration    → /admin (admin-only)
    ├── Users & Roles
    ├── Tokens
    ├── Audit Log
    ├── Agent Binaries
    └── System Settings
```

### 25.4 Role-Based UI Adaptation

| Role | Visible Navigation | Hidden |
|---|---|---|
| **Admin** | Everything | Nothing |
| **Operator** | Dashboard, Infrastructure, Topology, Discovery, Command Center, Docs, Time Machine, Integrations, Home | Administration |
| **Viewer** | Dashboard, Infrastructure (read-only), Topology, Docs, Time Machine | Discovery, Command Center, Integrations, Admin, Home |
| **Family** | Home (IoT), Dashboard (IoT board) | Everything else |

### 25.5 Key UI Patterns

**Global Search (Cmd+K):** Command palette searching across all entity types via PostgreSQL `search_index`. Results link directly to entity detail pages.

**Entity Detail System:** Universal detail panel pattern — every entity (node, service, network, group) opens in a consistent detail view with tabs, related entities, and contextual actions.

**Real-Time Updates:** WebSocket connection provides live updates for: execution status changes, discovery scan progress, notification delivery, agent status changes, dashboard widget refresh.

**MCP Chat Panel:** Slide-out panel on the right side of the screen. Persistent across navigation. Auto-scopes context to the current page (node detail → scoped to that node).

Detailed page specifications, component architecture, responsive design, accessibility, and state management are defined in **Hydra Web UI/UX Remodeling Specification v0.5.0**.

---

## 26. Authentication & RBAC

### 26.1 Authentication Methods

| Method | Use Case | Header |
|---|---|---|
| **JWT Bearer** | Web UI, MCP internal | `Authorization: Bearer <access_token>` |
| **API Key** | Agents, automation, MCP external | `X-API-Key: <api_key>` |
| **Registration Token** | Node registration | `X-Registration-Token: <token>` |

### 26.2 JWT Structure

```json
{
  "sub": "user_abc123",
  "role": "admin",
  "permissions": ["*:*"],
  "source": "web",
  "iat": 1708905600,
  "exp": 1708909200
}
```

Access tokens expire after 1 hour. Refresh tokens expire after 7 days.

### 26.3 Role Hierarchy

| Role | Level | Max Accounts | Base Permissions |
|---|---|---|---|
| `admin` | 100 | 3 | `*:*` (full access) |
| `operator` | 50 | 10 | Manage nodes, profiles, services, groups, networks, commands, docs |
| `viewer` | 25 | Unlimited | Read-only access to infrastructure data |
| `family` | 10 | Unlimited | IoT read + control, limited dashboard |
| `agent` | 0 | Unlimited | Write own profile, poll own commands, refresh own key |

### 26.4 Bootstrap Flow

First admin creation follows a special bootstrap path:

```
1. Fresh installation — no users exist
2. POST /api/v1/auth/bootstrap with admin credentials
3. First admin account created
4. Bootstrap endpoint permanently disabled
5. Subsequent users created via admin invitation (registration tokens)
```

### 26.5 Node Registration Flow

```
1. Admin/Operator creates registration token (scoped to role, expiry)
2. Agent uses token to register: POST /api/v1/nodes/register
3. API validates token, creates node with status=pending
4. API issues API key for the agent
5. Agent stores key, begins profiling
6. Admin can approve or the node auto-activates based on token settings
```

### 26.6 MCP Client Registration

```json
{
  "clientId": "claude-desktop-main",
  "name": "Claude Desktop",
  "type": "external",
  "trusted": true,
  "capabilities": ["read", "workflow-run"]
}
```

External MCP clients cannot execute commands directly — they can only invoke saved workflows that have `mcpCallable: true`.

---

## 27. Notification System

### 27.1 Notification Tiers

| Tier | Severity | Examples | Delivery |
|---|---|---|---|
| **Critical** | System-threatening | API database unreachable, agent crash | Toast + sound + badge + optional email |
| **Warning** | Attention needed | Agent offline 30min, disk > 90%, execution failed | Toast + badge |
| **Info** | Informational | Profile updated, scan completed, doc regenerated | Badge only |
| **Success** | Positive confirmation | Execution completed, workflow finished, agent installed | Toast (brief) |
| **System** | Operational | Scheduled maintenance, version update available | Banner |

### 27.2 Notification Features

- **Deduplication:** Same-source notifications within a window are grouped
- **Escalation:** Info → Warning → Critical if condition persists
- **Auto-resolve:** Notifications resolve when condition clears (e.g., agent comes back online)
- **Role-based:** Family users only see IoT-related notifications
- **WebSocket delivery:** Real-time push to connected web clients

---

## 28. AI Configuration & Chat

### 28.1 Multi-Provider Support

Hydra supports configuring multiple LLM providers for the web chat interface:

| Provider | Models | Configuration |
|---|---|---|
| Anthropic | Claude Sonnet, Claude Haiku | API key, model selection |
| OpenAI | GPT-4o, GPT-4o-mini | API key, model selection |
| Ollama | Any local model | Base URL, model name |
| Custom | OpenAI-compatible API | Base URL, API key, model |

### 28.2 Chat Architecture

Chat sessions connect to the MCP service with full internal permissions:

```
Web Client → WebSocket → hydra-api → hydra-mcp → LLM Provider
                                        ↕
                                   MCP Tools/Resources
                                        ↕
                                   MongoDB + PostgreSQL
```

Chat sessions are organized into projects. Messages include tool call records for transparency. The chat panel supports context-awareness based on the current page.

---

## 29. Known Services

The `known_services` collection provides a registry of recognized services for enrichment during service discovery:

```json
{
  "knownServiceId": "ks-pihole-ftl",
  "runtime": "systemd",
  "name": "pihole-FTL",
  "displayName": "Pi-hole",
  "description": "Network-level ad and tracker blocking",
  "matchPatterns": {
    "namePatterns": ["pihole-FTL", "pihole"],
    "portSignatures": [4711],
    "processPatterns": ["pihole-FTL"]
  },
  "tags": ["dns", "ad-blocking", "network"],
  "icon": "pihole",
  "documentationUrl": "https://docs.pi-hole.net"
}
```

Known services are seeded at API startup and can be extended by users and plugins.

---

## 30. Settings Management

### 30.1 System Settings (Singleton)

```json
{
  "smtp": { "host": "", "port": 587, "username": "", "encryption": "tls" },
  "objectStorage": { "endpoint": "", "bucket": "hydra-binaries", "accessKey": "", "secretKey": "" },
  "embedding": {
    "provider": "ollama",
    "model": "nomic-embed-text",
    "baseUrl": "http://ollama:11434",
    "dimension": 768,
    "batchSize": 32
  },
  "discovery": { "defaultPortTier": "tier1", "maxConcurrentScans": 3 },
  "profiling": { "defaultInterval": 86400, "retentionDays": 365 },
  "documentation": { "autoRegenerate": true, "regenIntervalHours": 24, "changeJournalFrequency": "weekly" },
  "audit": { "retentionMonths": 12, "partitionAutoCreate": true },
  "defaults": { "agentTier": "normal", "profileLevel": "neutral" }
}
```

### 30.2 User Settings

Per-user preferences for UI, notification delivery, default views, and dashboard selections.

---

## 31. Deployment

### 31.1 Docker Compose Stack

```yaml
version: '3.8'
services:
  hydra-api:
    image: hydra/api:0.5.0
    ports: ["8080:8080"]
    environment:
      MONGODB_URI: mongodb://mongo:27017/hydra
      POSTGRESQL_DSN: postgresql://hydra:password@postgres:5432/hydra
      REDIS_URL: redis://redis:6379
      JWT_SECRET: ${JWT_SECRET}
    depends_on: [mongo, postgres, redis]

  hydra-mcp:
    image: hydra/mcp:0.5.0
    ports: ["8081:8081"]
    environment:
      HYDRA_API_URL: http://hydra-api:8080
      POSTGRESQL_DSN: postgresql://hydra:password@postgres:5432/hydra
    depends_on: [hydra-api]

  hydra-web:
    image: hydra/web:0.5.0
    ports: ["3000:3000"]
    environment:
      VITE_API_URL: http://hydra-api:8080
      VITE_WS_URL: ws://hydra-api:8080

  mongo:
    image: mongo:7
    ports: ["27017:27017"]
    volumes: ["mongo-data:/data/db"]

  postgres:
    image: pgvector/pgvector:pg16
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: hydra
      POSTGRES_USER: hydra
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes: ["postgres-data:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  ollama:
    image: ollama/ollama:latest
    ports: ["11434:11434"]
    volumes: ["ollama-data:/root/.ollama"]
    profiles: ["local-embeddings"]

volumes:
  mongo-data:
  postgres-data:
  ollama-data:
```

### 31.2 Production Checklist

| Item | Details |
|---|---|
| TLS termination | Reverse proxy (nginx/Caddy) for HTTPS |
| MongoDB auth | Enable authentication, create dedicated user |
| PostgreSQL auth | Strong password, SSL connections |
| Redis auth | Set requirepass, consider TLS |
| JWT secret | Generate strong random secret, rotate periodically |
| Backups | MongoDB: mongodump scheduled; PostgreSQL: pg_dump scheduled |
| Alembic migrations | Run on API startup (`alembic upgrade head`) |
| pgvector extension | Ensure `CREATE EXTENSION vector;` on database |
| Embedding provider | Configure Ollama (local) or API keys (cloud) |
| Object storage | Configure Garage for agent binary distribution |
| Monitoring | Health endpoints: `/health` on all services |
| Log aggregation | JSON structured logs, centralized collection |

---

## 32. Testing Strategy

### 32.1 Test Categories

| Category | Scope | Tool |
|---|---|---|
| Unit tests | Individual functions, data models | pytest (API/MCP), cargo test (Agent) |
| Integration tests | API endpoints, database operations | pytest + test containers |
| E2E tests | Full user workflows | Playwright (Web) |
| Contract tests | Agent ↔ API payload validation | Schema validation |
| Load tests | Performance under scale | Locust |

### 32.2 Critical Test Paths

| Path | Tests |
|---|---|
| Node registration → profile → topology | End-to-end flow: register, submit profile, verify topology includes node |
| Command → execution → result | Submit command, verify queue, mock agent poll, verify result |
| Profile → doc generation → embedding | Submit profile, verify doc regenerated, verify embeddings updated |
| Discovery scan → classification → registration | Trigger scan, verify discoveries stored, register one, verify node created |
| Workflow → run → multi-step execution | Run workflow, verify block sequencing, conditional branching |
| Semantic search → results | Embed content, query with natural language, verify relevant results returned |
| RBAC enforcement | Verify each role can only access permitted endpoints |
| Time Machine → historical state | Submit multiple profiles, query at historical timestamps, verify correct state |
| PostgreSQL ↔ MongoDB consistency | Verify entity changes in MongoDB trigger staleness in PostgreSQL docs |

---

## 33. Technical Concerns & Mitigations

### 33.1 Security

| Concern | Mitigation |
|---|---|
| Command injection via execution | Commands are system-defined with parameterized translations. No raw shell input. |
| MCP external client escalation | Source-aware permissions. External clients cannot execute commands directly. |
| Agent impersonation | API key authentication per-agent. Keys scoped to specific node. |
| Credential exposure in profiles | Hash-only for sensitive configs. No plaintext secrets in profile data. |
| PostgreSQL injection | Parameterized queries via asyncpg. No raw SQL construction. |
| Embedding content leakage | Embeddings stored per-user context. RBAC applied to search results. |

### 33.2 Reliability

| Concern | Mitigation |
|---|---|
| MongoDB downtime | Core operations fail gracefully. API returns 503 with degradation notice. |
| PostgreSQL downtime | Docs/search/audit degrade. Core profiling continues. MCP falls back to keyword search. |
| Redis downtime | Execution queue fails. Polling agents wait. Profile submission continues (queue bypassed). |
| Embedding provider outage | Fallback to keyword-only search. New content queued for embedding when provider recovers. |
| Agent unreachable (max-tier) | Fallback from direct to poll-based execution. Scan delegation retries. |
| Plugin health failure | Plugin enters error state. Core functionality unaffected. Auto-recovery attempts. |

### 33.3 Scalability

| Concern | Mitigation |
|---|---|
| Large profile history | MongoDB TTL indexes or manual archival for profiles older than retention period |
| Embedding table growth | Content hash dedup prevents redundant embeddings. Old embeddings cleaned on source deletion. |
| Audit log volume | Time-partitioned tables. Old partitions detachable/archivable. |
| Search index size | Materialized index with periodic refresh. Entity deletion cascades to index. |
| Topology computation cost | Incremental diff from previous topology. Full rebuild only on schema changes. |
| Concurrent discovery scans | Rate-limited to `maxConcurrentScans` (default: 3). |

---

## 34. Appendices

### 34.1 Collection & Table Summary

**MongoDB Collections (~35):**

| Category | Collections |
|---|---|
| Core | nodes, profiles, profile_meta, services, groups, networks, topologies |
| Operations | executions, workflows, workflow_runs, discovered_nodes, discovery_scans, discovery_exclusions |
| Content | boards, board_templates, chat_projects, chat_sessions, chat_messages, notifications, notification_reads |
| System | users, users_pending, tokens, api_keys, password_reset_tokens, known_services, integrations, integration_configs, ai_models, global_api_keys, mcp_servers, mcp_clients, user_settings, system_settings |

**PostgreSQL Tables (7):**

| Category | Tables |
|---|---|
| Search & Intelligence | embeddings, search_index |
| Documentation | documents, document_sections, document_entity_links, document_versions |
| Compliance | audit_log (time-partitioned) |

### 34.2 ID Format Reference

| Entity | Format | Example |
|---|---|---|
| Node | `<user-chosen>` | `proxmox-01`, `opnsense.gw` |
| Profile | `prof-<nanoid>` | `prof-abc123xyz` |
| Service | `svc-<name>-<4hash>` | `svc-nginx-c3d4` |
| Group | `<user-chosen>` | `production-servers` |
| Network | `<auto-or-user>` | `homenet-lan`, `vlan-20-net` |
| Topology | `topo-<mode>-<timestamp>` | `topo-network-20260224T143022Z` |
| Execution | `exec_<nanoid>` | `exec_a1b2c3d4` |
| Workflow | `wf_<user-chosen>` | `wf_safe_restart` |
| Workflow Run | `wfr_<nanoid>` | `wfr_x7y8z9` |
| Board | `board_<nanoid>` | `board_m4n5o6` |
| Discovery | `disc::mac::<mac>` | `disc::mac::dc-a6-32-ab-cd-ef` |
| Scan | `scan_<nanoid>` | `scan_p1q2r3` |
| Plugin | `plg::<provider>` | `plg::docker`, `plg::proxmox` |
| Document | `doc::<type>::<entity>` | `doc::runbook::proxmox-01` |
| User | `user_<nanoid>` | `user_s4t5u6` |
| MCP Client | `<user-chosen>` | `claude-desktop-main` |
| API Key | `hk_<random>` | `hk_a1b2c3d4e5f6` |

### 34.3 Environment Variables

| Variable | Service | Description | Default |
|---|---|---|---|
| `MONGODB_URI` | API | MongoDB connection string | `mongodb://localhost:27017/hydra` |
| `POSTGRESQL_DSN` | API, MCP | PostgreSQL connection string | `postgresql://hydra:password@localhost:5432/hydra` |
| `REDIS_URL` | API | Redis connection string | `redis://localhost:6379` |
| `JWT_SECRET` | API | JWT signing secret | (required) |
| `HYDRA_API_URL` | MCP, Agent | API base URL | `http://localhost:8080` |
| `VITE_API_URL` | Web | API URL for frontend | `http://localhost:8080` |
| `VITE_WS_URL` | Web | WebSocket URL | `ws://localhost:8080` |
| `LOG_LEVEL` | All | Logging level | `info` |
| `LOG_FORMAT` | All | Log format | `json` |

### 34.4 Version History

| Version | Date | Changes |
|---|---|---|
| 0.1.0 | 2025-12-01 | Initial specification — Core profiling, topology, Time Machine |
| 0.2.0 | 2026-01-15 | Added services, groups, RBAC, notifications, MCP service |
| 0.3.0 | 2026-02-15 | Expanded data models, auth restructure, known services, settings |
| 0.4.0 | 2026-02-20 | Phase 2 feature specifications (separate documents) |
| 0.5.0 | 2026-02-25 | **Canonical merge:** Absorbed Phase 2 spec, Plugin Architecture, Dashboard Framework, Documentation System, Web UI Remodel into single document. Added dual-database architecture (MongoDB + PostgreSQL/pgvector). Added embedding pipeline, semantic search, global search index, audit log with time-partitioning. |

---

*End of Hydra Technical Documentation v0.5.0*
