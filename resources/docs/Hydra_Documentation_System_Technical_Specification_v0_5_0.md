# Hydra Documentation System Technical Specification

> **Version:** 0.5.0  
> **Last Updated:** 2026-02-22  
> **Status:** Technical Specification — Living Documentation System, Auto-Generation Pipeline, Hybrid Authoring, Portal Experience, MCP Knowledge Base, Template Engine  
> **Dependencies:** Phase 2 Technical Specification (Commands, Agent Architecture), Plugin Architecture v0.4.0 (All 19 Integrations), Technical Documentation v0.3.0 (Data Model, Profiles, Topology), API Reference v0.3.0 (Existing `/docs` endpoints)

---

## Table of Contents

1. [Document Overview](#1-document-overview)
2. [System Architecture](#2-system-architecture)
3. [Document Types & Taxonomy](#3-document-types--taxonomy)
4. [Auto-Generation Pipeline](#4-auto-generation-pipeline)
5. [Template Engine](#5-template-engine)
6. [Hybrid Authoring Model](#6-hybrid-authoring-model)
7. [Staleness Detection & Regeneration](#7-staleness-detection--regeneration)
8. [Document Portal Experience](#8-document-portal-experience)
9. [Navigation Tree & Information Architecture](#9-navigation-tree--information-architecture)
10. [Rich Content Rendering](#10-rich-content-rendering)
11. [Search & Discovery](#11-search--discovery)
12. [Versioning & Change Tracking](#12-versioning--change-tracking)
13. [MCP Knowledge Base Integration](#13-mcp-knowledge-base-integration)
14. [Plugin-Contributed Documentation](#14-plugin-contributed-documentation)
15. [Entity-Linked Context Panels](#15-entity-linked-context-panels)
16. [Export & Offline Access](#16-export--offline-access)
17. [RBAC & Visibility](#17-rbac--visibility)
18. [API Specification](#18-api-specification)
19. [Data Model](#19-data-model)
20. [hydra-web Implementation](#20-hydra-web-implementation)
21. [Implementation Roadmap](#21-implementation-roadmap)
22. [Appendices](#22-appendices)

---

## 1. Document Overview

### 1.1 Purpose

This document specifies Hydra's living documentation system — a framework that combines auto-generated infrastructure documentation with manual authoring, versioning, and AI-queryability to produce a continuously-updated knowledge base about the user's homelab, smart home, and infrastructure environment.

Unlike a static documentation site or wiki, Hydra's documentation system is **reactive to infrastructure state**. When a new node is profiled, a runbook is generated. When the topology changes, network architecture docs are flagged stale and regenerated. When a user writes a setup guide, it lives alongside generated docs as a first-class page with the same search, navigation, and MCP accessibility.

| Aspect | Scope |
|--------|-------|
| **Document Types** | Node runbooks, network architecture, service catalogs, change journals, capacity reports, integration docs, DR analysis, custom/manual docs |
| **Auto-Generation** | Template-based pipeline sourcing from profiles, topology, services, and plugin data |
| **Hybrid Authoring** | Section-level merge of auto-generated and manually-authored content |
| **Portal Experience** | Fumadocs-quality embedded documentation site with sidebar navigation, search, rich rendering |
| **MCP Integration** | Bidirectional — AI reads docs for knowledge, AI writes docs via tool calls |
| **Versioning** | Doc versions linked to infrastructure state via Time Machine |
| **Plugin Integration** | Each enabled integration contributes documentation sections and templates |

### 1.2 Design Principles

**Documentation Writes Itself**
The system's primary value is that 80% of infrastructure documentation is auto-generated from data Hydra already has. Profile data, topology edges, service discovery, plugin enrichment — these are the raw materials. Templates transform them into human-readable (and AI-readable) documentation. The remaining 20% — operational notes, recovery procedures, architecture decisions — is where human authoring fills in.

**Generated and Manual Are Peers**
A user reading the documentation portal cannot distinguish between an auto-generated node runbook and a manually-written setup guide without looking at the metadata. Both live in the same navigation tree, both use the same rich rendering, both are searchable, both are versioned, both are queryable by MCP.

**Documents Are Entity-Linked**
Every document is linked to the infrastructure entities it describes. A node runbook is linked to its node. A network architecture doc is linked to its networks. A service catalog entry is linked to its service. This linking enables contextual navigation (from node detail → runbook), entity-aware search ("find docs about proxmox-01"), and staleness detection (when the linked entity changes, the doc is potentially stale).

**Living, Not Static**
Documents have a lifecycle: generated → current → stale → regenerated. Change journals accumulate automatically. Capacity reports update periodically. The documentation portal is never "done" — it evolves with the infrastructure.

**Documentation Is a Knowledge Base**
The portal is simultaneously a human-facing documentation site and a structured knowledge base for the MCP service. Every document contributes to the AI's understanding of the user's infrastructure. Natural language queries against the MCP resolve by searching documentation content, making the documentation investment doubly valuable.

### 1.3 Component Responsibility Matrix

| Concern | hydra-api | hydra-web | hydra-mcp | hydra-agent |
|---------|-----------|-----------|-----------|-------------|
| Document CRUD | Storage, validation, versioning | Editor, portal viewer | Doc tools (create, query, update) | N/A |
| Auto-Generation | Template engine, pipeline orchestration, scheduling | Generation trigger UI | "Document my setup" tool calls | Profile data (indirect) |
| Search | Full-text index, faceted search | Search UI, results page | Knowledge base queries | N/A |
| Rendering | Serves raw content + metadata | MDX-style rich renderer | N/A | N/A |
| Staleness | Change detection, flag management | Stale indicators, regen buttons | N/A | Triggers via profile submission |
| Navigation Tree | Computes tree from doc metadata | Sidebar tree renderer | N/A | N/A |
| Versioning | Version storage, diff computation | Version browser, diff viewer | Version query tools | N/A |

### 1.4 Practical Use Cases

| Use Case | Persona | What Happens |
|----------|---------|-------------|
| **New node registered** | System | Auto-generates node runbook from profile data, services, topology position. Appears in portal immediately. |
| **"What's my network setup?"** | Homelabber via MCP | MCP searches generated network architecture docs. Returns structured answer citing subnet layout, VLAN assignments, gateway config. |
| **Network topology changes** | System | Network architecture docs flagged stale. Regeneration queued. User can trigger immediate regen or wait for scheduled regen. |
| **Writing a setup guide** | Homelabber | Creates new manual doc via portal editor. Appears alongside generated docs in the same navigation tree. Full rich text editing. |
| **"What breaks if proxmox-01 goes down?"** | Homelabber via MCP | MCP reads auto-generated DR/blast radius doc for proxmox-01. Returns affected VMs, services, and dependency chain. |
| **Weekly infrastructure report** | System (scheduled) | Change journal auto-generated: profile diffs, topology changes, new services discovered, containers updated, integration health changes. |
| **Capacity planning review** | Homelabber | Opens capacity report doc. Sees per-node storage fill rates, RAM utilization trends, CPU headroom. Estimates from profile history. |
| **Docker plugin enabled** | System | Auto-generates Docker integration documentation section: connected hosts, container summary, compose projects, volume inventory. |
| **Viewing a node detail page** | Homelabber | Contextual panel shows link to node's runbook, last doc update time. Click opens full runbook in portal. |
| **Exporting for compliance** | Small business operator | Exports full infrastructure documentation as PDF bundle. Includes network architecture, service catalog, security configuration. |

---

## 2. System Architecture

### 2.1 Architectural Overview

The documentation system is a layered pipeline where infrastructure data flows through templates to produce documents that are served through a portal and searchable by both humans and AI.

```
┌──────────────────────────────────────────────────────────────────────┐
│                        PORTAL LAYER                                 │
│  Navigation Tree · Rich Renderer · Search UI · Editor · Export      │
├──────────────────────────────────────────────────────────────────────┤
│                        KNOWLEDGE LAYER                              │
│  Full-Text Search Index · Entity Linking · MCP Resource Exposure    │
├──────────────────────────────────────────────────────────────────────┤
│                        AUTHORING LAYER                              │
│  Manual Editor · Section Merge Engine · Version Control             │
├──────────────────────────────────────────────────────────────────────┤
│                        GENERATION LAYER                             │
│  Template Engine · Generation Pipeline · Staleness Detector         │
├──────────────────────────────────────────────────────────────────────┤
│                        DATA LAYER (existing)                        │
│  Profiles · Topology · Services · Integrations · Commands · Nodes   │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 Generation Data Flow

```
Infrastructure event (new profile, topology change, plugin sync)
    │
    ▼
Staleness detector identifies affected documents
    │
    ▼
Generation pipeline triggered (immediate, scheduled, or manual)
    │
    ▼
Template engine loads template for document type
    │
    ▼
Data resolver fetches required data from API collections
    │  (profiles, nodes, services, topology, pluginData)
    ▼
Template renders data into structured markdown sections
    │
    ▼
Merge engine combines generated sections with any manual overrides
    │
    ▼
Document saved to MongoDB with new version
    │
    ▼
Search index updated
    │
    ▼
Portal navigation tree refreshed
```

### 2.3 Document Content Model

A document is not a monolithic blob of markdown. It's a **section-structured document** where each section has metadata about its source (generated or manual), its data dependencies, and its staleness state.

```json
{
  "docId": "doc::runbook::proxmox-01",
  "title": "Node Runbook: proxmox-01",
  "sections": [
    {
      "sectionId": "overview",
      "title": "Overview",
      "source": "generated",
      "templateRef": "tmpl::runbook::overview",
      "dataFingerprint": "a3f2c8...",
      "content": "## Overview\n\nproxmox-01 is a physical compute node...",
      "lastGenerated": "2026-02-22T08:00:00Z"
    },
    {
      "sectionId": "hardware",
      "title": "Hardware Specifications",
      "source": "generated",
      "templateRef": "tmpl::runbook::hardware",
      "dataFingerprint": "b7e1d4...",
      "content": "## Hardware Specifications\n\n| Component | Value |\n|...",
      "lastGenerated": "2026-02-22T08:00:00Z"
    },
    {
      "sectionId": "known-issues",
      "title": "Known Issues",
      "source": "manual",
      "content": "## Known Issues\n\n- Fan #3 occasionally reports false temperature readings...",
      "lastEdited": "2026-02-20T15:30:00Z",
      "editedBy": "user_admin001"
    },
    {
      "sectionId": "recovery",
      "title": "Recovery Procedures",
      "source": "manual",
      "content": "## Recovery Procedures\n\n### If Node Is Unresponsive\n\n1. Check IPMI console...",
      "lastEdited": "2026-02-18T10:00:00Z",
      "editedBy": "user_admin001"
    }
  ]
}
```

This section model is the foundation for hybrid authoring, section-level staleness, and selective regeneration.

---

## 3. Document Types & Taxonomy

### 3.1 Auto-Generated Document Types

These are created and maintained by the generation pipeline. Users can add manual sections but don't need to create the base document.

| Type ID | Name | Source Data | Trigger | Entity Link |
|---------|------|-------------|---------|-------------|
| `runbook` | Node Runbook | Profile, services, topology, pluginData | Node registration / profile update | Node |
| `network-arch` | Network Architecture | Topology, networks, plugin enrichment (pfSense, Pi-hole, UniFi, Tailscale) | Topology change / network discovery | Network(s) |
| `service-catalog` | Service Catalog Entry | Service object, node, topology edges, plugin enrichment (Traefik, Uptime Kuma) | Service discovery / update | Service |
| `change-journal` | Change Journal | Time Machine diffs, profile history, topology history | Scheduled (daily/weekly/monthly) | None (time-scoped) |
| `capacity-report` | Capacity Planning Report | Profile resource data (disk, RAM, CPU) across nodes | Scheduled (weekly/monthly) or on-demand | None (aggregate) |
| `integration-doc` | Integration Documentation | Plugin config, health status, contributed commands/data | Plugin enabled / config change | Integration |
| `blast-radius` | Blast Radius Analysis | Topology dependency graph, service dependencies | Topology change / on-demand | Node |
| `inventory` | Infrastructure Inventory | All nodes, services, networks | On-demand / scheduled | None (aggregate) |

### 3.2 Manual Document Types

These are created entirely by users. The system provides templates to get started.

| Type ID | Name | Description | Starter Templates |
|---------|------|-------------|-------------------|
| `guide` | Setup / How-To Guide | Step-by-step instructions for setting up or configuring something | Blank, Service Setup, Network Config |
| `adr` | Architecture Decision Record | Record of a significant architectural decision and its rationale | Standard ADR template |
| `runbook-manual` | Custom Runbook | Operational procedures not tied to auto-generation | Incident Response, Maintenance Window |
| `reference` | Reference Document | Specifications, credential references (no secrets), vendor info | Blank |
| `note` | Operational Note | Quick notes, observations, reminders | Blank |

### 3.3 Document Taxonomy

Documents are organized along multiple axes that drive navigation and search.

**Categories** (primary grouping for navigation tree):

| Category | Contains |
|----------|----------|
| `infrastructure` | Node runbooks, blast radius analysis, capacity reports, infrastructure inventory |
| `network` | Network architecture, subnet docs, firewall documentation, DNS configuration, VPN/overlay docs |
| `services` | Service catalog entries, reverse proxy docs, container documentation |
| `iot` | IoT device documentation, room configurations, automation descriptions |
| `integrations` | Per-integration documentation, setup guides, health status |
| `operations` | Change journals, incident reports, maintenance records |
| `planning` | Capacity reports, migration plans, project docs |
| `custom` | User-authored guides, ADRs, notes, references |

**Status** (document lifecycle):

| Status | Description |
|--------|-------------|
| `current` | Up-to-date with underlying data, all sections fresh |
| `stale` | One or more generated sections have outdated data fingerprints |
| `draft` | Manual document not yet published |
| `published` | Manual document visible in portal |
| `archived` | Soft-deleted, not shown in navigation but searchable and recoverable |

**Tags** (free-form, for cross-cutting search):

Tags are user-applied labels like `proxmox`, `docker`, `critical`, `networking`, `backup`, etc. Used for filtering and faceted search.

---

## 4. Auto-Generation Pipeline

### 4.1 Pipeline Architecture

The generation pipeline is an internal API service that transforms infrastructure data into document sections using templates.

```python
class GenerationPipeline:
    """
    Orchestrates document generation from templates and data.
    """

    def __init__(self, template_engine: TemplateEngine, data_resolver: DataResolver):
        self.template_engine = template_engine
        self.data_resolver = data_resolver

    async def generate_document(self, doc_type: str, params: dict) -> GeneratedDocument:
        """
        Generate or regenerate a document.

        Args:
            doc_type: e.g., "runbook", "network-arch", "service-catalog"
            params: e.g., {"nodeId": "proxmox-01"} or {"networkId": "homenet-lan"}

        Returns:
            GeneratedDocument with sections, fingerprints, and metadata.
        """
        # 1. Load template set for this doc type
        template_set = self.template_engine.get_template_set(doc_type)

        # 2. Resolve all data dependencies
        data_context = await self.data_resolver.resolve(template_set.data_requirements, params)

        # 3. Compute data fingerprint (for change detection)
        fingerprint = compute_fingerprint(data_context)

        # 4. Render each section
        sections = []
        for section_template in template_set.sections:
            rendered = self.template_engine.render_section(section_template, data_context)
            sections.append(GeneratedSection(
                section_id=section_template.section_id,
                title=section_template.title,
                source="generated",
                template_ref=section_template.template_id,
                data_fingerprint=compute_fingerprint(data_context, section_template.data_keys),
                content=rendered,
                last_generated=datetime.utcnow()
            ))

        return GeneratedDocument(
            doc_type=doc_type,
            params=params,
            sections=sections,
            fingerprint=fingerprint
        )
```

### 4.2 Generation Triggers

| Trigger | When | What Happens |
|---------|------|-------------|
| **Node registration** | New node registered via API | Generate node runbook, update infrastructure inventory |
| **Profile submission** | New profile received for existing node | Flag runbook stale, regenerate on next cycle or immediately if configured |
| **Topology update** | Topology edges added/removed/changed | Flag network architecture and blast radius docs stale |
| **Service discovery** | New service discovered or existing service state change | Generate/update service catalog entry |
| **Plugin enabled** | Integration plugin activated | Generate integration documentation |
| **Plugin data sync** | Plugin profile enrichment data updated | Flag related docs stale (e.g., Docker plugin sync → flag container-related service catalog entries) |
| **Scheduled** | Cron-based schedule | Generate change journals (daily/weekly), capacity reports (weekly/monthly) |
| **Manual trigger** | User clicks "Regenerate" or MCP tool call | Regenerate specified document immediately |
| **Bulk regeneration** | Admin triggers full doc rebuild | Regenerate all auto-generated documents from current data |

### 4.3 Data Resolver

The data resolver fetches all required data for a template set. It abstracts away the specific MongoDB queries and API calls.

```python
class DataResolver:
    """
    Resolves template data requirements into actual data from Hydra collections.
    """

    async def resolve(self, requirements: list[DataRequirement], params: dict) -> DataContext:
        context = DataContext()

        for req in requirements:
            match req.source:
                case "nodes":
                    context[req.key] = await self.db.nodes.find_one({"nodeId": params.get("nodeId")})
                case "profiles.latest":
                    context[req.key] = await self.get_latest_profile(params.get("nodeId"))
                case "profiles.history":
                    context[req.key] = await self.get_profile_history(params.get("nodeId"), limit=req.limit)
                case "services":
                    context[req.key] = await self.db.services.find(req.build_query(params)).to_list()
                case "topology":
                    context[req.key] = await self.get_topology_for_entity(params)
                case "topology.dependencies":
                    context[req.key] = await self.compute_dependency_tree(params.get("nodeId"))
                case "networks":
                    context[req.key] = await self.db.networks.find(req.build_query(params)).to_list()
                case "plugin_data":
                    context[req.key] = await self.extract_plugin_data(
                        params.get("nodeId"), req.plugin_id
                    )
                case "integrations":
                    context[req.key] = await self.db.integrations.find_one({"pluginId": req.plugin_id})
                case "commands":
                    context[req.key] = await self.db.commands.find(req.build_query(params)).to_list()
                case "time_machine.diffs":
                    context[req.key] = await self.compute_diffs(
                        params.get("startDate"), params.get("endDate")
                    )

        return context
```

### 4.4 Fingerprinting for Change Detection

Every generated section stores a `dataFingerprint` — a hash of the data that was used to render it. When the underlying data changes, the new fingerprint won't match, and the section is flagged stale.

```python
def compute_fingerprint(data: dict, keys: list[str] | None = None) -> str:
    """
    Compute a stable hash of the data used to generate a section.
    If keys are provided, only hash those specific keys.
    Uses the same Jaccard-distance-aware hashing as profile versioning.
    """
    if keys:
        data = {k: data[k] for k in keys if k in data}

    # Canonical JSON serialization (sorted keys, no whitespace)
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
```

This reuses the hash-based change detection pattern established in Hydra's profile versioning system.

---

## 5. Template Engine

### 5.1 Template Architecture

Templates are Jinja2-based markdown templates with structured data access. Each template set defines a document type with multiple section templates.

### 5.2 Template Set Definition

```json
{
  "templateSetId": "tmpl-set::runbook",
  "docType": "runbook",
  "displayName": "Node Runbook",
  "description": "Auto-generated operational runbook for a compute node",
  "paramSchema": {
    "type": "object",
    "required": ["nodeId"],
    "properties": {
      "nodeId": { "type": "string" }
    }
  },
  "dataRequirements": [
    { "key": "node", "source": "nodes", "required": true },
    { "key": "profile", "source": "profiles.latest", "required": true },
    { "key": "services", "source": "services", "query": { "nodeId": "{nodeId}" } },
    { "key": "topology", "source": "topology", "query": { "entityId": "{nodeId}" } },
    { "key": "dependents", "source": "topology.dependencies", "direction": "inbound" },
    { "key": "dependencies", "source": "topology.dependencies", "direction": "outbound" },
    { "key": "docker_data", "source": "plugin_data", "pluginId": "plg::docker", "required": false },
    { "key": "proxmox_data", "source": "plugin_data", "pluginId": "plg::proxmox", "required": false }
  ],
  "sections": [
    {
      "sectionId": "overview",
      "title": "Overview",
      "templateId": "tmpl::runbook::overview",
      "dataKeys": ["node", "profile"],
      "order": 1
    },
    {
      "sectionId": "hardware",
      "title": "Hardware Specifications",
      "templateId": "tmpl::runbook::hardware",
      "dataKeys": ["profile"],
      "order": 2,
      "condition": "node.nodeType == 'physical'"
    },
    {
      "sectionId": "network",
      "title": "Network Configuration",
      "templateId": "tmpl::runbook::network",
      "dataKeys": ["profile", "topology"],
      "order": 3
    },
    {
      "sectionId": "services",
      "title": "Running Services",
      "templateId": "tmpl::runbook::services",
      "dataKeys": ["services"],
      "order": 4
    },
    {
      "sectionId": "containers",
      "title": "Docker Containers",
      "templateId": "tmpl::runbook::containers",
      "dataKeys": ["docker_data"],
      "order": 5,
      "condition": "docker_data is not none"
    },
    {
      "sectionId": "dependencies",
      "title": "Dependencies",
      "templateId": "tmpl::runbook::dependencies",
      "dataKeys": ["dependents", "dependencies"],
      "order": 6
    },
    {
      "sectionId": "blast-radius",
      "title": "Blast Radius",
      "templateId": "tmpl::runbook::blast-radius",
      "dataKeys": ["dependents"],
      "order": 7
    }
  ],
  "manualSectionSlots": [
    { "sectionId": "access", "title": "Access Information", "order": 8, "hint": "SSH keys, IPMI credentials, physical location" },
    { "sectionId": "known-issues", "title": "Known Issues", "order": 9, "hint": "Known quirks, workarounds, things to watch for" },
    { "sectionId": "recovery", "title": "Recovery Procedures", "order": 10, "hint": "What to do if this node fails" },
    { "sectionId": "notes", "title": "Operational Notes", "order": 11, "hint": "Any additional notes about this node" }
  ]
}
```

### 5.3 Section Template Examples

#### Node Runbook — Overview Section

```jinja2
{# tmpl::runbook::overview #}
## Overview

**{{ node.displayName }}** is a {{ "physical" if node.nodeType == "physical" else "logical" }} {{ node.class }} node
{%- if node.class == "compute" %} running {{ profile.os.distribution }} {{ profile.os.version }}{% endif %}.

| Property | Value |
|----------|-------|
| **Node ID** | `{{ node.nodeId }}` |
| **Class** | {{ node.class | title }} |
| **Type** | {{ node.nodeType | title }} |
| **Status** | {{ node.status | title }} |
{% if node.nodeType == "physical" -%}
| **Location** | {{ node.location | default("Not specified") }} |
{%- endif %}
| **Registered** | {{ node.registeredAt | dateformat }} |
| **Last Profile** | {{ profile.submittedAt | dateformat }} ({{ profile.submittedAt | timeago }}) |
| **Agent Tier** | {{ node.agentTier | default("None") }} |

{% if node.description -%}
{{ node.description }}
{%- endif %}
```

#### Node Runbook — Blast Radius Section

```jinja2
{# tmpl::runbook::blast-radius #}
## Blast Radius

If **{{ node.displayName }}** goes down, the following entities are directly affected:

{% if dependents | length == 0 -%}
> No entities depend directly on this node.
{% else -%}

### Directly Dependent Entities

| Entity | Type | Impact |
|--------|------|--------|
{% for dep in dependents -%}
| {{ dep.displayName }} | {{ dep.entityType | title }} | {{ dep.relationship }} |
{% endfor %}

### Cascade Analysis

{% set cascade = compute_cascade(dependents) -%}
{% if cascade.total > dependents | length -%}
Including transitive dependencies, **{{ cascade.total }} entities** would be affected:

{% for level in cascade.levels -%}
**Level {{ level.depth }}** ({{ level.description }}):
{% for entity in level.entities -%}
- {{ entity.displayName }} ({{ entity.entityType }})
{% endfor %}
{% endfor %}
{% else -%}
No additional transitive dependencies detected beyond the direct dependents above.
{%- endif %}
{%- endif %}
```

#### Network Architecture — Subnet Section

```jinja2
{# tmpl::network-arch::subnet #}
## {{ network.cidr }} — {{ network.name }}

| Property | Value |
|----------|-------|
| **CIDR** | `{{ network.cidr }}` |
| **Gateway** | `{{ network.gateway | default("Not configured") }}` |
| **VLAN** | {{ network.vlanId | default("None (untagged)") }} |
| **DHCP Range** | {{ network.dhcpRange | default("Not configured") }} |
| **DNS Server** | {{ network.dnsServer | default("Inherited from gateway") }} |
| **Purpose** | {{ network.purpose | default("General") }} |

### Connected Nodes ({{ nodes_on_network | length }})

| Node | Class | IP Address | Status |
|------|-------|------------|--------|
{% for node in nodes_on_network | sort(attribute='displayName') -%}
| [{{ node.displayName }}](/docs/doc::runbook::{{ node.nodeId }}) | {{ node.class | title }} | `{{ node.ip }}` | {{ node.status | status_badge }} |
{% endfor %}

{% if firewall_rules -%}
### Firewall Rules

{% for rule in firewall_rules -%}
- **{{ rule.action | upper }}** {{ rule.source }} → {{ rule.destination }} ({{ rule.protocol }}/{{ rule.port }}) — {{ rule.description }}
{% endfor %}
{%- endif %}

{% if dns_overrides -%}
### DNS Overrides

| Domain | Target | Source |
|--------|--------|--------|
{% for record in dns_overrides -%}
| `{{ record.domain }}` | `{{ record.target }}` | {{ record.source }} |
{% endfor %}
{%- endif %}
```

#### Change Journal — Weekly Section

```jinja2
{# tmpl::change-journal::weekly #}
## Infrastructure Changes — Week of {{ start_date | dateformat("%B %d, %Y") }}

### Summary

- **{{ profile_changes | length }}** profile changes across **{{ affected_nodes | length }}** nodes
- **{{ topology_changes | length }}** topology changes
- **{{ new_services | length }}** new services discovered
- **{{ removed_services | length }}** services removed
- **{{ container_updates | length }}** container image updates

{% if profile_changes -%}
### Profile Changes

{% for change in profile_changes | sort(attribute='timestamp', reverse=true) -%}
#### {{ change.node.displayName }} — {{ change.timestamp | dateformat }}

{% for diff in change.diffs -%}
- **{{ diff.field }}**: {{ diff.old_value }} → {{ diff.new_value }}
{% endfor %}
{% endfor %}
{%- endif %}

{% if topology_changes -%}
### Topology Changes

{% for change in topology_changes -%}
- {{ change.description }} ({{ change.timestamp | dateformat }})
{% endfor %}
{%- endif %}

{% if new_services -%}
### New Services Discovered

| Service | Node | Port | Discovered |
|---------|------|------|------------|
{% for svc in new_services -%}
| {{ svc.displayName }} | {{ svc.node.displayName }} | {{ svc.port }} | {{ svc.discoveredAt | dateformat }} |
{% endfor %}
{%- endif %}

{% if container_updates -%}
### Container Image Updates

| Container | Host | Old Image | New Image | Updated |
|-----------|------|-----------|-----------|---------|
{% for update in container_updates -%}
| {{ update.name }} | {{ update.host.displayName }} | `{{ update.oldTag }}` | `{{ update.newTag }}` | {{ update.timestamp | dateformat }} |
{% endfor %}
{%- endif %}
```

### 5.4 Template Registry

Templates are loaded from the filesystem on API startup. Hydra ships with built-in templates; admins can add custom templates.

```
templates/
├── runbook/
│   ├── template-set.json        # Template set definition
│   ├── overview.md.j2           # Section templates
│   ├── hardware.md.j2
│   ├── network.md.j2
│   ├── services.md.j2
│   ├── containers.md.j2
│   ├── dependencies.md.j2
│   └── blast-radius.md.j2
├── network-arch/
│   ├── template-set.json
│   ├── overview.md.j2
│   ├── subnet.md.j2             # Rendered once per network
│   ├── firewall.md.j2
│   ├── dns.md.j2
│   └── overlay.md.j2
├── service-catalog/
│   ├── template-set.json
│   └── entry.md.j2
├── change-journal/
│   ├── template-set.json
│   ├── daily.md.j2
│   ├── weekly.md.j2
│   └── monthly.md.j2
├── capacity-report/
│   ├── template-set.json
│   └── report.md.j2
├── blast-radius/
│   ├── template-set.json
│   └── analysis.md.j2
├── integration-doc/
│   ├── template-set.json
│   └── integration.md.j2
└── inventory/
    ├── template-set.json
    └── full-inventory.md.j2
```

---

## 6. Hybrid Authoring Model

### 6.1 The Problem

Auto-generated documentation is valuable but incomplete. An operator knows things Hydra doesn't — "this node runs hot in summer," "the backup takes 4 hours on Sundays," "contact vendor X if the RAID controller fails." Users need to add this information without losing it when the document regenerates.

### 6.2 Section-Level Merge Strategy

The document is structured as an ordered list of sections. Each section is either `generated` or `manual`. The merge engine preserves manual sections across regenerations.

**Rules:**

1. **Generated sections are regenerated.** Their content is replaced entirely. The `dataFingerprint` is updated.
2. **Manual sections are preserved.** They are never touched by regeneration. Their content, order, and metadata survive.
3. **Manual section slots** defined in the template set create placeholder entries in new documents, encouraging users to fill them in. These appear as empty sections with hint text.
4. **Users can add new manual sections** at any position in the document. These are tracked with `source: "manual"` and a unique `sectionId`.
5. **Users can override a generated section.** This converts the section from `source: "generated"` to `source: "manual-override"`. The original generated content is preserved as a reference. The section is now excluded from regeneration.
6. **Users can revert a manual override** back to generated, which re-enters the section into the regeneration cycle.

### 6.3 Section State Machine

```
GENERATED (fresh)
    │
    ├─► STALE (data changed, content outdated)
    │       │
    │       └─► GENERATED (regenerated with new data)
    │
    └─► MANUAL-OVERRIDE (user replaced generated content)
            │
            └─► GENERATED (user reverted override)

MANUAL (user-authored)
    │
    ├─► MANUAL (user edited)
    │
    └─► ARCHIVED (user deleted section — preserved in version history)

MANUAL-SLOT (empty placeholder from template)
    │
    └─► MANUAL (user filled in content)
```

### 6.4 Merge Algorithm

On regeneration:

```python
def merge_document(existing: Document, generated: GeneratedDocument) -> Document:
    """
    Merge regenerated sections with existing manual content.
    """
    merged_sections = []
    existing_by_id = {s.section_id: s for s in existing.sections}

    # Process all generated sections in template order
    for gen_section in generated.sections:
        existing_section = existing_by_id.get(gen_section.section_id)

        if existing_section and existing_section.source == "manual-override":
            # User has overridden this section — preserve their content
            merged_sections.append(existing_section)
        else:
            # Replace with fresh generated content
            merged_sections.append(gen_section)

        # Remove from existing map (handled)
        existing_by_id.pop(gen_section.section_id, None)

    # Append remaining manual sections (user-added, not part of template)
    # Maintain their original order relative to generated sections
    for section in existing.sections:
        if section.section_id in existing_by_id and section.source in ("manual", "manual-slot"):
            merged_sections.append(section)

    return Document(sections=merged_sections, ...)
```

---

## 7. Staleness Detection & Regeneration

### 7.1 How Staleness Is Detected

When infrastructure data changes (new profile, topology update, plugin sync), the system computes a fresh fingerprint for affected document sections and compares against stored fingerprints.

```python
async def check_staleness(doc: Document) -> list[StaleSection]:
    """
    Check if any generated sections are stale.
    """
    stale_sections = []

    for section in doc.sections:
        if section.source != "generated":
            continue

        # Resolve current data for this section's data keys
        current_data = await data_resolver.resolve_for_section(doc, section)
        current_fingerprint = compute_fingerprint(current_data, section.data_keys)

        if current_fingerprint != section.data_fingerprint:
            stale_sections.append(StaleSection(
                section_id=section.section_id,
                stored_fingerprint=section.data_fingerprint,
                current_fingerprint=current_fingerprint,
                age=datetime.utcnow() - section.last_generated
            ))

    return stale_sections
```

### 7.2 Staleness Propagation Rules

| Data Change | Affected Document Types |
|-------------|------------------------|
| Profile submitted for node X | `runbook` for X, `capacity-report` (aggregate), `inventory` |
| Topology edge added/removed | `network-arch`, `blast-radius` for affected nodes, `runbook` dependency sections |
| Service discovered/changed | `service-catalog` for that service, `runbook` services section for host node |
| Plugin data updated (Docker) | `runbook` containers section for host, `service-catalog` for containerized services |
| Plugin data updated (HA) | IoT-related docs, `runbook` for HA host if applicable |
| Network added/changed | `network-arch`, `inventory` |
| Integration config changed | `integration-doc` for that plugin |

### 7.3 Regeneration Modes

| Mode | Description | Configuration |
|------|-------------|---------------|
| **Immediate** | Regenerate as soon as staleness detected | Per-doc-type setting. Recommended for `runbook` and `service-catalog`. |
| **Scheduled** | Regenerate on a schedule regardless of staleness | For `change-journal` (daily, weekly, monthly), `capacity-report` (weekly). |
| **On-Access** | Regenerate when a stale doc is opened in the portal | Default for most doc types. Lazy but ensures freshness when viewed. |
| **Manual** | Only regenerate when user clicks "Regenerate" or MCP tool call | For large documents or when users want control over timing. |
| **Batch** | Admin triggers full rebuild of all auto-generated docs | For recovery, template updates, or initial setup. |

### 7.4 Regeneration API

```
POST /docs/{docId}/regenerate
```

Triggers immediate regeneration. Returns the updated document.

```
POST /docs/regenerate-batch
{
  "docType": "runbook",
  "scope": "all"
}
```

Triggers batch regeneration of all documents of a type. Queued for background processing.

---

## 8. Document Portal Experience

### 8.1 Portal Design Goals

The documentation portal is a Fumadocs-quality experience embedded within the Hydra web interface. It is a proper documentation site with its own navigation, search, and rendering — not a simple markdown viewer.

### 8.2 Portal Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Hydra Sidebar  │  Doc Portal Sidebar  │  Document Content     │  Context  │
│  (collapsed)    │  (navigation tree)   │  (rendered markdown)  │  Panel    │
│                 │                      │                       │           │
│  Observe        │  ▼ Infrastructure    │  # Node Runbook:      │  Entity   │
│  Infrastructure │    ▼ Nodes           │    proxmox-01         │  Card:    │
│  Operate        │      proxmox-01  ←   │                       │  Status:  │
│  Knowledge ←    │      proxmox-02      │  ## Overview          │  Online   │
│    Docs ←       │      docker-host-01  │  ...                  │  Last     │
│    MCP Chat     │    ▼ Services        │                       │  Profile: │
│  Admin          │      plex            │  ## Hardware           │  2m ago  │
│                 │      pihole          │  ...                  │           │
│                 │    ▼ Blast Radius    │                       │  Links:   │
│                 │  ▼ Network           │  ## Services          │  Topology │
│                 │    192.168.0.0/24    │  ...                  │  Services │
│                 │    192.168.1.0/24    │                       │  Commands │
│                 │  ▼ Operations        │  [TOC sidebar →]      │           │
│                 │    Change Journal    │                       │           │
│                 │  ▼ Custom            │                       │           │
│                 │    My Setup Guide    │                       │           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.3 Portal Features

| Feature | Description |
|---------|-------------|
| **Navigation tree** | Hierarchical sidebar organized by category, expandable/collapsible, shows doc count per category |
| **Breadcrumbs** | `Knowledge > Docs > Infrastructure > Nodes > proxmox-01` |
| **Table of contents** | Auto-generated from document headings, sticky sidebar on desktop |
| **Full-text search** | Search across all docs with highlighted snippets and faceted filtering |
| **Rich rendering** | Full markdown + extensions (tables, code blocks, callouts, tabs, collapsible sections, diagrams) |
| **Status indicators** | Badge per doc showing Current / Stale / Draft with last updated time |
| **Entity context panel** | When viewing entity-linked docs, shows live entity card alongside (status, specs, quick actions) |
| **Regenerate button** | For stale docs, a "Regenerate" button refreshes from current data |
| **Section editing** | Click a pencil icon on any section to edit inline. Manual sections are freely editable. Generated sections show "Override" option. |
| **Version history** | Per-document version timeline with diff viewer |
| **Export** | Export individual doc or entire category as PDF or markdown bundle |
| **Cross-linking** | Docs can link to other docs, entities, dashboards, and topology views |
| **Print mode** | Clean print stylesheet for paper copies |

---

## 9. Navigation Tree & Information Architecture

### 9.1 Tree Structure

The navigation tree is computed server-side from document metadata and served via API. The tree is hierarchical, category-based, and includes document counts.

```json
{
  "tree": [
    {
      "id": "infrastructure",
      "label": "Infrastructure",
      "icon": "server",
      "count": 12,
      "children": [
        {
          "id": "infrastructure/nodes",
          "label": "Nodes",
          "count": 5,
          "children": [
            { "id": "doc::runbook::proxmox-01", "label": "proxmox-01", "status": "current", "type": "runbook" },
            { "id": "doc::runbook::proxmox-02", "label": "proxmox-02", "status": "stale", "type": "runbook" },
            { "id": "doc::runbook::docker-host-01", "label": "docker-host-01", "status": "current", "type": "runbook" }
          ]
        },
        {
          "id": "infrastructure/blast-radius",
          "label": "Blast Radius Analysis",
          "count": 3,
          "children": [
            { "id": "doc::blast-radius::proxmox-01", "label": "proxmox-01", "status": "current" }
          ]
        },
        { "id": "doc::inventory::latest", "label": "Infrastructure Inventory", "status": "current", "type": "inventory" },
        { "id": "doc::capacity-report::latest", "label": "Capacity Report", "status": "current", "type": "capacity-report" }
      ]
    },
    {
      "id": "network",
      "label": "Network",
      "icon": "network",
      "count": 4,
      "children": [
        { "id": "doc::network-arch::overview", "label": "Architecture Overview", "status": "current" },
        {
          "id": "network/subnets",
          "label": "Subnets",
          "count": 2,
          "children": [
            { "id": "doc::network-arch::192.168.0.0-24", "label": "192.168.0.0/24 — Management", "status": "current" },
            { "id": "doc::network-arch::192.168.1.0-24", "label": "192.168.1.0/24 — IoT", "status": "stale" }
          ]
        }
      ]
    },
    {
      "id": "services",
      "label": "Services",
      "icon": "package",
      "count": 15,
      "children": [
        { "id": "doc::service-catalog::plex", "label": "Plex Media Server", "status": "current" },
        { "id": "doc::service-catalog::pihole", "label": "Pi-hole", "status": "current" }
      ]
    },
    {
      "id": "integrations",
      "label": "Integrations",
      "icon": "plug",
      "count": 5,
      "children": [
        { "id": "doc::integration-doc::plg-docker", "label": "Docker Engine", "status": "current" },
        { "id": "doc::integration-doc::plg-proxmox", "label": "Proxmox VE", "status": "current" },
        { "id": "doc::integration-doc::plg-ha", "label": "Home Assistant", "status": "stale" }
      ]
    },
    {
      "id": "operations",
      "label": "Operations",
      "icon": "clipboard-list",
      "count": 8,
      "children": [
        {
          "id": "operations/change-journals",
          "label": "Change Journals",
          "count": 4,
          "children": [
            { "id": "doc::change-journal::2026-w08", "label": "Week 8 — Feb 17–23", "status": "current" },
            { "id": "doc::change-journal::2026-w07", "label": "Week 7 — Feb 10–16", "status": "current" }
          ]
        }
      ]
    },
    {
      "id": "custom",
      "label": "Custom Docs",
      "icon": "edit-3",
      "count": 3,
      "children": [
        { "id": "doc::guide::proxmox-cluster-setup", "label": "Proxmox Cluster Setup Guide", "status": "published" },
        { "id": "doc::adr::vlan-segmentation", "label": "ADR: VLAN Segmentation Decision", "status": "published" },
        { "id": "doc::note::router-replacement", "label": "Router Replacement Notes", "status": "draft" }
      ]
    }
  ]
}
```

### 9.2 Navigation Tree API

```
GET /docs/tree
```

Returns the full navigation tree, filtered by the requesting user's role.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `category` | string | Return only a specific category subtree |
| `includeArchived` | boolean | Include archived docs (default: false) |

---

## 10. Rich Content Rendering

### 10.1 Rendering Engine

The frontend renders document content as rich markdown using a custom MDX-like renderer built on `react-markdown` with `remark` and `rehype` plugins.

### 10.2 Supported Content Features

| Feature | Markdown Syntax | Renders As |
|---------|----------------|------------|
| **Headings** | `# H1` through `###### H6` | Styled headings with anchor links |
| **Tables** | Standard GFM tables | Styled, sortable tables |
| **Code blocks** | Triple backtick with language tag | Syntax highlighted with copy button |
| **Inline code** | Single backtick | Highlighted inline code |
| **Links** | `[text](url)` | Clickable links; internal doc links navigate within portal |
| **Images** | `![alt](url)` | Rendered images with lightbox on click |
| **Callouts** | `> [!NOTE]`, `> [!WARNING]`, `> [!DANGER]`, `> [!TIP]` | Styled callout boxes with icons |
| **Collapsible** | `<details><summary>Title</summary>Content</details>` | Expandable sections |
| **Tabs** | `:::tabs\n:::tab{label="Linux"}\n...\n:::` | Tabbed content panels |
| **Diagrams** | `mermaid` code blocks | Rendered Mermaid diagrams |
| **Entity refs** | `[[node:proxmox-01]]` | Linked entity chip (clickable, shows status on hover) |
| **Doc refs** | `[[doc:doc::runbook::proxmox-01]]` | Linked document chip (clickable) |
| **Status badges** | `{{status:online}}`, `{{status:offline}}` | Colored status badges |
| **Metric values** | `{{metric:node/proxmox-01/cpu-cores}}` | Live-resolved metric values |

### 10.3 Entity Reference Resolution

Entity references (`[[node:proxmox-01]]`) are resolved at render time. The renderer fetches the entity's current name and status, rendering a linked chip:

```
[proxmox-01 ● Online] ← clickable, navigates to node detail
```

If the entity no longer exists, the chip shows a warning state:

```
[proxmox-01 ⚠ Not Found] ← grayed out
```

---

## 11. Search & Discovery

### 11.1 Full-Text Search

Document content is indexed in MongoDB's text index (already defined in the existing docs collection). Search covers title, description, content, tags, and linked entity names.

### 11.2 Search API

```
GET /docs/search?q=proxmox+cluster&category=infrastructure&status=current
```

**Response:**

```json
{
  "results": [
    {
      "docId": "doc::runbook::proxmox-01",
      "title": "Node Runbook: proxmox-01",
      "type": "runbook",
      "category": "infrastructure",
      "snippet": "...proxmox-01 is a physical compute node running Proxmox VE 8.1 in a **cluster** configuration...",
      "score": 0.95,
      "status": "current",
      "updatedAt": "2026-02-22T08:00:00Z"
    }
  ],
  "total": 3,
  "facets": {
    "category": { "infrastructure": 2, "custom": 1 },
    "type": { "runbook": 2, "guide": 1 },
    "status": { "current": 2, "stale": 1 }
  }
}
```

### 11.3 Search Features

| Feature | Description |
|---------|-------------|
| **Fuzzy matching** | Handles typos and partial matches |
| **Faceted filtering** | Filter by category, type, status, tags, linked entity |
| **Snippet highlighting** | Search terms highlighted in result snippets |
| **Entity-scoped search** | "Find docs about proxmox-01" searches entity links |
| **Tag filtering** | Filter by one or more tags |
| **Sort options** | Relevance, last updated, title |
| **Recent docs** | "Recently viewed" and "Recently updated" quick filters |

---

## 12. Versioning & Change Tracking

### 12.1 Version Model

Every save to a document (whether from regeneration or manual edit) creates a new version. The current version is stored inline in the `docs` collection; previous versions are stored in `doc_versions`.

### 12.2 Version Metadata

```json
{
  "docId": "doc::runbook::proxmox-01",
  "version": 7,
  "changeType": "regenerated",
  "changeSummary": "Hardware section updated (new RAM detected), Services section updated (2 new services)",
  "changedSections": ["hardware", "services"],
  "trigger": "profile-submission",
  "triggeredBy": "system",
  "previousVersion": 6,
  "savedAt": "2026-02-22T08:00:00Z"
}
```

**Change Types:**

| Type | Description |
|------|-------------|
| `regenerated` | One or more generated sections were updated |
| `manual-edit` | User edited a manual section |
| `manual-override` | User overrode a generated section |
| `section-added` | New manual section added |
| `section-removed` | Manual section deleted |
| `metadata-update` | Title, tags, category, or other metadata changed |

### 12.3 Diff Viewer

The portal includes a diff viewer that shows changes between any two versions of a document.

- **Section-level diff**: Which sections changed, which are unchanged.
- **Content diff**: Inline diff (additions in green, deletions in red) within changed sections.
- **Metadata diff**: Changes to title, tags, linked entities.

### 12.4 Time Machine Integration

Documents can be viewed at historical points via Time Machine integration:

```
GET /docs/{docId}?asOf=2026-01-15T00:00:00Z
```

This returns the document version that was current at the specified timestamp. Combined with Time Machine topology/profile snapshots, this enables "show me what my infrastructure documentation looked like on January 15th."

---

## 13. MCP Knowledge Base Integration

### 13.1 Bidirectional Interface

The documentation system integrates with hydra-mcp-service in both directions:

**AI Reads Docs (Knowledge Retrieval):**
The MCP service can search and read documentation to answer user queries about their infrastructure.

**AI Writes Docs (Generation Triggers):**
The MCP service can trigger document generation and create manual documents.

### 13.2 MCP Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `search_docs` | Search documentation content | `query`, `category`, `type`, `entityId` |
| `get_doc` | Retrieve a specific document | `docId`, `version` |
| `get_doc_section` | Retrieve a specific section of a document | `docId`, `sectionId` |
| `generate_doc` | Trigger auto-generation for a specific document type | `docType`, `params` (e.g., `nodeId`) |
| `create_doc` | Create a new manual document | `title`, `type`, `category`, `content`, `tags` |
| `update_doc_section` | Update a manual section of a document | `docId`, `sectionId`, `content` |
| `list_stale_docs` | List documents with stale sections | None |
| `regenerate_doc` | Regenerate a specific stale document | `docId` |
| `get_doc_tree` | Get the navigation tree | `category` |
| `get_blast_radius` | Get blast radius analysis for a node | `nodeId` |
| `get_change_journal` | Get change journal for a period | `period` (`daily`, `weekly`, `monthly`), `date` |

### 13.3 MCP Resources

Documents are exposed as MCP resources:

```
Resource URI: hydra://docs/{docId}
Content Type: text/markdown
```

This allows MCP clients to read documentation content directly as resources, in addition to using tools.

### 13.4 Knowledge Query Examples

| User Query | MCP Behavior |
|------------|-------------|
| "How is my network segmented?" | `search_docs(query="network segmentation VLAN", category="network")` → reads generated network architecture docs |
| "What happens if proxmox-01 goes down?" | `get_blast_radius(nodeId="proxmox-01")` → reads blast radius analysis doc |
| "What changed in my infra last week?" | `get_change_journal(period="weekly", date="2026-02-15")` → reads weekly change journal |
| "Document my current Docker setup" | `generate_doc(docType="integration-doc", params={"pluginId": "plg::docker"})` → triggers Docker integration doc generation |
| "What's the recovery procedure for my NAS?" | `search_docs(query="recovery NAS TrueNAS", type="runbook")` → reads TrueNAS node runbook, recovery section |
| "Create a setup guide for my new server" | `create_doc(title="New Server Setup", type="guide", category="custom", content="...")` → creates manual doc |

### 13.5 AI-Assisted Documentation

The MCP service can also enhance documentation by generating content suggestions:

1. User opens a manual section slot (e.g., "Recovery Procedures" on a node runbook).
2. User clicks "AI Assist" button.
3. Frontend calls MCP with context: "Suggest recovery procedures for proxmox-01 based on its configuration, dependencies, and common Proxmox recovery patterns."
4. MCP generates suggested content based on node profile, topology, and its general knowledge.
5. User reviews, edits, and saves the suggestion.

This is an authoring aid, not auto-generation — the content goes through human review before becoming part of the document.

---

## 14. Plugin-Contributed Documentation

### 14.1 How Plugins Contribute Docs

When a plugin is enabled, it can contribute documentation through two mechanisms:

**Template Contributions:** The plugin provides additional template sections that enrich existing document types.

```python
class DockerPluginDriver(PluginDriver):
    def get_doc_template_contributions(self) -> list[TemplateSectionContribution]:
        return [
            TemplateSectionContribution(
                target_template_set="tmpl-set::runbook",
                section=SectionTemplate(
                    section_id="docker-containers",
                    title="Docker Containers",
                    template_id="tmpl::plg-docker::runbook-containers",
                    data_keys=["docker_data"],
                    order=5,
                    condition="docker_data is not none"
                )
            ),
            TemplateSectionContribution(
                target_template_set="tmpl-set::service-catalog",
                section=SectionTemplate(
                    section_id="docker-details",
                    title="Container Details",
                    template_id="tmpl::plg-docker::service-container-details",
                    data_keys=["docker_data"],
                    condition="service.runtime == 'docker'"
                )
            )
        ]
```

**Standalone Documentation:** The plugin triggers generation of its own integration documentation when enabled.

### 14.2 Plugin Documentation by Integration

| Plugin | Contributions to Existing Docs | Standalone Docs |
|--------|-------------------------------|-----------------|
| **Proxmox** | Runbook: VM/LXC list section, cluster info. Service catalog: VM-backed service details. | Integration doc: cluster topology, HA groups, storage pools |
| **Docker** | Runbook: container inventory section. Service catalog: container config, image details. | Integration doc: all hosts, compose projects, image inventory |
| **Home Assistant** | Runbook: HA-connected devices section (for HA host). | Integration doc: area/device/entity hierarchy, automation list |
| **Ansible** | Runbook: last playbook run section. | Integration doc: inventory groups, playbook catalog, role list |
| **Terraform** | — | Integration doc: workspaces, managed resources, last apply status |
| **Prometheus** | — | Integration doc: targets, alert rules, recording rules |
| **UniFi** | Network arch: VLAN assignments, wireless topology. | Integration doc: sites, APs, client summary |
| **pfSense/OPNsense** | Network arch: firewall rules, NAT mappings, VPN tunnels. | Integration doc: interface config, DHCP, packages |
| **Pi-hole/AdGuard** | Network arch: DNS config, blocklists. | Integration doc: query stats, client groups, custom records |
| **Traefik/NPM** | Service catalog: route config, TLS status, middleware. | Integration doc: all routes, certificate inventory |
| **TrueNAS** | Runbook: pool/dataset section. | Integration doc: pools, snapshots, replication status, SMART health |
| **Uptime Kuma** | Service catalog: uptime history, response time. | Integration doc: all monitors, status pages |
| **Tailscale** | Network arch: overlay topology. Runbook: Tailscale IP section. | Integration doc: device list, ACL tags, exit nodes |
| **IPMI/Redfish** | Runbook: BMC sensor readings, firmware versions. | Integration doc: managed BMCs, power states |
| **SNMP** | Runbook: SNMP-discovered interface status. | Integration doc: managed devices, MIB inventory |
| **Podman** | Runbook: pod/container inventory section. | Integration doc: hosts, pods, systemd units |

### 14.3 Plugin Disable Behavior

When a plugin is disabled:
1. Plugin-contributed sections in existing docs are removed on next regeneration.
2. Plugin's standalone integration documentation is archived (not deleted).
3. Navigation tree is updated to remove plugin doc entries.
4. If a manual section references plugin data that no longer exists, it's preserved but a warning indicator appears.

---

## 15. Entity-Linked Context Panels

### 15.1 Bidirectional Entity Linking

Every auto-generated document is linked to the infrastructure entities it describes. This linking is bidirectional:

- **Doc → Entity**: The document's `linkedEntities` array lists all referenced entities.
- **Entity → Doc**: The entity detail pages in hydra-web show a "Documentation" panel listing all docs that reference this entity.

### 15.2 Context Panel in Portal

When viewing an entity-linked document in the portal, a context panel appears alongside the document content:

**For a Node Runbook:**
```
┌─ Entity Context ──────────────┐
│  proxmox-01                   │
│  Status: ● Online             │
│  Last Profile: 2 minutes ago  │
│  Agent Tier: Max              │
│                               │
│  Quick Stats:                 │
│  CPU: 32 cores (AMD EPYC)    │
│  RAM: 128 GB                 │
│  Disk: 2.4 TB (3 drives)    │
│                               │
│  ─── Links ───               │
│  → View in Topology           │
│  → View Services (12)         │
│  → Command History            │
│  → Dashboard Widget           │
│  → Time Machine               │
└───────────────────────────────┘
```

### 15.3 Cross-Feature Navigation

From the documentation portal, users can navigate to:
- **Node/service/network detail pages** via entity reference clicks
- **Topology viewer** focused on the documented entity
- **Time Machine** at the document version's timestamp
- **Dashboard** filtered to the documented entity
- **Command Center** for the documented node

From other pages, users can navigate to:
- **Node detail page** → "View Runbook" button → opens runbook in portal
- **Topology viewer** → right-click node → "Open Documentation" → opens runbook
- **Command Center** → post-execution → "View Node Runbook" link
- **Dashboard** → entity widget context menu → "Open Documentation"

---

## 16. Export & Offline Access

### 16.1 Export Formats

| Format | Scope | Use Case |
|--------|-------|----------|
| **Markdown** | Single doc or category bundle | Backup, version control, offline editing |
| **PDF** | Single doc or category bundle | Compliance, printing, offline reference |
| **HTML** | Single doc (self-contained) | Sharing, offline browser viewing |

### 16.2 Export API

```
GET /docs/{docId}/export?format=pdf
GET /docs/export?category=infrastructure&format=pdf
GET /docs/export?format=markdown&bundle=zip
```

### 16.3 PDF Generation

PDF export uses the Hydra API to render markdown to PDF via a server-side rendering pipeline (WeasyPrint or similar). The PDF includes:
- Cover page with document title, generation date, Hydra branding
- Table of contents (for multi-section documents)
- Rendered markdown with tables, code blocks, diagrams
- Entity references rendered as text (no interactive elements)
- Page numbers, headers, footers

### 16.4 Bundle Export

Category-level export bundles all documents in a category into a ZIP archive:

```
infrastructure-docs-2026-02-22.zip
├── index.md                     # Navigation tree as markdown links
├── nodes/
│   ├── proxmox-01.md
│   ├── proxmox-02.md
│   └── docker-host-01.md
├── blast-radius/
│   ├── proxmox-01.md
│   └── docker-host-01.md
├── capacity-report.md
└── inventory.md
```

---

## 17. RBAC & Visibility

### 17.1 Role-Based Document Access

| Capability | admin | operator | viewer | family |
|------------|-------|----------|--------|--------|
| View all docs | ✓ | ✓ | ✓ (infrastructure, network, services) | IoT docs only |
| Create manual docs | ✓ | ✓ | ✗ | ✗ |
| Edit manual docs | ✓ | ✓ (own docs) | ✗ | ✗ |
| Override generated sections | ✓ | ✓ | ✗ | ✗ |
| Trigger regeneration | ✓ | ✓ | ✗ | ✗ |
| Trigger batch regeneration | ✓ | ✗ | ✗ | ✗ |
| Export docs | ✓ | ✓ | ✓ | ✗ |
| Delete/archive docs | ✓ | ✓ (own manual docs) | ✗ | ✗ |
| Manage templates | ✓ | ✗ | ✗ | ✗ |

### 17.2 Document Visibility Scoping

Documents inherit visibility from their linked entities. A node runbook is visible to any role that can view the node. IoT documentation is visible to the `family` role if the linked entities are IoT devices.

Additionally, manual documents have an explicit visibility setting:
- `public` — visible to all authenticated users
- `role-restricted` — visible only to specified roles
- `private` — visible only to the author and admins

---

## 18. API Specification

### 18.1 Extended Document Endpoints

The existing v0.3.0 docs endpoints (§API Reference) are extended with:

#### Navigation Tree

```
GET /docs/tree
```

Returns the hierarchical navigation tree. See §9.2.

---

#### Search

```
GET /docs/search
```

Full-text search with faceted filtering. See §11.2.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | string | Search query |
| `category` | string | Filter by category |
| `type` | string | Filter by document type |
| `status` | string | Filter by status |
| `tags` | string | Comma-separated tags |
| `entityType` | string | Filter by linked entity type |
| `entityId` | string | Filter by linked entity ID |
| `sort` | enum | `relevance`, `updated`, `title` |
| `limit` | integer | Max results (default: 20) |
| `offset` | integer | Pagination offset |

---

#### Regenerate Document

```
POST /docs/{docId}/regenerate
```

Triggers immediate regeneration of all stale sections.

**Response:** `200 OK` — Updated document.

**Required Permission:** `docs:generate`

---

#### Batch Regenerate

```
POST /docs/regenerate-batch
```

**Request Body:**

```json
{
  "docType": "runbook",
  "scope": "all",
  "force": false
}
```

`force: true` regenerates even non-stale docs.

**Response:** `202 Accepted`

```json
{
  "jobId": "gen_abc123",
  "documentCount": 5,
  "status": "queued"
}
```

**Required Permission:** `docs:generate` + admin

---

#### Get Document Version

```
GET /docs/{docId}/versions
```

Returns version history for a document.

```
GET /docs/{docId}/versions/{version}
```

Returns a specific version's full content.

---

#### Diff Between Versions

```
GET /docs/{docId}/diff?from={version1}&to={version2}
```

Returns section-level and content-level diff.

---

#### Export

```
GET /docs/{docId}/export?format=pdf
GET /docs/{docId}/export?format=markdown
GET /docs/export?category={category}&format=pdf&bundle=zip
```

---

#### Document Sections (new, for hybrid authoring)

```
PUT /docs/{docId}/sections/{sectionId}
```

Update a specific section. For manual sections, replaces content. For generated sections, creates a manual override.

```
DELETE /docs/{docId}/sections/{sectionId}/override
```

Revert a manual override back to generated.

```
POST /docs/{docId}/sections
```

Add a new manual section.

```json
{
  "sectionId": "custom-notes",
  "title": "Custom Notes",
  "content": "## Custom Notes\n\nSome notes...",
  "insertAfter": "services"
}
```

---

#### Staleness Check

```
GET /docs/{docId}/staleness
```

Returns staleness status per section.

```json
{
  "docId": "doc::runbook::proxmox-01",
  "overallStatus": "stale",
  "sections": [
    { "sectionId": "overview", "status": "current", "age": "2h" },
    { "sectionId": "hardware", "status": "stale", "age": "3d", "reason": "Profile data changed" },
    { "sectionId": "services", "status": "stale", "age": "1d", "reason": "2 new services discovered" }
  ]
}
```

---

## 19. Data Model

### 19.1 Collection: `docs` (Extended Schema)

Extends the existing v0.3.0 docs collection with section-based content model:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:docs:v2",
  "title": "Document",
  "type": "object",
  "required": ["docId", "title", "type", "category", "status"],
  "properties": {
    "_id": { "type": "string" },
    "docId": { "type": "string", "pattern": "^doc::[a-z0-9:-]+$" },
    "title": { "type": "string", "maxLength": 256 },
    "description": { "type": "string", "maxLength": 2048 },
    "type": {
      "type": "string",
      "enum": ["runbook", "network-arch", "service-catalog", "change-journal",
               "capacity-report", "integration-doc", "blast-radius", "inventory",
               "guide", "adr", "runbook-manual", "reference", "note"]
    },
    "category": {
      "type": "string",
      "enum": ["infrastructure", "network", "services", "iot",
               "integrations", "operations", "planning", "custom"]
    },
    "format": { "type": "string", "enum": ["markdown", "sections"], "default": "sections" },
    "content": {
      "type": ["string", "null"],
      "description": "Legacy flat content field (for backward compatibility with v0.3.0 docs)"
    },
    "sections": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["sectionId", "title", "source", "content"],
        "properties": {
          "sectionId": { "type": "string" },
          "title": { "type": "string" },
          "source": { "type": "string", "enum": ["generated", "manual", "manual-override", "manual-slot"] },
          "templateRef": { "type": ["string", "null"] },
          "dataFingerprint": { "type": ["string", "null"] },
          "content": { "type": "string" },
          "lastGenerated": { "type": ["string", "null"], "format": "date-time" },
          "lastEdited": { "type": ["string", "null"], "format": "date-time" },
          "editedBy": { "type": ["string", "null"] },
          "order": { "type": "integer" },
          "originalContent": {
            "type": ["string", "null"],
            "description": "For manual-override sections: the last generated content, preserved for revert"
          },
          "hint": {
            "type": ["string", "null"],
            "description": "For manual-slot sections: placeholder text shown before user fills in"
          }
        }
      }
    },
    "linkedEntities": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "entityType": { "type": "string", "enum": ["node", "service", "network", "integration"] },
          "entityId": { "type": "string" }
        }
      }
    },
    "generationConfig": {
      "type": "object",
      "description": "For auto-generated docs: configuration for the generation pipeline",
      "properties": {
        "templateSetId": { "type": "string" },
        "params": { "type": "object" },
        "regenerationMode": { "type": "string", "enum": ["immediate", "scheduled", "on-access", "manual"] },
        "schedule": { "type": ["string", "null"], "description": "Cron expression for scheduled regeneration" },
        "lastFullRegeneration": { "type": ["string", "null"], "format": "date-time" }
      }
    },
    "tags": { "type": "array", "items": { "type": "string" } },
    "status": { "type": "string", "enum": ["current", "stale", "draft", "published", "archived"] },
    "visibility": {
      "type": "object",
      "properties": {
        "scope": { "type": "string", "enum": ["public", "role-restricted", "private"] },
        "roles": { "type": "array", "items": { "type": "string" } }
      }
    },
    "version": { "type": "integer", "minimum": 1 },
    "author": { "type": "string" },
    "createdAt": { "type": "string", "format": "date-time" },
    "updatedAt": { "type": "string", "format": "date-time" },
    "archivedAt": { "type": ["string", "null"], "format": "date-time" }
  }
}
```

**Indexes:**

```javascript
db.docs.createIndexes([
  { key: { "docId": 1 }, unique: true },
  { key: { "type": 1, "category": 1 } },
  { key: { "status": 1 } },
  { key: { "linkedEntities.entityType": 1, "linkedEntities.entityId": 1 } },
  { key: { "tags": 1 } },
  { key: { "category": 1, "type": 1, "status": 1 } },
  { key: { "generationConfig.templateSetId": 1 } },
  { key: { "updatedAt": -1 } },
  { key: { "title": "text", "description": "text", "tags": "text", "sections.content": "text" } }
])
```

### 19.2 Collection: `doc_versions`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:doc_versions",
  "title": "DocumentVersion",
  "type": "object",
  "required": ["docId", "version", "snapshot", "changeType", "savedAt"],
  "properties": {
    "_id": { "type": "string" },
    "docId": { "type": "string" },
    "version": { "type": "integer" },
    "snapshot": { "type": "object", "description": "Complete document at this version" },
    "changeType": {
      "type": "string",
      "enum": ["regenerated", "manual-edit", "manual-override", "section-added", "section-removed", "metadata-update"]
    },
    "changeSummary": { "type": "string" },
    "changedSections": { "type": "array", "items": { "type": "string" } },
    "trigger": { "type": "string" },
    "triggeredBy": { "type": "string" },
    "savedAt": { "type": "string", "format": "date-time" }
  }
}
```

**Indexes:**

```javascript
db.doc_versions.createIndexes([
  { key: { "docId": 1, "version": -1 } },
  { key: { "docId": 1, "savedAt": -1 } },
  { key: { "savedAt": -1 } }
])
```

### 19.3 Collection: `doc_templates`

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:doc_templates",
  "title": "DocumentTemplateSet",
  "type": "object",
  "required": ["templateSetId", "docType", "sections"],
  "properties": {
    "_id": { "type": "string" },
    "templateSetId": { "type": "string", "pattern": "^tmpl-set::[a-z0-9-]+$" },
    "docType": { "type": "string" },
    "displayName": { "type": "string" },
    "description": { "type": "string" },
    "paramSchema": { "type": "object" },
    "dataRequirements": { "type": "array" },
    "sections": { "type": "array" },
    "manualSectionSlots": { "type": "array" },
    "pluginContributions": {
      "type": "array",
      "description": "Sections contributed by plugins, dynamically merged",
      "items": {
        "type": "object",
        "properties": {
          "pluginId": { "type": "string" },
          "section": { "type": "object" }
        }
      }
    },
    "source": { "type": "string", "enum": ["system", "custom"] },
    "createdAt": { "type": "string", "format": "date-time" },
    "updatedAt": { "type": "string", "format": "date-time" }
  }
}
```

### 19.4 Collection: `doc_generation_jobs`

Tracks batch and scheduled generation jobs.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "hydra:doc_generation_jobs",
  "title": "GenerationJob",
  "type": "object",
  "properties": {
    "_id": { "type": "string" },
    "jobId": { "type": "string", "pattern": "^gen_[a-z0-9]+$" },
    "jobType": { "type": "string", "enum": ["single", "batch", "scheduled"] },
    "docType": { "type": "string" },
    "scope": { "type": "string", "enum": ["single", "type", "all"] },
    "params": { "type": "object" },
    "status": { "type": "string", "enum": ["queued", "running", "completed", "failed"] },
    "progress": {
      "type": "object",
      "properties": {
        "total": { "type": "integer" },
        "completed": { "type": "integer" },
        "failed": { "type": "integer" }
      }
    },
    "triggeredBy": { "type": "string" },
    "startedAt": { "type": ["string", "null"], "format": "date-time" },
    "completedAt": { "type": ["string", "null"], "format": "date-time" },
    "error": { "type": ["string", "null"] },
    "createdAt": { "type": "string", "format": "date-time" }
  }
}
```

---

## 20. hydra-web Implementation

### 20.1 Component Architecture

```
src/
├── features/
│   └── docs/
│       ├── pages/
│       │   ├── DocsPortalPage.tsx          # Portal shell (tree + content + context)
│       │   ├── DocViewPage.tsx             # Document viewer (rich renderer)
│       │   ├── DocEditorPage.tsx           # Manual doc editor (MDX-style editor)
│       │   ├── DocSearchPage.tsx           # Search results with facets
│       │   ├── DocVersionsPage.tsx         # Version history and diff viewer
│       │   └── DocExportPage.tsx           # Export configuration
│       ├── components/
│       │   ├── portal/
│       │   │   ├── DocNavTree.tsx          # Sidebar navigation tree
│       │   │   ├── DocBreadcrumbs.tsx      # Breadcrumb trail
│       │   │   ├── DocTableOfContents.tsx  # Per-page TOC (sticky sidebar)
│       │   │   ├── DocStatusBadge.tsx      # Current/Stale/Draft badge
│       │   │   └── DocSearchBar.tsx        # Search input with suggestions
│       │   ├── renderer/
│       │   │   ├── DocRenderer.tsx         # Main markdown renderer (react-markdown + plugins)
│       │   │   ├── CalloutBlock.tsx        # Note/Warning/Danger/Tip callouts
│       │   │   ├── CodeBlock.tsx           # Syntax highlighted code with copy
│       │   │   ├── TabsBlock.tsx           # Tabbed content panels
│       │   │   ├── CollapsibleBlock.tsx    # Expandable sections
│       │   │   ├── EntityRef.tsx           # [[node:x]] inline chips
│       │   │   ├── DocRef.tsx             # [[doc:x]] inline chips
│       │   │   ├── StatusBadge.tsx         # {{status:x}} inline badges
│       │   │   ├── MermaidDiagram.tsx      # Mermaid diagram renderer
│       │   │   └── MetricValue.tsx         # {{metric:x}} live values
│       │   ├── editor/
│       │   │   ├── SectionEditor.tsx       # Per-section inline editor
│       │   │   ├── MarkdownEditor.tsx      # Rich markdown editor (toolbar + preview)
│       │   │   ├── SectionOverrideDialog.tsx # Confirm override of generated section
│       │   │   └── AddSectionDialog.tsx    # Add new manual section
│       │   ├── versioning/
│       │   │   ├── VersionTimeline.tsx     # Visual version history
│       │   │   ├── DiffViewer.tsx          # Section + content diff
│       │   │   └── VersionCompare.tsx      # Side-by-side version comparison
│       │   ├── context/
│       │   │   ├── EntityContextPanel.tsx  # Live entity card alongside doc
│       │   │   ├── EntityLinks.tsx         # Cross-feature navigation links
│       │   │   └── RelatedDocs.tsx         # Other docs referencing same entity
│       │   └── generation/
│       │       ├── RegenerateButton.tsx    # Trigger doc regeneration
│       │       ├── StalenessIndicator.tsx  # Per-section staleness badges
│       │       ├── GenerationJobStatus.tsx # Batch job progress
│       │       └── AiAssistButton.tsx      # MCP-powered content suggestion
│       ├── hooks/
│       │   ├── useDoc.ts                  # Document load/save
│       │   ├── useDocTree.ts              # Navigation tree
│       │   ├── useDocSearch.ts            # Search with TanStack Query
│       │   ├── useDocVersions.ts          # Version history
│       │   ├── useDocStaleness.ts         # Staleness check
│       │   └── useDocExport.ts            # Export handling
│       ├── stores/
│       │   └── docsStore.ts               # Zustand store for portal state
│       └── utils/
│           ├── markdownPlugins.ts         # Custom remark/rehype plugins
│           ├── entityRefResolver.ts       # Resolve [[entity:x]] references
│           └── treeBuilder.ts             # Build navigation tree from flat doc list
```

### 20.2 Key Dependencies

| Library | Purpose |
|---------|---------|
| `react-markdown` | Base markdown rendering |
| `remark-gfm` | GitHub Flavored Markdown (tables, strikethrough, task lists) |
| `remark-directive` | Custom directives (callouts, tabs) |
| `rehype-highlight` | Syntax highlighting for code blocks |
| `rehype-slug` | Auto-generate heading IDs for TOC |
| `mermaid` | Diagram rendering |
| `diff` | Content-level diff computation |

---

## 21. Implementation Roadmap

### Phase 1: Foundation (Core Document System)

| Task | Component | Priority |
|------|-----------|----------|
| Extend docs collection schema to section model | API | P0 |
| Document CRUD with section support | API | P0 |
| Navigation tree endpoint | API | P0 |
| Basic portal page with nav tree + markdown renderer | Web | P0 |
| Rich rendering (code blocks, tables, callouts) | Web | P0 |
| Manual document creation and editing | Web | P0 |
| Full-text search | API + Web | P0 |
| Basic version history | API + Web | P0 |

### Phase 2: Auto-Generation Pipeline

| Task | Component | Priority |
|------|-----------|----------|
| Template engine (Jinja2) | API | P0 |
| Data resolver | API | P0 |
| Node runbook template set | API | P0 |
| Service catalog template set | API | P0 |
| Network architecture template set | API | P1 |
| Generation triggers (profile submission, topology change, etc.) | API | P0 |
| Fingerprint-based staleness detection | API | P0 |
| Regeneration modes (immediate, on-access, manual) | API | P0 |
| Regenerate button in portal UI | Web | P0 |

### Phase 3: Hybrid Authoring

| Task | Component | Priority |
|------|-----------|----------|
| Section merge engine | API | P0 |
| Manual section slots with hints | API + Web | P0 |
| Manual override of generated sections | API + Web | P0 |
| Override revert capability | API + Web | P0 |
| Inline section editing in portal | Web | P1 |
| Add new manual section flow | Web | P1 |

### Phase 4: Advanced Templates & Scheduling

| Task | Component | Priority |
|------|-----------|----------|
| Change journal templates (daily/weekly/monthly) | API | P1 |
| Capacity report template | API | P1 |
| Blast radius analysis template | API | P1 |
| Integration documentation template | API | P1 |
| Infrastructure inventory template | API | P1 |
| Scheduled generation (cron-based) | API | P1 |
| Batch regeneration endpoint and UI | API + Web | P1 |
| Generation job tracking | API + Web | P1 |

### Phase 5: Plugin Contributions & MCP

| Task | Component | Priority |
|------|-----------|----------|
| Plugin template contribution API | API | P1 |
| Plugin-contributed sections for runbooks (Docker, Proxmox, HA) | API | P1 |
| Plugin standalone documentation generation | API | P1 |
| MCP documentation tools | MCP | P1 |
| MCP knowledge base search | MCP | P1 |
| AI-assisted content suggestion | MCP + Web | P2 |

### Phase 6: Polish & Advanced Features

| Task | Component | Priority |
|------|-----------|----------|
| Version diff viewer | Web | P1 |
| Time Machine integration (view docs at historical point) | API + Web | P2 |
| Entity context panels | Web | P1 |
| Cross-feature navigation links | Web | P1 |
| PDF export | API | P1 |
| Bundle export (ZIP) | API | P2 |
| Mermaid diagram rendering | Web | P2 |
| Entity reference resolution (live chips) | Web | P2 |
| Custom template creation (admin) | API + Web | P2 |
| ADR and guide starter templates | API | P2 |

---

## 22. Appendices

### A. Document ID Conventions

| Doc Type | Pattern | Example |
|----------|---------|---------|
| Node runbook | `doc::runbook::{nodeId}` | `doc::runbook::proxmox-01` |
| Network architecture | `doc::network-arch::{networkId}` | `doc::network-arch::192.168.0.0-24` |
| Service catalog | `doc::service-catalog::{serviceId}` | `doc::service-catalog::plex` |
| Change journal | `doc::change-journal::{period}` | `doc::change-journal::2026-w08` |
| Capacity report | `doc::capacity-report::{period}` | `doc::capacity-report::2026-02` |
| Blast radius | `doc::blast-radius::{nodeId}` | `doc::blast-radius::proxmox-01` |
| Integration doc | `doc::integration-doc::{pluginId}` | `doc::integration-doc::plg-docker` |
| Inventory | `doc::inventory::latest` | `doc::inventory::latest` |
| Manual docs | `doc::{type}::{user-slug}` | `doc::guide::proxmox-cluster-setup` |

### B. Template Filter Functions

Custom Jinja2 filters available in templates:

| Filter | Description | Example |
|--------|-------------|---------|
| `dateformat(fmt)` | Format datetime | `{{ timestamp \| dateformat("%B %d, %Y") }}` |
| `timeago` | Relative time ("2 hours ago") | `{{ timestamp \| timeago }}` |
| `status_badge` | Render status as badge markdown | `{{ status \| status_badge }}` |
| `filesize` | Human-readable file size | `{{ bytes \| filesize }}` |
| `entity_link` | Generate entity reference markdown | `{{ node \| entity_link }}` |
| `doc_link` | Generate doc reference markdown | `{{ docId \| doc_link }}` |
| `pluralize(singular, plural)` | Pluralization | `{{ count \| pluralize("service", "services") }}` |
| `truncate(length)` | Truncate with ellipsis | `{{ text \| truncate(100) }}` |
| `sort_by(attr)` | Sort list by attribute | `{{ nodes \| sort_by("displayName") }}` |
| `group_by(attr)` | Group list by attribute | `{{ services \| group_by("status") }}` |

### C. Generation Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Single runbook generation | < 500ms | Including data resolution |
| Service catalog entry generation | < 200ms | Single entity |
| Network architecture full generation | < 2s | All networks + plugin data |
| Change journal (weekly) | < 5s | Diff computation across all profiles |
| Capacity report | < 3s | Aggregate across all nodes |
| Blast radius analysis | < 1s | Topology graph traversal |
| Batch regeneration (all runbooks, 20 nodes) | < 15s | Parallelized |
| Full rebuild (all doc types) | < 60s | Background job |

### D. Document Size Limits

| Constraint | Limit | Rationale |
|------------|-------|-----------|
| Max sections per document | 30 | Rendering performance |
| Max section content size | 100 KB | MongoDB document size management |
| Max total document size | 1 MB | MongoDB 16 MB doc limit with versions overhead |
| Max documents per instance | 10,000 | Search index performance |
| Max versions per document | 100 | Storage management (oldest pruned) |
| Max template sets | 50 | Including custom and plugin-contributed |
| Max concurrent generation jobs | 5 | API resource management |

### E. Backward Compatibility with v0.3.0 Docs API

The existing v0.3.0 `/docs` endpoints continue to work. Documents created with the flat `content` field (no `sections`) are treated as single-section manual documents with `sectionId: "content"`. The `format` field distinguishes: `"markdown"` = legacy flat content, `"sections"` = new section-based model.

Migration path: existing v0.3.0 documents are auto-migrated to the section model on first access, wrapping their `content` in a single manual section.
