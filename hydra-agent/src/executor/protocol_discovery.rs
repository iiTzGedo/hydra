//! Agent-side multicast protocol discovery (mDNS + SSDP).
//!
//! Runs once per scan, before the per-host TCP fan-out, when
//! ``include_iot_protocols`` is true. Results key by IPv4 host so
//! ``network_handler::scan_host`` can merge protocol details into each
//! host's ``rawEvidence.protocolDetails`` with no cross-host leakage.
//!
//! LLDP is intentionally not implemented here — it requires raw socket
//! capability (``CAP_NET_RAW``) and an EtherType 0x88CC listener, which
//! is unsafe to assume for an unprivileged agent. The API performs LLDP
//! from its own host where ``CAP_NET_RAW`` can be granted.
//!
//! Both backends degrade gracefully when multicast bind fails (sealed
//! networks, IPv6-only hosts, missing permissions) — they log a warning
//! and return empty results so the scan never aborts.

use std::collections::{HashMap, HashSet};
use std::time::Duration;

use futures_util::StreamExt;
use mdns_sd::{ResolvedService, ServiceDaemon, ServiceEvent};
use serde_json::{json, Value};
use ssdp_client::SearchTarget;
use tokio::time::Instant;
use tracing::{debug, warn};

/// mDNS service types to browse. Must mirror
/// `hydra-api/hydra/api/v1/services/discovery/protocols.py` so the
/// API-direct and agent-delegated scans return comparable evidence.
const MDNS_BROWSE_TARGETS: &[&str] = &[
    "_services._dns-sd._udp.local.",
    "_hue._tcp.local.",
    "_homekit._tcp.local.",
    "_googlecast._tcp.local.",
    "_esphomelib._tcp.local.",
    "_shelly._tcp.local.",
    "_hap._tcp.local.",
    "_miio._udp.local.",
    "_matter._tcp.local.",
    "_matterc._udp.local.",
];

/// One mDNS entry aggregated per IPv4 host.
#[derive(Debug, Default, Clone)]
pub struct MdnsEntry {
    pub services: HashSet<String>,
    pub hostname: Option<String>,
    pub txt_records: HashMap<String, String>,
}

/// One SSDP entry per IPv4 host, keyed by the ``LOCATION`` URL host.
#[derive(Debug, Default, Clone)]
pub struct SsdpEntry {
    pub server: Option<String>,
    pub location: Option<String>,
    pub usn: Option<String>,
    pub device_type: Option<String>,
}

fn merge_service_info(
    results: &mut HashMap<String, MdnsEntry>,
    service_type: &str,
    info: &ResolvedService,
) {
    let addresses: Vec<String> = info
        .get_addresses_v4()
        .iter()
        .map(|ip| ip.to_string())
        .collect();
    for ip in addresses {
        let entry = results.entry(ip).or_default();
        // Strip trailing dot from fully-qualified service names for the
        // services list: ``_hue._tcp.local.`` → ``_hue._tcp.local``.
        entry
            .services
            .insert(service_type.trim_end_matches('.').to_string());
        if entry.hostname.is_none() {
            let host = info.get_hostname();
            if !host.is_empty() {
                entry.hostname = Some(host.trim_end_matches('.').to_string());
            }
        }
        for prop in info.get_properties().iter() {
            let key = prop.key().to_string();
            let val = prop.val_str().to_string();
            entry.txt_records.entry(key).or_insert(val);
        }
    }
}

/// Browse mDNS for a fixed duration and return results keyed by IPv4.
pub async fn discover_mdns(duration: Duration) -> HashMap<String, MdnsEntry> {
    let daemon = match ServiceDaemon::new() {
        Ok(d) => d,
        Err(err) => {
            warn!(error = %err, "mdns daemon failed to start; skipping");
            return HashMap::new();
        }
    };

    let (tx, mut rx) =
        tokio::sync::mpsc::channel::<(String, Box<ResolvedService>)>(128);
    let mut handles = Vec::new();
    for service_type in MDNS_BROWSE_TARGETS {
        let browse_rx = match daemon.browse(service_type) {
            Ok(r) => r,
            Err(err) => {
                debug!(
                    error = %err,
                    service_type = service_type,
                    "mdns browse failed"
                );
                continue;
            }
        };
        let tx_clone = tx.clone();
        let type_owned = (*service_type).to_string();
        handles.push(tokio::spawn(async move {
            while let Ok(event) = browse_rx.recv_async().await {
                if let ServiceEvent::ServiceResolved(info) = event {
                    if tx_clone.send((type_owned.clone(), info)).await.is_err() {
                        break;
                    }
                }
            }
        }));
    }
    drop(tx);

    let mut results: HashMap<String, MdnsEntry> = HashMap::new();
    let deadline = Instant::now() + duration;
    loop {
        let remaining = deadline.saturating_duration_since(Instant::now());
        if remaining.is_zero() {
            break;
        }
        match tokio::time::timeout(remaining, rx.recv()).await {
            Ok(Some((ty, info))) => merge_service_info(&mut results, &ty, info.as_ref()),
            Ok(None) => break, // all browse tasks ended
            Err(_) => break,   // deadline reached
        }
    }

    // Tear down the daemon before aborting tasks — daemon.shutdown()
    // closes its internal channels so recv_async() returns Err and each
    // browse task exits cleanly; abort is a defensive fallback.
    let _ = daemon.shutdown();
    for handle in handles {
        handle.abort();
    }
    results
}

