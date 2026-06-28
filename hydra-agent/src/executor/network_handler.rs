//! Network discovery execution handler.
//!
//! Executes delegated discovery scans on an agent and returns structured
//! device evidence that the API can ingest into discovery records.

use std::collections::HashMap;
use std::net::Ipv4Addr;
use std::sync::Arc;

use chrono::Utc;
use serde_json::{json, Value};
use tokio::net::TcpStream;
use tokio::sync::{RwLock, Semaphore};
use tokio::time::{timeout, Duration};
use tracing::{info, warn};

use crate::config::AgentConfig;

use super::protocol_discovery;
use super::CommandResult;

const MAX_SCAN_HOSTS: usize = 1024;
const HOST_SCAN_CONCURRENCY: usize = 64;
const PORT_SCAN_CONCURRENCY: usize = 32;

#[derive(Debug, Clone)]
struct ScanTarget {
    subnet: String,
    network_id: Option<String>,
}

#[derive(Debug, Clone)]
struct ScanRequest {
    scan_id: String,
    targets: Vec<ScanTarget>,
    methods: Vec<String>,
    port_tier: String,
    timeout_seconds: u64,
    include_iot_protocols: bool,
}

pub async fn execute(
    parameters: &Option<Value>,
    timeout_secs: u64,
    config: Arc<RwLock<AgentConfig>>,
) -> CommandResult {
    let request = match parse_scan_request(parameters, timeout_secs) {
        Ok(request) => request,
        Err(error) => return CommandResult::error(&error),
    };

    let node_id = config.read().await.node.node_id.clone();
    let ports = ports_for_tier(&request.port_tier, request.include_iot_protocols);
    let started_at = Utc::now();
    let started = std::time::Instant::now();

    let expanded_hosts = match expand_targets(&request.targets) {
        Ok(hosts) => hosts,
        Err(error) => return CommandResult::error(&error),
    };

    // Run mDNS + SSDP discovery once per scan before the host fan-out, when
    // IoT protocols are enabled. Multicast is network-wide; doing it per-host
    // would waste N×timeout seconds. A panic in either crate is contained by
    // the spawn boundary and degrades to an empty map.
    let protocol_details_by_ip = if request.include_iot_protocols {
        let budget = Duration::from_secs(request.timeout_seconds / 2)
            .min(Duration::from_secs(5));
        run_multicast_discovery(budget).await
    } else {
        HashMap::new()
    };
    let protocol_details_by_ip = Arc::new(protocol_details_by_ip);

    let host_semaphore = Arc::new(Semaphore::new(HOST_SCAN_CONCURRENCY));
    let mut tasks = Vec::with_capacity(expanded_hosts.len());

    for (ip, target) in expanded_hosts {
        let permit = host_semaphore.clone();
        let node_id = node_id.clone();
        let methods = request.methods.clone();
        let ports = ports.clone();
        let scan_id = request.scan_id.clone();
        let proto_details = protocol_details_by_ip.clone();
        tasks.push(tokio::spawn(async move {
            let _permit = permit.acquire_owned().await.ok()?;
            scan_host(
                &ip,
                &target,
                &node_id,
                &scan_id,
                &methods,
                &ports,
                started_at.to_rfc3339(),
                proto_details.as_ref(),
            )
            .await
        }));
    }

    let mut results = Vec::new();
    let mut failed_hosts = 0u64;
    for task in tasks {
        match timeout(Duration::from_secs(request.timeout_seconds), task).await {
            Ok(Ok(Some(result))) => results.push(result),
            Ok(Ok(None)) => {}
            Ok(Err(e)) => {
                warn!("Network scan task failed: {}", e);
                failed_hosts += 1;
            }
            Err(_) => {
                warn!("Network scan task timed out after {}s", request.timeout_seconds);
                failed_hosts += 1;
            }
        }
    }
    if failed_hosts > 0 {
        warn!(failed_hosts, "Network scan completed with failed/timed-out hosts");
    }

    let hosts_scanned = expanded_hosts_count(&request.targets);
    let hosts_alive = results.len();
    let duration_ms = started.elapsed().as_millis() as u64;

    info!(
        scan_id = %request.scan_id,
        hosts_scanned = hosts_scanned,
        hosts_alive = hosts_alive,
        duration_ms = duration_ms,
        "Delegated network scan completed"
    );

    CommandResult {
        success: true,
        output: Some(format!(
            "Scanned {} host(s); {} host(s) produced discovery evidence.",
            hosts_scanned, hosts_alive
        )),
        exit_code: Some(0),
        error: None,
        data: Some(json!({
            "scanId": request.scan_id,
            "summary": {
                "hostsScanned": hosts_scanned,
                "hostsAlive": hosts_alive,
                "newDiscoveries": hosts_alive,
                "returningDevices": 0,
                "errors": [],
            },
            "results": results,
            "durationMs": duration_ms,
        })),
    }
}

