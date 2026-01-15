//! Config command for managing agent configuration.
//!
//! Provides get/set/unset operations for agent configuration values.
//! Changes are applied to the TOML configuration file.
//! In live mode, node.* changes are automatically pushed to the API.

use anyhow::{anyhow, Context, Result};
use clap::{Args, Subcommand};
use reqwest::Client;
use serde::Serialize;
use std::collections::BTreeMap;
use std::path::PathBuf;
use std::time::Duration;
use toml_edit::{DocumentMut, Item, Value};
use tracing::{debug, info, warn};

use crate::vault::Vault;

#[derive(Clone, Copy)]
enum ConfigValueType {
    String,
    Bool,
    Integer,
    StringList,
}

fn config_value_type(section: &str, key: &str) -> Option<ConfigValueType> {
    match (section, key) {
        ("api", "url") => Some(ConfigValueType::String),
        ("api", "credentials_file") => Some(ConfigValueType::String),
        ("api", "timeout_seconds") => Some(ConfigValueType::Integer),
        ("api", "retries") => Some(ConfigValueType::Integer),
        ("node", "node_id") => Some(ConfigValueType::String),
        ("node", "class") => Some(ConfigValueType::String),
        ("node", "node_type") => Some(ConfigValueType::String),
        ("node", "kind") => Some(ConfigValueType::String),
        ("node", "display_name") => Some(ConfigValueType::String),
        ("node", "description") => Some(ConfigValueType::String),
        ("node", "tags") => Some(ConfigValueType::StringList),
        ("node", "parent_node_id") => Some(ConfigValueType::String),
        ("collection", "level") => Some(ConfigValueType::String),
        ("collection", "collectors") => Some(ConfigValueType::StringList),
        ("collection", "include_packages") => Some(ConfigValueType::Bool),
        ("collection", "include_users") => Some(ConfigValueType::Bool),
        ("collection", "config_files") => Some(ConfigValueType::StringList),
        ("schedule", "enabled") => Some(ConfigValueType::Bool),
        ("schedule", "interval_seconds") => Some(ConfigValueType::Integer),
        ("schedule", "on_startup") => Some(ConfigValueType::Bool),
        _ => None,
    }
}

fn parse_key(key: &str) -> Result<(String, String, ConfigValueType)> {
    let parts: Vec<&str> = key.split('.').collect();
    if parts.len() != 2 {
        return Err(anyhow!(
            "Invalid key format '{}'. Expected <section>.<key>",
            key
        ));
    }

    let section = parts[0];
    let field = parts[1];
    let value_type = config_value_type(section, field).ok_or_else(|| {
        anyhow!(
            "Unknown configuration key '{}'. Allowed sections: api, node, collection, schedule",
            key
        )
    })?;

    Ok((section.to_string(), field.to_string(), value_type))
}

fn parse_list_values(value: &str) -> Vec<String> {
    let trimmed = value.trim().trim_start_matches('[').trim_end_matches(']');
    trimmed
        .split(',')
        .map(|s| s.trim().trim_matches('"').to_string())
        .filter(|s| !s.is_empty())
        .collect()
}

fn backup_config(config_path: &PathBuf) -> Result<()> {
    if config_path.exists() {
        let backup_path = config_path.with_extension("toml.bak");
        std::fs::copy(config_path, &backup_path).with_context(|| {
            format!(
                "Failed to create backup file: {}",
                backup_path.display()
            )
        })?;
    }
    Ok(())
}

/// Config command arguments
#[derive(Args, Debug)]
pub struct ConfigArgs {
    #[command(subcommand)]
    pub command: ConfigCommand,
}

#[derive(Subcommand, Debug)]
pub enum ConfigCommand {
    /// Get a configuration value
    Get {
        /// Configuration key (e.g., "node.node_id", "api.url")
        key: String,
    },

    /// Set a configuration value
    Set {
        /// Configuration key (e.g., "node.node_id", "api.url")
        key: String,
        /// Value to set
        value: String,
    },

    /// Unset (remove) a configuration value
    Unset {
        /// Configuration key to remove
        key: String,
        /// Optional value to remove (for list entries)
        value: Option<String>,
    },

    /// List all configuration values
    List,