/// Issue a single SSDP M-SEARCH and collect responses until duration elapses.
pub async fn discover_ssdp(duration: Duration) -> HashMap<String, SsdpEntry> {
    let stream = match ssdp_client::search(
        &SearchTarget::All,
        duration,
        2,
        None,
    )
    .await
    {
        Ok(s) => s,
        Err(err) => {
            warn!(error = %err, "ssdp M-SEARCH failed; skipping");
            return HashMap::new();
        }
    };

    let mut pinned = Box::pin(stream);
    let mut results: HashMap<String, SsdpEntry> = HashMap::new();
    // Safety window: the stream is expected to end around ``duration``,
    // but we wrap the loop in a larger timeout so a stuck stream does
    // not hang the scan.
    let safety = duration + Duration::from_secs(1);
    let _ = tokio::time::timeout(safety, async {
        while let Some(resp_result) = pinned.next().await {
            match resp_result {
                Ok(resp) => {
                    let location = resp.location().to_string();
                    let host = extract_host_from_location(&location)
                        .unwrap_or_else(|| location.clone());
                    let usn = resp.usn().to_string();
                    let entry = results.entry(host).or_default();
                    // SSDP responders often answer M-SEARCH twice; skip
                    // when we already have the same USN for this host.
                    if entry.usn.as_deref() == Some(usn.as_str()) {
                        continue;
                    }
                    entry.location = Some(location);
                    entry.server = Some(resp.server().to_string());
                    entry.usn = Some(usn);
                    entry.device_type = Some(resp.search_target().to_string());
                }
                Err(err) => {
                    debug!(error = %err, "ssdp response parse error");
                }
            }
        }
    })
    .await;

    results
}

/// Parse the host portion of a ``LOCATION`` URL (``http://host:port/...``).
///
/// Returns ``None`` when the URL doesn't match the expected SSDP form so the
/// caller can fall back to using the full URL as the map key.
pub(crate) fn extract_host_from_location(loc: &str) -> Option<String> {
    let rest = loc
        .strip_prefix("http://")
        .or_else(|| loc.strip_prefix("https://"))?;
    let end = rest.find('/').unwrap_or(rest.len());
    let host_port = &rest[..end];
    // Strip IPv6 bracket notation ``[fe80::1]:port`` → ``fe80::1``.
    let host_port = host_port
        .strip_prefix('[')
        .and_then(|s| s.split_once(']'))
        .map(|(h, _)| h)
        .unwrap_or(host_port);
    let host = match host_port.rfind(':') {
        Some(idx) if host_port.matches(':').count() == 1 => &host_port[..idx],
        _ => host_port,
    };
    if host.is_empty() {
        return None;
    }
    Some(host.to_string())
}

/// Serialize an ``MdnsEntry`` to the API's ``MdnsDetail`` camelCase shape.
pub fn mdns_entry_to_json(entry: &MdnsEntry) -> Value {
    let mut services: Vec<String> = entry.services.iter().cloned().collect();
    services.sort();
    json!({
        "services": services,
        "hostname": entry.hostname,
        "txtRecords": entry.txt_records,
    })
}

/// Serialize an ``SsdpEntry`` to the API's ``SsdpDetail`` camelCase shape.
pub fn ssdp_entry_to_json(entry: &SsdpEntry) -> Value {
    json!({
        "server": entry.server,
        "location": entry.location,
        "usn": entry.usn,
        "deviceType": entry.device_type,
    })
}

