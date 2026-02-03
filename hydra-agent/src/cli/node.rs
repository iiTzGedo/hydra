//! Node command for managing node registration and status.
//!
//! Handles node registration with the Hydra API and displays node information.

use anyhow::{anyhow, Context, Result};
use clap::{Args, Subcommand};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tracing::{debug, info};

use crate::config::AgentConfig;
use crate::vault::{NodeRegistrationData, Vault};

/// Node command arguments
#[derive(Args, Debug)]
pub struct NodeArgs {
    /// Update node details (shorthand for 'update' subcommand)
    #[arg(short = 'u', long, value_name = "KEY=VALUE")]
    pub update: Option<String>,

    #[command(subcommand)]
    pub command: Option<NodeCommand>,
}

#[derive(Subcommand, Debug)]
pub enum NodeCommand {
    /// Register this node with the Hydra API
    #[command(alias = "r")]
    Register {
        /// Registration token (optional, uses agent credentials if not provided)
        #[arg(short, long)]
        token: Option<String>,

        /// Override node ID from config
        #[arg(long)]
        node_id: Option<String>,

        /// Node class (compute, networking, iot)
        #[arg(long)]
        class: Option<String>,

        /// Node type (physical, logical)
        #[arg(long)]
        node_type: Option<String>,

        /// Node kind (bare-metal, vm, lxc, docker, k8s-pod)
        #[arg(long)]
        kind: Option<String>,

        /// Display name for the node
        #[arg(long)]
        display_name: Option<String>,

        /// Tags for the node (comma-separated)
        #[arg(long)]
        tags: Option<String>,

        /// Force re-registration even if already registered
        #[arg(long)]
        force: bool,
    },

    /// Show node registration status
    Status,

    /// Unregister this node
    Unregister,

    /// Show node information from the API
    Info,

