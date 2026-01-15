//! Network information collector.

use anyhow::Result;
use serde::Serialize;
use sysinfo::Networks;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct NetworkProfile {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hostname: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub domain: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fqdn: Option<String>,
    pub interfaces: Vec<NetworkInterface>,
    pub dns_servers: Vec<String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub dns_search: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub default_gateway: Option<String>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub routes: Vec<NetworkRoute>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct NetworkInterface {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mac_address: Option<String>,
    pub ipv4_addresses: Vec<String>,
    pub ipv6_addresses: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub netmask: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gateway: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mtu: Option<u32>,
    pub state: String,
    #[serde(skip_serializing_if = "Option::is_none", rename = "type")]
    pub interface_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub speed_mbps: Option<u32>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct NetworkRoute {
    pub destination: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gateway: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub interface: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metric: Option<u32>,
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
                netmask: None, // Would require platform-specific enumeration
                gateway: None,
                mtu: None,
                state: "up".to_string(),
                interface_type: None,
                speed_mbps: None,
            });
        }

        // Get hostname
        let hostname = hostname::get()
            .ok()
            .and_then(|h| h.into_string().ok());

        // Get domain and FQDN
        let (domain, fqdn) = Self::get_domain_info(&hostname);

        // DNS servers and search domains
        let (dns_servers, dns_search) = Self::get_dns_config();

        // Default gateway and routes
        let (default_gateway, routes) = Self::get_routing_info();

        Ok(NetworkProfile {
            hostname,
            domain,
            fqdn,
            interfaces,
            dns_servers,
            dns_search,
            default_gateway,
            routes,
        })
    }

    /// Get domain and FQDN.
    fn get_domain_info(hostname: &Option<String>) -> (Option<String>, Option<String>) {
        #[cfg(unix)]
        {
            if let Ok(contents) = std::fs::read_to_string("/etc/resolv.conf") {
                for line in contents.lines() {
                    if line.starts_with("domain") {
                        let domain = line.split_whitespace().nth(1).map(String::from);
                        let fqdn = hostname.as_ref().and_then(|h| {
                            domain.as_ref().map(|d| format!("{}.{}", h, d))
                        });
                        return (domain, fqdn);
                    }
                }
            }
        }
        #[cfg(windows)]
        {
            use std::process::Command;
            if let Ok(output) = Command::new("powershell")
                .args(["-NoProfile", "-Command", "(Get-WmiObject Win32_ComputerSystem).Domain"])
                .output()
            {
                if output.status.success() {
                    let domain = String::from_utf8_lossy(&output.stdout).trim().to_string();
                    if !domain.is_empty() && domain != "WORKGROUP" {
                        let fqdn = hostname.as_ref().map(|h| format!("{}.{}", h, domain));
                        return (Some(domain), fqdn);
                    }
                }
            }
        }
        (None, hostname.clone())
    }

    /// Get DNS configuration (servers and search domains).
    #[cfg(unix)]
    fn get_dns_config() -> (Vec<String>, Vec<String>) {
        let mut servers = Vec::new();
        let mut search = Vec::new();

        if let Ok(contents) = std::fs::read_to_string("/etc/resolv.conf") {
            for line in contents.lines() {
                if line.starts_with("nameserver") {
                    if let Some(server) = line.split_whitespace().nth(1) {
                        servers.push(server.to_string());
                    }
                } else if line.starts_with("search") {
                    search = line.split_whitespace().skip(1).map(String::from).collect();
                }
            }
        }

        (servers, search)
    }

    #[cfg(windows)]
    fn get_dns_config() -> (Vec<String>, Vec<String>) {
        use std::process::Command;
        let mut servers = Vec::new();
        let search = Vec::new();

        if let Ok(output) = Command::new("netsh")
            .args(["interface", "ip", "show", "dns"])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    let trimmed = line.trim();
                    if let Some(ip) = trimmed.split_whitespace().last() {
                        if ip.contains('.') && ip.chars().all(|c| c.is_ascii_digit() || c == '.') {
                            servers.push(ip.to_string());
                        }
                    }
                }
            }
        }

        (servers, search)
    }

    /// Get routing information.
    #[cfg(target_os = "linux")]
    fn get_routing_info() -> (Option<String>, Vec<NetworkRoute>) {
        use std::process::Command;
        let mut default_gateway = None;
        let mut routes = Vec::new();

        if let Ok(output) = Command::new("ip").args(["route", "show"]).output() {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    let parts: Vec<&str> = line.split_whitespace().collect();
                    if parts.is_empty() {
                        continue;
                    }

                    let destination = parts[0].to_string();
                    let mut gateway = None;
                    let mut interface = None;
                    let mut metric = None;

                    for i in 0..parts.len() {
                        match parts[i] {
                            "via" => gateway = parts.get(i + 1).map(|s| s.to_string()),
                            "dev" => interface = parts.get(i + 1).map(|s| s.to_string()),
                            "metric" => metric = parts.get(i + 1).and_then(|s| s.parse().ok()),
                            _ => {}
                        }
                    }

                    if destination == "default" {
                        default_gateway = gateway.clone();
                    }

                    routes.push(NetworkRoute {
                        destination,
                        gateway,
                        interface,
                        metric,
                    });
                }
            }
        }

        (default_gateway, routes)
    }

    #[cfg(target_os = "windows")]
    fn get_routing_info() -> (Option<String>, Vec<NetworkRoute>) {
        use std::process::Command;
        let mut default_gateway = None;
        let mut routes = Vec::new();

        if let Ok(output) = Command::new("route").args(["print", "0.0.0.0"]).output() {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    let parts: Vec<&str> = line.split_whitespace().collect();
                    if parts.len() >= 5 && parts[0] == "0.0.0.0" {
                        default_gateway = Some(parts[2].to_string());
                        routes.push(NetworkRoute {
                            destination: "default".to_string(),
                            gateway: Some(parts[2].to_string()),
                            interface: Some(parts[3].to_string()),
                            metric: parts.get(4).and_then(|s| s.parse().ok()),
                        });
                        break;
                    }
                }
            }
        }

        (default_gateway, routes)
    }

    #[cfg(target_os = "macos")]
    fn get_routing_info() -> (Option<String>, Vec<NetworkRoute>) {
        use std::process::Command;
        let mut default_gateway = None;
        let routes = Vec::new();

        if let Ok(output) = Command::new("route").args(["-n", "get", "default"]).output() {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    if line.trim().starts_with("gateway:") {
                        default_gateway = line.split(':').nth(1).map(|s| s.trim().to_string());
                        break;
                    }
                }
            }
        }

        (default_gateway, routes)
    }

    #[cfg(not(any(target_os = "linux", target_os = "windows", target_os = "macos")))]
    fn get_routing_info() -> (Option<String>, Vec<NetworkRoute>) {
        (None, Vec::new())
    }
}