fn parse_scan_request(parameters: &Option<Value>, timeout_secs: u64) -> Result<ScanRequest, String> {
    let Some(params) = parameters.as_ref().and_then(Value::as_object) else {
        return Err("network-scan requires an object parameter payload".to_string());
    };

    let scan_id = params
        .get("scanId")
        .and_then(Value::as_str)
        .ok_or_else(|| "network-scan requires scanId".to_string())?
        .to_string();

    let mut targets = Vec::new();
    if let Some(target_specs) = params.get("targetSpecs").and_then(Value::as_array) {
        for target in target_specs {
            let Some(target_obj) = target.as_object() else {
                continue;
            };
            let Some(subnet) = target_obj.get("subnet").and_then(Value::as_str) else {
                continue;
            };
            targets.push(ScanTarget {
                subnet: subnet.to_string(),
                network_id: target_obj
                    .get("networkId")
                    .and_then(Value::as_str)
                    .map(ToString::to_string),
            });
        }
    }

    if targets.is_empty() {
        if let Some(targets_array) = params.get("targets").and_then(Value::as_array) {
            for target in targets_array {
                if let Some(subnet) = target.as_str() {
                    targets.push(ScanTarget {
                        subnet: subnet.to_string(),
                        network_id: None,
                    });
                }
            }
        }
    }

    if targets.is_empty() {
        return Err("network-scan requires at least one CIDR target".to_string());
    }

    let methods = params
        .get("methods")
        .and_then(Value::as_array)
        .map(|values| {
            values
                .iter()
                .filter_map(Value::as_str)
                .map(ToString::to_string)
                .collect::<Vec<_>>()
        })
        .filter(|values| !values.is_empty())
        .unwrap_or_else(|| vec!["tcp_port".to_string()]);

    Ok(ScanRequest {
        scan_id,
        targets,
        methods,
        port_tier: params
            .get("portTier")
            .and_then(Value::as_str)
            .unwrap_or("tier1")
            .to_string(),
        timeout_seconds: params
            .get("timeoutSeconds")
            .and_then(Value::as_u64)
            .unwrap_or(timeout_secs.max(1)),
        include_iot_protocols: params
            .get("includeIoTProtocols")
            .and_then(Value::as_bool)
            .unwrap_or(false),
    })
}

// MUST match hydra-api/hydra/api/v1/services/discovery/scanner.py
// and hydra-api/hydra/api/v1/services/discovery/fingerprint.py.
fn ports_for_tier(port_tier: &str, include_iot_protocols: bool) -> Vec<u16> {
    // Tier 1: 32 core infrastructure ports
    let mut ports = vec![
        22, 23, 25, 53, 80, 110, 143, 161, 389, 443, 445,
        554, 623, 993, 995, 1194, 1433, 1883, 1900, 2375,
        2376, 3306, 3389, 5353, 5432, 5683, 5900, 6379,
        8006, 8080, 8123, 8443,
    ];
    if port_tier == "tier2" {
        // Tier 2: 71 additional ports for deeper fingerprinting
        ports.extend_from_slice(&[
            21, 69, 111, 135, 179, 427, 500, 514, 515, 548,
            587, 631, 636, 873, 902, 1080, 1521, 1723,
            2049, 2222, 2379, 2380, 3000, 3260, 3478, 4243,
            4505, 4506, 5000, 5001, 5060, 5222, 5269, 5672,
            5984, 6000, 6443, 6633, 6881, 7001, 7077, 7474,
            8000, 8008, 8081, 8088, 8090, 8139, 8291, 8444,
            8883, 8888, 9000, 9042, 9090, 9100, 9200, 9300,
            9418, 9999, 10000, 10001, 10250, 10255, 11211, 15672,
            25565, 27017, 28017, 50000,
        ]);
    }
    if !include_iot_protocols {
        ports.retain(|port| !matches!(port, 1883 | 1900 | 5353 | 5683 | 8123 | 8883 | 10001));
    }
    ports.sort_unstable();
    ports.dedup();
    ports
}