    /// Update node metadata
    Update {
        /// New display name
        #[arg(long)]
        display_name: Option<String>,

        /// New tags (comma-separated, replaces existing)
        #[arg(long)]
        tags: Option<String>,
    },
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct NodeRegisterRequest {
    node_id: String,
    #[serde(rename = "class")]
    class: String,
    #[serde(rename = "type")]
    node_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    kind: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    display_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tags: Option<Vec<String>>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
#[allow(dead_code)]
struct NodeRegisterResponse {
    node_id: String,
    api_key: String,
    api_key_id: String,
    status: String,
    registered_at: String,
    registered_by: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct NodeInfoResponse {
    node_id: String,
    class: String,
    #[serde(rename = "type")]
    node_type: String,
    kind: Option<String>,
    display_name: Option<String>,
    tags: Option<Vec<String>>,
    status: String,
    created_at: String,
    updated_at: String,
    last_seen_at: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct NodeUpdateRequest {
    #[serde(skip_serializing_if = "Option::is_none")]
    display_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tags: Option<Vec<String>>,
}

#[derive(Debug, Deserialize)]
struct ApiError {
    error: ApiErrorDetail,
}

#[derive(Debug, Deserialize)]
struct ApiErrorDetail {
    code: String,
    message: String,
}

/// Execute the node command
pub async fn execute(args: &NodeArgs, config: &AgentConfig, vault: &Vault) -> Result<()> {
    if let Some(update_value) = &args.update {
        if let Some((key, value)) = update_value.split_once('=') {
            return update_node_field(config, vault, key.trim(), value.trim()).await;
        } else {
            return Err(anyhow!("Invalid update format. Use: --update key=value"));
        }
    }

    match &args.command {
        Some(NodeCommand::Register {
            token,
            node_id,
            class,
            node_type,
            kind,
            display_name,
            tags,
            force,
        }) => {
            register_node(
                config,
                vault,
                token.as_deref(),
                node_id.as_deref(),
                class.as_deref(),
                node_type.as_deref(),
                kind.as_deref(),
                display_name.as_deref(),
                tags.as_deref(),
                *force,
            )
            .await
        }
        Some(NodeCommand::Status) => show_status(vault),
        Some(NodeCommand::Unregister) => unregister_node(vault),
        Some(NodeCommand::Info) => show_info(config, vault).await,
        Some(NodeCommand::Update { display_name, tags }) => {
            update_node(config, vault, display_name.as_deref(), tags.as_deref()).await
        }
        None => {
            show_status(vault)
        }
    }
}

/// Update a single node field (for --update / -u shorthand)
async fn update_node_field(config: &AgentConfig, vault: &Vault, key: &str, value: &str) -> Result<()> {
    match key {
        "display_name" | "displayName" => {
            update_node(config, vault, Some(value), None).await
        }
        "tags" => {
            update_node(config, vault, None, Some(value)).await
        }
        "kind" => {
            // Update kind via API - need to implement
            Err(anyhow!("Updating 'kind' is not yet supported via shorthand. Use config to update."))
        }
        _ => {
            Err(anyhow!("Unknown node field: '{}'. Valid fields: display_name, tags", key))
        }
    }
}

/// Register node with the API
#[allow(clippy::too_many_arguments)]
async fn register_node(
    config: &AgentConfig,
    vault: &Vault,
    token: Option<&str>,
    node_id: Option<&str>,
    class: Option<&str>,
    node_type: Option<&str>,
    kind: Option<&str>,
    display_name: Option<&str>,
    tags: Option<&str>,
    force: bool,
) -> Result<()> {
    let actual_node_id = node_id.unwrap_or(&config.node.node_id);

    if vault.has_node_registration() && !force {
        let reg = vault.load_node_registration()?.unwrap();

        // Reconcile: Check if API still has this node registered
        if let Some((header_name, header_value)) = vault.get_auth_header()? {
            match check_node_exists_in_api(config, &header_name, &header_value, &reg.node_id).await {
                Ok(true) => {
                    println!();
                    println!("Node '{}' is already registered.", reg.node_id);
                    println!("  Status: {}", reg.status);
                    println!("  Registered at: {}", reg.registered_at);
                    println!();
                    println!("Local and API state are synchronized.");
                    println!("Use --force to re-register if you need to update node details.");
                    return Ok(());
                }
                Ok(false) => {
                    // Node exists locally but not in API - clear local and re-register
                    info!("Local registration exists but node not found in API. Re-registering...");
                    vault.delete_node_registration()?;
                }
                Err(e) => {
                    // Couldn't check API - warn but don't fail
                    debug!("Could not verify node in API: {}", e);
                    return Err(anyhow!(
                        "Node '{}' is already registered locally. Use --force to re-register.\n  (API check failed: {})",
                        reg.node_id, e
                    ));
                }
            }
        } else {
            return Err(anyhow!(
                "Node '{}' is already registered. Use --force to re-register.",
                reg.node_id
            ));
        }
    }

    let actual_class = class.unwrap_or(&config.node.class);
    let actual_node_type = node_type.unwrap_or(&config.node.node_type);
    let actual_kind = kind.map(String::from).or_else(|| config.node.kind.clone());
    let actual_display_name = display_name
        .map(String::from)
        .or_else(|| config.node.display_name.clone());
    let actual_tags: Option<Vec<String>> = tags
        .map(|t| t.split(',').map(|s| s.trim().to_string()).collect())
        .or_else(|| {
            if config.node.tags.is_empty() {
                None
            } else {
                Some(config.node.tags.clone())
            }
        });

    info!("Registering node '{}' with Hydra API...", actual_node_id);

    let client = Client::builder()
        .timeout(Duration::from_secs(30))
        .build()
        .context("Failed to create HTTP client")?;

    let register_url = format!("{}/node/register", config.api.url);
    let request = NodeRegisterRequest {
        node_id: actual_node_id.to_string(),
        class: actual_class.to_string(),
        node_type: actual_node_type.to_string(),
        kind: actual_kind,
        display_name: actual_display_name,
        tags: actual_tags,
    };

    debug!("Sending node registration request to {}", register_url);

    let auth = vault.get_auth_header()?;

    let mut req_builder = client.post(&register_url).json(&request);

    if let Some(t) = token {
        req_builder = req_builder.header("X-Registration-Token", t);
    } else if let Some((header_name, header_value)) = auth {
        req_builder = req_builder.header(header_name, header_value);
    } else {
        return Err(anyhow!(
            "No authentication available. Run 'hydra-agent login' or provide --token"
        ));
    }

    let response = req_builder
        .send()
        .await
        .context("Failed to send registration request")?;

    let status_code = response.status();

    if !status_code.is_success() {
        // Handle specific error codes for idempotency
        if status_code == reqwest::StatusCode::CONFLICT {
            // Node already exists in API - try to reconcile
            info!("Node '{}' already exists in API. Syncing local state...", actual_node_id);
            if let Some((header_name, header_value)) = vault.get_auth_header()? {
                match fetch_and_save_node_registration(config, vault, &header_name, &header_value, actual_node_id).await {
                    Ok(_) => {
                        println!();
                        println!("✓ Node '{}' already registered in API.", actual_node_id);
                        println!("  Local state synchronized with API.");
                        println!();
                        println!("Run 'hydra-agent run' to start collecting profiles.");
                        return Ok(());
                    }
                    Err(e) => {
                        return Err(anyhow!(
                            "Node already exists in API but failed to sync local state: {}",
                            e
                        ));
                    }
                }
            }
        }

        let error: ApiError = response.json().await.unwrap_or_else(|_| ApiError {
            error: ApiErrorDetail {
                code: "UNKNOWN".to_string(),
                message: "Node registration failed".to_string(),
            },
        });
        return Err(anyhow!(
            "Node registration failed: {} - {}",
            error.error.code,
            error.error.message
        ));
    }

    let reg_response: NodeRegisterResponse = response
        .json()
        .await
        .context("Failed to parse registration response")?;

    let registration = NodeRegistrationData {
        node_id: reg_response.node_id.clone(),
        registered_at: reg_response.registered_at.clone(),
        registered_by: reg_response.registered_by.clone(),
        status: reg_response.status.clone(),
    };

    vault.save_node_registration(&registration)?;

    println!();
    println!("✓ Node registered successfully!");
    println!("  Node ID: {}", reg_response.node_id);
    println!("  Status: {}", reg_response.status);
    println!("  Registered by: {}", reg_response.registered_by);
    println!("  Registered at: {}", reg_response.registered_at);
    println!();
    println!("Run 'hydra-agent run' to start collecting profiles.");

    Ok(())
}

/// Check if a node exists in the API
async fn check_node_exists_in_api(
    config: &AgentConfig,
    header_name: &str,
    header_value: &str,
    node_id: &str,
) -> Result<bool> {
    let client = Client::builder()
        .timeout(Duration::from_secs(10))
        .build()?;

    let url = format!("{}/nodes/{}", config.api.url, node_id);
    let response = client
        .get(&url)
        .header(header_name, header_value)
        .send()
        .await?;

    Ok(response.status().is_success())
}

/// Fetch node info from API and save to vault
async fn fetch_and_save_node_registration(
    config: &AgentConfig,
    vault: &Vault,
    header_name: &str,
    header_value: &str,
    node_id: &str,
) -> Result<()> {
    let client = Client::builder()
        .timeout(Duration::from_secs(10))
        .build()?;

    let url = format!("{}/nodes/{}", config.api.url, node_id);
    let response = client
        .get(&url)
        .header(header_name, header_value)
        .send()
        .await?;

    if !response.status().is_success() {
        return Err(anyhow!("Failed to fetch node info from API"));
    }

    let info: NodeInfoResponse = response.json().await?;

    let registration = NodeRegistrationData {
        node_id: info.node_id,
        registered_at: info.created_at,
        registered_by: "synced".to_string(),
        status: info.status,
    };

    vault.save_node_registration(&registration)?;
    Ok(())
}

/// Show node registration status
fn show_status(vault: &Vault) -> Result<()> {
    println!();
    println!("Node Registration Status");
    println!("========================");

    match vault.load_node_registration()? {
        Some(reg) => {
            println!("  Status: Registered");
            println!("  Node ID: {}", reg.node_id);
            println!("  Registered by: {}", reg.registered_by);
            println!("  Registered at: {}", reg.registered_at);
            println!("  Node Status: {}", reg.status);
        }
        None => {
            println!("  Status: Not registered");
            println!();
            println!("Run 'hydra-agent node register' to register this node.");
        }
    }

    println!();
    Ok(())
}

/// Unregister node (local only, doesn't delete from API)
fn unregister_node(vault: &Vault) -> Result<()> {
    if vault.has_node_registration() {
        vault.delete_node_registration()?;
        println!("✓ Node registration cleared locally.");
        println!();
        println!("Note: The node record still exists in the Hydra API.");
        println!("Run 'hydra-agent node register' to re-register.");
    } else {
        println!("No node registration to clear.");
    }
    Ok(())
}

/// Show node info from API
async fn show_info(config: &AgentConfig, vault: &Vault) -> Result<()> {
    let reg = vault
        .load_node_registration()?
        .ok_or_else(|| anyhow!("Node is not registered. Run 'hydra-agent node register' first."))?;

    let client = Client::builder()
        .timeout(Duration::from_secs(30))
        .build()
        .context("Failed to create HTTP client")?;

    let info_url = format!("{}/nodes/{}", config.api.url, reg.node_id);

    let auth = vault
        .get_auth_header()?
        .ok_or_else(|| anyhow!("No authentication available. Run 'hydra-agent login' first."))?;

    let response = client
        .get(&info_url)
        .header(auth.0, auth.1)
        .send()
        .await
        .context("Failed to fetch node info")?;

    if !response.status().is_success() {
        let error: ApiError = response.json().await.unwrap_or_else(|_| ApiError {
            error: ApiErrorDetail {
                code: "UNKNOWN".to_string(),
                message: "Failed to fetch node info".to_string(),
            },
        });
        return Err(anyhow!(
            "Failed to fetch node info: {} - {}",
            error.error.code,
            error.error.message
        ));
    }

    let info: NodeInfoResponse = response
        .json()
        .await
        .context("Failed to parse node info response")?;

    println!();
    println!("Node Information");
    println!("================");
    println!("  Node ID: {}", info.node_id);
    println!("  Class: {}", info.class);
    println!("  Type: {}", info.node_type);
    if let Some(kind) = &info.kind {
        println!("  Kind: {}", kind);
    }
    if let Some(name) = &info.display_name {
        println!("  Display Name: {}", name);
    }
    if let Some(tags) = &info.tags {
        println!("  Tags: {}", tags.join(", "));
    }
    println!("  Status: {}", info.status);
    println!("  Created: {}", info.created_at);
    println!("  Updated: {}", info.updated_at);
    if let Some(last_seen) = &info.last_seen_at {
        println!("  Last Seen: {}", last_seen);
    }
    println!();

    Ok(())
}

/// Update node metadata
async fn update_node(
    config: &AgentConfig,
    vault: &Vault,
    display_name: Option<&str>,
    tags: Option<&str>,
) -> Result<()> {
    if display_name.is_none() && tags.is_none() {
        return Err(anyhow!("At least one of --display-name or --tags is required"));
    }

    let reg = vault
        .load_node_registration()?
        .ok_or_else(|| anyhow!("Node is not registered. Run 'hydra-agent node register' first."))?;

    let client = Client::builder()
        .timeout(Duration::from_secs(30))
        .build()
        .context("Failed to create HTTP client")?;

    let update_url = format!("{}/nodes/{}", config.api.url, reg.node_id);

    let auth = vault
        .get_auth_header()?
        .ok_or_else(|| anyhow!("No authentication available. Run 'hydra-agent login' first."))?;

    let request = NodeUpdateRequest {
        display_name: display_name.map(String::from),
        tags: tags.map(|t| t.split(',').map(|s| s.trim().to_string()).collect()),
    };

    let response = client
        .patch(&update_url)
        .header(auth.0, auth.1)
        .json(&request)
        .send()
        .await
        .context("Failed to send update request")?;

    if !response.status().is_success() {
        let error: ApiError = response.json().await.unwrap_or_else(|_| ApiError {
            error: ApiErrorDetail {
                code: "UNKNOWN".to_string(),
                message: "Failed to update node".to_string(),
            },
        });
        return Err(anyhow!(
            "Failed to update node: {} - {}",
            error.error.code,
            error.error.message
        ));
    }

    println!("✓ Node updated successfully!");
    if let Some(name) = display_name {
        println!("  Display Name: {}", name);
    }
    if let Some(t) = tags {
        println!("  Tags: {}", t);
    }

    Ok(())
}
