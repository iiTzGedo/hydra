//! Network information collector.
//!
//! Collects network configuration including interfaces, DNS settings,
//! and routing information using platform-specific APIs and commands.

use anyhow::Result;
use serde::Serialize;
use std::collections::HashMap;
use sysinfo::Networks;

/// Interface IP data: (ipv4_addrs, ipv6_addrs, first_netmask).
type InterfaceIpData = (Vec<String>, Vec<String>, Option<String>);

/// Network profile containing hostname, interfaces, DNS, and routing information.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct NetworkProfile {
    /// System hostname
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hostname: Option<String>,
    /// Network domain
    #[serde(skip_serializing_if = "Option::is_none")]
    pub domain: Option<String>,
    /// Fully qualified domain name
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fqdn: Option<String>,
    /// List of network interfaces
    pub interfaces: Vec<NetworkInterface>,
    /// Configured DNS servers
    pub dns_servers: Vec<String>,
    /// DNS search domains
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub dns_search: Vec<String>,
    /// Default gateway IP address
    #[serde(skip_serializing_if = "Option::is_none")]
    pub default_gateway: Option<String>,
    /// Routing table entries
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub routes: Vec<NetworkRoute>,
}

/// Network interface information.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct NetworkInterface {
    /// Interface name (e.g., "eth0", "enp0s3")
    pub name: String,
    /// MAC address in colon-separated format
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mac_address: Option<String>,
    /// IPv4 addresses assigned to this interface
    pub ipv4_addresses: Vec<String>,
    /// IPv6 addresses assigned to this interface
    pub ipv6_addresses: Vec<String>,
    /// Network mask
    #[serde(skip_serializing_if = "Option::is_none")]
    pub netmask: Option<String>,
    /// Gateway for this interface
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gateway: Option<String>,
    /// Maximum transmission unit
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mtu: Option<u32>,
    /// Interface state (e.g., "up", "down")
    pub state: String,
    /// Interface type (e.g., "ethernet", "wireless")
    #[serde(skip_serializing_if = "Option::is_none", rename = "type")]
    pub interface_type: Option<String>,
    /// Link speed in Mbps
    #[serde(skip_serializing_if = "Option::is_none")]
    pub speed_mbps: Option<u32>,
}

/// Network route entry.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct NetworkRoute {
    /// Destination network or "default"
    pub destination: String,
    /// Gateway IP address
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gateway: Option<String>,
    /// Outgoing interface
    #[serde(skip_serializing_if = "Option::is_none")]
    pub interface: Option<String>,
    /// Route metric/priority
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metric: Option<u32>,
}

/// Collector for network information.
pub struct NetworkCollector;

