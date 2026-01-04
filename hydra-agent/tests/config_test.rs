//! Tests for configuration loading and parsing.

use hydra_agent::config::{AgentConfig, Credentials};
use tempfile::NamedTempFile;
use std::io::Write;

#[test]
fn test_load_valid_config() {
    let config_content = r#"
[api]
url = "http://localhost:8080"
credentials_file = "/etc/hydra/creds.json"
timeout_seconds = 60
retries = 5

[node]
node_id = "my-server-01"
class = "compute"
node_type = "physical"
kind = "bare-metal"
display_name = "My Server"
description = "Production server"
tags = ["prod", "web"]

[collection]
level = "deep"
collectors = ["hardware", "network", "storage", "software"]
include_packages = true
include_users = false
config_files = ["/etc/nginx/nginx.conf"]

[schedule]
enabled = true
interval_seconds = 3600
on_startup = true
"#;

    let mut temp_file = NamedTempFile::new().unwrap();
    temp_file.write_all(config_content.as_bytes()).unwrap();

    let config = AgentConfig::load(temp_file.path());
    assert!(config.is_ok(), "Config should load successfully");

    let config = config.unwrap();
    assert_eq!(config.api.url, "http://localhost:8080");
    assert_eq!(config.api.timeout_seconds, 60);
    assert_eq!(config.api.retries, 5);
    assert_eq!(config.node.node_id, "my-server-01");
    assert_eq!(config.node.class, "compute");
    assert_eq!(config.node.kind, Some("bare-metal".to_string()));
    assert_eq!(config.node.tags.len(), 2);
    assert_eq!(config.collection.level, "deep");
    assert_eq!(config.collection.collectors.len(), 4);
    assert!(config.collection.include_packages);
    assert!(!config.collection.include_users);
    assert!(config.schedule.enabled);
    assert_eq!(config.schedule.interval_seconds, 3600);
}

#[test]
fn test_load_minimal_config() {
    let config_content = r#"
[api]
url = "http://localhost:8080"

[node]
node_id = "minimal-node"
"#;

    let mut temp_file = NamedTempFile::new().unwrap();
    temp_file.write_all(config_content.as_bytes()).unwrap();

    let config = AgentConfig::load(temp_file.path());
    assert!(config.is_ok(), "Minimal config should load with defaults");

    let config = config.unwrap();
    assert_eq!(config.api.url, "http://localhost:8080");
    assert_eq!(config.node.node_id, "minimal-node");
    // Check defaults are applied
    assert_eq!(config.node.class, "compute");
    assert_eq!(config.node.node_type, "physical");
    assert!(config.collection.include_packages);
    assert!(config.schedule.enabled);
}

#[test]
fn test_invalid_config() {
    let config_content = "invalid = [toml";

    let mut temp_file = NamedTempFile::new().unwrap();
    temp_file.write_all(config_content.as_bytes()).unwrap();

    let config = AgentConfig::load(temp_file.path());
    assert!(config.is_err(), "Invalid config should fail to load");
}

#[test]
fn test_missing_required_fields() {
    let config_content = r#"
[api]
url = "http://localhost:8080"
# Missing [node] section with node_id
"#;

    let mut temp_file = NamedTempFile::new().unwrap();
    temp_file.write_all(config_content.as_bytes()).unwrap();

    let config = AgentConfig::load(temp_file.path());
    assert!(config.is_err(), "Config without required fields should fail");
}

#[test]
fn test_credentials_save_and_load() {
    let temp_file = NamedTempFile::new().unwrap();
    let path = temp_file.path().to_str().unwrap();

    let creds = Credentials {
        api_key: "test_api_key".to_string(),
        api_key_id: "test_key_id".to_string(),
        node_id: "test-node".to_string(),
        created_at: "2024-12-31T23:59:59Z".to_string(),
    };

    // Save credentials
    let save_result = creds.save(path);
    assert!(save_result.is_ok(), "Credentials should save successfully");

    // Load credentials
    let loaded = Credentials::load(path);
    assert!(loaded.is_ok(), "Credentials should load successfully");

    let loaded = loaded.unwrap();
    assert_eq!(loaded.api_key, "test_api_key");
    assert_eq!(loaded.api_key_id, "test_key_id");
    assert_eq!(loaded.node_id, "test-node");
    assert_eq!(loaded.created_at, "2024-12-31T23:59:59Z".to_string());
}

#[test]
fn test_credentials_missing_file() {
    let result = Credentials::load("/nonexistent/path/credentials.json");
    assert!(result.is_err(), "Loading missing credentials should fail");
}
