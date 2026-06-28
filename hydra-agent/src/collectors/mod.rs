//! System profile collectors for infrastructure profiling.
//!
//! This module provides collectors for gathering system information:
//! - [`hardware`] - CPU, memory, and system identification
//! - [`network`] - Network interfaces and configuration
//! - [`software`] - Operating system, packages, and services
//! - [`storage`] - Disks, filesystems, and mounts

pub mod configs;
pub mod hardware;
pub mod network;
pub mod services;
pub mod software;
pub mod storage;
pub mod users;

use anyhow::Result;
use chrono::{DateTime, Utc};
use serde::Serialize;
use serde_json::json;
use tracing::info;

use crate::config::AgentConfig;

pub use configs::ConfigsCollector;
pub use hardware::HardwareCollector;
pub use network::NetworkCollector;
pub use services::ServicesCollector;
pub use software::SoftwareCollector;
pub use storage::StorageCollector;
pub use users::UsersCollector;

/// Complete system profile containing all collected data sections.
///
/// A profile represents a point-in-time snapshot of a node's system state.
/// Each section is optional and collected based on configuration.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Profile {
    /// Unique identifier for the node
    pub node_id: String,
    /// Profile version using hexadecimal versioning (Ex-W.X.Y.Z)
    pub version: String,
    /// Timestamp when the profile was collected
    pub collected_at: DateTime<Utc>,
    /// Version of the agent that collected this profile
    pub agent_version: String,
    /// Agent tier (lite, normal, max)
    pub agent_tier: String,
    /// Collection level used (minimal, neutral, comprehensive)
    pub collection_level: String,
    /// Hardware information (CPU, memory, system IDs)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hardware: Option<hardware::HardwareProfile>,
    /// Network configuration and interfaces
    #[serde(skip_serializing_if = "Option::is_none")]
    pub network: Option<network::NetworkProfile>,
    /// Storage devices and filesystems
    #[serde(skip_serializing_if = "Option::is_none")]
    pub storage: Option<storage::StorageProfile>,
    /// Operating system and software information
    #[serde(skip_serializing_if = "Option::is_none")]
    pub software: Option<software::SoftwareProfile>,
    /// Discovered services (systemd, docker, launchd, windows, rc)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub services: Option<services::ServicesProfile>,
    /// Local user accounts and SSH key fingerprints
    #[serde(skip_serializing_if = "Option::is_none")]
    pub users: Option<users::UsersProfile>,
    /// Tracked configuration file hashes
    #[serde(skip_serializing_if = "Option::is_none")]
    pub configs: Option<configs::ConfigsProfile>,
    /// Additional metadata key-value pairs
    pub metadata: std::collections::HashMap<String, serde_json::Value>,
}

impl Profile {
    /// Returns a list of section names that were collected in this profile.
    ///
    /// # Returns
    ///
    /// A vector of section names (e.g., "hardware", "network", "storage", "software").
    pub fn sections(&self) -> Vec<&str> {
        let mut sections = vec![];
        if self.hardware.is_some() {
            sections.push("hardware");
        }
        if self.network.is_some() {
            sections.push("network");
        }
        if self.storage.is_some() {
            sections.push("storage");
        }
        if self.software.is_some() {
            sections.push("software");
        }
        if self.services.is_some() {
            sections.push("services");
        }
        if self.users.is_some() {
            sections.push("users");
        }
        if self.configs.is_some() {
            sections.push("configs");
        }
        sections
    }
}

/// Collects a complete system profile based on configuration.
///
/// Runs all enabled collectors as specified in the configuration and
/// assembles the results into a complete profile.
///
/// # Arguments
///
/// * `config` - Agent configuration specifying which collectors to run
///
/// # Returns
///
/// A complete profile containing all collected sections.
///
/// # Errors
///
/// Returns an error if any enabled collector fails.
///
/// # Examples
///
/// ```ignore
/// use hydra_agent::config::AgentConfig;
/// use hydra_agent::collectors::collect_profile;
///
/// # async fn example() -> anyhow::Result<()> {
/// let config = AgentConfig::load(std::path::Path::new("/etc/hydra/agent.toml"))?;
/// let profile = collect_profile(&config).await?;
/// println!("Collected sections: {:?}", profile.sections());
/// # Ok(())
/// # }
/// ```
pub async fn collect_profile(config: &AgentConfig) -> Result<Profile> {
    let collectors: std::collections::HashSet<&str> =
        config.collection.collectors.iter().map(|s| s.as_str()).collect();
    let mut profile = Profile {
        node_id: config.node.node_id.clone(),
        version: String::new(),
        collected_at: Utc::now(),
        agent_version: env!("CARGO_PKG_VERSION").to_string(),
        agent_tier: config.node.tier.to_string(),
        collection_level: config.collection.level.clone(),
        hardware: None,
        network: None,
        storage: None,
        software: None,
        services: None,
        users: None,
        configs: None,
        metadata: std::collections::HashMap::new(),
    };

    if let Some(target) = detect_target() {
        profile
            .metadata
            .insert("agentTarget".to_string(), json!(target));
    }
    profile.metadata.insert(
        "scheduleIntervalSeconds".to_string(),
        json!(config.schedule.interval_seconds),
    );
    profile.metadata.insert(
        "scheduleEnabled".to_string(),
        json!(config.schedule.enabled),
    );

    if collectors.contains("hardware") {
        info!("Collecting hardware information...");
        profile.hardware = Some(HardwareCollector::collect()?);
    }

    if collectors.contains("network") {
        info!("Collecting network information...");
        profile.network = Some(NetworkCollector::collect()?);
    }

    if collectors.contains("storage") {
        info!("Collecting storage information...");
        profile.storage = Some(StorageCollector::collect(config.node.kind.as_deref())?);
    }

    if collectors.contains("software") {
        info!("Collecting software information...");
        profile.software = Some(SoftwareCollector::collect(config)?);
    }

    if collectors.contains("services") {
        info!("Collecting service information...");
        profile.services = Some(ServicesCollector::collect());
    }

    // Users are gated by the include_users flag rather than the collector list
    // so existing configs keep working; the section is collected whenever the
    // "software" or "users" collector is enabled and include_users is set.
    if config.collection.include_users
        && (collectors.contains("software") || collectors.contains("users"))
    {
        info!("Collecting user accounts and SSH keys...");
        profile.users = Some(UsersCollector::collect());
    }

    // Config-file tracking runs whenever the operator configured paths to track.
    if !config.collection.config_files.is_empty() {
        info!(
            count = config.collection.config_files.len(),
            "Hashing tracked configuration files..."
        );
        profile.configs = Some(ConfigsCollector::collect(&config.collection.config_files));
    }

    Ok(profile)
}

fn detect_target() -> Option<String> {
    let os = std::env::consts::OS;
    let arch = std::env::consts::ARCH;

    let target_os = match os {
        "linux" => "linux",
        "macos" => "darwin",
        "windows" => "windows",
        "freebsd" => "freebsd",
        _ => return None,
    };

    let target_arch = match arch {
        "x86_64" => "amd64",
        "aarch64" => "arm64",
        "arm" => "armv7",
        _ => return None,
    };

    Some(format!("{}-{}", target_os, target_arch))
}