    /// Show the configuration file path
    Path,

    /// Initialize a new configuration file
    Init {
        /// Node ID for this agent
        #[arg(long)]
        node_id: String,

        /// API URL
        #[arg(long, default_value = "https://hydra.local/api/v1")]
        api_url: String,

        /// Node class (compute, networking, iot)
        #[arg(long, default_value = "compute")]
        class: String,

        /// Force overwrite existing config
        #[arg(long)]
        force: bool,
    },

    /// Validate configuration file
    Validate,
}

/// Context for config command execution
pub struct ConfigContext<'a> {
    pub config_path: &'a PathBuf,
    pub vault: Option<&'a Vault>,
    pub live_mode: bool,
}

/// Execute the config command
pub async fn execute(args: &ConfigArgs, ctx: &ConfigContext<'_>) -> Result<()> {
    match &args.command {
        ConfigCommand::Get { key } => get_value(ctx.config_path, key),
        ConfigCommand::Set { key, value } => set_value(ctx, key, value).await,
        ConfigCommand::Unset { key, value } => unset_value(ctx.config_path, key, value.as_deref()),
        ConfigCommand::List => list_values(ctx.config_path),
        ConfigCommand::Path => show_path(ctx.config_path),
        ConfigCommand::Init {
            node_id,
            api_url,
            class,
            force,
        } => init_config(ctx.config_path, node_id, api_url, class, *force),
        ConfigCommand::Validate => validate_config(ctx.config_path),
    }
}

/// Get a configuration value by key
fn get_value(config_path: &PathBuf, key: &str) -> Result<()> {
    let contents = std::fs::read_to_string(config_path)
        .with_context(|| format!("Failed to read config file: {}", config_path.display()))?;

    let doc = contents
        .parse::<DocumentMut>()
        .context("Failed to parse config file")?;

    let parts: Vec<&str> = key.split('.').collect();
    let value = get_nested_value(&doc, &parts);

    match value {
        Some(v) => {
            println!("{}", format_value(v));
            Ok(())
        }
        None => Err(anyhow!("Key '{}' not found in configuration", key)),
    }
}

/// Request body for node update API
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct NodeUpdateRequest {
    #[serde(skip_serializing_if = "Option::is_none")]
    display_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    tags: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    kind: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    description: Option<String>,
}

/// Set a configuration value
async fn set_value(ctx: &ConfigContext<'_>, key: &str, value: &str) -> Result<()> {
    let contents = std::fs::read_to_string(ctx.config_path)
        .with_context(|| format!("Failed to read config file: {}", ctx.config_path.display()))?;

    let mut doc = contents
        .parse::<DocumentMut>()
        .context("Failed to parse config file")?;

    let (section, field, value_type) = parse_key(key)?;
    let parts: Vec<&str> = key.split('.').collect();

    match value_type {
        ConfigValueType::String => {
            set_nested_value_item(&mut doc, &parts, Item::Value(Value::from(value)))?;
        }
        ConfigValueType::Bool => {
            let parsed = value.parse::<bool>().map_err(|_| anyhow!("Invalid boolean: {}", value))?;
            set_nested_value_item(&mut doc, &parts, Item::Value(Value::from(parsed)))?;
        }
        ConfigValueType::Integer => {
            let parsed = value.parse::<i64>().map_err(|_| anyhow!("Invalid integer: {}", value))?;
            set_nested_value_item(&mut doc, &parts, Item::Value(Value::from(parsed)))?;
        }
        ConfigValueType::StringList => {
            let values = parse_list_values(value);
            let mut array = if let Some(item) = get_nested_value(&doc, &parts) {
                item.as_array()
                    .cloned()
                    .unwrap_or_else(toml_edit::Array::new)
            } else {
                toml_edit::Array::new()
            };

            let mut existing: Vec<String> = array
                .iter()
                .filter_map(|v| v.as_str().map(|s| s.to_string()))
                .collect();

            for v in values {
                if !existing.contains(&v) {
                    existing.push(v);
                }
            }

            array.clear();
            for v in existing {
                array.push(v);
            }

            set_nested_value_item(&mut doc, &parts, Item::Value(Value::Array(array)))?;
        }
    }

    backup_config(ctx.config_path)?;
    std::fs::write(ctx.config_path, doc.to_string())
        .with_context(|| format!("Failed to write config file: {}", ctx.config_path.display()))?;

    info!("Set {} = {}", key, value);
    println!("✓ Set {} = {}", key, value);

    // In live mode, auto-push node.* changes to the API
    if section == "node" && ctx.live_mode {
        if let Err(e) = push_node_update_to_api(ctx, &field, value, &value_type).await {
            warn!("Failed to push node update to API: {}", e);
            println!("⚠ Config saved locally but API update failed: {}", e);
            println!("  Run 'hydra-agent node update' to sync manually.");
        } else {
            println!("✓ API updated with new node configuration.");
        }
    } else {
        println!("Note: Restart the hydra-agent service to apply changes.");
    }

    Ok(())
}