impl NetworkCollector {
    /// Collects network information from the current system.
    ///
    /// Gathers interface details, DNS configuration, and routing information
    /// using platform-specific methods.
    ///
    /// # Returns
    ///
    /// A network profile containing all collected data.
    ///
    /// # Errors
    ///
    /// Returns an error if network information cannot be retrieved.
    pub fn collect() -> Result<NetworkProfile> {
        let networks = Networks::new_with_refreshed_list();

        // Collect per-interface IP addresses and netmasks
        let ip_map = Self::collect_interface_ips();

        let mut interfaces = Vec::new();

        for (name, data) in &networks {
            let mac = data.mac_address();
            let mac_str = format!(
                "{:02x}:{:02x}:{:02x}:{:02x}:{:02x}:{:02x}",
                mac.0[0], mac.0[1], mac.0[2], mac.0[3], mac.0[4], mac.0[5]
            );

            // Get IPs for this specific interface
            let (ipv4_addresses, ipv6_addresses, netmask) =
                ip_map.get(name.as_str()).cloned().unwrap_or_default();

            // Read interface metadata from sysfs (Linux) or platform APIs
            let (state, mtu, speed_mbps, interface_type) = Self::get_interface_metadata(name);

            interfaces.push(NetworkInterface {
                name: name.clone(),
                mac_address: Some(mac_str),
                ipv4_addresses,
                ipv6_addresses,
                netmask,
                gateway: None,
                mtu,
                state,
                interface_type,
                speed_mbps,
            });
        }

        let hostname = hostname::get().ok().and_then(|h| h.into_string().ok());

        let (domain, fqdn) = Self::get_domain_info(&hostname);
        let (dns_servers, dns_search) = Self::get_dns_config();
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

    /// Collects IP addresses per interface using platform-specific methods.
    ///
    /// Returns a map of interface name -> (ipv4_addrs, ipv6_addrs, first_netmask).
    #[cfg(unix)]
    fn collect_interface_ips() -> HashMap<String, InterfaceIpData> {
        let mut map: HashMap<String, InterfaceIpData> = HashMap::new();

        if let Ok(addrs) = nix::ifaddrs::getifaddrs() {
            for ifaddr in addrs {
                let name = ifaddr.interface_name.clone();
                let entry = map.entry(name).or_insert_with(|| (vec![], vec![], None));

                if let Some(addr) = ifaddr.address {
                    if let Some(sockaddr) = addr.as_sockaddr_in() {
                        let ip = sockaddr.ip();
                        entry.0.push(ip.to_string());

                        // Extract netmask for this interface
                        if entry.2.is_none() {
                            if let Some(mask) = ifaddr.netmask {
                                if let Some(mask_in) = mask.as_sockaddr_in() {
                                    let mask_ip = mask_in.ip();
                                    entry.2 = Some(mask_ip.to_string());
                                }
                            }
                        }
                    } else if let Some(sockaddr6) = addr.as_sockaddr_in6() {
                        let ip = sockaddr6.ip();
                        entry.1.push(ip.to_string());
                    }
                }
            }
        }

        map
    }

    #[cfg(windows)]
    fn collect_interface_ips() -> HashMap<String, (Vec<String>, Vec<String>, Option<String>)> {
        let mut map = HashMap::new();
        // Fall back to single system IP on Windows
        if let Ok(ip) = local_ip_address::local_ip() {
            let entry = map
                .entry("default".to_string())
                .or_insert_with(|| (vec![], vec![], None));
            match ip {
                std::net::IpAddr::V4(v4) => entry.0.push(v4.to_string()),
                std::net::IpAddr::V6(v6) => entry.1.push(v6.to_string()),
            }
        }
        map
    }

    /// Reads interface metadata from sysfs (Linux) or returns defaults.
    #[cfg(target_os = "linux")]
    fn get_interface_metadata(name: &str) -> (String, Option<u32>, Option<u32>, Option<String>) {
        let sysfs = format!("/sys/class/net/{}", name);

        // operstate: up, down, unknown, dormant, etc.
        let state = std::fs::read_to_string(format!("{}/operstate", sysfs))
            .map(|s| s.trim().to_string())
            .unwrap_or_else(|_| "unknown".to_string());

        // MTU
        let mtu = std::fs::read_to_string(format!("{}/mtu", sysfs))
            .ok()
            .and_then(|s| s.trim().parse::<u32>().ok());

        // Speed in Mbps (only valid for physical interfaces, returns error for virtual)
        let speed_mbps = std::fs::read_to_string(format!("{}/speed", sysfs))
            .ok()
            .and_then(|s| s.trim().parse::<i32>().ok())
            .and_then(|s| if s > 0 { Some(s as u32) } else { None });

        // Interface type from sysfs type code
        let interface_type = std::fs::read_to_string(format!("{}/type", sysfs))
            .ok()
            .and_then(|s| s.trim().parse::<u32>().ok())
            .map(|t| match t {
                1 => "ethernet",
                772 => "loopback",
                801 | 802 => "wireless",
                _ => "other",
            })
            .map(String::from);

        (state, mtu, speed_mbps, interface_type)
    }

    #[cfg(not(target_os = "linux"))]
    fn get_interface_metadata(_name: &str) -> (String, Option<u32>, Option<u32>, Option<String>) {
        ("up".to_string(), None, None, None)
    }

    fn get_domain_info(hostname: &Option<String>) -> (Option<String>, Option<String>) {
        #[cfg(unix)]
        {
            if let Ok(contents) = std::fs::read_to_string("/etc/resolv.conf") {
                for line in contents.lines() {
                    if line.starts_with("domain") {
                        let domain = line.split_whitespace().nth(1).map(String::from);
                        let fqdn = hostname
                            .as_ref()
                            .and_then(|h| domain.as_ref().map(|d| format!("{}.{}", h, d)));
                        return (domain, fqdn);
                    }
                }
            }
        }
        #[cfg(windows)]
        {
            use std::process::Command;
            if let Ok(output) = Command::new("powershell")
                .args([
                    "-NoProfile",
                    "-Command",
                    "(Get-WmiObject Win32_ComputerSystem).Domain",
                ])
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

        // Detect systemd-resolved stub (127.0.0.53) and try to get real DNS servers
        let is_stub = servers.len() == 1 && servers[0] == "127.0.0.53";
        if servers.is_empty() || is_stub {
            if let Some((resolved_servers, resolved_search)) = Self::get_resolved_dns() {
                if !resolved_servers.is_empty() {
                    servers = resolved_servers;
                }
                if !resolved_search.is_empty() {
                    search = resolved_search;
                }
            }
        }

        (servers, search)
    }

    /// Attempts to get DNS configuration from systemd-resolved via resolvectl.
    #[cfg(unix)]
    fn get_resolved_dns() -> Option<(Vec<String>, Vec<String>)> {
        use std::process::Command;

        let output = Command::new("resolvectl")
            .args(["status", "--no-pager"])
            .output()
            .ok()?;

        if !output.status.success() {
            // Try legacy command
            let output = Command::new("systemd-resolve")
                .args(["--status", "--no-pager"])
                .output()
                .ok()?;
            if !output.status.success() {
                return None;
            }
            return Self::parse_resolved_output(&String::from_utf8_lossy(&output.stdout));
        }

        Self::parse_resolved_output(&String::from_utf8_lossy(&output.stdout))
    }

    #[cfg(unix)]
    fn parse_resolved_output(stdout: &str) -> Option<(Vec<String>, Vec<String>)> {
        let mut servers = Vec::new();
        let mut search = Vec::new();
        let mut in_dns_servers = false;
        let mut in_dns_domain = false;

        for line in stdout.lines() {
            let trimmed = line.trim();

            if trimmed.starts_with("DNS Servers:") || trimmed.starts_with("DNS Server:") {
                in_dns_servers = true;
                in_dns_domain = false;
                if let Some(server) = trimmed.split(':').nth(1) {
                    let s = server.trim();
                    if !s.is_empty() {
                        servers.push(s.to_string());
                    }
                }
            } else if trimmed.starts_with("DNS Domain:") {
                in_dns_domain = true;
                in_dns_servers = false;
                if let Some(domain) = trimmed.split(':').nth(1) {
                    let d = domain.trim();
                    if !d.is_empty() {
                        search.push(d.to_string());
                    }
                }
            } else if trimmed.contains(':') {
                // New section — stop collecting
                in_dns_servers = false;
                in_dns_domain = false;
            } else if in_dns_servers && !trimmed.is_empty() {
                servers.push(trimmed.to_string());
            } else if in_dns_domain && !trimmed.is_empty() {
                search.push(trimmed.to_string());
            }
        }

        if servers.is_empty() {
            return None;
        }

        Some((servers, search))
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

        if let Ok(output) = Command::new("route")
            .args(["-n", "get", "default"])
            .output()
        {
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
