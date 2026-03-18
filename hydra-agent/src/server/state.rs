//! Shared application state for the embedded control server.

use std::sync::Arc;
use std::time::Instant;

use tokio::sync::RwLock;

use crate::config::AgentConfig;

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
}
