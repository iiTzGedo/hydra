//! Command execution engine.
//!
//! Dispatches commands to the appropriate handler based on category (type) and action.
//! Each handler is responsible for validating inputs and executing the command safely.
//!
//! The executor enforces timeout boundaries and prevents arbitrary command execution
//! by only routing to known handler functions.

pub mod agent_handler;
pub mod network_handler;
pub mod node_handler;
pub mod process;
pub mod service_handler;

use std::path::PathBuf;
use std::sync::Arc;
use std::time::Instant;

use tokio::sync::RwLock;
use tracing::{info, warn};

use crate::api::{ApiClient, PollCommand};
use crate::config::AgentConfig;
use crate::vault::Vault;

/// Result of a command execution.
#[derive(Debug, Clone)]
pub struct CommandResult {
    pub success: bool,
    pub output: Option<String>,
    pub exit_code: Option<i32>,
    pub error: Option<String>,
    pub data: Option<serde_json::Value>,
}

impl CommandResult {
    /// Create an error result with a message.
    pub fn error(message: &str) -> Self {
        Self {
            success: false,
            output: None,
            exit_code: None,
            error: Some(message.to_string()),
            data: None,
        }
    }
}

/// Command executor that dispatches commands to the appropriate handler.
pub struct CommandExecutor {
    config: Arc<RwLock<AgentConfig>>,
    start_time: Instant,
    /// API client for agent commands that need to call the API (collect-now, update).
    /// None when running in the direct /execute server context (no API client available).
    api_client: Option<Arc<ApiClient>>,
    /// Path to agent.toml for config-reload.
    /// None when running in the direct /execute server context.
    config_path: Option<PathBuf>,
    /// Vault access for commands that need stored credentials or secrets.
    vault: Option<Vault>,
}

impl CommandExecutor {
    /// Create a new command executor with full context (for poll-based execution).
    pub fn new(
        config: Arc<RwLock<AgentConfig>>,
        start_time: Instant,
        api_client: Option<Arc<ApiClient>>,
        config_path: Option<PathBuf>,
        vault: Option<Vault>,
    ) -> Self {
        Self {
            config,
            start_time,
            api_client,
            config_path,
            vault,
        }
    }

    /// Execute a command by dispatching to the appropriate handler.
    ///
    /// Routes based on `command_type` (category):
    /// - `"service"` → service_handler
    /// - `"node"` → node_handler
    /// - `"agent"` → agent_handler
    ///
    /// Unknown categories return an error result.
    pub async fn execute(&self, cmd: &PollCommand) -> CommandResult {
        let timeout_secs = cmd.timeout_seconds.max(1); // Minimum 1 second

        info!(
            command_id = %cmd.command_id,
            category = %cmd.command_type,
            action = %cmd.action,
            timeout_secs = timeout_secs,
            "Dispatching command"
        );

        let result = match cmd.command_type.as_str() {
            "service" => service_handler::execute(&cmd.action, &cmd.parameters, timeout_secs).await,
            "node" => node_handler::execute(&cmd.action, &cmd.parameters, timeout_secs).await,
            "agent" if cmd.action == "network-scan" => {
                network_handler::execute(
                    &cmd.parameters,
                    timeout_secs,
                    self.config.clone(),
                )
                .await
            }
            "agent" => {
                agent_handler::execute(
                    &cmd.action,
                    &cmd.parameters,
                    timeout_secs,
                    self.config.clone(),
                    self.start_time,
                    self.api_client.as_ref(),
                    self.config_path.as_deref(),
                    self.vault.as_ref(),
                )
                .await
            }
            other => {
                warn!(
                    command_id = %cmd.command_id,
                    category = other,
                    "Unknown command category"
                );
                CommandResult::error(&format!("Unknown command category: '{}'", other))
            }
        };

        if result.success {
            info!(
                command_id = %cmd.command_id,
                exit_code = ?result.exit_code,
                "Command completed successfully"
            );
        } else {
            warn!(
                command_id = %cmd.command_id,
                error = ?result.error,
                exit_code = ?result.exit_code,
                "Command failed"
            );
        }

        result
    }
}