fn expand_targets(targets: &[ScanTarget]) -> Result<Vec<(String, ScanTarget)>, String> {
    let mut hosts = Vec::new();
    for target in targets {
        let mut expanded = expand_ipv4_cidr(&target.subnet)?;
        if hosts.len() + expanded.len() > MAX_SCAN_HOSTS {
            return Err(format!(
                "network-scan exceeds the {} host limit for a single request",
                MAX_SCAN_HOSTS
            ));
        }
        for ip in expanded.drain(..) {
            hosts.push((ip, target.clone()));
        }
    }
    Ok(hosts)
}

fn expanded_hosts_count(targets: &[ScanTarget]) -> usize {
    targets
        .iter()
        .filter_map(|target| expand_ipv4_cidr(&target.subnet).ok())
        .map(|hosts| hosts.len())
        .sum()
}

#[allow(clippy::too_many_arguments)]
async fn scan_host(
    ip: &str,
    target: &ScanTarget,
    node_id: &str,
    scan_id: &str,
    methods: &[String],
    ports: &[u16],
    scanned_at: String,
    protocol_details_by_ip: &HashMap<String, Value>,
) -> Option<Value> {
    let port_semaphore = Arc::new(Semaphore::new(PORT_SCAN_CONCURRENCY));
    let mut port_tasks = Vec::with_capacity(ports.len());

    for port in ports {
        let ip = ip.to_string();
        let port = *port;
        let permit = port_semaphore.clone();
        port_tasks.push(tokio::spawn(async move {
            let _permit = permit.acquire_owned().await.ok()?;
            if port_is_open(&ip, port).await {
                Some(port)
            } else {
                None
            }
        }));
    }

    let mut open_ports = Vec::new();
    for task in port_tasks {
        if let Ok(Ok(Some(port))) = timeout(Duration::from_millis(1200), task).await {
            open_ports.push(port);
        }
    }

    if open_ports.is_empty() {
        return None;
    }

    open_ports.sort_unstable();
    let mut protocols = infer_protocols(&open_ports, methods);
    let banners = collect_banners(ip, &open_ports).await;
    let dns_names = reverse_dns_names(ip).await;

    // Merge multicast discovery results, when present, on top of the
    // port-inferred stubs. Real mDNS data also promotes ``mdns`` and
    // ``ssdp`` into the protocols list so the signal list and the
    // primary-method heuristic see them even when ports 5353/1900 are
    // closed (the host answered via multicast alone).
    let mut protocol_details =
        merge_protocol_details(&protocols, &banners, protocol_details_by_ip.get(ip));
    if protocol_details.get("mdns").is_some()
        && !protocols.iter().any(|p| p == "mdns")
    {
        protocols.push("mdns".to_string());
    }
    if protocol_details.get("ssdp").is_some()
        && !protocols.iter().any(|p| p == "ssdp")
    {
        protocols.push("ssdp".to_string());
    }
    protocols.sort();
    protocols.dedup();

    let signals = build_signals(&open_ports, &protocols, &banners);
    let primary_method = if protocols.iter().any(|protocol| protocol == "snmp") {
        "snmp"
    } else if protocols.iter().any(|protocol| protocol == "ssdp") {
        "ssdp"
    } else if protocols.iter().any(|protocol| protocol == "mdns") {
        "mdns"
    } else {
        "tcp_port"
    };

    // Prefer the hostname reported by mDNS over reverse-DNS when both exist.
    let hostname = protocol_details
        .get("mdns")
        .and_then(|v| v.get("hostname"))
        .and_then(Value::as_str)
        .map(str::to_string)
        .or_else(|| dns_names.first().cloned());

    // Remove internal bookkeeping keys from protocol_details before
    // serialization (no-op today; forward-compatible).
    let _ = protocol_details.remove("_internal");

    Some(json!({
        "identity": {
            "primaryMac": Value::Null,
            "currentIp": ip,
            "hostname": hostname,
        },
        "networkId": target.network_id,
        "probe": {
            "scannedBy": node_id,
            "method": primary_method,
            "scannedAt": scanned_at,
            "sourceSubnet": target.subnet,
            "delegatedByScanId": scan_id,
            "scanMethods": methods,
        },
        "openPorts": open_ports,
        "protocols": protocols,
        "rawEvidence": {
            "vendor": Value::Null,
            "macOui": Value::Null,
            "dnsNames": dns_names,
            "banners": banners,
            "protocolDetails": Value::Object(protocol_details),
            "signals": signals,
        },
    }))
}