/// Merge mDNS and SSDP discovery results into per-IP JSON objects suitable
/// for ``scan_host`` to drop into ``rawEvidence.protocolDetails``.
pub fn build_per_host_details(
    mdns: &HashMap<String, MdnsEntry>,
    ssdp: &HashMap<String, SsdpEntry>,
) -> HashMap<String, Value> {
    let mut keys: HashSet<&str> = HashSet::new();
    keys.extend(mdns.keys().map(String::as_str));
    keys.extend(ssdp.keys().map(String::as_str));

    let mut out: HashMap<String, Value> = HashMap::new();
    for key in keys {
        let mut obj = serde_json::Map::new();
        if let Some(m) = mdns.get(key) {
            obj.insert("mdns".to_string(), mdns_entry_to_json(m));
        }
        if let Some(s) = ssdp.get(key) {
            obj.insert("ssdp".to_string(), ssdp_entry_to_json(s));
        }
        out.insert(key.to_string(), Value::Object(obj));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extract_host_from_http_location() {
        assert_eq!(
            extract_host_from_location("http://192.168.1.100:80/device.xml"),
            Some("192.168.1.100".to_string()),
        );
    }

    #[test]
    fn extract_host_from_https_location_no_port() {
        assert_eq!(
            extract_host_from_location("https://example.local/desc"),
            Some("example.local".to_string()),
        );
    }

    #[test]
    fn extract_host_from_ipv6_location() {
        assert_eq!(
            extract_host_from_location("http://[fe80::1]:8080/x"),
            Some("fe80::1".to_string()),
        );
    }

    #[test]
    fn extract_host_rejects_non_http_scheme() {
        assert_eq!(extract_host_from_location("ftp://host/x"), None);
    }

    #[test]
    fn mdns_entry_to_json_camel_case_keys() {
        let mut entry = MdnsEntry::default();
        entry.services.insert("_hue._tcp.local".to_string());
        entry.hostname = Some("hue-bridge".to_string());
        entry
            .txt_records
            .insert("model".to_string(), "BSB002".to_string());
        let v = mdns_entry_to_json(&entry);
        assert_eq!(v["services"], json!(["_hue._tcp.local"]));
        assert_eq!(v["hostname"], json!("hue-bridge"));
        assert_eq!(v["txtRecords"]["model"], json!("BSB002"));
    }

    #[test]
    fn ssdp_entry_to_json_uses_device_type_key() {
        let entry = SsdpEntry {
            server: Some("Linux/5.4 UPnP/1.1 MiniDLNA/1.3".to_string()),
            location: Some("http://192.168.1.50:8200/rootDesc.xml".to_string()),
            usn: Some("uuid:abc::upnp:rootdevice".to_string()),
            device_type: Some("upnp:rootdevice".to_string()),
        };
        let v = ssdp_entry_to_json(&entry);
        assert_eq!(v["deviceType"], json!("upnp:rootdevice"));
        assert!(v.get("device_type").is_none(), "must serialize camelCase");
    }

    #[test]
    fn build_per_host_details_merges_both_sources() {
        let m_entry = MdnsEntry {
            hostname: Some("shelly-plug".to_string()),
            ..Default::default()
        };
        let mdns = HashMap::from([("192.168.1.10".to_string(), m_entry)]);

        let mut ssdp = HashMap::new();
        ssdp.insert(
            "192.168.1.10".to_string(),
            SsdpEntry {
                server: Some("Shelly/1.11.8".to_string()),
                location: Some("http://192.168.1.10/shelly".to_string()),
                usn: Some("uuid:shelly-123::upnp:rootdevice".to_string()),
                device_type: Some("urn:schemas-shelly-cloud:device:Switch:1".to_string()),
            },
        );

        let merged = build_per_host_details(&mdns, &ssdp);
        let entry = merged.get("192.168.1.10").expect("merged entry");
        assert!(entry.get("mdns").is_some());
        assert!(entry.get("ssdp").is_some());
    }

    #[test]
    fn build_per_host_details_handles_one_sided() {
        let mut mdns = HashMap::new();
        mdns.insert("192.168.1.5".to_string(), MdnsEntry::default());
        let ssdp = HashMap::new();
        let merged = build_per_host_details(&mdns, &ssdp);
        assert!(merged.contains_key("192.168.1.5"));
        assert!(merged["192.168.1.5"].get("ssdp").is_none());
    }

    #[tokio::test]
    async fn discover_mdns_short_timeout_returns_empty_gracefully() {
        // On CI containers without multicast routing, or with the 50ms
        // window being too short to see anything, this should degrade
        // to an empty map without panicking.
        let results = discover_mdns(Duration::from_millis(50)).await;
        // Only assertion: the call completes. Value may be empty or
        // populated depending on test host network.
        let _ = results;
    }

    #[tokio::test]
    async fn discover_ssdp_short_timeout_returns_gracefully() {
        let results = discover_ssdp(Duration::from_millis(50)).await;
        let _ = results;
    }
}
