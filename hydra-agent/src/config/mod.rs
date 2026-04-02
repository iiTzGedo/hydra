//! Agent configuration management.
//!
//! Configuration files are stored at platform-specific locations:
//! - Unix: `/etc/hydra/agent.toml`
//! - Windows: `C:\ProgramData\Hydra\agent.toml`

use anyhow::{anyhow, Context, Result};
use regex::Regex;
use serde::{Deserialize, Serialize};
use std::path::Path;

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
    /// Embedded control server settings (max-tier only)
    #[serde(default)]
    pub server: ServerConfig,
}

/// API connection configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiConfig {
    /// Base URL of the Hydra API (e.g., "https://hydra.local/api/v1")
    pub url: String,
    /// Request timeout in seconds
    #[serde(default = "default_timeout")]
    pub timeout_seconds: u64,
    /// Number of retries for failed requests
    #[serde(default = "default_retries")]
    pub retries: u32,
}

/// Agent tier determining communication capabilities.
///
/// - `Lite`: Profile collection only (SBCs, low-resource nodes)
/// - `Normal`: Profile + poll-based command execution (general compute)
/// - `Max`: Profile + embedded HTTP server for sync execution + delegated scanning
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum AgentTier {
    Lite,
    Normal,
    Max,
}

impl Default for AgentTier {
    fn default() -> Self {
        AgentTier::Normal
    }
}

impl std::fmt::Display for AgentTier {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            AgentTier::Lite => write!(f, "lite"),
            AgentTier::Normal => write!(f, "normal"),
            AgentTier::Max => write!(f, "max"),
        }
    }
}

/// Node identification and classification configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeConfig {
    /// Unique node identifier matching pattern `^[a-z]+([._-][a-z0-9]+){0,2}$`
    pub node_id: String,
    /// Node class: "compute", "networking", or "iot"
    #[serde(default = "default_class")]
    pub class: String,
    /// Agent tier: lite, normal, or max
    #[serde(default)]
    pub tier: AgentTier,
    /// Node type: "physical" or "logical"
    #[serde(default = "default_type")]
    pub node_type: String,
    /// Node kind (e.g., "bare-metal", "vm", "lxc", "docker")
    pub kind: Option<String>,
    /// Human-readable display name
    pub display_name: Option<String>,
    /// Description text
    pub description: Option<String>,
    /// Tags for grouping and filtering
    #[serde(default)]
    pub tags: Vec<String>,
    /// Parent node ID for nested nodes (VMs, containers)
    pub parent_node_id: Option<String>,
}

/// Profile collection configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CollectionConfig {
    /// Collection depth: "shallow", "neutral", or "deep"
    #[serde(default = "default_level")]
    pub level: String,
    /// Enabled collectors (hardware, network, storage, software)
    #[serde(default = "default_collectors")]
    pub collectors: Vec<String>,
    /// Whether to include package list in profiles
    #[serde(default = "default_true")]
    pub include_packages: bool,
    /// Whether to include user list in profiles
    #[serde(default = "default_true")]
    pub include_users: bool,
    /// Configuration file paths to track changes
    #[serde(default)]
    pub config_files: Vec<String>,
}

/// Embedded HTTP control server configuration (max-tier only).
///
/// When enabled on a max-tier agent, the server accepts authenticated
/// requests from the Hydra API for synchronous command execution,
/// health checks, network probing, and remote configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerConfig {
    /// Whether the control server is enabled
    #[serde(default)]
    pub enabled: bool,
    /// Bind address for the server
    #[serde(default = "default_bind_address")]
    pub bind_address: String,
    /// Reachable address advertised to the API for direct control requests
    pub advertise_address: Option<String>,
    /// Port for the control server
    #[serde(default = "default_server_port")]
    pub port: u16,
    /// Enable TLS encryption (recommended for production)
    #[serde(default = "default_true")]
    pub tls_enabled: bool,
    /// Path to TLS certificate file (PEM format)
    pub tls_cert_file: Option<String>,
    /// Path to TLS private key file (PEM format)
    pub tls_key_file: Option<String>,
}

/// Scheduled collection configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScheduleConfig {
    /// Enable scheduled collection
    #[serde(default = "default_true")]
    pub enabled: bool,
    /// Collection interval in seconds
    #[serde(default = "default_interval")]
    pub interval_seconds: u64,
    /// Collect immediately on agent startup
    #[serde(default = "default_true")]
    pub on_startup: bool,
    /// Interval between command poll requests in seconds (normal/max tier only)
    #[serde(default = "default_poll_interval")]
    pub poll_interval_seconds: u64,
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
    ]
}