/// Push a node config change to the API
async fn push_node_update_to_api(
    ctx: &ConfigContext<'_>,
    field: &str,
    value: &str,
    value_type: &ConfigValueType,
) -> Result<()> {
    // Load config to get API URL and node_id
    use crate::config::AgentConfig;

    let config = AgentConfig::load(ctx.config_path)?;
    let vault = ctx.vault.ok_or_else(|| anyhow!("Vault not available for API call"))?;

    // Check if node is registered
    if !vault.has_node_registration() {
        debug!("Node not registered, skipping API update");
        return Ok(());
    }

    let node_reg = vault.load_node_registration()?.ok_or_else(|| anyhow!("Node registration data not found"))?;

    // Get auth header
    let auth = vault.get_auth_header()?.ok_or_else(|| anyhow!("No authentication available"))?;

    // Build update request based on changed field
    // Only certain fields can be updated via API: display_name, tags, kind, description
    let update_request = match field {
        "display_name" => NodeUpdateRequest {
            display_name: Some(value.to_string()),
            tags: None,
            kind: None,
            description: None,
        },
        "tags" => {
            let tags = match value_type {
                ConfigValueType::StringList => parse_list_values(value),
                _ => vec![value.to_string()],
            };
            NodeUpdateRequest {
                display_name: None,
                tags: Some(tags),
                kind: None,
                description: None,
            }
        }
        "kind" => NodeUpdateRequest {
            display_name: None,
            tags: None,
            kind: Some(value.to_string()),
            description: None,
        },
        "description" => NodeUpdateRequest {
            display_name: None,
            tags: None,
            kind: None,
            description: Some(value.to_string()),
        },
        _ => {
            // Fields like node_id, class, node_type cannot be updated via API
            debug!("Field '{}' cannot be updated via API, skipping", field);
            return Ok(());
        }
    };

    let client = Client::builder()
        .timeout(Duration::from_secs(30))
        .build()?;

    let update_url = format!("{}/nodes/{}", config.api.url, node_reg.node_id);
    debug!("Pushing node update to {}", update_url);

    let response = client
        .patch(&update_url)
        .header(auth.0, auth.1)
        .json(&update_request)
        .send()
        .await?;

    if !response.status().is_success() {
        let status = response.status();
        let error_text = response.text().await.unwrap_or_else(|_| "Unknown error".to_string());
        return Err(anyhow!("API returned {}: {}", status, error_text));
    }

    info!("Successfully pushed node.{} update to API", field);
    Ok(())
}

