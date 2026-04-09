//! Shared application state for the embedded control server.

use std::sync::Arc;
use std::time::Instant;

use tokio::sync::RwLock;

use crate::api::ApiClient;
use crate::config::AgentConfig;
use crate::plugins::PluginState;
use crate::vault::Vault;

/// Shared state accessible by all server handlers.
#[derive(Clone)]
pub struct AppState {
    /// Agent configuration (wrapped in RwLock for runtime updates via /config endpoint)
    pub config: Arc<RwLock<AgentConfig>>,
    /// Path to the config file on disk (for /config endpoint writes)
    pub config_path: std::path::PathBuf,
    /// Server secret for authenticating incoming requests (loaded from vault at startup)
    pub server_secret: String,
    /// Server start time (for uptime calculation)
    pub start_time: Instant,
    /// API client for direct command execution paths that need API access.
    pub api_client: Option<Arc<ApiClient>>,
    /// Vault access for update execution and other credential-backed operations.
    pub vault: Option<Vault>,
    /// Shared plugin state for plugin configuration received from the API.
    pub plugin_state: Arc<RwLock<PluginState>>,
}
