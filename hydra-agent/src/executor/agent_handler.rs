//! Agent command handler.
//!
//! Handles agent self-management commands: status, config-reload, collect-now,
//! restart, update, probe-network.

use std::net::Ipv4Addr;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Instant;

use serde::Serialize;
use serde_json::Value;
use tokio::process::Command;
use tokio::sync::RwLock;
use tokio::task::JoinSet;
use tracing::{info, warn};

use crate::api::ApiClient;
use crate::config::AgentConfig;
use crate::vault::Vault;

use super::CommandResult;

const MAX_PROBE_HOSTS: usize = 256;
const DEFAULT_PROBE_TIMEOUT_MS: u64 = 1000;
const MAX_PROBE_TIMEOUT_MS: u64 = 5000;
const PROBE_CONCURRENCY: usize = 32;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProbeHostResult {
    pub ip: String,
    pub reachable: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hostname: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub latency_ms: Option<u64>,
}

#[derive(Debug, Clone)]
pub struct ProbeExecution {
    pub hosts: Vec<ProbeHostResult>,
    pub scanned_subnets: Vec<String>,
    pub total_hosts: usize,
    pub duration_ms: u64,
}

/// Execute an agent command.
///
/// # Arguments
/// * `action` - The agent action (status, config-reload, collect-now, restart, update, probe-network)
/// * `parameters` - Command parameters
/// * `timeout_secs` - Maximum execution time
/// * `config` - Shared agent configuration
/// * `start_time` - Agent start time for uptime calculation
/// * `api_client` - Optional API client for commands that need to call the API
/// * `config_path` - Optional path to agent.toml for config-reload
/// * `vault` - Optional vault for commands that need stored credentials
pub async fn execute(
    action: &str,
    parameters: &Option<Value>,
    timeout_secs: u64,
    config: Arc<RwLock<AgentConfig>>,
    start_time: Instant,
    api_client: Option<&Arc<ApiClient>>,
    config_path: Option<&PathBuf>,
    vault: Option<&Vault>,
) -> CommandResult {
    info!(action = action, "Executing agent command");

    match action {
        "status" => execute_status(config, start_time).await,
        "config-reload" => execute_config_reload(config, config_path).await,
        "collect-now" => execute_collect_now(config, timeout_secs, api_client).await,
        "restart" => execute_restart(timeout_secs).await,
        "update" => execute_update(parameters, config, vault).await,
        "probe-network" => execute_probe_network(parameters, timeout_secs).await,
        other => CommandResult::error(&format!("Unknown agent action: {}", other)),
    }
}

/// Return agent status information.
async fn execute_status(config: Arc<RwLock<AgentConfig>>, start_time: Instant) -> CommandResult {
    let config = config.read().await;
    let uptime = start_time.elapsed().as_secs();

    let status = format!(
        "Hydra Agent v{}\n\
         Node ID: {}\n\
         Class: {}\n\
         Type: {}\n\
         Tier: {}\n\
         Uptime: {}s\n\
         API URL: {}\n\
         Schedule: {} (interval: {}s)\n\
         Poll interval: {}s",
        env!("CARGO_PKG_VERSION"),
        config.node.node_id,
        config.node.class,
        config.node.node_type,
        config.node.tier,
        uptime,
        config.api.url,
        if config.schedule.enabled {
            "enabled"
        } else {
            "disabled"
        },
        config.schedule.interval_seconds,
        config.schedule.poll_interval_seconds,
    );

    CommandResult {
        success: true,
        output: Some(status),
        exit_code: Some(0),
        error: None,
        data: None,
    }
}

/// Reload the agent configuration from disk.
///
/// Re-reads agent.toml and updates the in-memory config via RwLock.
async fn execute_config_reload(
    config: Arc<RwLock<AgentConfig>>,
    config_path: Option<&PathBuf>,
) -> CommandResult {
    let path = match config_path {
        Some(p) => p,
        None => {
            return CommandResult::error(
                "Config reload unavailable: config path not available in this execution context",
            );
        }
    };

    if !path.exists() {
        return CommandResult::error(&format!("Config file not found: {}", path.display()));
    }

    info!(config_path = %path.display(), "Reloading configuration from disk");

    match AgentConfig::load(path) {
        Ok(new_config) => {
            let node_id = new_config.node.node_id.clone();
            let mut current = config.write().await;
            *current = new_config;
            drop(current);

            CommandResult {
                success: true,
                output: Some(format!(
                    "Configuration reloaded from {}. Node ID: {}",
                    path.display(),
                    node_id,
                )),
                exit_code: Some(0),
                error: None,
                data: None,
            }
        }
        Err(e) => CommandResult {
            success: false,
            output: None,
            exit_code: Some(1),
            error: Some(format!("Failed to reload config from {}: {}", path.display(), e)),
            data: None,
        },
    }
}