/// Unset (remove) a configuration value
fn unset_value(config_path: &PathBuf, key: &str, value: Option<&str>) -> Result<()> {
    let contents = std::fs::read_to_string(config_path)
        .with_context(|| format!("Failed to read config file: {}", config_path.display()))?;

    let mut doc = contents
        .parse::<DocumentMut>()
        .context("Failed to parse config file")?;

    let (_, _, value_type) = parse_key(key)?;
    let parts: Vec<&str> = key.split('.').collect();

    match value_type {
        ConfigValueType::String => {
            set_nested_value_item(&mut doc, &parts, Item::Value(Value::from("")))?;
        }
        ConfigValueType::Bool => {
            set_nested_value_item(&mut doc, &parts, Item::Value(Value::from(false)))?;
        }
        ConfigValueType::Integer => {
            set_nested_value_item(&mut doc, &parts, Item::Value(Value::from(0)))?;
        }
        ConfigValueType::StringList => {
            let mut array = if let Some(item) = get_nested_value(&doc, &parts) {
                item.as_array()
                    .cloned()
                    .unwrap_or_else(toml_edit::Array::new)
            } else {
                toml_edit::Array::new()
            };

            if let Some(val) = value {
                let remove_values = parse_list_values(val);
                let filtered: Vec<String> = array
                    .iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .filter(|v| !remove_values.contains(v))
                    .collect();
                array.clear();
                for v in filtered {
                    array.push(v);
                }
            } else {
                array.clear();
            }

            set_nested_value_item(&mut doc, &parts, Item::Value(Value::Array(array)))?;
        }
    }

    backup_config(config_path)?;
    std::fs::write(config_path, doc.to_string())
        .with_context(|| format!("Failed to write config file: {}", config_path.display()))?;

    info!("Unset {}", key);
    println!("✓ Removed {}", key);
    println!("Note: Restart the hydra-agent service to apply changes.");
    Ok(())
}

/// List all configuration values
fn list_values(config_path: &PathBuf) -> Result<()> {
    let contents = std::fs::read_to_string(config_path)
        .with_context(|| format!("Failed to read config file: {}", config_path.display()))?;

    let doc = contents
        .parse::<DocumentMut>()
        .context("Failed to parse config file")?;

    println!("Configuration: {}", config_path.display());
    println!();

    let mut values: BTreeMap<String, String> = BTreeMap::new();
    collect_values(&doc.as_table(), "", &mut values);

    for (key, value) in values {
        println!("  {} = {}", key, value);
    }

    Ok(())
}

/// Show configuration file path
fn show_path(config_path: &PathBuf) -> Result<()> {
    println!("{}", config_path.display());

    if config_path.exists() {
        println!("  Status: exists");
    } else {
        println!("  Status: not found");
    }

    Ok(())
}

/// Initialize a new configuration file
fn init_config(
    config_path: &PathBuf,
    node_id: &str,
    api_url: &str,
    class: &str,
    force: bool,
) -> Result<()> {
    if config_path.exists() && !force {
        return Err(anyhow!(
            "Config file already exists at {}. Use --force to overwrite.",
            config_path.display()
        ));
    }

    // Validate node class
    let valid_classes = ["compute", "networking", "iot"];
    if !valid_classes.contains(&class) {
        return Err(anyhow!(
            "Invalid node class '{}'. Must be one of: {}",
            class,
            valid_classes.join(", ")
        ));
    }

    let config = format!(
        r#"# Hydra Agent Configuration
# Generated by hydra-agent config init

[node]
node_id = "{node_id}"
class = "{class}"
node_type = "physical"
# kind = "bare-metal"
# display_name = "My Server"
# tags = ["production"]

[api]
url = "{api_url}"
timeout_seconds = 30
retries = 3

[collection]
level = "neutral"
include_packages = true
include_users = true

[schedule]
enabled = true
interval_seconds = 21600  # 6 hours
on_startup = true
"#
    );

    // Ensure parent directory exists
    if let Some(parent) = config_path.parent() {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("Failed to create directory: {}", parent.display()))?;
    }

    std::fs::write(config_path, config)
        .with_context(|| format!("Failed to write config file: {}", config_path.display()))?;

    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(config_path, std::fs::Permissions::from_mode(0o644))?;
    }

    info!("Created config file at {}", config_path.display());
    println!("✓ Created configuration file: {}", config_path.display());
    println!();
    println!("Next steps:");
    println!("  1. Review and customize the configuration");
    println!("  2. Run 'hydra-agent login' to authenticate");
    println!("  3. Run 'hydra-agent register' to create an agent account");

    Ok(())
}