/// Run mDNS + SSDP discovery in parallel with a shared budget.
///
/// Spawns both in `tokio::spawn` so a panic in either third-party crate
/// is contained and degrades to an empty map instead of failing the scan.
async fn run_multicast_discovery(budget: Duration) -> HashMap<String, Value> {
    let mdns_handle =
        tokio::spawn(async move { protocol_discovery::discover_mdns(budget).await });
    let ssdp_handle =
        tokio::spawn(async move { protocol_discovery::discover_ssdp(budget).await });

    let mdns = match mdns_handle.await {
        Ok(m) => m,
        Err(err) => {
            warn!(error = %err, "mdns task panicked");
            HashMap::new()
        }
    };
    let ssdp = match ssdp_handle.await {
        Ok(s) => s,
        Err(err) => {
            warn!(error = %err, "ssdp task panicked");
            HashMap::new()
        }
    };

    info!(
        mdns_hosts = mdns.len(),
        ssdp_hosts = ssdp.len(),
        "Multicast discovery finished"
    );
    protocol_discovery::build_per_host_details(&mdns, &ssdp)
}

/// Merge port-inferred protocol stubs with real multicast evidence.
///
/// The final object wins for each key: multicast data replaces the stub
/// for ``mdns``/``ssdp`` when present; ``snmp`` populated from banner
/// grabbing continues unchanged.
fn merge_protocol_details(
    protocols: &[String],
    banners: &HashMap<String, String>,
    multicast: Option<&Value>,
) -> serde_json::Map<String, Value> {
    let mut details = match build_protocol_details(protocols, banners) {
        Value::Object(m) => m,
        _ => serde_json::Map::new(),
    };
    if let Some(Value::Object(src)) = multicast {
        for (key, value) in src {
            details.insert(key.clone(), value.clone());
        }
    }
    details
}

async fn port_is_open(ip: &str, port: u16) -> bool {
    matches!(
        timeout(
            Duration::from_millis(350),
            TcpStream::connect((ip, port)),
        )
        .await,
        Ok(Ok(_))
    )
}

async fn collect_banners(ip: &str, open_ports: &[u16]) -> HashMap<String, String> {
    let mut banners = HashMap::new();
    let port_set: std::collections::HashSet<u16> = open_ports.iter().copied().collect();

    // SSH banner (port 22): servers send version string on connect (RFC 4253)
    if port_set.contains(&22) {
        if let Some(banner) = grab_ssh_banner(ip).await {
            banners.insert("22".to_string(), banner);
        }
    }

    // SNMP sysDescr (port 161): raw SNMPv1 GET via UDP
    if port_set.contains(&161) {
        if let Some(banner) = grab_snmp_sysdescr(ip).await {
            banners.insert("161".to_string(), banner);
        }
    }

    // MQTT CONNACK (port 1883): send CONNECT, read return code
    if port_set.contains(&1883) {
        if let Some(banner) = grab_mqtt_banner(ip, 1883).await {
            banners.insert("1883".to_string(), banner);
        }
    }
    if port_set.contains(&8883) {
        if let Some(banner) = grab_mqtt_banner(ip, 8883).await {
            banners.insert("8883".to_string(), banner);
        }
    }

    // HTTP banners via reqwest
    let http_ports = [
        80_u16, 443, 3000, 5000, 8000, 8006, 8008,
        8080, 8081, 8123, 8443, 8888, 9090, 9100,
    ];
    let client = match reqwest::Client::builder()
        .timeout(Duration::from_millis(1200))
        .danger_accept_invalid_certs(true)
        .build()
    {
        Ok(client) => client,
        Err(_) => return banners,
    };
    for port in open_ports {
        if !http_ports.contains(port) || banners.contains_key(&port.to_string()) {
            continue;
        }
        let scheme = if *port == 443 || *port == 8443 { "https" } else { "http" };
        let url = format!("{}://{}:{}/", scheme, ip, port);
        if let Ok(response) = client.get(&url).send().await {
            if let Some(server) = response.headers().get(reqwest::header::SERVER) {
                if let Ok(server_str) = server.to_str() {
                    banners.insert(port.to_string(), server_str.to_string());
                    continue;
                }
            }
            banners.insert(port.to_string(), format!("http:{}", response.status()));
        }
    }
    banners
}