/// Trigger an immediate profile collection and submission.
async fn execute_collect_now(
    config: Arc<RwLock<AgentConfig>>,
    timeout_secs: u64,
    api_client: Option<&Arc<ApiClient>>,
) -> CommandResult {
    let config = config.read().await;

    info!(
        node_id = %config.node.node_id,
        "Triggering immediate profile collection"
    );

    let profile = match tokio::time::timeout(
        std::time::Duration::from_secs(timeout_secs),
        crate::collectors::collect_profile(&config),
    )
    .await
    {
        Ok(Ok(profile)) => profile,
        Ok(Err(error)) => {
            return CommandResult {
                success: false,
                output: None,
                exit_code: Some(1),
                error: Some(format!("Profile collection failed: {}", error)),
                data: None,
            };
        }
        Err(_) => {
            return CommandResult {
                success: false,
                output: None,
                exit_code: None,
                error: Some(format!(
                    "Profile collection timed out after {} seconds",
                    timeout_secs
                )),
                data: None,
            };
        }
    };

    let sections: Vec<String> = profile.sections().iter().map(|section| section.to_string()).collect();
    let Some(client) = api_client else {
        return CommandResult::error(
            "Profile collection requires API access in this execution context",
        );
    };

    match client.submit_profile(&profile).await {
        Ok(result) => {
            info!(
                profile_id = %result.profile_id,
                version = %result.version,
                "Profile collected and submitted via collect-now"
            );
            CommandResult {
                success: true,
                output: Some(format!(
                    "Profile collected and submitted.\nProfile ID: {}\nVersion: {}\nSections: {}",
                    result.profile_id,
                    result.version,
                    sections.join(", ")
                )),
                exit_code: Some(0),
                error: None,
                data: Some(serde_json::json!({
                    "profileId": result.profile_id,
                    "version": result.version,
                    "sections": sections,
                })),
            }
        }
        Err(error) => {
            warn!(error = %error, "Profile collected but submission failed");
            CommandResult {
                success: false,
                output: Some(format!(
                    "Profile collected ({} sections) but submission failed.",
                    sections.len()
                )),
                exit_code: Some(1),
                error: Some(format!("Profile submission failed: {}", error)),
                data: Some(serde_json::json!({
                    "sections": sections,
                })),
            }
        }
    }
}

/// Restart the hydra-agent service.
///
/// The result is submitted back to the API before the restart happens,
/// since the agent process will be replaced.
#[cfg(target_os = "linux")]
async fn execute_restart(_timeout_secs: u64) -> CommandResult {
    info!("Agent restart requested — will restart after result submission");

    tokio::spawn(async {
        tokio::time::sleep(std::time::Duration::from_secs(2)).await;
        let _ = Command::new("systemctl")
            .args(["restart", "hydra-agent.service"])
            .status()
            .await;
    });

    CommandResult {
        success: true,
        output: Some("Agent restart initiated. The service will restart momentarily.".to_string()),
        exit_code: Some(0),
        error: None,
        data: None,
    }
}

#[cfg(not(target_os = "linux"))]
async fn execute_restart(_timeout_secs: u64) -> CommandResult {
    CommandResult::error("Agent restart via systemctl is only supported on Linux")
}

async fn execute_update(
    parameters: &Option<Value>,
    config: Arc<RwLock<AgentConfig>>,
    vault: Option<&Vault>,
) -> CommandResult {
    let Some(vault) = vault else {
        return CommandResult::error(
            "Agent update requires vault access in this execution context",
        );
    };

    let target_version =
        extract_string_parameter(parameters, &["targetVersion", "target_version", "version"]);
    let source = extract_string_parameter(parameters, &["source"]);
    let config_snapshot = config.read().await.clone();

    match crate::cli::upgrade::schedule_upgrade(
        config_snapshot,
        vault.clone(),
        target_version.clone(),
        source.clone(),
    )
    .await
    {
        Ok(accepted) => CommandResult {
            success: true,
            output: Some(accepted.message.clone()),
            exit_code: Some(0),
            error: None,
            data: Some(serde_json::json!({
                "currentVersion": accepted.current_version,
                "targetVersion": accepted.target_version,
                "source": accepted.source,
                "scheduled": true,
            })),
        },
        Err(error) => CommandResult::error(&format!("Failed to schedule agent update: {}", error)),
    }
}

