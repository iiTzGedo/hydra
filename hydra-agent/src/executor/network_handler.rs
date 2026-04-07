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
use tracing::info;

use crate::config::AgentConfig;

use super::CommandResult;

const MAX_SCAN_HOSTS: usize = 1024;
const HOST_SCAN_CONCURRENCY: usize = 64;
const PORT_SCAN_CONCURRENCY: usize = 16;

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

    let host_semaphore = Arc::new(Semaphore::new(HOST_SCAN_CONCURRENCY));
    let mut tasks = Vec::with_capacity(expanded_hosts.len());

    for (ip, target) in expanded_hosts {
        let permit = host_semaphore.clone();
        let node_id = node_id.clone();
        let methods = request.methods.clone();
        let ports = ports.clone();
        let scan_id = request.scan_id.clone();
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
            )
            .await
        }));
    }

    let mut results = Vec::new();
    for task in tasks {
        match timeout(Duration::from_secs(request.timeout_seconds), task).await {
            Ok(Ok(Some(result))) => results.push(result),
            Ok(Ok(None)) => {}
            Ok(Err(_)) | Err(_) => {}
        }
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

fn ports_for_tier(port_tier: &str, include_iot_protocols: bool) -> Vec<u16> {
    let mut ports = vec![22, 53, 80, 161, 443, 1883, 1900, 5353, 5683, 8080, 8123, 8443];
    if port_tier == "tier2" {
        ports.extend_from_slice(&[623, 2375, 2376, 3000, 3389, 6443, 8006, 8291, 9090, 9100, 10001, 10250]);
    }
    if !include_iot_protocols {
        ports.retain(|port| !matches!(port, 1883 | 1900 | 5353 | 5683 | 8123 | 10001));
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

async fn scan_host(
    ip: &str,
    target: &ScanTarget,
    node_id: &str,
    scan_id: &str,
    methods: &[String],
    ports: &[u16],
    scanned_at: String,
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
    let protocols = infer_protocols(&open_ports, methods);
    let banners = collect_banners(ip, &open_ports).await;
    let dns_names = reverse_dns_names(ip);
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

    Some(json!({
        "identity": {
            "primaryMac": Value::Null,
            "currentIp": ip,
            "hostname": dns_names.first().cloned(),
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
            "protocolDetails": {
                "scanMethods": methods,
                "sourceSubnet": target.subnet,
            },
            "signals": signals,
        },
    }))
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
    let http_ports = [80_u16, 8080, 8006, 8123];
    let client = match reqwest::Client::builder()
        .timeout(Duration::from_millis(1200))
        .build()
    {
        Ok(client) => client,
        Err(_) => return banners,
    };
    for port in open_ports {
        if !http_ports.contains(port) {
            continue;
        }
        let url = format!("http://{}:{}/", ip, port);
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

fn reverse_dns_names(_ip: &str) -> Vec<String> {
    Vec::new()
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
