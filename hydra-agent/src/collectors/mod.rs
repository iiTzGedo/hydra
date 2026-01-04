//! System profile collectors.

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

/// Complete system profile.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Profile {
    pub node_id: String,
    pub collected_at: DateTime<Utc>,
    pub agent_version: String,
    pub collection_level: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hardware: Option<hardware::HardwareProfile>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub network: Option<network::NetworkProfile>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub storage: Option<storage::StorageProfile>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub software: Option<software::SoftwareProfile>,
    pub metadata: std::collections::HashMap<String, serde_json::Value>,
}

impl Profile {
    /// Get list of collected sections.
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

/// Collect a complete system profile.
pub async fn collect_profile(config: &AgentConfig) -> Result<Profile> {
    let collectors = &config.collection.collectors;
    let mut profile = Profile {
        node_id: config.node.node_id.clone(),
        collected_at: Utc::now(),
        agent_version: env!("CARGO_PKG_VERSION").to_string(),
        collection_level: config.collection.level.clone(),
        hardware: None,
        network: None,
        storage: None,
        software: None,
        metadata: std::collections::HashMap::new(),
    };

    // Collect hardware
    if collectors.contains(&"hardware".to_string()) {
        info!("Collecting hardware information...");
        profile.hardware = Some(HardwareCollector::collect()?);
    }

    // Collect network
    if collectors.contains(&"network".to_string()) {
        info!("Collecting network information...");
        profile.network = Some(NetworkCollector::collect()?);
    }

    // Collect storage
    if collectors.contains(&"storage".to_string()) {
        info!("Collecting storage information...");
        profile.storage = Some(StorageCollector::collect()?);
    }

    // Collect software
    if collectors.contains(&"software".to_string()) {
        info!("Collecting software information...");
        profile.software = Some(SoftwareCollector::collect(config)?);
    }

    Ok(profile)
}