async fn execute_probe_network(parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let targets = match extract_probe_targets(parameters) {
        Ok(targets) => targets,
        Err(error) => return CommandResult::error(&error),
    };

    let options = parameters
        .as_ref()
        .and_then(|params| params.get("options"))
        .cloned();

    let result = tokio::time::timeout(
        std::time::Duration::from_secs(timeout_secs.max(1)),
        execute_probe_request("subnet", targets, options),
    )
    .await;

    let probe = match result {
        Ok(Ok(probe)) => probe,
        Ok(Err(error)) => return CommandResult::error(&error),
        Err(_) => {
            return CommandResult::error(&format!(
                "Network probe timed out after {} seconds",
                timeout_secs
            ));
        }
    };

    let reachable_count = probe.hosts.iter().filter(|host| host.reachable).count();
    CommandResult {
        success: true,
        output: Some(format!(
            "Probed {} host(s) across {} subnet(s); {} host(s) responded.",
            probe.total_hosts,
            probe.scanned_subnets.len(),
            reachable_count
        )),
        exit_code: Some(0),
        error: None,
        data: Some(serde_json::json!({
            "hosts": probe.hosts,
            "scannedSubnets": probe.scanned_subnets,
            "totalHosts": probe.total_hosts,
            "durationMs": probe.duration_ms,
        })),
    }
}

pub async fn execute_probe_request(
    probe_type: &str,
    targets: Vec<String>,
    options: Option<Value>,
) -> Result<ProbeExecution, String> {
    validate_probe_type(probe_type)?;

    if targets.is_empty() {
        return Err("Subnet probing requires at least one CIDR target".to_string());
    }

    let per_host_timeout_ms = options
        .as_ref()
        .and_then(|value| value.get("timeoutMs").and_then(Value::as_u64))
        .unwrap_or(DEFAULT_PROBE_TIMEOUT_MS)
        .clamp(100, MAX_PROBE_TIMEOUT_MS);

    let started = Instant::now();
    let mut expanded_hosts = Vec::new();
    let mut scanned_subnets = Vec::new();

    for target in targets {
        let mut subnet_hosts = expand_ipv4_cidr(&target)?;
        if expanded_hosts.len() + subnet_hosts.len() > MAX_PROBE_HOSTS {
            return Err(format!(
                "Subnet probe exceeds the {} host limit for a single request",
                MAX_PROBE_HOSTS
            ));
        }
        scanned_subnets.push(target);
        expanded_hosts.append(&mut subnet_hosts);
    }

    let total_hosts = expanded_hosts.len();
    let mut tasks = JoinSet::new();
    let mut hosts = Vec::with_capacity(total_hosts);

    for ip in expanded_hosts {
        tasks.spawn(async move { probe_host(ip, per_host_timeout_ms).await });
        if tasks.len() >= PROBE_CONCURRENCY {
            match tasks.join_next().await {
                Some(Ok(host)) => hosts.push(host),
                Some(Err(error)) => {
                    return Err(format!("Probe execution task failed: {}", error));
                }
                None => break,
            }
        }
    }

    while let Some(result) = tasks.join_next().await {
        match result {
            Ok(host) => hosts.push(host),
            Err(error) => {
                return Err(format!("Probe execution task failed: {}", error));
            }
        }
    }

    hosts.sort_by(|left, right| left.ip.cmp(&right.ip));

    Ok(ProbeExecution {
        hosts,
        scanned_subnets,
        total_hosts,
        duration_ms: started.elapsed().as_millis() as u64,
    })
}

fn validate_probe_type(probe_type: &str) -> Result<(), String> {
    if probe_type == "subnet" || probe_type == "cidr" {
        Ok(())
    } else {
        Err(format!(
            "Unsupported probe type '{}'. Only subnet/CIDR probing is available in this phase",
            probe_type
        ))
    }
}

fn extract_probe_targets(parameters: &Option<Value>) -> Result<Vec<String>, String> {
    let Some(params) = parameters.as_ref() else {
        return Err("probe-network requires parameters with a 'subnet' or 'targets' field".to_string());
    };

    if let Some(probe_type) = extract_string_parameter(parameters, &["probeType", "probe_type"]) {
        validate_probe_type(&probe_type)?;
    }

    let mut targets = Vec::new();

    if let Some(subnet) = params.get("subnet").and_then(Value::as_str) {
        targets.push(subnet.to_string());
    }

    if let Some(values) = params.get("targets").and_then(Value::as_array) {
        for value in values {
            let Some(target) = value.as_str() else {
                return Err("probe-network targets must be an array of CIDR strings".to_string());
            };
            targets.push(target.to_string());
        }
    }

    if targets.is_empty() {
        return Err("probe-network requires at least one CIDR subnet target".to_string());
    }

    Ok(targets)
}

