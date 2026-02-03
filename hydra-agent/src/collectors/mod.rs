//! System profile collectors for infrastructure profiling.
//!
//! This module provides collectors for gathering system information:
//! - [`hardware`] - CPU, memory, and system identification
//! - [`network`] - Network interfaces and configuration
//! - [`software`] - Operating system, packages, and services
//! - [`storage`] - Disks, filesystems, and mounts

pub mod hardware;
pub mod network;
pub mod software;
pub mod storage;

use anyhow::Result;
use chrono::{DateTime, Utc};
use serde::Serialize;
use tracing::info;

use crate::config::AgentConfig;

pub use hardware::HardwareCollector;
pub use network::NetworkCollector;
pub use software::SoftwareCollector;
pub use storage::StorageCollector;

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
    let collectors = &config.collection.collectors;
    let mut profile = Profile {
        node_id: config.node.node_id.clone(),
        version: String::new(),
        collected_at: Utc::now(),
        agent_version: env!("CARGO_PKG_VERSION").to_string(),
        collection_level: config.collection.level.clone(),
        hardware: None,
        network: None,
        storage: None,
        software: None,
        metadata: std::collections::HashMap::new(),
    };

    if collectors.contains(&"hardware".to_string()) {
        info!("Collecting hardware information...");
        profile.hardware = Some(HardwareCollector::collect()?);
    }

    if collectors.contains(&"network".to_string()) {
        info!("Collecting network information...");
        profile.network = Some(NetworkCollector::collect()?);
    }

    if collectors.contains(&"storage".to_string()) {
        info!("Collecting storage information...");
        profile.storage = Some(StorageCollector::collect(config.node.kind.as_deref())?);
    }

    if collectors.contains(&"software".to_string()) {
        info!("Collecting software information...");
        profile.software = Some(SoftwareCollector::collect(config)?);
    }

    Ok(profile)
}