async fn grab_ssh_banner(ip: &str) -> Option<String> {
    let addr = format!("{}:22", ip);
    let stream = timeout(Duration::from_millis(800), TcpStream::connect(&addr))
        .await
        .ok()?
        .ok()?;
    let mut buf = vec![0u8; 256];
    stream.readable().await.ok()?;
    let n = stream.try_read(&mut buf).ok()?;
    if n == 0 {
        return None;
    }
    let banner = String::from_utf8_lossy(&buf[..n]).trim().to_string();
    if banner.starts_with("SSH-") {
        Some(banner)
    } else {
        None
    }
}

async fn grab_snmp_sysdescr(ip: &str) -> Option<String> {
    use tokio::net::UdpSocket;

    // BER-encoded SNMPv1 GET-REQUEST for sysDescr.0 (1.3.6.1.2.1.1.1.0)
    // community = "public"
    let pdu: &[u8] = &[
        0x30, 0x29, // SEQUENCE, length 41
        0x02, 0x01, 0x00, // INTEGER version=0 (SNMPv1)
        0x04, 0x06, 0x70, 0x75, 0x62, 0x6c, 0x69, 0x63, // OCTET STRING "public"
        0xa0, 0x1c, // GetRequest-PDU, length 28
        0x02, 0x01, 0x01, // INTEGER request-id=1
        0x02, 0x01, 0x00, // INTEGER error-status=0
        0x02, 0x01, 0x00, // INTEGER error-index=0
        0x30, 0x11, // SEQUENCE (VarBindList), length 17
        0x30, 0x0f, // SEQUENCE (VarBind), length 15
        0x06, 0x08, 0x2b, 0x06, 0x01, 0x02, 0x01, 0x01, 0x01, 0x00, // OID 1.3.6.1.2.1.1.1.0
        0x05, 0x00, // NULL
    ];

    let sock = UdpSocket::bind("0.0.0.0:0").await.ok()?;
    let dest = format!("{}:161", ip);
    sock.send_to(pdu, &dest).await.ok()?;

    let mut buf = vec![0u8; 2048];
    let n = timeout(Duration::from_millis(1500), sock.recv(&mut buf))
        .await
        .ok()?
        .ok()?;

    // Minimal BER parse: find the first OCTET STRING (0x04) value in the response
    // after the GetResponse-PDU tag (0xA2)
    let data = &buf[..n];
    extract_snmp_octet_string(data)
}

fn extract_snmp_octet_string(data: &[u8]) -> Option<String> {
    // Walk through BER to find tag 0xA2 (GetResponse), then find first 0x04 (OCTET STRING)
    let mut found_response = false;
    let mut i = 0;
    while i < data.len() {
        let tag = data[i];
        i += 1;
        if i >= data.len() {
            break;
        }
        let (length, consumed) = ber_read_length(data, i)?;
        i += consumed;

        if tag == 0xA2 {
            found_response = true;
            // Don't skip content — parse inside the response PDU
            continue;
        }
        if found_response && tag == 0x04 && length > 0 && i + length <= data.len() {
            return Some(String::from_utf8_lossy(&data[i..i + length]).to_string());
        }
        // Skip content of structured types we don't care about at this level
        if tag == 0x30 || tag == 0xA0 {
            continue; // parse inside sequences
        }
        i += length;
    }
    None
}

