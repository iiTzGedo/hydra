# Hydra Plugin Deep Dive — Operational Specification

> **Version:** 0.4.1  
> **Last Updated:** 2026-02-24  
> **Status:** Technical Specification — Extension of Plugin Architecture v0.4.0  
> **Dependencies:** Hydra Integrations & Plugin Architecture v0.4.0 (parent document), Phase 2 Technical Specification, Technical Documentation v0.3.0  
> **Scope:** Cross-plugin reconciliation, field-level authority, failure modes, edge cases, cross-plugin interactions, lifecycle management, security, performance

---

## Table of Contents

1. [Document Purpose & Relationship](#1-document-purpose--relationship)
2. [Cross-Plugin Entity Reconciliation](#2-cross-plugin-entity-reconciliation)
3. [Field-Level Authority Model](#3-field-level-authority-model)
4. [Plugin Lifecycle & Health Management](#4-plugin-lifecycle--health-management)
5. [Failure Modes & Graceful Degradation](#5-failure-modes--graceful-degradation)
6. [Cross-Plugin Interaction Matrix](#6-cross-plugin-interaction-matrix)
7. [Core Plugin Deep Dives — Edge Cases & Hard Problems](#7-core-plugin-deep-dives--edge-cases--hard-problems)
8. [Default Plugin Deep Dives — Edge Cases & Hard Problems](#8-default-plugin-deep-dives--edge-cases--hard-problems)
9. [Security & Credential Management](#9-security--credential-management)
10. [Performance, Rate Limiting & Caching](#10-performance-rate-limiting--caching)
11. [Version Compatibility & External API Stability](#11-version-compatibility--external-api-stability)
12. [Data Consistency Patterns](#12-data-consistency-patterns)
13. [Plugin Testing Strategy](#13-plugin-testing-strategy)
14. [Appendices](#14-appendices)

---

## 1. Document Purpose & Relationship

### 1.1 What This Document Is

The parent document (Plugin Architecture v0.4.0) defines the *what* of each integration: manifests, touchpoints, configuration schemas, profile enrichment data shapes, commands, and topology edges. This document defines the *how it actually works in practice* — the operational reality of running 19 plugins simultaneously against a real homelab, where devices overlap, APIs flake, networks segment, and data conflicts.

### 1.2 What This Document Covers That the Parent Does Not

| Concern                   | Parent Doc (v0.4.0)              | This Document                                                                      |
| ------------------------- | -------------------------------- | ---------------------------------------------------------------------------------- |
| Plugin mechanics          | Touchpoints, config, data shapes | N/A (see parent)                                                                   |
| Entity reconciliation     | Mentioned briefly                | Full reconciliation engine with correlation keys, merge rules, conflict resolution |
| Field authority           | Not covered                      | Per-field ownership model when multiple plugins report on the same entity          |
| Failure modes             | "Graceful degradation" principle | Per-plugin failure catalog with fallback chains, recovery actions, error reporting |
| Edge cases                | Not covered                      | Per-plugin hard problems with worked examples                                      |
| Cross-plugin interactions | Not covered                      | Interaction matrix, data flow between plugins, topology edge conflict resolution   |
| Plugin lifecycle          | Enable/disable mentioned         | Full state machine, health monitoring, circuit breaker, auto-recovery              |
| Security                  | Credential config shapes         | Credential rotation, least-privilege API tokens, network exposure analysis         |
| Performance               | Not covered                      | Rate limits per external API, caching strategies, batch vs serial queries          |
| Version compatibility     | Not covered                      | External API version matrix, breaking change handling, feature detection           |
| Data consistency          | Not covered                      | Eventual consistency model, stale data handling, conflict resolution ordering      |

---

## 2. Cross-Plugin Entity Reconciliation

### 2.1 The Problem

Multiple discovery sources can report the same physical or logical entity. A single server might be discovered by:
- **Network scan** (by IP/MAC — "there's a device at 192.168.0.10")
- **Proxmox** (by VMID — "VM 105 runs on proxmox-01")
- **Docker** (by container ID — "container nginx runs on this host")
- **Home Assistant** (by entity ID — "sensor.server_room_temperature")
- **UniFi** (by MAC — "client aa:bb:cc:dd:ee:ff on port 3")
- **Prometheus** (by scrape target — "node_exporter at 192.168.0.10:9100")
- **Tailscale** (by node key — "tailscale device ts-server-01")
- **SNMP** (by LLDP neighbor — "device proxmox-01 on local port 1")

Without reconciliation, Hydra would create 8 separate node entries for the same machine.

### 2.2 Correlation Keys

Each discovery source provides one or more correlation keys that can be used to match against existing entities.

| Discovery Source | Primary Correlation Key | Secondary Correlation Key | Tertiary |
|-----------------|------------------------|---------------------------|----------|
| Network scan | IP address | MAC address | Hostname (rDNS) |
| Proxmox VE | — (discovers *new* logical nodes) | IP (from QEMU guest agent) | MAC (from network config) |
| Docker | — (discovers containers as services) | Container IP (bridge network) | Published ports + host IP |
| Home Assistant | — (discovers IoT devices) | IP (from HA device attributes) | MAC (from HA device attributes) |
| UniFi | MAC address | IP (from DHCP) | Hostname (from DHCP) |
| Prometheus | IP:port (scrape target) | Hostname (from `nodename` label) | — |
| Tailscale | Tailscale IP (100.x.x.x) | Hostname | Machine key |
| SNMP | IP (query target) | MAC (from ARP table) | sysName (from SNMP sysDescr) |
| IPMI/Redfish | BMC IP | — | — |
| pfSense/OPNsense | — (discovers DHCP clients) | IP + MAC from lease table | Hostname from lease |
| Pi-hole/AdGuard | — (discovers DNS clients) | IP | Hostname from query log |

### 2.3 Reconciliation Engine

The reconciliation engine runs after every discovery cycle and processes discovery results in priority order.

```python
class ReconciliationEngine:
    """
    Matches newly discovered entities against existing Hydra nodes
    to prevent duplicates and merge data from multiple sources.
    """

    # Source priority: higher = more authoritative for creating new entities
    SOURCE_PRIORITY = {
        "agent-registration": 100,  # Agent self-registered — highest trust
        "plg::proxmox-ve": 90,      # PVE knows its own VMs/LXCs
        "plg::docker": 85,          # Docker knows its own containers (as services)
        "plg::home-assistant": 80,  # HA knows its own devices
        "plg::unifi": 70,           # UniFi knows its network clients
        "network-scan": 60,         # Network scan has broad but shallow knowledge
        "plg::snmp": 55,            # SNMP provides device-level detail
        "plg::prometheus": 50,      # Prometheus targets are a weaker signal
        "plg::tailscale": 50,       # Tailscale overlay nodes
        "plg::pfsense": 40,         # Firewall sees DHCP clients
        "plg::opnsense": 40,
        "plg::pihole": 30,          # DNS sees query clients — weakest signal
        "plg::adguard": 30,
    }

    async def reconcile(self, discovered: list[DiscoveredEntity]) -> ReconciliationResult:
        result = ReconciliationResult()

        for entity in sorted(discovered, key=lambda e: self.SOURCE_PRIORITY.get(e.source, 0), reverse=True):
            match = await self._find_match(entity)

            if match:
                # Entity already exists — merge metadata
                merged = await self._merge_entity(match, entity)
                result.merged.append(merged)
            elif self._should_create(entity):
                # No match and entity is worth creating
                created = await self._create_entity(entity)
                result.created.append(created)
            else:
                # No match and entity is too low-confidence to create
                result.ignored.append(entity)

        return result

    async def _find_match(self, entity: DiscoveredEntity) -> Optional[Node]:
        """
        Try to match a discovered entity against existing nodes.
        Uses cascading correlation keys.
        """
        # 1. Exact MAC match (strongest — physical identity)
        if entity.mac:
            match = await self.db.nodes.find_one({
                "network.interfaces.mac": entity.mac.lower()
            })
            if match:
                return match

        # 2. IP match within same network
        if entity.ip:
            match = await self.db.nodes.find_one({
                "network.interfaces.ipv4": entity.ip,
                "status": {"$ne": "deregistered"}
            })
            if match:
                return match

        # 3. Hostname match (weaker — hostnames can collide)
        if entity.hostname:
            match = await self.db.nodes.find_one({
                "$or": [
                    {"displayName": entity.hostname},
                    {"nodeId": entity.hostname}
                ],
                "status": {"$ne": "deregistered"}
            })
            if match and self._confirm_hostname_match(match, entity):
                return match

        # 4. Plugin-specific matching
        if entity.source == "plg::tailscale" and entity.metadata.get("tailscaleIp"):
            match = await self.db.nodes.find_one({
                "network.interfaces.ipv4": entity.metadata["tailscaleIp"]
            })
            if match:
                return match

        if entity.source == "plg::proxmox-ve" and entity.metadata.get("vmid"):
            match = await self.db.nodes.find_one({
                "pluginData.plg::proxmox-ve.vmid": entity.metadata["vmid"],
                "pluginData.plg::proxmox-ve.parentHost": entity.metadata.get("parentHost")
            })
            if match:
                return match

        return None

    def _should_create(self, entity: DiscoveredEntity) -> bool:
        """
        Determine if a discovered entity warrants a new node entry.
        Low-confidence sources (DNS query clients, Prometheus targets)
        shouldn't create nodes unless they have strong identifying info.
        """
        source_priority = self.SOURCE_PRIORITY.get(entity.source, 0)

        # High-priority sources always create
        if source_priority >= 70:
            return True

        # Medium-priority sources create if they have IP + hostname
        if source_priority >= 50:
            return entity.ip is not None and entity.hostname is not None

        # Low-priority sources never auto-create — they only merge
        return False
```

### 2.4 Reconciliation Edge Cases

#### Case 1: VM Migrates Between Proxmox Hosts

**Scenario:** VM 105 (pihole-lxc) lives on proxmox-01. Admin live-migrates it to proxmox-02.

**What happens:**
1. Proxmox discovery next cycle reports VM 105 on proxmox-02 (not proxmox-01).
2. Reconciliation engine matches by VMID + IP (same VM, same IP, different parent).
3. Node `pihole-lxc` entity is updated: `parentNodeId` changes from `proxmox-01` to `proxmox-02`.
4. Topology edges update: old `proxmox-01 → pihole-lxc` edge removed, new `proxmox-02 → pihole-lxc` edge created.
5. Network scan still finds pihole-lxc at same IP — no conflict.

**Edge case within the edge case:** During live migration, there's a brief window where the VM exists on both hosts. Proxmox API reports `status: "migrating"`. Hydra should not create a duplicate during this window.

**Rule:** If a Proxmox-discovered entity has `status: "migrating"`, skip reconciliation for this entity until next cycle.

#### Case 2: Docker Container Recreated with New ID

**Scenario:** User does `docker compose down && docker compose up`. The `nginx` container gets a new container ID (`a1b2c3d4` → `e5f6g7h8`).

**What happens:**
1. Docker plugin reports container `e5f6g7h8` named "nginx" with same image, ports, networks.
2. Old container `a1b2c3d4` is no longer reported (it was destroyed).
3. The *service* `svc::docker::nginx` is the stable entity, not the container ID. The container ID is metadata within the service.
4. Reconciliation matches by: service name + Docker host node + port mapping.
5. Service entity updated with new container ID. No duplicate created.

**Edge case:** If the user renames the container (`nginx` → `nginx-v2`), the service name changes. This should be treated as a *new* service with the old service marked as `removed`. The name is the primary service identity for Docker containers.

#### Case 3: Same Device on Multiple Networks

**Scenario:** `proxmox-01` has two NICs: `192.168.0.10` (management VLAN) and `192.168.1.10` (storage VLAN). Network scan finds both IPs.

**What happens:**
1. Network scan reports two discovered entities at different IPs.
2. If both share the same MAC → immediate reconciliation to one entity.
3. If different MACs (two separate NICs) → both IPs are discovered independently.
4. Agent registration resolves this: the agent on proxmox-01 reports both interfaces. The reconciliation engine matches the first discovered IP to the existing node, then matches the second IP by hostname/MAC on a different interface.

**Rule:** When a node has multiple interfaces, all IPs are indexed as correlation keys. A discovery match on *any* IP for a multi-homed node matches the node.

#### Case 4: Home Assistant Device Is Also a Network-Scanned Compute Node

**Scenario:** A Raspberry Pi runs Home Assistant. It's discovered by:
- Network scan (IP 192.168.0.50)
- Agent registration (it runs hydra-agent)
- Home Assistant plugin (HA sees itself as a device in its own registry)

**What happens:**
1. Agent registration creates the node first (highest priority).
2. Network scan matches by IP → merges network data.
3. HA plugin discovers "Home Assistant Core" as a device → this is a *different kind of entity*. The HA device represents the HA software, not the Pi hardware.

**Rule:** HA-discovered devices are created as IoT-class nodes by default. If an HA device's IP matches an existing compute node, Hydra does NOT merge them — they represent different levels of abstraction. The HA device becomes a topology child of the compute node.

#### Case 5: IPMI/BMC Has Separate Management IP

**Scenario:** `proxmox-01` has system IP `192.168.0.10` and BMC IP `192.168.0.110`. IPMI plugin discovers the BMC at `192.168.0.110`.

**What happens:**
1. IPMI discovery reports a device at `192.168.0.110`.
2. This is NOT a separate node — it's the management interface of `proxmox-01`.
3. Reconciliation uses a special IPMI matching rule: look for a node whose profile includes `hardware.bmc.ip` matching the BMC IP.
4. If no profile match (agent hasn't reported BMC yet), IPMI plugin stores the BMC as a *pending correlation* until an agent profile includes BMC info.

**Rule:** IPMI/Redfish-discovered BMCs are never created as standalone nodes. They are always correlated to an existing compute node or held in a pending queue.

#### Case 6: Tailscale Overlay vs Physical Network Identity

**Scenario:** `docker-host-01` is at `192.168.0.20` on the physical network and `100.64.0.5` on the Tailscale overlay.

**What happens:**
1. Agent registers with physical IP `192.168.0.20`.
2. Tailscale plugin discovers device at `100.64.0.5` with hostname `docker-host-01`.
3. Reconciliation matches by hostname → merges Tailscale IP into the node's interface list with `network: "tailscale"` tag.
4. Both IPs now index to the same node for future correlation.

**Rule:** Tailscale IPs are stored as additional interfaces with `interfaceType: "overlay"`. They participate in correlation but don't override the primary IP.

---

## 3. Field-Level Authority Model

### 3.1 Why Field-Level Authority Matters

When multiple plugins report data about the same entity, conflicts arise. Proxmox says a VM has 4GB RAM (allocated). The agent running inside the VM says 3.8GB (visible to OS after firmware/kernel reservation). Prometheus says 3.6GB (available). Which is the "real" number?

The answer depends on *what you're asking*. Allocated? Visible? Available? Each data source is authoritative for different questions.

### 3.2 Authority Matrix

| Data Field | Authoritative Source | Why | Fallback Source |
|------------|---------------------|-----|-----------------|
| **Hardware: CPU model, cores (physical)** | Agent (native profile) | Agent reads `/proc/cpuinfo` — ground truth | IPMI/Redfish, Proxmox (for host) |
| **Hardware: CPU cores (allocated to VM/LXC)** | Proxmox VE | PVE controls the allocation | Agent (sees allocated cores) |
| **Hardware: RAM total** | Agent (native profile) | Agent reads `/proc/meminfo` — what OS sees | Proxmox (allocated), IPMI (physical DIMMs) |
| **Hardware: RAM installed (physical DIMMs)** | IPMI/Redfish | BMC reads SPD data directly | Agent (if `dmidecode` available) |
| **Hardware: Disk physical devices** | Agent (native profile) | Agent reads `/sys/block/` | IPMI (for NVMe/SAS via Redfish) |
| **Hardware: Disk pools/datasets (ZFS)** | TrueNAS | TrueNAS manages ZFS — authoritative | Agent (zpool list) |
| **Hardware: SMART data** | Agent or TrueNAS | Depends on who manages the disk | IPMI (for SAS drives) |
| **Network: IP addresses** | Agent (native profile) | Agent sees actual interface config | Network scan, DHCP (pfSense/OPNsense), UniFi |
| **Network: MAC addresses** | Agent (native profile) | Agent reads from interface | UniFi (port table), SNMP (ARP), network scan |
| **Network: Switch port assignment** | UniFi or SNMP | Switch knows its own port table | Network scan (inference from ARP) |
| **Network: VLAN membership** | UniFi or SNMP | Switch assigns VLANs | pfSense/OPNsense (VLAN interface config) |
| **Network: DNS records** | Pi-hole or AdGuard | DNS server is authoritative for DNS | pfSense (if also DNS server) |
| **Network: Firewall rules** | pfSense or OPNsense | Firewall is authoritative for firewall rules | — |
| **Network: Reverse proxy routes** | Traefik or NPM | Proxy is authoritative for route config | — |
| **Network: Tailscale identity** | Tailscale | Tailscale owns the overlay | Agent (tailscale status) |
| **Services: Container config** | Docker or Podman | Container runtime is authoritative | Agent (can list containers via CLI) |
| **Services: Container image updates** | Docker or Podman | Runtime knows current vs available tags | — |
| **Services: Uptime/response time** | Uptime Kuma | UK is purpose-built for monitoring | Prometheus (if blackbox_exporter) |
| **Services: External URL/route** | Traefik or NPM | Proxy defines external access | — |
| **IoT: Device purpose/type** | Home Assistant | HA knows device intent (light, thermostat) | — |
| **IoT: Device state** | Home Assistant | HA has real-time state | — |
| **IoT: Device network position** | Network scan or UniFi | Network infrastructure knows location | HA (if device reports IP) |
| **Virtualization: VM/LXC existence** | Proxmox VE | PVE is the hypervisor | Agent (can detect it's a VM) |
| **Virtualization: VM resource allocation** | Proxmox VE | PVE allocates resources | — |
| **Virtualization: VM snapshots/backups** | Proxmox VE | PVE manages snapshots | — |
| **Metrics: CPU/RAM/disk utilization** | Prometheus | Purpose-built for metrics collection | Agent (snapshot at profile time) |
| **IaC: Infrastructure state** | Terraform | Terraform owns its state file | — |
| **IaC: Configuration state** | Ansible | Ansible defines desired state | — |
| **BMC: Sensor readings** | IPMI/Redfish | BMC has hardware sensors | — |
| **BMC: Power state** | IPMI/Redfish | BMC controls power | Proxmox (for VM power state) |

### 3.3 Conflict Resolution Rules

When two sources disagree on the same field, Hydra applies these rules:

**Rule 1: Authoritative source wins.** If the field has a defined authoritative source (per matrix above) and that source is available, its value is canonical.

**Rule 2: Freshest data wins (for non-authoritative conflicts).** If two non-authoritative sources disagree, the more recently collected value is used.

**Rule 3: Higher-fidelity source wins.** Agent-collected data (direct system access) beats network-inferred data (scan, DNS, DHCP). Plugin-collected data (API integration) beats agent inference.

**Rule 4: Manual overrides win everything.** If a user has manually set a field value, it overrides all automated sources. Manual overrides are tracked with `source: "manual"` and `overriddenBy: userId`.

### 3.4 Practical Example: Reconciling a Full Node

`proxmox-01` is reported by 7 sources:

```
Agent:      CPU: AMD EPYC 7302 (16C/32T), RAM: 128GB, IP: 192.168.0.10, MAC: aa:bb:cc:dd:ee:01
Proxmox:    Cluster member, 3 VMs + 2 LXCs, storage pools, HA config
UniFi:      Port 1, 1Gbps, VLAN 10, MAC: aa:bb:cc:dd:ee:01
SNMP:       LLDP neighbor "proxmox-01" on switch port Gi0/1
Prometheus: node_exporter at 192.168.0.10:9100, avg CPU 12%
Tailscale:  ts IP 100.64.0.1, hostname "proxmox-01"
IPMI:       BMC at 192.168.0.110, 2x PSU, 4x fans, inlet temp 22°C
```

**Resulting unified node profile:**

| Field | Value | Source | Authority |
|-------|-------|--------|-----------|
| CPU model | AMD EPYC 7302 | Agent | Authoritative |
| CPU cores | 16C/32T | Agent | Authoritative |
| RAM | 128 GB | Agent | Authoritative (OS-visible) |
| RAM DIMMs | 4x 32GB DDR4-3200 | IPMI | Authoritative (physical) |
| Primary IP | 192.168.0.10 | Agent | Authoritative |
| Tailscale IP | 100.64.0.1 | Tailscale | Authoritative (overlay) |
| BMC IP | 192.168.0.110 | IPMI | Authoritative |
| MAC | aa:bb:cc:dd:ee:01 | Agent | Authoritative |
| Switch port | Gi0/1 (USW-Pro-24 port 1) | UniFi | Authoritative |
| VLAN | 10 (Management) | UniFi | Authoritative |
| Avg CPU utilization | 12% | Prometheus | Authoritative (metrics) |
| VM guests | 3 VMs + 2 LXCs | Proxmox | Authoritative (hypervisor) |
| HA group | critical-services | Proxmox | Authoritative |
| Power supplies | 2x PSU (both OK) | IPMI | Authoritative |
| Inlet temperature | 22°C | IPMI | Authoritative |

No conflicts — each field comes from its authoritative source, and every source contributes unique data.

---

## 4. Plugin Lifecycle & Health Management

### 4.1 Plugin State Machine

```
                        ┌─────────────┐
                        │  AVAILABLE   │  (in registry, not enabled)
                        └──────┬──────┘
                               │ enable()
                               ▼
                        ┌─────────────┐
                  ┌────►│ CONNECTING   │  (validating credentials, testing API)
                  │     └──────┬──────┘
                  │            │ success        │ failure
                  │            ▼                ▼
                  │     ┌─────────────┐  ┌─────────────┐
                  │     │  HEALTHY     │  │   ERROR      │
                  │     └──────┬──────┘  └──────┬──────┘
                  │            │                │
                  │     health check fail       │ retry (with backoff)
                  │            ▼                │
                  │     ┌─────────────┐         │
                  │     │  DEGRADED    │─────────┘
                  │     └──────┬──────┘
                  │            │ consecutive failures > threshold
                  │            ▼
                  │     ┌─────────────┐
                  │     │  CIRCUIT     │  (stop polling, wait for manual re-enable
                  │     │  OPEN        │   or auto-recovery timer)
                  │     └──────┬──────┘
                  │            │ auto-recovery timeout or manual re-enable
                  │            │
                  │            ▼
                  │     ┌─────────────┐
                  └─────│  RECOVERING  │  (single test call before full re-enable)
                        └─────────────┘

        At any state:
            disable() → DISABLED (removed from active plugin set, data preserved)
            uninstall() → AVAILABLE (configuration cleared, data preserved in profiles)
```

### 4.2 Health Check Mechanics

Each plugin implements a `health_check()` method that must complete within 10 seconds. The API calls health checks at the configured interval (default: 60 seconds).

```python
class PluginHealthResult:
    status: Literal["healthy", "degraded", "error"]
    latency_ms: int
    details: dict                # Plugin-specific health info
    capabilities_available: list  # Which touchpoints are currently functional
    last_successful: datetime
    consecutive_failures: int

# Example: Docker plugin health check
async def health_check(self) -> PluginHealthResult:
    try:
        start = time.monotonic()
        info = await self.docker_client.info()  # GET /info
        latency = (time.monotonic() - start) * 1000

        return PluginHealthResult(
            status="healthy" if latency < 5000 else "degraded",
            latency_ms=int(latency),
            details={
                "version": info["ServerVersion"],
                "containers": info["Containers"],
                "containersRunning": info["ContainersRunning"],
                "driverStatus": info["Driver"]
            },
            capabilities_available=["profileEnrichment", "discovery",
                                    "commandProvider", "executionHandler",
                                    "topologyProvider"]
        )
    except ConnectionError:
        return PluginHealthResult(
            status="error",
            latency_ms=-1,
            details={"error": "Docker socket unreachable"},
            capabilities_available=[]
        )
```

### 4.3 Circuit Breaker Configuration

```json
{
  "circuitBreaker": {
    "failureThreshold": 5,
    "degradedThreshold": 3,
    "recoveryTimeoutSeconds": 300,
    "halfOpenMaxAttempts": 2,
    "healthCheckIntervalSeconds": 60,
    "healthCheckIntervalDegradedSeconds": 30,
    "healthCheckIntervalErrorSeconds": 120
  }
}
```

**Behavior:**
- After 3 consecutive health check failures → state transitions to `DEGRADED`. Commands still attempted but with increased timeout awareness.
- After 5 consecutive failures → state transitions to `CIRCUIT_OPEN`. No commands routed to this plugin. Discovery/enrichment skipped. WebSocket event emitted to web clients.
- After 300 seconds in `CIRCUIT_OPEN` → automatic transition to `RECOVERING`. Single health check attempted.
- If recovery health check succeeds → back to `HEALTHY`. If fails → back to `CIRCUIT_OPEN` with doubled recovery timeout (exponential backoff, max 1 hour).

### 4.4 Health Dashboard Data

```json
{
  "pluginId": "plg::docker",
  "state": "healthy",
  "health": {
    "status": "healthy",
    "latencyMs": 45,
    "consecutiveFailures": 0,
    "lastSuccessful": "2026-02-24T12:00:00Z",
    "lastCheck": "2026-02-24T12:01:00Z",
    "uptimePercent": 99.8,
    "capabilitiesAvailable": ["profileEnrichment", "discovery", "commands", "execution", "topology"]
  },
  "stats": {
    "enrichmentsCompleted": 1247,
    "enrichmentsFailed": 3,
    "discoveryRuns": 48,
    "commandsExecuted": 156,
    "commandsFailed": 2,
    "avgEnrichmentMs": 320,
    "avgCommandMs": 1500
  },
  "nodeBindings": {
    "total": 3,
    "active": 3,
    "nodes": ["docker-host-01", "docker-host-02", "homelab-01"]
  }
}
```

---

## 5. Failure Modes & Graceful Degradation

### 5.1 Failure Mode Catalog

Every plugin can fail. The question is: what breaks when it does, and what still works?

#### 5.1.1 Proxmox VE Failures

| Failure | Impact | Fallback | Recovery |
|---------|--------|----------|----------|
| PVE API unreachable | No VM/LXC discovery, no profile enrichment, no Proxmox commands | VM nodes still exist from last successful discovery. Agent profiles still collected natively. Service commands fall back to agent-based execution. | Auto-recover when API returns. Re-run discovery. |
| PVE API auth expired | Same as unreachable | Same | Alert user to regenerate API token. |
| PVE returns stale data (node in cluster partition) | Inconsistent VM locations, possible duplicate VMs across hosts | Use `migration` status flag to detect splits. If quorum lost, mark all Proxmox data as `confidence: low`. | Wait for cluster recovery, then full re-discovery. |
| VMID collision after restore | Restored VM has same VMID as existing VM on different host | Detect by VMID + host combination. If VMID matches but host differs and it's not a migration, flag for manual review. | Admin reconciliation via UI. |

#### 5.1.2 Docker Failures

| Failure | Impact | Fallback | Recovery |
|---------|--------|----------|----------|
| Docker socket inaccessible | No container data, no Docker commands | Services discovered via port scan still show as running. Agent can still report process list. | Check socket permissions (`/var/run/docker.sock` needs group `docker`). Agent restarts detection. |
| Docker daemon not responding (hung) | API calls timeout, commands fail | Circuit breaker opens. Commands fall back to agent shell execution. | Docker daemon restart on host. Plugin auto-recovers. |
| Docker compose file not found | `compose-up` / `compose-down` commands fail | Individual container commands still work. | User provides correct compose path. |
| Docker image registry unreachable | `docker pull` fails | No fallback — pull is network-dependent. | Report registry error to user. Retry later. |
| Rootless Docker different socket path | Plugin can't connect to socket | Agent detection reports correct socket path. | User updates plugin config with correct `socketPath`. |

#### 5.1.3 Home Assistant Failures

| Failure | Impact | Fallback | Recovery |
|---------|--------|----------|----------|
| HA unreachable | No IoT device states, no HA commands, family users lose functionality | IoT nodes show last-known state with staleness indicator. No control commands available. | Auto-recover when HA returns. |
| HA long-lived token expired | Auth fails, all HA operations fail | Same as unreachable | Alert user to generate new token in HA UI and update config. |
| HA WebSocket disconnects | No real-time state updates | Fall back to polling REST API at reduced interval. | Auto-reconnect with exponential backoff. |
| HA integration (e.g., Hue) unavailable | Subset of entities show "unavailable" | Hydra reflects HA's entity state — "unavailable" is accurate data. | HA-side fix (restart integration, check hub connectivity). |
| HA database corruption | Stale states, missing devices | If HA reports fewer entities than last sync, don't auto-delete Hydra nodes. Flag as "possibly stale" for manual review. | HA backup restore. Hydra re-syncs automatically. |

#### 5.1.4 Ansible Failures

| Failure | Impact | Fallback | Recovery |
|---------|--------|----------|----------|
| Ansible not installed on API host | All Ansible commands fail | Detection reports ansible unavailable. Commands rejected with clear error. | Install ansible on API host. |
| SSH key auth failure | Playbook runs fail for affected hosts | Per-host failure reported in results. Other hosts succeed. | Fix SSH keys for affected hosts. |
| Playbook syntax error | Playbook fails before executing any tasks | Ansible reports syntax error in output. Hydra captures and returns to user. | User fixes playbook. |
| Target host unreachable via SSH | Individual host fails in batch | Ansible marks host as "unreachable". Other hosts complete. Hydra reports per-host results. | Fix network/SSH connectivity. |
| Vault password file missing | Encrypted variables unavailable | Playbooks using vault vars fail. Non-vault playbooks succeed. | Provide vault password file path. |
| Concurrent playbook execution | State conflicts on target hosts | Hydra implements execution lock per host — second playbook queues until first completes. | Automatic queuing with configurable concurrency limit. |

#### 5.1.5 Terraform Failures

| Failure | Impact | Fallback | Recovery |
|---------|--------|----------|----------|
| Terraform not installed | All TF commands fail | Detection reports unavailable. | Install terraform on API host. |
| State file locked | Apply/plan blocked | Report lock holder and age to user. | `terraform force-unlock` if lock is stale. |
| State file corrupted | All operations fail for workspace | Alert user immediately. Do not attempt automatic recovery. | User restores state from backup. |
| Provider API unreachable | Plan/apply fails for that provider | Report which provider failed. Other providers in same config may succeed partially. | Fix provider connectivity. |
| Plan shows destructive changes | User may accidentally destroy infrastructure | Hydra always requires explicit approval for plans that include `destroy` actions. Plan output shown in full before confirmation. | User reviews and decides. |
| Concurrent apply | State corruption risk | Hydra implements workspace lock — only one operation per workspace at a time. | Automatic locking with clear error on conflict. |

#### 5.1.6 Network/Firewall Plugin Failures (UniFi, SNMP, pfSense, OPNsense)

| Failure | Impact | Fallback | Recovery |
|---------|--------|----------|----------|
| UniFi controller unreachable | No switch port data, no client tracking, no network topology | Last-known topology preserved. Network scan provides basic connectivity data. SNMP can fill in switch port data if enabled. | Auto-recover when controller returns. |
| SNMP timeout on device | No interface/VLAN data for that device | Other SNMP devices still polled. Network scan provides basic connectivity. | Check SNMP community string, network reachability. |
| pfSense/OPNsense API package not installed | All firewall commands fail | Detection reports API unavailable. Firewall still functions, just can't be managed via Hydra. | Install FauxAPI/pfSense-api package or OPNsense API plugin. |
| Firewall rule reload causes brief outage | Network disruption during `cmd::pfsense::reload-rules` | This is expected behavior, not a failure. Command output should warn about potential brief disruption. | Self-resolving within seconds. |

#### 5.1.7 DNS Plugin Failures (Pi-hole, AdGuard)

| Failure | Impact | Fallback | Recovery |
|---------|--------|----------|----------|
| Pi-hole API unreachable | No DNS stats, no ad blocking toggle | DNS resolution still works (Pi-hole functions independently of its API). Hydra shows stale stats. | Auto-recover. |
| Pi-hole disable command while users are browsing | Ads appear for all network users | Command confirmation warns about network-wide impact. | User re-enables or timeout restores (Pi-hole supports timed disable). |
| AdGuard filter update fails | Stale blocklists | No user-facing impact unless specific domains now unblocked. | Retry update. Check upstream filter URLs. |

#### 5.1.8 Monitoring/Storage Plugin Failures (Prometheus, TrueNAS, Uptime Kuma, IPMI)

| Failure | Impact | Fallback | Recovery |
|---------|--------|----------|----------|
| Prometheus server unreachable | No metric enrichment, no metric query MCP tools | Agent-collected profile snapshots still provide basic resource data. Stale metrics shown with indicator. | Auto-recover. |
| TrueNAS API unreachable | No pool/dataset data, no storage commands | Agent on TrueNAS host can still collect basic disk info natively. | Auto-recover. |
| Uptime Kuma unreachable | No service uptime data | Services still tracked by Hydra's native service discovery. Uptime history pauses. | Auto-recover. |
| IPMI tool missing | No BMC access, no sensor readings, no power control | Agent-collected hardware data via `/sys/` and `dmidecode` still available. No remote power control. | Install `ipmitool` or `ipmi-sensors` on agent host. |
| IPMI BMC on separate management VLAN unreachable from API | API can't reach BMC directly | If agent has access (dual-homed), agent proxies IPMI commands (max tier). | Configure agent-proxied IPMI or add route to management VLAN. |

### 5.2 Cascading Failure Scenarios

#### Scenario: Proxmox Host Goes Down

```
Event: proxmox-01 becomes unreachable

Direct Impact:
  - plg::proxmox-ve: Can't query PVE API → DEGRADED
  - Agent on proxmox-01: Goes offline → all plugins using agent-local execution lose that node
  - plg::docker (on proxmox-01): Socket inaccessible → CIRCUIT_OPEN for that node binding
  - plg::ipmi (for proxmox-01): BMC may still be reachable (separate power) → check BMC health

Indirect Impact:
  - All VMs/LXCs on proxmox-01: Agents go offline if they were virtual guests
  - plg::docker on VMs that ran Docker: Those Docker hosts are also down
  - Services on those VMs: Marked offline via Uptime Kuma (if monitoring them)
  - Topology: Entire branch of proxmox-01 → VM → containers marked "parent offline"

What Hydra Does:
  1. Detects proxmox-01 agent offline (missed heartbeat)
  2. Proxmox plugin health check fails → DEGRADED → CIRCUIT_OPEN
  3. All child nodes (VMs/LXCs) agents also go offline
  4. Topology graph shows proxmox-01 subtree in error state
  5. Blast radius doc for proxmox-01 immediately relevant
  6. Dashboard widgets show cascading red state
  7. MCP can answer: "What's affected by proxmox-01 being down?" using topology data

What Hydra Does NOT Do:
  - Does NOT delete any nodes or services
  - Does NOT deregister agents
  - Does NOT remove topology edges
  - Preserves all last-known state for Time Machine
```

#### Scenario: Network Partition (Management VLAN Isolated)

```
Event: Switch misconfiguration isolates VLAN 10 (management) from VLAN 1 (API)

Direct Impact:
  - All nodes on VLAN 10 become unreachable from API
  - Agent heartbeats fail for VLAN 10 nodes
  - All plugins using API-direct communication to VLAN 10 devices fail
  - UniFi controller (if on VLAN 10) → plg::unifi CIRCUIT_OPEN
  - pfSense (if management on VLAN 10) → plg::pfsense CIRCUIT_OPEN

Still Working:
  - Agents on VLAN 10 nodes continue collecting profiles locally (cached)
  - When partition heals, agents submit cached profiles
  - Plugins on unaffected VLANs continue normally
  - If API and Tailscale are on different paths, Tailscale overlay may still work

What Hydra Does:
  1. Detects multiple simultaneous agent failures on same VLAN
  2. Correlates failures to network segment (nodes share 192.168.10.0/24)
  3. Marks VLAN 10 network entity as "connectivity issue"
  4. Does not trigger per-node alerts (would be noisy) — triggers single network alert
  5. When partition heals, processes queued agent submissions in batch
```

---

## 6. Cross-Plugin Interaction Matrix

### 6.1 Plugin Pair Interactions

Not all 19 plugins interact with each other. This matrix identifies pairs that do and describes the interaction.

| Plugin A | Plugin B | Interaction Type | Description |
|----------|----------|-----------------|-------------|
| **Proxmox** | **Docker** | Parent-child chaining | VMs discovered by Proxmox may run Docker. Topology: `pve-host → VM → container`. Docker plugin on VM needs to know it's a Proxmox guest (for migration-aware behavior). |
| **Proxmox** | **IPMI** | Physical-virtual mapping | IPMI manages the physical server running Proxmox. Power commands affect all VMs. Hydra must warn before IPMI power-off of a Proxmox host. |
| **Proxmox** | **TrueNAS** | Storage provider | TrueNAS SCALE runs on Proxmox or shares storage with it. ZFS pools on TrueNAS may be NFS-mounted by Proxmox for VM storage. |
| **Docker** | **Traefik** | Service-to-route mapping | Traefik routes to Docker containers. Container labels define routes. Hydra can map `traefik route → Docker container → host node` as a complete request path. |
| **Docker** | **NPM** | Service-to-proxy mapping | NPM proxies to Docker containers by IP:port. Hydra correlates NPM proxy hosts to Docker services. |
| **Docker** | **Uptime Kuma** | Service-to-monitor mapping | Uptime Kuma monitors Docker service endpoints. Hydra correlates UK monitors to Docker services by URL/port matching. |
| **Docker** | **Podman** | Mutual exclusion | Both manage containers. A host runs Docker OR Podman (or both in rare cases). If both are detected on the same host, Hydra treats them as separate container runtimes with separate service namespaces. |
| **Home Assistant** | **Network scan** | Entity deduplication | HA devices often appear in network scans. See reconciliation §2.4 Case 4. HA provides purpose/state, network scan provides network position. |
| **Home Assistant** | **Pi-hole/AdGuard** | DNS + IoT correlation | Pi-hole sees DNS queries from IoT devices HA manages. Hydra can correlate: "light.living_room queries ntp.ubuntu.com 50 times/day" for device behavior analysis. |
| **UniFi** | **SNMP** | Complementary network data | UniFi provides managed switch data. SNMP provides data for non-UniFi managed switches. Both contribute to network topology. UniFi-managed devices should NOT also be polled via SNMP (duplicate data). |
| **UniFi** | **Tailscale** | Overlay-underlay correlation | UniFi sees physical client at MAC/port. Tailscale sees overlay node at Tailscale IP. Hydra merges both views into a single node with both network identities. |
| **pfSense** | **Pi-hole** | DNS + firewall correlation | pfSense provides DHCP leases and firewall rules. Pi-hole provides DNS resolution. Together they paint a complete network access picture per client. |
| **pfSense** | **OPNsense** | Mutual exclusion | Both are firewalls. User has one or the other, not both. If both are somehow enabled, Hydra will have conflicting firewall data. Config validation should prevent this. |
| **Prometheus** | **All agent-connected plugins** | Metrics complement profiles | Prometheus provides time-series metrics while profiles are point-in-time snapshots. Prometheus enrichment adds "typical" values alongside profile "current" values. |
| **Ansible** | **Terraform** | Complementary IaC | Terraform provisions infrastructure, Ansible configures it. Workflow: `terraform apply (create VM) → ansible playbook (configure VM)`. The workflow builder should support this chain natively. |
| **Ansible** | **All compute nodes** | Configuration management | Ansible can target any Hydra compute node via SSH. Hydra's dynamic inventory ensures Ansible always has current host data. |
| **Traefik** | **NPM** | Mutual exclusion per service | A service is proxied by Traefik OR NPM, not both. If both claim routes to the same backend, the user has a misconfiguration. Hydra should flag this. |

### 6.2 Topology Edge Conflicts

When multiple plugins contribute topology edges for the same entity pair, rules determine which edge wins or how edges merge.

| Conflict | Resolution |
|----------|-----------|
| UniFi says "node X on port 5" but SNMP says "node X on port 3" | UniFi wins for UniFi-managed switches (it's the controller). SNMP wins for non-UniFi switches. If the switch is UniFi-managed, SNMP data for that switch is suppressed. |
| Proxmox says "VM on proxmox-01" but agent says "I'm running on proxmox-02" (post-migration) | Agent self-report takes precedence for *current* location. Proxmox data may be stale if migration occurred between discovery cycles. |
| Traefik says "routes to 192.168.0.20:8080" and Docker says "nginx is on 192.168.0.20:8080" | These are not conflicting — they're complementary. Merge into a single topology chain: `traefik-route → docker-host:8080 → nginx-container`. |
| Two different Docker hosts both report a container named "nginx" | No conflict — these are different entities (`svc::docker::nginx@docker-host-01` vs `svc::docker::nginx@docker-host-02`). ServiceId is scoped to the host. |

---

## 7. Core Plugin Deep Dives — Edge Cases & Hard Problems

### 7.1 Proxmox VE — Deep Dive

#### 7.1.1 Cluster HA Failover

**Problem:** Proxmox HA can automatically migrate a VM from a failed node to a healthy one. This happens without user intervention and can occur between Hydra discovery cycles.

**Impact on Hydra:**
- VM's `parentNodeId` needs to change
- Topology edges need to update
- The VM may briefly have a different IP if DHCP-assigned
- Agent on the VM (if any) may lose connectivity briefly

**Solution:**
```python
async def handle_proxmox_ha_event(self, event: dict):
    """
    Called when Proxmox HA triggers a migration.
    Proxmox can notify via webhook (if configured) or we detect during discovery.
    """
    vmid = event["vmid"]
    old_host = event["source_node"]
    new_host = event["target_node"]

    # 1. Find Hydra node for this VMID
    node = await self.db.nodes.find_one({
        "pluginData.plg::proxmox-ve.vmid": vmid
    })
    if not node:
        return  # VM not tracked by Hydra

    # 2. Update parent node
    await self.db.nodes.update_one(
        {"nodeId": node["nodeId"]},
        {"$set": {
            "parentNodeId": self.resolve_hydra_node_id(new_host),
            "pluginData.plg::proxmox-ve.currentHost": new_host,
            "pluginData.plg::proxmox-ve.lastMigration": {
                "from": old_host,
                "to": new_host,
                "timestamp": datetime.utcnow(),
                "type": "ha-failover"
            }
        }}
    )

    # 3. Update topology edges
    await self.topology_service.remove_edge(old_host, node["nodeId"], "hosts")
    await self.topology_service.add_edge(new_host, node["nodeId"], "hosts", {
        "vmid": vmid, "type": "ha-migrated"
    })

    # 4. If the VM runs Docker, update Docker plugin binding to reflect new physical host
    if "plg::docker" in node.get("plugins", {}):
        # Docker plugin binding is to the VM, not the physical host — no change needed
        # But if Docker plugin uses agent proxy through the physical host, route needs updating
        pass
```

#### 7.1.2 Ceph Storage Across Cluster

**Problem:** Proxmox clusters with Ceph have shared storage that doesn't belong to any single host. VM disks live on Ceph OSDs distributed across nodes.

**Impact on Hydra:**
- Storage pool appears on all cluster nodes but is a single logical entity
- Disk usage is shared, not per-host
- VM migration doesn't require disk copy (Ceph is already shared)

**Solution:** Ceph storage pools are tracked as first-class entities in the topology graph with edges to all cluster nodes. Profile enrichment reports Ceph pools separately from local storage.

```json
{
  "ceph": {
    "poolName": "rbd-pool",
    "totalGb": 2000,
    "usedGb": 750,
    "osdCount": 6,
    "replicas": 2,
    "status": "HEALTH_OK"
  }
}
```

#### 7.1.3 Nested Virtualization

**Problem:** A Proxmox VM runs Docker inside it. From Hydra's perspective, this creates a three-level hierarchy: `pve-host → VM → Docker container`.

**Impact:** Docker plugin binds to the VM (where the socket is), not the Proxmox host. But the VM's resources are constrained by Proxmox allocation. Capacity planning must account for this: the Docker containers can't use more RAM than the VM is allocated, even if the VM thinks it has "free" RAM.

**Solution:** When computing capacity for a Docker host that is also a Proxmox VM, Hydra uses `min(VM_allocated_RAM, VM_visible_RAM)` as the ceiling. The VM's Proxmox allocation data (from `plg::proxmox-ve`) constrains the Docker resource calculations (from `plg::docker`).

#### 7.1.4 Templates vs Running VMs

**Problem:** Proxmox templates show up in the VM list but are not running entities. They should not be created as Hydra nodes, not targeted by commands, and not profiled.

**Solution:** The Proxmox discovery filter excludes entities where `template: true`. Templates appear in Proxmox profile enrichment data (as available templates for cloning) but don't create Hydra node entries.

### 7.2 Docker — Deep Dive

#### 7.2.1 Multi-Host Container Aggregation

**Problem:** User has Docker on 3 hosts. They want to see "all my containers" in one view, not per-host. The Dashboard Framework, Doc System, and MCP all need to aggregate.

**Solution:** Containers are scoped to host in the data model (`svc::docker::nginx@docker-host-01`), but query endpoints support cross-host aggregation:

```
GET /services?runtime=docker          → all Docker containers across all hosts
GET /services?runtime=docker&nodeId=X → containers on host X only
```

MCP tool `list_docker_containers` aggregates across all Docker hosts by default. The Dashboard "Docker Fleet" template uses the cross-host query.

#### 7.2.2 Docker-in-Docker and Socket Mapping

**Problem:** Some setups mount the Docker socket into a container (e.g., Portainer, CI runners). The container can create other containers, making the discovered container tree misleading.

**Impact:** Hydra sees containers created by Portainer as children of the host, not of Portainer. There's no parent-child relationship in Docker's data model for "container A created container B."

**Solution:** Hydra tracks the `com.docker.compose.project` label to group containers by compose project. Containers without a compose project are grouped by image name similarity. The DinD scenario is documented as a known limitation — Hydra profiles the *host's* Docker state, not per-container Docker state.

#### 7.2.3 Image Update Detection

**Problem:** A container runs `nginx:latest` but the local image is 3 months old. The registry has a newer `nginx:latest`. How does Hydra detect this?

**Solution:** The Docker plugin enrichment includes the image digest (`sha256:...`). Image update detection is a scheduled job (not real-time) that compares local digests against registry manifests. This requires registry access and is opt-in per host.

```json
{
  "imageUpdates": [
    {
      "image": "nginx:latest",
      "localDigest": "sha256:abc123...",
      "registryDigest": "sha256:def456...",
      "updateAvailable": true,
      "localCreated": "2025-11-15T00:00:00Z",
      "registryCreated": "2026-02-20T00:00:00Z"
    }
  ]
}
```

#### 7.2.4 Compose Project File Location

**Problem:** The Docker API doesn't reliably report compose file paths. Container labels include `com.docker.compose.project.working_dir` but this may not be the actual file location (could be `/` if compose was run from stdin).

**Solution:** The agent scans common locations (`/opt/stacks/`, `/home/*/docker/`, `/docker/`, etc.) for `docker-compose.yml` / `compose.yml` files and matches them to running projects by service name correlation. Configurable via `composeSearchPaths` in plugin config.

### 7.3 Home Assistant — Deep Dive

#### 7.3.1 The Authority Problem

**Problem:** When both HA and network scan discover the same device (e.g., a smart plug at 192.168.1.50), which is the source of truth?

**Answer (from §3 Authority Model):**
- HA is authoritative for: device purpose (it's a smart plug), state (it's on/off), device type (switch.living_room_plug), area assignment (living room).
- Network scan is authoritative for: network position (IP, MAC, which switch port, which VLAN).
- Neither overrides the other — they contribute to different fields.

**Implementation:** The reconciliation engine matches by IP/MAC but does NOT merge the HA device *into* the network scan result. Instead, it creates a topology edge: `network-device → ha-entity`, allowing both identities to coexist.

#### 7.3.2 Entity Explosion

**Problem:** A typical HA installation has hundreds of entities (every light, sensor, automation, script, binary_sensor). If every entity becomes a Hydra node, the node list becomes unusable.

**Solution:** Hydra does NOT create a Hydra node per HA entity. Instead:
- HA **devices** may become Hydra IoT nodes (one node per physical device, e.g., "Philips Hue Bridge").
- HA **entities** are profile enrichment data on the device node.
- The `filters.includeDomains` config controls which domains are tracked.
- HA **areas** become topology grouping nodes.

Default filter: `["light", "switch", "climate", "sensor", "binary_sensor", "media_player", "lock", "cover", "fan"]` — excludes automation, script, scene, input_*, etc. from discovery.

#### 7.3.3 HA Device Without IP (Zigbee/Z-Wave)

**Problem:** Many HA devices communicate via Zigbee or Z-Wave through a coordinator. They don't have IP addresses. Network scan can't find them.

**Impact:** No network-scan correlation possible. These devices exist only in HA's registry.

**Solution:** Zigbee/Z-Wave devices are discovered purely through HA. They become IoT-class nodes with `networkType: "zigbee"` or `networkType: "zwave"`. Their topology parent is the coordinator device (e.g., the Zigbee USB stick's host node). They participate in the HA area hierarchy but not in the IP-based network topology.

#### 7.3.4 HA WebSocket vs REST API Tradeoffs

**Problem:** HA's REST API is simple but polling-based. The WebSocket API provides real-time state changes but is more complex to manage (connection drops, event flood).

**Solution:** Hydra uses REST API by default (polling at profile intervals — infrequent, not real-time). WebSocket is an opt-in feature (`websocketEvents: true`) that provides real-time state updates to the Dashboard and MCP. WebSocket events are NOT stored as profile data — they update a separate `iot_state_cache` collection for dashboard widgets.

### 7.4 Ansible — Deep Dive

#### 7.4.1 Idempotency Tracking

**Problem:** Ansible playbooks should be idempotent, but Hydra can't verify this. Running the same playbook twice might show "changed" tasks, indicating the target drifted from expected state.

**Solution:** Hydra tracks playbook run history per node and compares "changed" task counts across runs. If a playbook that previously showed 0 changes now shows 5, Hydra flags "configuration drift detected" on those nodes. This feeds into the Documentation System's change journal.

#### 7.4.2 SSH Key Bootstrap Problem

**Problem:** Ansible needs SSH access to target hosts. But for a new node just registered in Hydra, SSH keys might not be deployed yet. Chicken-and-egg: you want Ansible to configure the node, but Ansible can't reach the node.

**Solution:** The agent installation process (via hydra-agent remote installation) can optionally deploy an SSH public key for the Ansible control user during agent bootstrap. The installation script:
1. Downloads and installs hydra-agent
2. Creates `hydra-ansible` user (if configured)
3. Adds Hydra's SSH public key to `authorized_keys`
4. Reports SSH readiness in registration

This makes the node Ansible-ready from the moment it registers.

#### 7.4.3 Concurrent Execution Locks

**Problem:** Two users trigger Ansible playbooks targeting the same host simultaneously. Package installations conflict, service restarts race.

**Solution:** Hydra implements per-host execution locks for Ansible operations:

```python
class AnsibleExecutionLock:
    """
    Prevents concurrent Ansible operations targeting the same hosts.
    """
    async def acquire(self, target_hosts: list[str], execution_id: str) -> bool:
        # Try to lock all target hosts atomically
        for host in target_hosts:
            existing_lock = await self.db.ansible_locks.find_one({
                "host": host,
                "released": False,
                "expiresAt": {"$gt": datetime.utcnow()}
            })
            if existing_lock:
                raise ExecutionConflict(
                    f"Host {host} is locked by execution {existing_lock['executionId']} "
                    f"(started {existing_lock['acquiredAt']}). "
                    f"Wait for completion or force-release."
                )

        # Acquire locks for all hosts
        for host in target_hosts:
            await self.db.ansible_locks.insert_one({
                "host": host,
                "executionId": execution_id,
                "acquiredAt": datetime.utcnow(),
                "expiresAt": datetime.utcnow() + timedelta(seconds=3600),
                "released": False
            })
        return True
```

### 7.5 Terraform — Deep Dive

#### 7.5.1 Plan-Approve-Apply Lifecycle in Workflows

**Problem:** Terraform operations are multi-phase. A `plan` produces a preview. A human reviews it. An `apply` executes it. This lifecycle must be represented in the workflow builder as a gate, not a single step.

**Solution:** The Terraform workflow block type has a built-in gate:

```
┌──────────┐     ┌──────────────┐     ┌──────────┐
│  tf plan  │────►│ Human Review  │────►│ tf apply  │
│           │     │ (gate block)  │     │           │
└──────────┘     └──────────────┘     └──────────┘
                     │ reject
                     ▼
                 ┌──────────┐
                 │  Cancel   │
                 └──────────┘
```

The plan output (additions, changes, deletions) is presented in the web UI. The workflow pauses at the gate until an admin approves or rejects. Timeout configurable (default: 24 hours).

#### 7.5.2 State File Security

**Problem:** Terraform state files contain sensitive information (resource IDs, IP addresses, sometimes passwords). They must be secured.

**Solution:**
- State files stored in Hydra-managed directory with strict filesystem permissions (0600).
- State file contents are NEVER exposed through the Hydra API.
- `cmd::terraform::state-list` returns resource names only, not full state.
- State backup taken before every `apply` operation.
- State encryption at rest is configurable (using Terraform's built-in state encryption or SOPS).

#### 7.5.3 Long-Running Apply Operations

**Problem:** Cloud provider operations (e.g., creating a VM, provisioning DNS) can take 10+ minutes. The workflow shouldn't block the entire API.

**Solution:** Terraform operations run as background tasks with progress reporting:

1. `terraform apply` starts as a subprocess.
2. Output is streamed line-by-line to a WebSocket channel.
3. The execution record is updated with progress as Terraform reports resource creation.
4. Client can disconnect and reconnect — output is buffered.
5. Timeout is per-workspace configurable (default: 30 minutes, max: 2 hours).

### 7.6 Prometheus — Deep Dive

#### 7.6.1 Label-to-Node Correlation

**Problem:** Prometheus identifies targets by labels (`instance`, `job`, `nodename`). Hydra identifies nodes by `nodeId`. Mapping between them is required for metric enrichment and MCP queries.

**Solution:** Hydra maintains a `prometheus_target_map` that correlates Prometheus labels to Hydra nodes:

```python
async def build_target_map(self):
    """
    Build mapping from Prometheus target labels to Hydra node IDs.
    Uses IP matching as primary correlation.
    """
    targets = await self.prometheus.get("/api/v1/targets")
    nodes = await self.db.nodes.find({"status": "active"}).to_list()

    node_by_ip = {}
    for node in nodes:
        for iface in node.get("network", {}).get("interfaces", []):
            if iface.get("ipv4"):
                node_by_ip[iface["ipv4"]] = node["nodeId"]

    target_map = {}
    for target in targets["data"]["activeTargets"]:
        instance = target["labels"].get("instance", "")
        ip = instance.split(":")[0]
        if ip in node_by_ip:
            target_map[instance] = node_by_ip[ip]

    return target_map
```

#### 7.6.2 Prometheus Enrichment Is Not Real-Time Monitoring

**Critical distinction:** Hydra captures metric snapshots at profile time, not continuous time-series. When Prometheus enriches a node profile, it takes a 5-minute window average, not a current value. This is intentional — Hydra profiles "what is this node like" not "what is this node doing right now."

If users want real-time monitoring, they should use Prometheus + Grafana directly. Hydra's Prometheus integration is for *profile-time characterization*.

---

## 8. Default Plugin Deep Dives — Edge Cases & Hard Problems

### 8.1 Podman — vs Docker Differentiation

**Key differences that affect implementation:**

| Concern | Docker | Podman |
|---------|--------|--------|
| Socket path | `/var/run/docker.sock` | `$XDG_RUNTIME_DIR/podman/podman.sock` (rootless) or `/run/podman/podman.sock` (rootful) |
| Daemon | Always running | Socket-activated (starts on demand, may timeout) |
| Pod grouping | Not native (compose projects) | Native pods (like k8s pods) |
| Systemd integration | Separate from systemd | `podman generate systemd` creates native units |
| Service identity | Container name | Container name OR pod name + container |
| Rootless default | No (rootful default) | Yes (rootless default) |

**Socket activation problem:** Podman's socket activates on first API call and may deactivate after a timeout. Agent detection must `curl` the socket to wake it up before checking availability. If the socket exists but Podman isn't installed, the activation fails — distinguish between "socket exists but broken" and "Podman not installed."

**Pod-aware service modeling:** When Podman runs containers in pods, the pod is the service unit (like a k8s pod). Services should be identified as `svc::podman::pod-name::container-name`, not just by container name.

### 8.2 UniFi — Practical Challenges

#### 8.2.1 Unofficial API

**Problem:** UniFi's REST API is unofficial and undocumented. It changes between firmware versions without notice.

**Solution:**
- Version detection on connect: check UniFi controller version and select appropriate API client module.
- Defensive parsing: treat all fields as optional, log unexpected response shapes.
- Community-maintained API spec: track https://ubntwiki.com/products/software/unifi-controller/api for changes.

#### 8.2.2 Client Churn (Transient vs Permanent)

**Problem:** Wireless clients come and go constantly (phones, tablets, guests). Creating a Hydra node for every device that ever connected would flood the node list.

**Solution:**
- Only create Hydra nodes for UniFi clients that are "known" (given a fixed IP, alias, or group in UniFi).
- Transient clients (connected < 24 hours, no alias, no static IP) are tracked in UniFi enrichment data but do NOT create Hydra nodes.
- Configurable threshold: `clientRetentionHours: 168` (7 days) — clients unseen for this long are pruned from enrichment data.

#### 8.2.3 Multi-Site UniFi

**Problem:** Some users run multiple UniFi sites (e.g., "Home" and "Office") on the same controller.

**Solution:** The UniFi plugin config includes `site: "default"` or specific site name. If multiple sites are needed, multiple plugin instances can be configured with different `site` values. Each instance has its own health check and node bindings.

### 8.3 SNMP — Classification Challenge

**Problem:** SNMP returns `sysDescr` (a free-text string) and OID trees. How do you know if a device is a switch, a printer, a UPS, or a NAS?

**Solution:** Hydra uses a classification heuristic based on known OID patterns:

```python
DEVICE_CLASSIFIERS = [
    # Check for bridge MIB (switches)
    {"oid": "1.3.6.1.2.1.17", "class": "networking", "kind": "switch"},
    # Check for printer MIB
    {"oid": "1.3.6.1.2.1.43", "class": "compute", "kind": "printer"},
    # Check for UPS MIB
    {"oid": "1.3.6.1.2.1.33", "class": "compute", "kind": "ups"},
    # Check for ifTable with many interfaces (likely switch)
    {"oid": "1.3.6.1.2.1.2.2.1", "class": "networking", "kind": "switch",
     "condition": "ifCount > 8"},
]

# Fallback: parse sysDescr for keywords
SYSDESCR_KEYWORDS = {
    "ProCurve": ("networking", "switch"),
    "Cisco": ("networking", "switch"),
    "APC": ("compute", "ups"),
    "Brother": ("compute", "printer"),
    "Synology": ("compute", "nas"),
}
```

### 8.4 pfSense vs OPNsense — Why Separate Plugins

Despite similar functionality, the APIs are completely different:

| Concern | pfSense | OPNsense |
|---------|---------|----------|
| API type | FauxAPI (3rd party package) | Built-in REST API |
| Auth method | API key + secret (header) | API key + secret (HTTP basic auth) |
| Endpoint structure | `/fauxapi/v1/?action=...` | `/api/{module}/{controller}/{action}` |
| Firewall rules format | XML-based (pfSense config) | JSON (native API) |
| Plugin availability | Requires manual package install | Built into OPNsense |
| Error handling | HTTP 200 with error in body | Proper HTTP status codes |

Attempting to abstract both behind a single "firewall" driver would leak complexity everywhere. Separate plugins are cleaner.

### 8.5 Traefik vs NPM — Complementary But Exclusive

**Problem:** Both are reverse proxies. A service should be routed through one or the other, not both. But a user might have Traefik for some services and NPM for others on the same network.

**Solution:** Both plugins can be enabled simultaneously. Hydra tracks which proxy routes to which backend. If both claim a route to the same backend (same IP:port), Hydra flags a configuration warning. Services are tagged with their proxy source: `proxy: "traefik"` or `proxy: "npm"`.

### 8.6 TrueNAS — ZFS Complexity

#### 8.6.1 Pool/Dataset/Zvol Hierarchy

**Problem:** TrueNAS storage is hierarchical: `pool → dataset → child-dataset → zvol`. This hierarchy needs to be represented in both profile enrichment and topology.

**Solution:** The TrueNAS plugin reports the full hierarchy in profile enrichment:

```json
{
  "pools": [
    {
      "name": "tank",
      "topology": { "data": [{ "type": "raidz2", "disks": 6 }] },
      "datasets": [
        {
          "name": "tank/media",
          "used": "2.5T",
          "available": "5.5T",
          "compression": "lz4",
          "children": [
            { "name": "tank/media/movies", "used": "1.8T" },
            { "name": "tank/media/music", "used": "500G" }
          ]
        },
        {
          "name": "tank/vms",
          "children": [
            { "name": "tank/vms/docker-host-01", "type": "zvol", "size": "100G" }
          ]
        }
      ]
    }
  ]
}
```

#### 8.6.2 NFS/SMB Shares and Proxmox

**Problem:** TrueNAS exports NFS shares that Proxmox mounts for VM storage. This creates a cross-plugin dependency: Proxmox VM storage depends on TrueNAS availability.

**Solution:** Topology edges: `truenas-01 → (provides-storage) → proxmox-01`. If TrueNAS goes down, the blast radius analysis includes all Proxmox VMs whose storage is TrueNAS-backed.

### 8.7 Tailscale — Overlay Network Complexity

#### 8.7.1 ACL Tags vs Hydra Groups

**Problem:** Tailscale has ACL tags (e.g., `tag:servers`, `tag:iot`). Hydra has node groups. These are independent grouping systems that may overlap or conflict.

**Solution:** Hydra imports Tailscale ACL tags as node metadata (stored in enrichment data) but does NOT auto-create Hydra groups from them. Users can manually map Tailscale tags to Hydra groups if desired. MCP can query by Tailscale tag: "list all nodes with Tailscale tag:servers."

#### 8.7.2 Exit Node Topology

**Problem:** A Tailscale exit node routes all traffic for a subnet through a specific device. This creates a dependency that isn't visible in the physical network topology.

**Solution:** The Tailscale plugin reports exit node relationships as topology edges with `relationship: "tailscale-exit-node"`. These appear as overlay edges in the topology graph, visually distinct from physical connections.

### 8.8 IPMI/Redfish — Safety Critical Operations

#### 8.8.1 Power Off Your Only Server

**Problem:** `cmd::ipmi::power-off` targeting `proxmox-01` would take down the entire homelab if it's the only hypervisor. This is catastrophically dangerous.

**Solution:** Multi-layer protection:
1. **RBAC:** Power commands require `admin` role.
2. **Confirmation:** Command requires explicit confirmation with a warning message.
3. **Blast radius pre-check:** Before executing, Hydra computes and displays the blast radius. "This will affect: 5 VMs, 23 containers, 12 services."
4. **Self-protection:** If `proxmox-01` hosts the Hydra API itself, the command is blocked with: "Cannot power off the node running Hydra API. Shut down Hydra first or use IPMI tools directly."
5. **Cool-down:** After a power-off, a 60-second lock prevents accidental immediate power-on (in case the user panics and hammers the button).

---

## 9. Security & Credential Management

### 9.1 Credential Storage

All plugin credentials are stored encrypted in MongoDB using AES-256-CBC. The encryption key is derived from the Hydra instance secret (configured at install time).

```python
class CredentialStore:
    """
    Encrypt/decrypt plugin credentials.
    """
    def encrypt(self, plaintext: str) -> str:
        # Returns "encrypted::base64encoded..."
        pass

    def decrypt(self, ciphertext: str) -> str:
        # Accepts "encrypted::base64encoded..."
        pass
```

Credential values are NEVER:
- Returned in API responses (masked as `"***"`)
- Logged in any log output
- Included in profile enrichment data
- Exposed to MCP tools
- Visible in the web UI after initial configuration

### 9.2 Least-Privilege Recommendations Per Plugin

| Plugin | Recommended Permissions | What NOT To Grant |
|--------|------------------------|-------------------|
| **Proxmox** | `PVEAuditor` role + specific VM permissions for command execution | Do not use `root@pam`. Create dedicated `hydra@pve` user. |
| **Docker** | `docker` group membership for agent user | Do not run agent as root just for Docker access. |
| **Home Assistant** | Long-lived access token with default permissions | Don't share the admin account — create a dedicated HA user for Hydra. |
| **UniFi** | Read-only admin (for profiling) or limited admin (for commands) | Don't use the super admin account. |
| **pfSense** | FauxAPI with read-only permissions (for profiling) | Write permissions only if using firewall commands. |
| **Prometheus** | No auth needed typically (read-only metrics endpoint) | If Prometheus requires auth, use a read-only token. |
| **TrueNAS** | API key with read-only access (for profiling) | Write access only for snapshot/dataset commands. |
| **Tailscale** | Tailscale API key with `devices:read` scope | `devices:write` only for approve/remove commands. |
| **IPMI** | Dedicated `hydra-ipmi` user with operator privileges | Never use ADMIN credentials. Operator can read sensors and control power. |

### 9.3 Network Exposure Analysis

| Plugin | Network Requirement | Risk | Mitigation |
|--------|-------------------|------|------------|
| Proxmox | API needs HTTPS access to PVE (port 8006) | PVE credentials traverse network | Use TLS with certificate verification. Prefer API tokens over passwords. |
| Docker | Agent needs local socket access | Docker socket = root access | Use docker group, not root. Consider rootless Docker. |
| Home Assistant | API needs HTTP(S) access to HA (port 8123) | HA token traverses network | Use HTTPS. Long-lived tokens are revocable. |
| SNMP | API needs UDP 161 access to devices | SNMP v2c community strings are plaintext | Use SNMP v3 with auth/priv encryption where supported. |
| IPMI | API or agent needs access to BMC network | IPMI v2 has known security weaknesses | Isolate BMC on dedicated management VLAN. Use Redfish (HTTPS) where available. |

---

## 10. Performance, Rate Limiting & Caching

### 10.1 External API Rate Limits

| Plugin | External API Rate Limit | Hydra's Approach |
|--------|------------------------|-----------------|
| **Proxmox** | No hard limit, but aggressive polling impacts web UI | Poll at 5-minute intervals. Batch guest list queries. |
| **Docker** | No limit (local socket) | No throttling needed for local operations. |
| **Home Assistant** | No hard limit, but HA can slow under load | Poll at 5-minute intervals. Use WebSocket for real-time if enabled. |
| **UniFi** | Unofficial API, aggressive polling may cause 429s | Poll at 5-minute intervals. Cache client list. Session cookie reuse. |
| **Pi-hole** | No hard limit, but stats queries can be slow | Cache stats for 60 seconds. Batch queries. |
| **Prometheus** | Query complexity limits (timeout), no rate limit | Use `instant` queries for enrichment, not `range` queries. Keep query window short. |
| **Tailscale** | 60 requests/minute per API key | Cache device list. Poll at 5-minute intervals. |
| **TrueNAS** | No hard limit, but reporting API can be slow | Cache pool/dataset data for 5 minutes. |
| **Uptime Kuma** | No hard limit (local API) | Poll at 2-minute intervals for monitor status. |

### 10.2 Enrichment Caching

Plugin enrichment data is cached per node to avoid re-querying external APIs on every profile request:

```python
class EnrichmentCache:
    """
    Cache plugin enrichment data with configurable TTL per plugin.
    """
    DEFAULT_TTL = {
        "plg::proxmox-ve": 300,    # 5 minutes
        "plg::docker": 60,          # 1 minute (local, fast)
        "plg::home-assistant": 300,  # 5 minutes
        "plg::unifi": 300,           # 5 minutes
        "plg::prometheus": 300,      # 5 minutes
        "plg::tailscale": 300,       # 5 minutes
        "plg::truenas": 600,         # 10 minutes (slow API)
        "plg::uptime-kuma": 120,     # 2 minutes
    }
```

### 10.3 Discovery Cycle Performance

Discovery across all enabled plugins should complete within a bounded time:

| Plugin | Typical Discovery Time | Scaling Factor |
|--------|----------------------|----------------|
| Proxmox | 500ms–2s | Per cluster (not per node) |
| Docker | 100ms–500ms per host | Per Docker host |
| HA | 1s–5s | Per HA instance (entity count) |
| UniFi | 500ms–2s | Per controller site |
| SNMP | 1s–10s per device | Per SNMP target (walk is slow) |
| Network scan | 5s–60s | Per subnet (parallel ping/SYN) |
| Prometheus | 200ms–1s | Per Prometheus server |

**Total budget:** Full discovery across a typical homelab (1 Proxmox cluster, 3 Docker hosts, 1 HA, 1 UniFi, 5 SNMP devices, 2 subnets) should complete within 30 seconds. Plugins are queried in parallel.

---

## 11. Version Compatibility & External API Stability

### 11.1 Minimum Supported Versions

| Plugin | External System | Minimum Version | Tested Up To | Notes |
|--------|----------------|-----------------|-------------|-------|
| Proxmox | Proxmox VE | 7.0 | 8.3 | API v2 required. Ceph features require 7.2+. |
| Docker | Docker Engine | 20.10 | 27.x | API version 1.41+ required. |
| Podman | Podman | 4.0 | 5.x | REST API required (not all distros enable by default). |
| HA | Home Assistant | 2023.1 | 2026.x | REST API stable. WebSocket API stable since 2021. |
| Ansible | Ansible | 2.12 | 2.17 | JSON callback plugin required for structured output. |
| Terraform | Terraform / OpenTofu | 1.0 | 1.9 / OpenTofu 1.8 | CLI interface stable. |
| Prometheus | Prometheus | 2.30 | 2.54 | HTTP API v1 stable. |
| UniFi | UniFi Network Application | 7.0 | 8.6 | API endpoints shift between major versions. |
| pfSense | pfSense + FauxAPI | 2.6 + FauxAPI 1.5 | 2.7.x | FauxAPI must be manually installed. |
| OPNsense | OPNsense | 23.1 | 24.7 | Built-in API, versioned endpoints. |
| Traefik | Traefik | 2.0 | 3.x | API endpoint structure changed in v3. |
| NPM | Nginx Proxy Manager | 2.9 | 2.12 | API is simple and stable. |
| Pi-hole | Pi-hole | 5.0 | 6.x | API v6 completely redesigned. Must detect version. |
| AdGuard | AdGuard Home | 0.107 | 0.108 | API is versioned and stable. |
| TrueNAS | TrueNAS SCALE/CORE | SCALE 22.12 / CORE 13.0 | SCALE 24.10 | API differs between CORE (FreeBSD) and SCALE (Linux). |
| Uptime Kuma | Uptime Kuma | 1.17 | 1.23 | API is simple REST. |
| Tailscale | Tailscale API | v2 | v2 | Official API, versioned, stable. |
| IPMI/Redfish | IPMI 2.0 / Redfish 1.0 | varies | varies | `ipmitool` or `redfishtool` CLI required. |

### 11.2 Breaking Change Detection

On every health check, the plugin records the external system's version. If the version changes (system was upgraded), Hydra:
1. Logs the version change.
2. Runs a compatibility check (test API call).
3. If the compatibility check fails, transitions to `DEGRADED` with a message like "UniFi controller upgraded to 8.5 — API compatibility check failed. Some features may not work."
4. Alerts the user to check Hydra compatibility notes.

---

## 12. Data Consistency Patterns

### 12.1 Eventual Consistency Model

Hydra's plugin data is eventually consistent. When Docker adds a container, Hydra won't know about it until the next enrichment cycle (or agent profile submission). This is by design — Hydra profiles infrastructure state, it doesn't mirror it in real-time.

**Consistency windows:**

| Data Type | Typical Staleness | Worst Case |
|-----------|-------------------|------------|
| Container list | 1–5 minutes | 1 hour (if enrichment cycle delayed) |
| VM/LXC list | 1–5 minutes | 1 hour |
| HA entity states | 5 minutes (REST) or real-time (WebSocket) | 10 minutes |
| Network topology | 5–15 minutes | 1 hour |
| Prometheus metrics | 5 minutes (snapshot window) | 15 minutes |
| Firewall rules | 5–15 minutes | 1 hour |
| DNS stats | 5–15 minutes | 1 hour |

### 12.2 Stale Data Indicators

Every plugin enrichment data point includes a `lastEnriched` timestamp. The web UI and MCP responses indicate data freshness:
- < 2x enrichment interval → "current" (no indicator)
- 2x–5x enrichment interval → "aging" (subtle indicator)
- 5x+ enrichment interval → "stale" (warning indicator)
- Plugin in CIRCUIT_OPEN → "unavailable" (error indicator with last-known data)

### 12.3 Conflict Resolution Ordering

When multiple enrichment sources update the same node's profile concurrently, the API processes them in this order:
1. Agent profile submission (always processed first — it's the base profile)
2. API-side enrichments in plugin priority order (Proxmox → Docker → HA → others)
3. Each enrichment is additive to `pluginData` — plugins don't overwrite each other's namespaces

This ordering is deterministic: the same inputs always produce the same profile state.

---

## 13. Plugin Testing Strategy

### 13.1 Testing Levels

| Level | What | How |
|-------|------|-----|
| **Unit tests** | Plugin driver methods in isolation | Mock external API responses. Test parsing, error handling, data transformation. |
| **Integration tests** | Plugin against real external system | Docker-compose environments with real Proxmox (mock), Docker, HA instances. |
| **Reconciliation tests** | Multi-plugin discovery with overlapping entities | Scripted scenarios with 3+ plugins discovering same devices. Verify no duplicates, correct merges. |
| **Failure tests** | Plugin behavior when external system is unavailable | Kill external service mid-operation. Verify circuit breaker, fallback, data preservation. |
| **Cross-plugin tests** | Plugin interactions (§6) | Scenarios: Proxmox+Docker nesting, HA+network scan dedup, UniFi+SNMP overlap. |

### 13.2 Test Environment

```yaml
# docker-compose.test.yml — Plugin test environment
services:
  hydra-api:
    build: ./hydra-api
    environment:
      - MONGODB_URI=mongodb://mongo:27017/hydra-test

  mongo:
    image: mongo:7

  # Mock external services
  proxmox-mock:
    image: hydra-test/proxmox-mock
    # Returns canned Proxmox API responses

  ha-mock:
    image: hydra-test/ha-mock
    # Returns canned HA API responses

  docker-host:
    image: docker:dind
    privileged: true
    # Real Docker-in-Docker for Docker plugin testing

  snmp-simulator:
    image: tandoor/snmp-simulator
    # Simulates SNMP devices with configurable MIBs

  uptime-kuma:
    image: louislam/uptime-kuma:1
    # Real Uptime Kuma for integration testing
```

---

## 14. Appendices

### A. Plugin Error Code Catalog

| Code | Plugin | Meaning |
|------|--------|---------|
| `PLG-001` | Any | Connection refused — external system not reachable |
| `PLG-002` | Any | Authentication failed — credentials invalid or expired |
| `PLG-003` | Any | Health check timeout — external system responding too slowly |
| `PLG-004` | Any | API version incompatible — detected version not supported |
| `PLG-010` | Proxmox | Cluster quorum lost — data may be inconsistent |
| `PLG-011` | Proxmox | VM migration in progress — skipping reconciliation |
| `PLG-020` | Docker | Socket permission denied — agent user not in docker group |
| `PLG-021` | Docker | Compose file not found at configured path |
| `PLG-022` | Docker | Registry unreachable — image pull operations will fail |
| `PLG-030` | HA | WebSocket disconnected — falling back to REST polling |
| `PLG-031` | HA | Entity count mismatch — fewer entities than last sync |
| `PLG-040` | Ansible | SSH auth failure for one or more target hosts |
| `PLG-041` | Ansible | Playbook not found in catalog |
| `PLG-042` | Ansible | Concurrent execution blocked by host lock |
| `PLG-050` | Terraform | State file locked by another process |
| `PLG-051` | Terraform | Destructive plan requires approval |
| `PLG-052` | Terraform | Provider credentials invalid |
| `PLG-060` | SNMP | Community string rejected — wrong credentials |
| `PLG-061` | SNMP | Device classification failed — unknown device type |
| `PLG-070` | IPMI | Self-protection: target hosts Hydra API — power-off blocked |
| `PLG-071` | IPMI | BMC unreachable on management network |

### B. Plugin Data Namespace Separation

Each plugin writes ONLY to its own namespace in `pluginData`:

```
profile.pluginData["plg::docker"]     ← Docker plugin owns this
profile.pluginData["plg::proxmox-ve"] ← Proxmox plugin owns this
profile.pluginData["plg::prometheus"]  ← Prometheus plugin owns this
```

A plugin MUST NEVER read or write another plugin's namespace. Cross-plugin data sharing happens through the data resolver (§4 of Documentation spec) or through topology edges (which are a shared resource).

### C. Reconciliation Confidence Levels

| Confidence | Meaning | Creates Node? | Example |
|------------|---------|---------------|---------|
| `high` | Strong identification — unique ID match | Yes | Proxmox VMID, Docker container ID, agent self-registration |
| `medium` | Good identification — IP + hostname match | Yes | Network scan with rDNS, Prometheus target with nodename label |
| `low` | Weak identification — IP only, hostname only, or DNS query | Merge only (if matches existing) | Pi-hole DNS client, Prometheus target without labels |
| `transient` | Very weak — appears briefly | Never creates | UniFi wireless client without alias, ARP table entry |

---

_End of Hydra Plugin Deep Dive — Operational Specification_
