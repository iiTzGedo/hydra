//! Plugin system for the Hydra agent.
//!
//! Provides configuration storage, detection, and command execution dispatch
//! for plugin-contributed commands. Each plugin module handles its own
//! action routing and external system interaction.

pub mod ansible;
pub mod detection;
pub mod docker;
pub mod ha;
pub mod prometheus;
pub mod proxmox;
pub mod terraform;

use serde::{Deserialize, Serialize};
use serde_json::Value;
use tracing::warn;

use crate::executor::CommandResult;

/// Configuration for a single plugin delivered from the API.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PluginConfig {
    /// Plugin identifier (e.g. "plg::docker").
    pub plugin_id: String,
    /// Plugin-specific configuration map.
    pub config: Value,
    /// Whether this plugin is enabled on this node.
    pub enabled: bool,
}

/// In-memory state holding all plugin configurations received from the API.
#[derive(Debug, Clone, Default)]
pub struct PluginState {
    pub configs: Vec<PluginConfig>,
}

impl PluginState {
    /// Create a new empty plugin state.
    pub fn new() -> Self {
        Self::default()
    }

    /// Receive or update a plugin configuration.
    ///
    /// If a config for the same plugin_id already exists, it is replaced.
    pub fn receive_config(&mut self, config: PluginConfig) {
        self.configs.retain(|c| c.plugin_id != config.plugin_id);
        self.configs.push(config);
    }

    /// Look up the configuration for a specific plugin.
    pub fn get_config(&self, plugin_id: &str) -> Option<&PluginConfig> {
        self.configs.iter().find(|c| c.plugin_id == plugin_id)
    }
}

/// Execute a plugin-contributed command.
///
/// Dispatches to the appropriate plugin handler based on the action prefix.
/// Actions follow the format `{plugin}::{sub_action}` (e.g. `docker::list-containers`).
pub async fn execute(
    action: &str,
    parameters: &Option<Value>,
    timeout_secs: u64,
    plugin_state: &PluginState,
) -> CommandResult {
    // Split action into plugin prefix and sub-action
    let (prefix, sub_action) = match action.split_once("::") {
        Some((p, s)) => (p, s),
        None => {
            warn!(action = action, "Plugin action missing '::' separator");
            return CommandResult::error(&format!(
                "Invalid plugin action format '{}': expected 'plugin::action'",
                action
            ));
        }
    };

    match prefix {
        "docker" => docker::execute(sub_action, parameters, timeout_secs, plugin_state).await,
        "proxmox" => proxmox::execute(sub_action, parameters, timeout_secs, plugin_state).await,
        "ha" => ha::execute(sub_action, parameters, timeout_secs, plugin_state).await,
        "prometheus" => {
            prometheus::execute(sub_action, parameters, timeout_secs, plugin_state).await
        }
        "ansible" => ansible::execute(sub_action, parameters, timeout_secs, plugin_state).await,
        "terraform" => {
            terraform::execute(sub_action, parameters, timeout_secs, plugin_state).await
        }
        other => {
            warn!(plugin = other, action = action, "Unknown plugin prefix");
            CommandResult::error(&format!("Unknown plugin: '{}'", other))
        }
    }
}