fn ber_read_length(data: &[u8], offset: usize) -> Option<(usize, usize)> {
    if offset >= data.len() {
        return None;
    }
    let first = data[offset] as usize;
    if first < 0x80 {
        return Some((first, 1));
    }
    let num_bytes = first & 0x7f;
    if num_bytes == 0 || offset + 1 + num_bytes > data.len() {
        return None;
    }
    let mut length = 0usize;
    for j in 0..num_bytes {
        length = (length << 8) | (data[offset + 1 + j] as usize);
    }
    Some((length, 1 + num_bytes))
}

async fn grab_mqtt_banner(ip: &str, port: u16) -> Option<String> {
    let addr = format!("{}:{}", ip, port);
    let stream = timeout(Duration::from_millis(800), TcpStream::connect(&addr))
        .await
        .ok()?
        .ok()?;

    // MQTT 3.1.1 CONNECT: client ID "hydra-probe"
    let connect_packet: &[u8] = &[
        0x10, 0x1d, // Fixed header: CONNECT, remaining length 29
        0x00, 0x04, b'M', b'Q', b'T', b'T', // Protocol Name
        0x04, // Protocol Level (3.1.1)
        0x02, // Connect Flags (Clean Session)
        0x00, 0x3c, // Keep Alive (60s)
        0x00, 0x0b, // Client ID length (11)
        b'h', b'y', b'd', b'r', b'a', b'-', b'p', b'r', b'o', b'b', b'e',
    ];

    stream.writable().await.ok()?;
    stream.try_write(connect_packet).ok()?;

    let mut buf = [0u8; 4];
    stream.readable().await.ok()?;
    let n = timeout(Duration::from_millis(800), async {
        loop {
            match stream.try_read(&mut buf) {
                Ok(n) => return n,
                Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                    stream.readable().await.ok();
                }
                Err(_) => return 0,
            }
        }
    })
    .await
    .ok()?;

    if n >= 4 && buf[0] == 0x20 {
        // CONNACK: byte[3] is return code
        Some(format!("mqtt:connack:{}", buf[3]))
    } else {
        None
    }
}

async fn reverse_dns_names(ip: &str) -> Vec<String> {
    let ip = ip.to_string();
    let result = tokio::task::spawn_blocking(move || -> Vec<String> {
        let addr: std::net::IpAddr = match ip.parse() {
            Ok(a) => a,
            Err(_) => return Vec::new(),
        };
        match dns_lookup::lookup_addr(&addr) {
            Ok(hostname) if hostname != ip => vec![hostname],
            _ => Vec::new(),
        }
    })
    .await;
    result.unwrap_or_default()
}

fn infer_protocols(open_ports: &[u16], requested_methods: &[String]) -> Vec<String> {
    let mut protocols = Vec::new();
    for port in open_ports {
        match port {
            22 => protocols.push("ssh".to_string()),
            53 => protocols.push("dns".to_string()),
            80 | 8080 => protocols.push("http".to_string()),
            161 => protocols.push("snmp".to_string()),
            443 | 8443 => protocols.push("https".to_string()),
            1883 => protocols.push("mqtt".to_string()),
            1900 => protocols.push("ssdp".to_string()),
            5353 => protocols.push("mdns".to_string()),
            5683 => protocols.push("coap".to_string()),
            8123 => protocols.push("homeassistant".to_string()),
            8291 => protocols.push("mikrotik-api".to_string()),
            6443 => protocols.push("k8s-api".to_string()),
            8006 => protocols.push("proxmox-web".to_string()),
            9090 => protocols.push("prometheus".to_string()),
            9100 => protocols.push("node-exporter".to_string()),
            10001 => protocols.push("ubiquiti-discovery".to_string()),
            10250 => protocols.push("kubelet".to_string()),
            _ => {}
        }
    }

    if requested_methods.iter().any(|method| method == "arp") {
        protocols.push("arp-presence".to_string());
    }

    protocols.sort();
    protocols.dedup();
    protocols
}

fn build_signals(
    open_ports: &[u16],
    protocols: &[String],
    banners: &HashMap<String, String>,
) -> Vec<String> {
    let mut signals = open_ports
        .iter()
        .map(|port| format!("port:{}-open", port))
        .collect::<Vec<_>>();
    for protocol in protocols {
        signals.push(format!("protocol:{}", protocol));
    }
    for (port, banner) in banners {
        signals.push(format!("banner:{}:{}", port, banner));
    }
    signals
}