/// Validate configuration file
fn validate_config(config_path: &PathBuf) -> Result<()> {
    use crate::config::AgentConfig;

    println!("Validating configuration: {}", config_path.display());
    println!();

    // Check file exists
    if !config_path.exists() {
        return Err(anyhow!(
            "Config file not found: {}",
            config_path.display()
        ));
    }

    // Try to parse as TOML
    let contents = std::fs::read_to_string(config_path)?;
    let _doc = contents
        .parse::<DocumentMut>()
        .context("Failed to parse as TOML")?;
    println!("  ✓ Valid TOML syntax");

    // Try to load as AgentConfig
    match AgentConfig::load(config_path) {
        Ok(config) => {
            println!("  ✓ Valid configuration structure");
            println!();
            println!("Configuration summary:");
            println!("  Node ID: {}", config.node.node_id);
            println!("  Class: {}", config.node.class);
            println!("  API URL: {}", config.api.url);
            println!();
            println!("✓ Configuration is valid");
        }
        Err(e) => {
            println!("  ✗ Invalid configuration structure");
            return Err(anyhow!("Configuration validation failed: {}", e));
        }
    }

    Ok(())
}

// Helper functions for nested value access

fn get_nested_value<'a>(doc: &'a DocumentMut, parts: &[&str]) -> Option<&'a Item> {
    let mut current: &Item = doc.as_item();

    for part in parts {
        current = current.as_table()?.get(*part)?;
    }

    Some(current)
}

fn set_nested_value_item(doc: &mut DocumentMut, parts: &[&str], item: Item) -> Result<()> {
    if parts.is_empty() {
        return Err(anyhow!("Empty key"));
    }

    // Navigate to parent and set the value
    let table = doc.as_table_mut();
    let last_idx = parts.len() - 1;

    let mut current = table;

    // Navigate to the parent table, creating intermediate tables as needed
    for &part in &parts[..last_idx] {
        if !current.contains_key(part) {
            current.insert(part, Item::Table(Default::default()));
        }
        current = current
            .get_mut(part)
            .and_then(|item| item.as_table_mut())
            .ok_or_else(|| anyhow!("Cannot create nested key '{}'", part))?;
    }

    // Set the value
    let key = parts[last_idx];
    current.insert(key, item);

    Ok(())
}

fn collect_values(table: &toml_edit::Table, prefix: &str, values: &mut BTreeMap<String, String>) {
    for (key, item) in table.iter() {
        let full_key = if prefix.is_empty() {
            key.to_string()
        } else {
            format!("{}.{}", prefix, key)
        };

        match item {
            Item::Table(t) => {
                collect_values(t, &full_key, values);
            }
            Item::Value(_) => {
                values.insert(full_key, format_value(item));
            }
            Item::ArrayOfTables(arr) => {
                for (i, t) in arr.iter().enumerate() {
                    let arr_key = format!("{}[{}]", full_key, i);
                    collect_values(t, &arr_key, values);
                }
            }
            Item::None => {}
        }
    }
}

fn format_value(item: &Item) -> String {
    match item {
        Item::Value(v) => match v {
            Value::String(s) => s.value().to_string(),
            Value::Integer(i) => i.value().to_string(),
            Value::Float(f) => f.value().to_string(),
            Value::Boolean(b) => b.value().to_string(),
            Value::Array(arr) => {
                let items: Vec<String> = arr.iter().map(|v| format_toml_value(v)).collect();
                format!("[{}]", items.join(", "))
            }
            Value::InlineTable(t) => {
                let items: Vec<String> = t
                    .iter()
                    .map(|(k, v)| format!("{} = {}", k, format_toml_value(v)))
                    .collect();
                format!("{{ {} }}", items.join(", "))
            }
            Value::Datetime(dt) => dt.to_string(),
        },
        Item::Table(_) => "[table]".to_string(),
        Item::ArrayOfTables(_) => "[[array]]".to_string(),
        Item::None => "".to_string(),
    }
}

fn format_toml_value(v: &Value) -> String {
    match v {
        Value::String(s) => format!("\"{}\"", s.value()),
        Value::Integer(i) => i.value().to_string(),
        Value::Float(f) => f.value().to_string(),
        Value::Boolean(b) => b.value().to_string(),
        Value::Array(arr) => {
            let items: Vec<String> = arr.iter().map(|v| format_toml_value(v)).collect();
            format!("[{}]", items.join(", "))
        }
        Value::InlineTable(t) => {
            let items: Vec<String> = t
                .iter()
                .map(|(k, v)| format!("{} = {}", k, format_toml_value(v)))
                .collect();
            format!("{{ {} }}", items.join(", "))
        }
        Value::Datetime(dt) => dt.to_string(),
    }
}
