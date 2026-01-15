//! Agent configuration management.
//!
//! Configuration files are stored at platform-specific locations:
//! - Unix: `/etc/hydra/agent.toml`
//! - Windows: `C:\ProgramData\Hydra\agent.toml`

use anyhow::{anyhow, Context, Result};
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::path::Path;

use crate::platform::paths;

/// Agent configuration loaded from TOML file.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentConfig {
    /// API connection settings
    pub api: ApiConfig,

    /// Node identification
    pub node: NodeConfig,

    /// Collection settings
    #[serde(default)]
    pub collection: CollectionConfig,

    /// Schedule settings
    #[serde(default)]
    pub schedule: ScheduleConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiConfig {
    /// Base URL of the Hydra API
    pub url: String,

    /// Path to credentials file (contains access/refresh tokens)
    #[serde(default = "default_credentials_path")]
    pub credentials_file: String,

    /// Request timeout in seconds
    #[serde(default = "default_timeout")]
    pub timeout_seconds: u64,

    /// Number of retries for failed requests
    #[serde(default = "default_retries")]
    pub retries: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeConfig {
    /// Unique node identifier
    pub node_id: String,

    /// Node class (compute, networking, iot)
    #[serde(default = "default_class")]
    pub class: String,

    /// Node type (physical, logical)
    #[serde(default = "default_type")]
    pub node_type: String,

    /// Node kind (bare-metal, vm, lxc, docker, etc.)
    pub kind: Option<String>,

    /// Display name for the node
    pub display_name: Option<String>,

    /// Description
    pub description: Option<String>,

    /// Tags for the node
    #[serde(default)]
    pub tags: Vec<String>,

    /// Parent node ID (for VMs/containers)
    pub parent_node_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CollectionConfig {
    /// Collection level (shallow, neutral, deep)
    #[serde(default = "default_level")]
    pub level: String,

    /// Enabled collectors
    #[serde(default = "default_collectors")]
    pub collectors: Vec<String>,

    /// Include package list
    #[serde(default = "default_true")]
    pub include_packages: bool,

    /// Include user list
    #[serde(default = "default_true")]
    pub include_users: bool,

    /// Config files to track (paths)
    #[serde(default)]
    pub config_files: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScheduleConfig {
    /// Enable scheduled collection
    #[serde(default = "default_true")]
    pub enabled: bool,

    /// Collection interval in seconds
    #[serde(default = "default_interval")]
    pub interval_seconds: u64,

    /// Collect on startup
    #[serde(default = "default_true")]
    pub on_startup: bool,
}

// Default value functions
fn default_credentials_path() -> String {
    paths::default_credentials_file()
        .to_string_lossy()
        .to_string()
}

fn default_timeout() -> u64 {
    30
}

fn default_retries() -> u32 {
    3
}

fn default_class() -> String {
    "compute".to_string()
}

fn default_type() -> String {
    "physical".to_string()
}

fn default_level() -> String {
    "neutral".to_string()
}

fn default_collectors() -> Vec<String> {
    vec![
        "hardware".to_string(),
        "network".to_string(),
        "storage".to_string(),
        "software".to_string(),
        "services".to_string(),
    ]
}

fn default_true() -> bool {
    true
}

fn default_interval() -> u64 {
    86400 // 24 hours
}

impl Default for CollectionConfig {
    fn default() -> Self {
        Self {
            level: default_level(),
            collectors: default_collectors(),
            include_packages: true,
            include_users: true,
            config_files: vec![],
        }
    }
}

impl Default for ScheduleConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            interval_seconds: default_interval(),
            on_startup: true,
        }
    }
}

impl AgentConfig {
    /// Load configuration from a TOML file.
    pub fn load(path: &Path) -> Result<Self> {
        let contents = std::fs::read_to_string(path)
            .with_context(|| format!("Failed to read config file: {}", path.display()))?;

        let config: Self = toml::from_str(&contents)
            .with_context(|| format!("Failed to parse config file: {}", path.display()))?;

        config.validate()?;

        Ok(config)
    }

    fn validate(&self) -> Result<()> {
        let node_id_re = Regex::new(r"^[a-z]+([._-][a-z0-9]+){0,2}$")
            .context("Invalid node ID regex pattern")?;
        let tag_re = Regex::new(r"^[a-z]+[_:]?[a-z]+$")
            .context("Invalid tag regex pattern")?;

        if !node_id_re.is_match(&self.node.node_id) {
            return Err(anyhow!(
                "Invalid node_id '{}'. Must match ^[a-z]+([._-][a-z0-9]+){{0,2}}$",
                self.node.node_id
            ));
        }

        if let Some(parent_node_id) = &self.node.parent_node_id {
            if !node_id_re.is_match(parent_node_id) {
                return Err(anyhow!(
                    "Invalid parent_node_id '{}'. Must match ^[a-z]+([._-][a-z0-9]+){{0,2}}$",
                    parent_node_id
                ));
            }
        }

        for tag in &self.node.tags {
            if tag.len() > 64 || !tag_re.is_match(tag) {
                return Err(anyhow!(
                    "Invalid tag '{}'. Must match ^[a-z]+[_:]?[a-z]+$ and be <= 64 chars",
                    tag
                ));
            }
        }

        // Validate collection level
        const VALID_LEVELS: &[&str] = &["shallow", "neutral", "deep"];
        if !VALID_LEVELS.contains(&self.collection.level.as_str()) {
            return Err(anyhow!(
                "Invalid collection level '{}'. Must be one of: shallow, neutral, deep",
                self.collection.level
            ));
        }

        // Validate node class
        const VALID_CLASSES: &[&str] = &["compute", "networking", "iot"];
        if !VALID_CLASSES.contains(&self.node.class.as_str()) {
            return Err(anyhow!(
                "Invalid node class '{}'. Must be one of: compute, networking, iot",
                self.node.class
            ));
        }

        // Validate node type
        const VALID_TYPES: &[&str] = &["physical", "logical"];
        if !VALID_TYPES.contains(&self.node.node_type.as_str()) {
            return Err(anyhow!(
                "Invalid node_type '{}'. Must be one of: physical, logical",
                self.node.node_type
            ));
        }

        // Validate collectors if specified
        const VALID_COLLECTORS: &[&str] = &["hardware", "network", "storage", "software", "services"];
        for collector in &self.collection.collectors {
            if !VALID_COLLECTORS.contains(&collector.as_str()) {
                return Err(anyhow!(
                    "Invalid collector '{}'. Must be one of: hardware, network, storage, software, services",
                    collector
                ));
            }
        }

        Ok(())
    }
}

/// Credentials stored after registration.
/// Uses API key authentication instead of JWT tokens.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Credentials {
    /// API key for authentication (sent as X-API-Key header)
    pub api_key: String,
    /// API key ID for reference
    pub api_key_id: String,
    /// Node ID this key is associated with
    pub node_id: String,
    /// When the key was created
    pub created_at: String,
}

impl Credentials {
    /// Load credentials from a JSON file.
    pub fn load(path: &str) -> Result<Self> {
        let contents = std::fs::read_to_string(path)
            .with_context(|| format!("Failed to read credentials file: {}", path))?;

        let creds: Self = serde_json::from_str(&contents)
            .with_context(|| format!("Failed to parse credentials file: {}", path))?;

        Ok(creds)
    }

    /// Save credentials to a JSON file.
    pub fn save(&self, path: &str) -> Result<()> {
        let contents = serde_json::to_string_pretty(self)?;
        std::fs::write(path, contents)
            .with_context(|| format!("Failed to write credentials file: {}", path))?;
        Ok(())
    }
}
