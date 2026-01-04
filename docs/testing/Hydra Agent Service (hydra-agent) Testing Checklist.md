

> **Version:** 0.3.0  
> **Component:** hydra-agent (Rust)  
> **Last Updated:** 2026-01-02

---

## Table of Contents

1. [Build & Installation](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#1-build--installation)
2. [Configuration](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#2-configuration)
3. [Registration Flow](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#3-registration-flow)
4. [API Client](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#4-api-client)
5. [Hardware Collector](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#5-hardware-collector)
6. [Network Collector](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#6-network-collector)
7. [Storage Collector](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#7-storage-collector)
8. [Software Collector](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#8-software-collector)
9. [Service Discovery](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#9-service-discovery)
10. [Virtualization Collector](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#10-virtualization-collector)
11. [User Collector](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#11-user-collector)
12. [Config Collector](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#12-config-collector)
13. [Profile Assembly & Submission](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#13-profile-assembly--submission)
14. [Scheduling](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#14-scheduling)
15. [Command Execution](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#15-command-execution)
16. [Error Handling & Resilience](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#16-error-handling--resilience)
17. [Resource Usage](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#17-resource-usage)
18. [Cross-Platform Support](https://claude.ai/chat/eb95da67-6ec0-436a-b5b8-0e3f9a851048#18-cross-platform-support)

---

## 1. Build & Installation

### 1.1 Build Process

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|1.1.1|Cargo build release (x86_64)|Single binary produced|☐|
|1.1.2|Cargo build release (ARM64)|Cross-compiled binary|☐|
|1.1.3|Binary size reasonable|< 20MB|☐|
|1.1.4|No dynamic library dependencies|ldd shows minimal deps|☐|
|1.1.5|cargo test passes|All unit tests pass|☐|
|1.1.6|cargo clippy clean|No warnings|☐|

### 1.2 Installation Script

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|1.2.1|curl-to-install works|`curl -sSL .../install \| bash`|☐|
|1.2.2|Downloads correct architecture|Detects x86_64 vs ARM64|☐|
|1.2.3|Binary placed in correct location|/usr/local/bin/hydra-agent|☐|
|1.2.4|Correct permissions set|755|☐|
|1.2.5|Config directory created|/etc/hydra/|☐|
|1.2.6|Default config written|/etc/hydra/agent.toml|☐|
|1.2.7|Log directory created|/var/log/hydra/|☐|

### 1.3 Systemd Integration

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|1.3.1|`hydra-agent install` creates service|systemd unit file created|☐|
|1.3.2|Service starts on boot|Enabled by default|☐|
|1.3.3|`systemctl status hydra-agent` works|Shows running status|☐|
|1.3.4|`systemctl restart hydra-agent` works|Clean restart|☐|
|1.3.5|Service user created (optional)|hydra-agent user|☐|
|1.3.6|Logs to journald|`journalctl -u hydra-agent` works|☐|

### 1.4 Uninstallation

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|1.4.1|`hydra-agent uninstall` removes service|Systemd unit removed|☐|
|1.4.2|Binary removed|/usr/local/bin/ cleaned|☐|
|1.4.3|Config preserved option|--keep-config flag|☐|

---

## 2. Configuration

### 2.1 TOML Configuration File

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.1.1|Reads /etc/hydra/agent.toml|Config loaded|☐|
|2.1.2|Custom config path supported|--config flag|☐|
|2.1.3|Missing config fails gracefully|Clear error message|☐|
|2.1.4|Invalid TOML syntax detected|Parse error reported|☐|
|2.1.5|Unknown keys ignored with warning|Forward compatibility|☐|

### 2.2 Agent Section

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.2.1|node_id loaded|Agent knows its identity|☐|
|2.2.2|node_class validated|compute, networking, iot|☐|
|2.2.3|node_type validated|physical, logical|☐|

### 2.3 API Section

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.3.1|base_url configured|API endpoint set|☐|
|2.3.2|credentials_file path|/etc/hydra/credentials.json|☐|
|2.3.3|timeout_seconds respected|Default 30s|☐|
|2.3.4|retry_attempts configured|Default 3|☐|
|2.3.5|verify_ssl toggle|TLS verification on/off|☐|

### 2.4 Schedule Section

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.4.1|cron expression parsed|"0 */6 * * *" works|☐|
|2.4.2|Invalid cron rejected|Parse error|☐|
|2.4.3|events list parsed|boot, network_change, package_change|☐|

### 2.5 Collection Section

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.5.1|level validated|shallow, neutral, deep|☐|
|2.5.2|Collector toggles work|hardware = true/false|☐|
|2.5.3|Nested collector options|collectors.software.include_packages|☐|
|2.5.4|service_include patterns|Glob patterns for services|☐|
|2.5.5|service_exclude patterns|Exclusion list|☐|
|2.5.6|tracked_paths for configs|File paths to monitor|☐|

### 2.6 Commands Section

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.6.1|enabled toggle|Enable/disable command execution|☐|
|2.6.2|allowed_types whitelist|service, package, config, system|☐|
|2.6.3|poll_interval_seconds|How often to poll for commands|☐|

### 2.7 Logging Section

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.7.1|level configured|info, debug, warn, error|☐|
|2.7.2|format configured|json, pretty|☐|
|2.7.3|file path configured|/var/log/hydra/agent.log|☐|
|2.7.4|Log rotation (optional)|Size-based rotation|☐|

### 2.8 Environment Variable Overrides

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|2.8.1|HYDRA_API_URL overrides base_url|ENV takes precedence|☐|
|2.8.2|HYDRA_NODE_ID overrides node_id|ENV takes precedence|☐|
|2.8.3|HYDRA_LOG_LEVEL overrides level|ENV takes precedence|☐|

---

## 3. Registration Flow

### 3.1 `hydra-agent register` Command

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.1.1|Register with --username --password|Prompts for credentials|☐|
|3.1.2|Validates credentials against API|401 if invalid|☐|
|3.1.3|Node registered via API|POST /node/register called|☐|
|3.1.4|API key received and stored|credentials.json created|☐|
|3.1.5|node_id stored in credentials|For future reference|☐|
|3.1.6|registeredBy tracked|User who ran command|☐|
|3.1.7|Duplicate node handled|Clear error if exists|☐|
|3.1.8|--node-id flag override|Custom node ID|☐|
|3.1.9|Auto-detect node class|Based on system info|☐|

### 3.2 Credential Storage

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.2.1|credentials.json created|/etc/hydra/credentials.json|☐|
|3.2.2|File permissions restricted|600 (owner only)|☐|
|3.2.3|Contains nodeId|Agent identity|☐|
|3.2.4|Contains apiKey|For authentication|☐|
|3.2.5|Contains apiKeyId|Key identifier|☐|
|3.2.6|Contains registeredAt|Timestamp|☐|
|3.2.7|No user password stored|Only API key|☐|

### 3.3 Re-registration

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|3.3.1|Existing credentials detected|Warning shown|☐|
|3.3.2|--force flag allows override|Re-registers|☐|
|3.3.3|Old credentials backed up|.bak file|☐|

---

## 4. API Client

### 4.1 Authentication

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.1.1|API key loaded from credentials|X-API-Key header set|☐|
|4.1.2|Missing credentials detected|Clear error, exit|☐|
|4.1.3|Expired API key detected|401 response handled|☐|
|4.1.4|Revoked API key detected|401 response handled|☐|

### 4.2 HTTP Client

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.2.1|HTTPS used|TLS connection|☐|
|4.2.2|TLS verification configurable|verify_ssl option|☐|
|4.2.3|Timeout enforced|Connection times out|☐|
|4.2.4|User-Agent header set|hydra-agent/version|☐|
|4.2.5|Content-Type: application/json|Correct header|☐|

### 4.3 Retry Logic

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.3.1|Retries on connection failure|Up to retry_attempts|☐|
|4.3.2|Exponential backoff|Increasing delays|☐|
|4.3.3|Retries on 5xx errors|Server errors|☐|
|4.3.4|No retry on 4xx errors|Client errors|☐|
|4.3.5|Retry exhaustion logged|Final failure recorded|☐|

### 4.4 Profile Submission

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|4.4.1|POST /profiles called|Profile submitted|☐|
|4.4.2|Large payload handled|Profiles can be several MB|☐|
|4.4.3|Response parsed|profileId, version extracted|☐|
|4.4.4|Success logged|Profile submission confirmed|☐|
|4.4.5|Failure logged|Error details recorded|☐|

---

## 5. Hardware Collector

### 5.1 System Information

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|5.1.1|Manufacturer detected|/sys/class/dmi/id/|☐|
|5.1.2|Product name detected|System model|☐|
|5.1.3|Serial number collected|If available|☐|
|5.1.4|BIOS version collected|Firmware info|☐|
|5.1.5|dmidecode fallback|When sysfs insufficient|☐|

### 5.2 CPU Information

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|5.2.1|CPU model detected|/proc/cpuinfo|☐|
|5.2.2|Core count accurate|Physical cores|☐|
|5.2.3|Thread count accurate|Logical processors|☐|
|5.2.4|Socket count (physical)|Multi-socket detection|☐|
|5.2.5|Architecture detected|x86_64, aarch64|☐|
|5.2.6|Cache sizes collected|L1, L2, L3|☐|
|5.2.7|CPU flags collected|Deep level only|☐|

### 5.3 Memory Information

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|5.3.1|Total memory detected|/proc/meminfo|☐|
|5.3.2|Memory type (DDR4, DDR5)|dmidecode|☐|
|5.3.3|Memory speed|MHz|☐|
|5.3.4|DIMM slot info (deep)|Per-slot details|☐|
|5.3.5|Swap space detected|Total swap|☐|

### 5.4 Graphics Information

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|5.4.1|GPU detected|lspci or sysfs|☐|
|5.4.2|GPU model identified|NVIDIA, AMD, Intel|☐|
|5.4.3|VRAM detected (if available)|Memory size|☐|
|5.4.4|Multiple GPUs detected|All GPUs listed|☐|

### 5.5 Collection Levels

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|5.5.1|Shallow: Basic info only|System, CPU cores, RAM total|☐|
|5.5.2|Neutral: Full hardware|All standard fields|☐|
|5.5.3|Deep: Extended details|CPU flags, DIMM slots, etc.|☐|

---

## 6. Network Collector

### 6.1 Interface Discovery

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.1.1|All interfaces detected|/sys/class/net/|☐|
|6.1.2|Interface names captured|eth0, ens192, etc.|☐|
|6.1.3|Interface type detected|ethernet, wifi, bridge, bond|☐|
|6.1.4|Virtual interfaces identified|veth, docker0, virbr|☐|
|6.1.5|Loopback excluded|lo filtered out|☐|

### 6.2 Interface Details

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.2.1|MAC address captured|Hardware address|☐|
|6.2.2|IPv4 addresses captured|All IPs on interface|☐|
|6.2.3|IPv6 addresses captured|Link-local and global|☐|
|6.2.4|Subnet mask captured|CIDR notation|☐|
|6.2.5|Interface state|up, down|☐|
|6.2.6|MTU captured|Packet size|☐|
|6.2.7|Speed detected|1000Mbps, etc.|☐|

### 6.3 Routing Information

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.3.1|Default gateway detected|/proc/net/route|☐|
|6.3.2|Route table parsed|`ip route` output|☐|
|6.3.3|Multiple gateways handled|Multi-homed systems|☐|

### 6.4 DNS Information

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.4.1|Nameservers from resolv.conf|/etc/resolv.conf|☐|
|6.4.2|systemd-resolved support|resolvectl status|☐|
|6.4.3|Search domains captured|DNS search list|☐|

### 6.5 Hostname

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|6.5.1|Hostname captured|/etc/hostname or hostnamectl|☐|
|6.5.2|FQDN captured if available|Full domain name|☐|

---

## 7. Storage Collector

### 7.1 Block Device Discovery

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|7.1.1|All disks detected|/sys/block/|☐|
|7.1.2|Device names captured|sda, nvme0n1|☐|
|7.1.3|Device type identified|HDD, SSD, NVMe|☐|
|7.1.4|Device size captured|Bytes|☐|
|7.1.5|Partitions detected|Child devices|☐|
|7.1.6|Virtual disks identified|LVM, RAID|☐|

### 7.2 Filesystem Information

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|7.2.1|Mounted filesystems detected|/proc/mounts|☐|
|7.2.2|Mount point captured|/, /home, etc.|☐|
|7.2.3|Filesystem type captured|ext4, xfs, btrfs|☐|
|7.2.4|Total size captured|df output|☐|
|7.2.5|Available space NOT captured|Not profiling usage|☐|

### 7.3 LVM Information

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|7.3.1|Volume groups detected|vgs command|☐|
|7.3.2|Logical volumes detected|lvs command|☐|
|7.3.3|Physical volumes detected|pvs command|☐|
|7.3.4|LVM not present handled|Graceful skip|☐|

### 7.4 ZFS Information (Deep Level)

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|7.4.1|ZFS pools detected|zpool list|☐|
|7.4.2|Pool health captured|ONLINE, DEGRADED|☐|
|7.4.3|Datasets detected|zfs list|☐|
|7.4.4|ZFS not present handled|Graceful skip|☐|

---

## 8. Software Collector

### 8.1 Operating System

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|8.1.1|OS name detected|/etc/os-release|☐|
|8.1.2|OS version detected|VERSION_ID|☐|
|8.1.3|OS codename detected|VERSION_CODENAME|☐|
|8.1.4|Kernel version detected|/proc/version|☐|
|8.1.5|Architecture detected|uname -m|☐|

### 8.2 Package Information (Deep Level)

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|8.2.1|Debian packages (dpkg)|dpkg-query|☐|
|8.2.2|RHEL packages (rpm)|rpm -qa|☐|
|8.2.3|Arch packages (pacman)|pacman -Q|☐|
|8.2.4|Package count captured|Total installed|☐|
|8.2.5|Notable packages tracked|nginx, docker, etc.|☐|
|8.2.6|include_packages config honored|Full list vs. notable|☐|

### 8.3 Collection Levels

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|8.3.1|Shallow: OS only|OS name/version|☐|
|8.3.2|Neutral: OS + notable packages|Common software|☐|
|8.3.3|Deep: Full package list|All packages|☐|

---

## 9. Service Discovery

### 9.1 Systemd Services

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.1.1|Running services detected|systemctl list-units|☐|
|9.1.2|Service name captured|nginx.service|☐|
|9.1.3|Service status captured|running, stopped|☐|
|9.1.4|Service enabled state|Starts on boot|☐|
|9.1.5|Service include filter|Matches patterns|☐|
|9.1.6|Service exclude filter|Filters out patterns|☐|
|9.1.7|Service ports detected|Listening ports|☐|

### 9.2 Docker Containers

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.2.1|Docker daemon detected|docker.sock exists|☐|
|9.2.2|Running containers listed|docker ps|☐|
|9.2.3|Container name captured|Container names|☐|
|9.2.4|Container image captured|Image:tag|☐|
|9.2.5|Container status captured|running, paused|☐|
|9.2.6|Port mappings captured|Exposed ports|☐|
|9.2.7|Resource limits captured|CPU, memory limits|☐|
|9.2.8|docker inspect used|Extended info|☐|

### 9.3 Podman Containers

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.3.1|Podman detected|podman available|☐|
|9.3.2|Containers listed|podman ps|☐|
|9.3.3|Same fields as Docker|Name, image, status|☐|

### 9.4 Service ID Generation

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|9.4.1|Format: svc::runtime::name|Correct pattern|☐|
|9.4.2|systemd: svc::systemd::nginx|Systemd services|☐|
|9.4.3|docker: svc::docker::mongodb|Docker containers|☐|
|9.4.4|Name sanitization|Lowercase, valid chars|☐|

---

## 10. Virtualization Collector

### 10.1 Virtualization Detection

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|10.1.1|VM detection|systemd-detect-virt|☐|
|10.1.2|Container detection|Detects if in container|☐|
|10.1.3|Hypervisor type|kvm, vmware, xen|☐|
|10.1.4|Bare metal detected|none|☐|

### 10.2 Proxmox VE (Host)

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|10.2.1|Proxmox detected|pveversion exists|☐|
|10.2.2|VMs listed|qm list|☐|
|10.2.3|LXCs listed|pct list|☐|
|10.2.4|VM/LXC details|ID, name, status|☐|

### 10.3 libvirt/KVM

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|10.3.1|libvirt detected|virsh available|☐|
|10.3.2|Domains listed|virsh list --all|☐|
|10.3.3|Domain details|Name, state, vCPUs|☐|

### 10.4 Guest Information

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|10.4.1|Running as VM detected|isVirtual: true|☐|
|10.4.2|Hypervisor identified|What VM tech|☐|
|10.4.3|Parent node association|parentNodeId set|☐|

---

## 11. User Collector

### 11.1 User Enumeration

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|11.1.1|Users from /etc/passwd|All users listed|☐|
|11.1.2|include_system_accounts toggle|Filter UID < 1000|☐|
|11.1.3|Username captured|Login name|☐|
|11.1.4|UID captured|User ID|☐|
|11.1.5|GID captured|Primary group|☐|
|11.1.6|Home directory captured|User home|☐|
|11.1.7|Shell captured|Login shell|☐|

### 11.2 SSH Keys (Optional)

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|11.2.1|include_ssh_keys toggle|Enable/disable|☐|
|11.2.2|authorized_keys parsed|~/.ssh/authorized_keys|☐|
|11.2.3|Key fingerprints captured|Not full keys|☐|
|11.2.4|Key type captured|ssh-rsa, ssh-ed25519|☐|
|11.2.5|Key comment captured|Key identifier|☐|

### 11.3 Group Information

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|11.3.1|Groups from /etc/group|All groups|☐|
|11.3.2|User's groups captured|Group memberships|☐|
|11.3.3|Sudo/wheel group noted|Admin indicator|☐|

---

## 12. Config Collector

### 12.1 Tracked Files

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.1.1|tracked_paths honored|Only specified paths|☐|
|12.1.2|Directory recursion|Files in directories|☐|
|12.1.3|File path captured|Relative to tracked path|☐|
|12.1.4|File hash captured|SHA-256 hash|☐|
|12.1.5|No file content captured|Hash only, no plaintext|☐|
|12.1.6|File permissions captured|Mode bits|☐|
|12.1.7|File owner captured|User/group|☐|
|12.1.8|Last modified captured|Mtime|☐|

### 12.2 Default Tracked Paths

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.2.1|/etc/network/ tracked|Network configs|☐|
|12.2.2|/etc/hostname tracked|Hostname file|☐|
|12.2.3|/etc/hosts tracked|Hosts file|☐|
|12.2.4|Custom paths added|Config extensible|☐|

### 12.3 File Change Detection

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|12.3.1|inotify support (optional)|Watch for changes|☐|
|12.3.2|Hash comparison|Detect modifications|☐|
|12.3.3|New files detected|Not previously tracked|☐|
|12.3.4|Deleted files detected|Previously existed|☐|

---

## 13. Profile Assembly & Submission

### 13.1 Profile Structure

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|13.1.1|nodeId included|Agent's node ID|☐|
|13.1.2|collectedAt timestamp|When data gathered|☐|
|13.1.3|agentVersion included|Agent binary version|☐|
|13.1.4|collectionLevel included|shallow/neutral/deep|☐|
|13.1.5|hardware section populated|Compute nodes|☐|
|13.1.6|network section populated|All nodes|☐|
|13.1.7|storage section populated|Compute nodes|☐|
|13.1.8|software section populated|Compute nodes|☐|
|13.1.9|services section populated|Discovered services|☐|
|13.1.10|virtualization section|VM hosts|☐|
|13.1.11|users section|If enabled|☐|
|13.1.12|configs section|If enabled|☐|

### 13.2 Profile Validation

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|13.2.1|JSON serialization works|Valid JSON output|☐|
|13.2.2|Required fields present|No missing fields|☐|
|13.2.3|Enums validated|Valid values only|☐|
|13.2.4|Payload size reasonable|< 5MB typical|☐|

### 13.3 Submission

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|13.3.1|POST /profiles called|API endpoint hit|☐|
|13.3.2|submittedAt different from collectedAt|Submission timestamp|☐|
|13.3.3|Response parsed|profileId, version|☐|
|13.3.4|Success logged|Confirmation message|☐|
|13.3.5|Version logged|New profile version|☐|

---

## 14. Scheduling

### 14.1 Cron-Based Scheduling

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|14.1.1|Cron expression parsed|Correct schedule|☐|
|14.1.2|Profile collected on schedule|Timed execution|☐|
|14.1.3|Next run time logged|Shows upcoming|☐|
|14.1.4|Missed run handled|Catch-up logic|☐|

### 14.2 Event-Based Triggers

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|14.2.1|Boot event trigger|Collection on startup|☐|
|14.2.2|network_change event|Interface changes|☐|
|14.2.3|package_change event|Package installs|☐|
|14.2.4|Debouncing|Don't flood on rapid changes|☐|

### 14.3 Manual Trigger

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|14.3.1|`hydra-agent collect` command|Manual collection|☐|
|14.3.2|`--dry-run` option|Show without submitting|☐|
|14.3.3|`--output` option|Save to file|☐|
|14.3.4|`--verbose` option|Detailed output|☐|

---

## 15. Command Execution

### 15.1 Command Polling

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|15.1.1|Polls GET /nodes/{nodeId}/commands/poll|Regular interval|☐|
|15.1.2|poll_interval_seconds honored|Configurable|☐|
|15.1.3|Commands enabled check|Skip if disabled|☐|
|15.1.4|Empty response handled|No commands pending|☐|
|15.1.5|Multiple commands handled|Process queue|☐|

### 15.2 Command Type Execution

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|15.2.1|allowed_types enforced|Reject unallowed|☐|
|15.2.2|service start|systemctl start|☐|
|15.2.3|service stop|systemctl stop|☐|
|15.2.4|service restart|systemctl restart|☐|
|15.2.5|service reload|systemctl reload|☐|
|15.2.6|Docker container restart|docker restart|☐|
|15.2.7|package install (admin)|apt/dnf install|☐|
|15.2.8|system reboot (admin)|reboot command|☐|

### 15.3 Result Reporting

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|15.3.1|POST .../result called|Result submitted|☐|
|15.3.2|Success status|success: true, exitCode: 0|☐|
|15.3.3|Failure status|success: false, error|☐|
|15.3.4|Output captured|stdout/stderr|☐|
|15.3.5|Timeout enforced|Command killed if too long|☐|

### 15.4 Safety Controls

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|15.4.1|Whitelist enforced|Only allowed commands|☐|
|15.4.2|No shell injection|Parameterized execution|☐|
|15.4.3|Timeout prevents hangs|Killed after limit|☐|
|15.4.4|Audit logging|Commands logged|☐|

---

## 16. Error Handling & Resilience

### 16.1 Collector Errors

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|16.1.1|Single collector failure|Others continue|☐|
|16.1.2|Partial data submitted|Available sections|☐|
|16.1.3|Missing permission handled|Skip with warning|☐|
|16.1.4|Binary not found handled|Graceful fallback|☐|

### 16.2 Network Errors

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|16.2.1|API unreachable|Retry with backoff|☐|
|16.2.2|DNS resolution failure|Clear error|☐|
|16.2.3|TLS handshake failure|Certificate error|☐|
|16.2.4|Offline queue (optional)|Store for later|☐|

### 16.3 Recovery

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|16.3.1|Reconnection logic|Resume after outage|☐|
|16.3.2|Staleness indicator|Track last success|☐|
|16.3.3|Alert on repeated failure|Log warnings|☐|

---

## 17. Resource Usage

### 17.1 Memory

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|17.1.1|Idle memory footprint|< 20MB RSS|☐|
|17.1.2|Collection memory spike|< 50MB RSS|☐|
|17.1.3|No memory leaks|Stable over time|☐|
|17.1.4|Large system handling|Scales appropriately|☐|

### 17.2 CPU

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|17.2.1|Idle CPU usage|Near 0%|☐|
|17.2.2|Collection CPU spike|Brief, acceptable|☐|
|17.2.3|Doesn't impact system|Low priority nice|☐|

### 17.3 Disk

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|17.3.1|Config files small|< 1KB typical|☐|
|17.3.2|Log rotation|Don't fill disk|☐|
|17.3.3|Credentials file small|< 1KB|☐|

---

## 18. Cross-Platform Support

### 18.1 Linux Distributions

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|18.1.1|Ubuntu 22.04 LTS|All collectors work|☐|
|18.1.2|Ubuntu 24.04 LTS|All collectors work|☐|
|18.1.3|Debian 12|All collectors work|☐|
|18.1.4|RHEL 9 / Rocky 9|All collectors work|☐|
|18.1.5|Fedora (latest)|All collectors work|☐|
|18.1.6|Arch Linux|All collectors work|☐|
|18.1.7|Alpine Linux|Minimal environment|☐|

### 18.2 Architectures

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|18.2.1|x86_64|Native execution|☐|
|18.2.2|ARM64/aarch64|Cross-compiled works|☐|
|18.2.3|Raspberry Pi (ARM)|Pi 4/5 support|☐|

### 18.3 Virtualization Environments

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|18.3.1|Proxmox VE host|Full support|☐|
|18.3.2|Proxmox VM guest|Guest detection|☐|
|18.3.3|Proxmox LXC|Container detection|☐|
|18.3.4|VMware ESXi guest|VMware detection|☐|
|18.3.5|Docker container|Not typical use case|☐|

### 18.4 macOS (Development)

|#|Test Case|Expected Result|Status|
|---|---|---|---|
|18.4.1|Builds on macOS|Development support|☐|
|18.4.2|Basic collectors work|Limited functionality|☐|

---

## Progress Summary

|Section|Total Tests|Passed|Failed|Blocked|Not Started|
|---|---|---|---|---|---|
|1. Build & Installation|18|0|0|0|18|
|2. Configuration|26|0|0|0|26|
|3. Registration Flow|14|0|0|0|14|
|4. API Client|18|0|0|0|18|
|5. Hardware Collector|21|0|0|0|21|
|6. Network Collector|18|0|0|0|18|
|7. Storage Collector|17|0|0|0|17|
|8. Software Collector|12|0|0|0|12|
|9. Service Discovery|20|0|0|0|20|
|10. Virtualization|14|0|0|0|14|
|11. User Collector|14|0|0|0|14|
|12. Config Collector|12|0|0|0|12|
|13. Profile Assembly|18|0|0|0|18|
|14. Scheduling|11|0|0|0|11|
|15. Command Execution|21|0|0|0|21|
|16. Error Handling|10|0|0|0|10|
|17. Resource Usage|10|0|0|0|10|
|18. Cross-Platform|16|0|0|0|16|
|**TOTAL**|**290**|**0**|**0**|**0**|**290**|

---

_Last Updated: 2026-01-02_