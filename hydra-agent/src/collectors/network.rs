//! Network information collector.

use anyhow::Result;
use serde::Serialize;
use sysinfo::Networks;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct NetworkProfile {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hostname: Option<String>,
    pub interfaces: Vec<NetworkInterface>,
    pub dns_servers: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct NetworkInterface {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mac_address: Option<String>,
    pub ipv4_addresses: Vec<String>,
    pub ipv6_addresses: Vec<String>,
    pub state: String,
}

pub struct NetworkCollector;

impl NetworkCollector {
    /// Collect network information.
    pub fn collect() -> Result<NetworkProfile> {
        let networks = Networks::new_with_refreshed_list();

        let mut interfaces = Vec::new();

        for (name, data) in &networks {
            let mac = data.mac_address();
            let mac_str = format!(
                "{:02x}:{:02x}:{:02x}:{:02x}:{:02x}:{:02x}",
                mac.0[0], mac.0[1], mac.0[2], mac.0[3], mac.0[4], mac.0[5]
            );

            // Get IP addresses using local-ip-address crate
            let mut ipv4_addresses = Vec::new();
            let mut ipv6_addresses = Vec::new();

            // Try to get local IP (simplified - production would enumerate all IPs)
            if let Ok(ip) = local_ip_address::local_ip() {
                match ip {
                    std::net::IpAddr::V4(v4) => ipv4_addresses.push(v4.to_string()),
                    std::net::IpAddr::V6(v6) => ipv6_addresses.push(v6.to_string()),
                }
            }

            interfaces.push(NetworkInterface {
                name: name.clone(),
                mac_address: Some(mac_str),
                ipv4_addresses,
                ipv6_addresses,
                state: "up".to_string(), // Simplified
            });
        }

        // Get hostname
        let hostname = hostname::get()
            .ok()
            .and_then(|h| h.into_string().ok());

        // DNS servers would require platform-specific reading of resolv.conf or registry
        let dns_servers = Self::get_dns_servers();

        Ok(NetworkProfile {
            hostname,
            interfaces,
            dns_servers,
        })
    }

    /// Get DNS servers on Unix-like systems (Linux, macOS, BSD).
    #[cfg(unix)]
    fn get_dns_servers() -> Vec<String> {
        // Read from /etc/resolv.conf (works on Linux, macOS, BSD)
        if let Ok(contents) = std::fs::read_to_string("/etc/resolv.conf") {
            contents
                .lines()
                .filter(|line| line.starts_with("nameserver"))
                .filter_map(|line| line.split_whitespace().nth(1))
                .map(String::from)
                .collect()
        } else {
            vec![]
        }
    }

    /// Get DNS servers on Windows by reading from the registry.
    #[cfg(windows)]
    fn get_dns_servers() -> Vec<String> {
        use std::process::Command;

        let mut servers = Vec::new();

        // Use netsh to get DNS server configuration
        if let Ok(output) = Command::new("netsh")
            .args(["interface", "ip", "show", "dns"])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    // Look for lines with IP addresses
                    let trimmed = line.trim();
                    if trimmed.starts_with("DNS Servers") || trimmed.starts_with("Statically") {
                        continue;
                    }
                    // Check if line contains an IP address
                    if let Some(ip) = trimmed.split_whitespace().last() {
                        // Basic validation - check if it looks like an IP
                        if ip.contains('.') && ip.chars().all(|c| c.is_ascii_digit() || c == '.') {
                            servers.push(ip.to_string());
                        }
                    }
                }
            }
        }

        // Fallback: try ipconfig
        if servers.is_empty() {
            if let Ok(output) = Command::new("ipconfig").args(["/all"]).output() {
                if output.status.success() {
                    let stdout = String::from_utf8_lossy(&output.stdout);
                    let mut capture_dns = false;
                    for line in stdout.lines() {
                        if line.contains("DNS Servers") {
                            capture_dns = true;
                            // Extract IP from same line if present
                            if let Some(ip) = line.split(':').nth(1) {
                                let ip = ip.trim();
                                if !ip.is_empty() && ip.contains('.') {
                                    servers.push(ip.to_string());
                                }
                            }
                        } else if capture_dns {
                            let trimmed = line.trim();
                            if trimmed.is_empty() || trimmed.contains(':') {
                                capture_dns = false;
                            } else if trimmed.contains('.') {
                                servers.push(trimmed.to_string());
                            }
                        }
                    }
                }
            }
        }

        servers
    }
}