fn build_protocol_details(
    protocols: &[String],
    banners: &HashMap<String, String>,
) -> Value {
    let mut details = serde_json::Map::new();

    // If SNMP banner was captured, populate snmp protocol details
    if protocols.contains(&"snmp".to_string()) {
        if let Some(snmp_banner) = banners.get("161") {
            let mut snmp = serde_json::Map::new();
            snmp.insert("sysDescr".to_string(), json!(snmp_banner));
            details.insert("snmp".to_string(), Value::Object(snmp));
        }
    }

    // Mark presence of other protocols for classification
    for proto in protocols {
        match proto.as_str() {
            "mdns" => {
                details
                    .entry("mdns".to_string())
                    .or_insert_with(|| json!({"services": [], "hostname": null}));
            }
            "ssdp" => {
                details
                    .entry("ssdp".to_string())
                    .or_insert_with(|| json!({"server": null, "deviceType": null}));
            }
            _ => {}
        }
    }

    Value::Object(details)
}

fn expand_ipv4_cidr(input: &str) -> Result<Vec<String>, String> {
    let (address_str, prefix_str) = input
        .split_once('/')
        .ok_or_else(|| format!("Invalid CIDR '{}': expected address/prefix", input))?;

    let address: Ipv4Addr = address_str
        .parse()
        .map_err(|_| format!("Invalid IPv4 address '{}'", address_str))?;
    let prefix: u32 = prefix_str
        .parse()
        .map_err(|_| format!("Invalid CIDR prefix '{}'", prefix_str))?;

    if prefix > 32 {
        return Err(format!("Invalid CIDR prefix '{}': must be <= 32", prefix));
    }
    if prefix < 16 {
        return Err("CIDR prefixes broader than /16 are not allowed for delegated scans".to_string());
    }

    let host_bits = 32 - prefix;
    let network_mask = if prefix == 0 { 0 } else { u32::MAX << host_bits };
    let network = u32::from(address) & network_mask;
    let host_count = 1_u64 << host_bits;

    let mut hosts = Vec::new();
    for offset in 0..host_count {
        if host_count > 2 && (offset == 0 || offset == host_count - 1) {
            continue;
        }
        let ip = Ipv4Addr::from(network + offset as u32);
        hosts.push(ip.to_string());
    }

    Ok(hosts)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;

    #[test]
    fn ports_for_tier_tier1_has_no_duplicates() {
        let ports = ports_for_tier("tier1", true);
        let unique: HashSet<u16> = ports.iter().copied().collect();
        assert_eq!(unique.len(), ports.len(), "tier1 has duplicates: {ports:?}");
    }

    #[test]
    fn ports_for_tier_tier2_has_no_duplicates() {
        let ports = ports_for_tier("tier2", true);
        let unique: HashSet<u16> = ports.iter().copied().collect();
        assert_eq!(unique.len(), ports.len(), "tier2 has duplicates: {ports:?}");
    }

    #[test]
    fn ports_for_tier_tier1_yields_32_ports() {
        let ports = ports_for_tier("tier1", true);
        assert_eq!(ports.len(), 32, "tier1 port count drifted from 32");
    }

    #[test]
    fn ports_for_tier_tier2_yields_tier1_plus_70() {
        let tier1 = ports_for_tier("tier1", true);
        let tier2 = ports_for_tier("tier2", true);
        assert_eq!(
            tier2.len(),
            tier1.len() + 70,
            "tier2 should be tier1 (32) + 70 additional ports after 993 dedup"
        );
    }

    #[test]
    fn ports_for_tier_key_infra_in_tier1() {
        let ports = ports_for_tier("tier1", true);
        for required in [22, 80, 443, 8006, 8123, 5353, 1883] {
            assert!(
                ports.contains(&required),
                "tier1 missing well-known port {required}"
            );
        }
    }

    #[test]
    fn ports_for_tier_include_iot_false_strips_iot_ports() {
        let ports = ports_for_tier("tier2", false);
        for stripped in [1883, 1900, 5353, 5683, 8123, 8883, 10001] {
            assert!(
                !ports.contains(&stripped),
                "tier2 with includeIoTProtocols=false should not contain {stripped}"
            );
        }
    }
}