fn default_true() -> bool {
    true
}

fn default_interval() -> u64 {
    86400
}

fn default_poll_interval() -> u64 {
    30
}

fn default_bind_address() -> String {
    "127.0.0.1".to_string()
}

fn default_server_port() -> u16 {
    9100
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

impl Default for ServerConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            bind_address: default_bind_address(),
            advertise_address: None,
            port: default_server_port(),
            tls_enabled: true,
            tls_cert_file: None,
            tls_key_file: None,
        }
    }
}

impl Default for ScheduleConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            interval_seconds: default_interval(),
            on_startup: true,
            poll_interval_seconds: default_poll_interval(),
        }
    }
}

impl AgentConfig {
    /// Loads configuration from a TOML file.
    ///
    /// # Arguments
    ///
    /// * `path` - Path to the TOML configuration file
    ///
    /// # Returns
    ///
    /// The parsed and validated agent configuration.
    ///
    /// # Errors
    ///
    /// Returns an error if the file cannot be read, parsed, or validation fails.
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
        let tag_re = Regex::new(r"^[a-z]+[-_:]?[a-z]+$").context("Invalid tag regex pattern")?;

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
                    "Invalid tag '{}'. Must match ^[a-z]+[-_:]?[a-z]+$ and be <= 64 chars",
                    tag
                ));
            }
        }

        const VALID_LEVELS: &[&str] = &["shallow", "neutral", "deep"];
        if !VALID_LEVELS.contains(&self.collection.level.as_str()) {
            return Err(anyhow!(
                "Invalid collection level '{}'. Must be one of: shallow, neutral, deep",
                self.collection.level
            ));
        }

        const VALID_CLASSES: &[&str] = &["compute", "networking", "iot"];
        if !VALID_CLASSES.contains(&self.node.class.as_str()) {
            return Err(anyhow!(
                "Invalid node class '{}'. Must be one of: compute, networking, iot",
                self.node.class
            ));
        }

        const VALID_TYPES: &[&str] = &["physical", "logical"];
        if !VALID_TYPES.contains(&self.node.node_type.as_str()) {
            return Err(anyhow!(
                "Invalid node_type '{}'. Must be one of: physical, logical",
                self.node.node_type
            ));
        }

        const VALID_COLLECTORS: &[&str] = &["hardware", "network", "storage", "software"];
        for collector in &self.collection.collectors {
            if !VALID_COLLECTORS.contains(&collector.as_str()) {
                return Err(anyhow!(
                    "Invalid collector '{}'. Must be one of: hardware, network, storage, software",
                    collector
                ));
            }
        }

        // Server config validation
        if self.server.enabled {
            if self.node.tier != AgentTier::Max {
                return Err(anyhow!(
                    "server.enabled requires node.tier = \"max\". Current tier is '{}'.",
                    self.node.tier
                ));
            }

            let bind_address = self
                .server
                .bind_address
                .parse::<std::net::IpAddr>()
                .map_err(|_| {
                    anyhow!(
                        "Invalid server bind_address '{}'. Must be a valid IP address.",
                        self.server.bind_address
                    )
                })?;
            let _ = bind_address;

            let advertise_address = self.server.advertise_address.as_deref().ok_or_else(|| {
                anyhow!("server.advertise_address is required when the control server is enabled")
            })?;
            if advertise_address.trim().is_empty() {
                return Err(anyhow!(
                    "server.advertise_address must not be empty when the control server is enabled"
                ));
            }
            if let Ok(advertise_ip) = advertise_address.parse::<std::net::IpAddr>() {
                if advertise_ip.is_unspecified() {
                    return Err(anyhow!(
                        "Invalid server advertise_address '{}'. Wildcard or unspecified addresses are not allowed.",
                        advertise_address
                    ));
                }
            }

            if self.server.tls_enabled {
                let cert_file = self.server.tls_cert_file.as_deref().ok_or_else(|| {
                    anyhow!("server.tls_cert_file is required when TLS is enabled")
                })?;
                let key_file = self.server.tls_key_file.as_deref().ok_or_else(|| {
                    anyhow!("server.tls_key_file is required when TLS is enabled")
                })?;

                if !Path::new(cert_file).exists() {
                    return Err(anyhow!("TLS certificate file not found: {}", cert_file));
                }
                if !Path::new(key_file).exists() {
                    return Err(anyhow!("TLS key file not found: {}", key_file));
                }
            }
        }

        Ok(())
    }
}