fn extract_string_parameter(parameters: &Option<Value>, keys: &[&str]) -> Option<String> {
    let params = parameters.as_ref()?;
    keys.iter().find_map(|key| {
        params
            .get(*key)
            .and_then(Value::as_str)
            .map(|value| value.to_string())
    })
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
        return Err(format!("Invalid CIDR prefix '{}': must be between 0 and 32", prefix));
    }

    let host_count = match prefix {
        32 => 1_u64,
        31 => 2_u64,
        _ => (1_u64 << (32 - prefix)) - 2,
    };

    if host_count == 0 {
        return Err(format!("CIDR '{}' does not contain probeable hosts", input));
    }

    if host_count > MAX_PROBE_HOSTS as u64 {
        return Err(format!(
            "CIDR '{}' expands to {} hosts which exceeds the {} host limit",
            input, host_count, MAX_PROBE_HOSTS
        ));
    }

    let base = u32::from(address);
    let mask = if prefix == 0 {
        0
    } else {
        u32::MAX << (32 - prefix)
    };
    let network = base & mask;
    let broadcast = network | !mask;

    let (start, end) = if prefix >= 31 {
        (network, broadcast)
    } else {
        (network + 1, broadcast - 1)
    };

    let mut hosts = Vec::with_capacity(host_count as usize);
    for ip in start..=end {
        hosts.push(Ipv4Addr::from(ip).to_string());
    }
    Ok(hosts)
}

async fn probe_host(ip: String, timeout_ms: u64) -> ProbeHostResult {
    let started = Instant::now();
    let output = ping_ip(&ip, timeout_ms).await;

    match output {
        Ok(status) if status.success() => ProbeHostResult {
            ip,
            reachable: true,
            hostname: None,
            latency_ms: Some(started.elapsed().as_millis() as u64),
        },
        Ok(_) => ProbeHostResult {
            ip,
            reachable: false,
            hostname: None,
            latency_ms: None,
        },
        Err(error) => {
            warn!(ip = %ip, error = %error, "Network probe ping failed");
            ProbeHostResult {
                ip,
                reachable: false,
                hostname: None,
                latency_ms: None,
            }
        }
    }
}

#[cfg(any(target_os = "linux", target_os = "android"))]
async fn ping_ip(ip: &str, timeout_ms: u64) -> Result<std::process::ExitStatus, String> {
    let timeout_secs = timeout_ms.div_ceil(1000).max(1);
    Command::new("ping")
        .args(["-c", "1", "-n", "-W", &timeout_secs.to_string(), ip])
        .status()
        .await
        .map_err(|error| format!("Failed to invoke ping: {}", error))
}

#[cfg(target_os = "windows")]
async fn ping_ip(ip: &str, timeout_ms: u64) -> Result<std::process::ExitStatus, String> {
    Command::new("ping")
        .args(["-n", "1", "-w", &timeout_ms.to_string(), ip])
        .status()
        .await
        .map_err(|error| format!("Failed to invoke ping: {}", error))
}

#[cfg(all(unix, not(target_os = "linux"), not(target_os = "android")))]
async fn ping_ip(ip: &str, timeout_ms: u64) -> Result<std::process::ExitStatus, String> {
    Command::new("ping")
        .args(["-c", "1", "-n", "-W", &timeout_ms.to_string(), ip])
        .status()
        .await
        .map_err(|error| format!("Failed to invoke ping: {}", error))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_expand_ipv4_cidr_expands_usable_hosts() {
        let hosts = expand_ipv4_cidr("192.168.1.0/30").expect("cidr should expand");
        assert_eq!(hosts, vec!["192.168.1.1", "192.168.1.2"]);
    }

    #[test]
    fn test_expand_ipv4_cidr_rejects_large_ranges() {
        let error = expand_ipv4_cidr("10.0.0.0/23").expect_err("large range should fail");
        assert!(error.contains("exceeds the 256 host limit"));
    }

    #[test]
    fn test_extract_probe_targets_accepts_subnet_and_targets() {
        let targets = extract_probe_targets(&Some(serde_json::json!({
            "subnet": "192.168.1.0/30",
            "targets": ["192.168.2.0/30"],
        })))
        .expect("targets should parse");

        assert_eq!(targets, vec!["192.168.1.0/30", "192.168.2.0/30"]);
    }
}
