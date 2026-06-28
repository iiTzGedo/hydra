//! Comprehensive tests for configuration loading and validation.
//!
//! Tests cover:
//! - Valid configuration loading
//! - Default value application
//! - Node ID validation (pattern matching)
//! - Tag validation
//! - Collection level validation
//! - Node class and type validation
//! - Collector validation
//! - Parent node ID validation
//! - Error cases and edge cases

use hydra_agent::config::{AgentConfig, AgentTier};
use std::io::Write;
use tempfile::NamedTempFile;

// =============================================================================
// Helper Functions
// =============================================================================

fn write_config(content: &str) -> NamedTempFile {
    let mut temp_file = NamedTempFile::new().expect("Failed to create temp file");
    temp_file
        .write_all(content.as_bytes())
        .expect("Failed to write config");
    temp_file
}

// =============================================================================
// Valid Configuration Tests
// =============================================================================

#[test]
fn test_load_valid_config() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"
timeout_seconds = 60
retries = 5

[node]
node_id = "my-server"
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

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path());
    assert!(config.is_ok(), "Config should load successfully");

    let config = config.unwrap();
    assert_eq!(config.api.url, "http://localhost:8080/api/v1");
    assert_eq!(config.api.timeout_seconds, 60);
    assert_eq!(config.api.retries, 5);
    assert_eq!(config.node.node_id, "my-server");
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
url = "http://localhost:8080/api/v1"

[node]
node_id = "minimal"
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path());
    assert!(config.is_ok(), "Minimal config should load with defaults");

    let config = config.unwrap();
    assert_eq!(config.api.url, "http://localhost:8080/api/v1");
    assert_eq!(config.node.node_id, "minimal");

    // Check defaults are applied
    assert_eq!(config.node.class, "compute");
    assert_eq!(config.node.node_type, "physical");
    assert!(config.collection.include_packages);
    assert!(config.schedule.enabled);
    assert_eq!(config.api.timeout_seconds, 30);
    assert_eq!(config.api.retries, 3);
    assert_eq!(config.collection.level, "neutral");
    assert_eq!(config.schedule.interval_seconds, 86400);
}

// =============================================================================
// Node ID Validation Tests
// =============================================================================

#[test]
fn test_valid_node_ids() {
    let valid_ids = vec![
        "server",
        "my-server",
        "my.server",
        "my_server",
        "proxmox-node1",
        "rack.server01",
        "web_server",
    ];

    for node_id in valid_ids {
        let config_content = format!(
            r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "{}"
"#,
            node_id
        );

        let temp_file = write_config(&config_content);
        let result = AgentConfig::load(temp_file.path());
        assert!(
            result.is_ok(),
            "Node ID '{}' should be valid, but got: {:?}",
            node_id,
            result.err()
        );
    }
}

#[test]
fn test_invalid_node_id_uppercase() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "MyServer"
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_err(), "Uppercase node ID should be invalid");

    let err = result.unwrap_err().to_string();
    assert!(err.contains("Invalid node_id"));
}

#[test]
fn test_invalid_node_id_starts_with_number() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "1server"
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(
        result.is_err(),
        "Node ID starting with number should be invalid"
    );
}

#[test]
fn test_invalid_node_id_spaces() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "my server"
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_err(), "Node ID with spaces should be invalid");
}

#[test]
fn test_invalid_node_id_special_chars() {
    let invalid_ids = vec![
        "server!",
        "server@home",
        "server#1",
        "server$",
        "server%",
        "server&",
        "server*",
    ];

    for node_id in invalid_ids {
        let config_content = format!(
            r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "{}"
"#,
            node_id
        );

        let temp_file = write_config(&config_content);
        let result = AgentConfig::load(temp_file.path());
        assert!(
            result.is_err(),
            "Node ID '{}' with special chars should be invalid",
            node_id
        );
    }
}

#[test]
fn test_invalid_node_id_too_many_segments() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "a.b.c.d"
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(
        result.is_err(),
        "Node ID with too many segments should be invalid"
    );
}

// =============================================================================
// Tag Validation Tests
// =============================================================================

#[test]
fn test_valid_tags() {
    let valid_tags = vec![
        "prod",
        "web",
        "database",
        "env:prod",
        "team_infra",
        "location:east",
    ];

    for tag in &valid_tags {
        let config_content = format!(
            r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
tags = ["{}"]
"#,
            tag
        );

        let temp_file = write_config(&config_content);
        let result = AgentConfig::load(temp_file.path());
        assert!(
            result.is_ok(),
            "Tag '{}' should be valid, but got: {:?}",
            tag,
            result.err()
        );
    }
}

#[test]
fn test_invalid_tag_uppercase() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
tags = ["Production"]
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_err(), "Uppercase tag should be invalid");
}

#[test]
fn test_invalid_tag_special_chars() {
    let invalid_tags = vec!["tag!", "tag@host", "tag#1", "tag$var"];

    for tag in invalid_tags {
        let config_content = format!(
            r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
tags = ["{}"]
"#,
            tag
        );

        let temp_file = write_config(&config_content);
        let result = AgentConfig::load(temp_file.path());
        assert!(
            result.is_err(),
            "Tag '{}' with special chars should be invalid",
            tag
        );
    }
}

#[test]
fn test_multiple_valid_tags() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
tags = ["prod", "web", "team:infra", "location_east"]
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_ok(), "Multiple valid tags should work");

    let config = result.unwrap();
    assert_eq!(config.node.tags.len(), 4);
}

#[test]
fn test_empty_tags() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
tags = []
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_ok(), "Empty tags should be valid");

    let config = result.unwrap();
    assert!(config.node.tags.is_empty());
}

// =============================================================================
// Collection Level Validation Tests
// =============================================================================

#[test]
fn test_valid_collection_levels() {
    let valid_levels = vec!["shallow", "neutral", "deep"];

    for level in valid_levels {
        let config_content = format!(
            r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"

[collection]
level = "{}"
"#,
            level
        );

        let temp_file = write_config(&config_content);
        let result = AgentConfig::load(temp_file.path());
        assert!(
            result.is_ok(),
            "Collection level '{}' should be valid",
            level
        );
    }
}

#[test]
fn test_invalid_collection_level() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"

[collection]
level = "maximum"
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_err(), "Invalid collection level should fail");

    let err = result.unwrap_err().to_string();
    assert!(err.contains("Invalid collection level"));
}

// =============================================================================
// Node Class Validation Tests
// =============================================================================

#[test]
fn test_valid_node_classes() {
    let valid_classes = vec!["compute", "networking", "iot"];

    for class in valid_classes {
        let config_content = format!(
            r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
class = "{}"
"#,
            class
        );

        let temp_file = write_config(&config_content);
        let result = AgentConfig::load(temp_file.path());
        assert!(result.is_ok(), "Node class '{}' should be valid", class);
    }
}

#[test]
fn test_invalid_node_class() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
class = "storage"
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_err(), "Invalid node class should fail");

    let err = result.unwrap_err().to_string();
    assert!(err.contains("Invalid node class"));
}

// =============================================================================
// Node Type Validation Tests
// =============================================================================

#[test]
fn test_valid_node_types() {
    let valid_types = vec!["physical", "logical"];

    for node_type in valid_types {
        let config_content = format!(
            r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
node_type = "{}"
"#,
            node_type
        );

        let temp_file = write_config(&config_content);
        let result = AgentConfig::load(temp_file.path());
        assert!(result.is_ok(), "Node type '{}' should be valid", node_type);
    }
}

#[test]
fn test_invalid_node_type() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
node_type = "virtual"
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_err(), "Invalid node type should fail");

    let err = result.unwrap_err().to_string();
    assert!(err.contains("Invalid node_type"));
}

// =============================================================================
// Collector Validation Tests
// =============================================================================

#[test]
fn test_valid_collectors() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"

[collection]
collectors = ["hardware", "network", "storage", "software"]
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_ok(), "All valid collectors should work");

    let config = result.unwrap();
    assert_eq!(config.collection.collectors.len(), 4);
}

#[test]
fn test_invalid_collector() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"

[collection]
collectors = ["hardware", "invalid_collector"]
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_err(), "Invalid collector should fail");

    let err = result.unwrap_err().to_string();
    assert!(err.contains("Invalid collector"));
}

#[test]
fn test_services_collector_is_accepted() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"

[collection]
collectors = ["hardware", "services", "users", "configs"]
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(
        result.is_ok(),
        "services/users/configs are valid collectors: {:?}",
        result.err()
    );
}

#[test]
fn test_unknown_collector_is_rejected() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"

[collection]
collectors = ["hardware", "bogus"]
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_err(), "unknown collector should be rejected");
    assert!(result.unwrap_err().to_string().contains("Invalid collector"));
}

#[test]
fn test_single_collector() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"

[collection]
collectors = ["hardware"]
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_ok(), "Single collector should work");

    let config = result.unwrap();
    assert_eq!(config.collection.collectors.len(), 1);
    assert_eq!(config.collection.collectors[0], "hardware");
}

#[test]
fn test_empty_collectors() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"

[collection]
collectors = []
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_ok(), "Empty collectors should work");

    let config = result.unwrap();
    assert!(config.collection.collectors.is_empty());
}

// =============================================================================
// Parent Node ID Validation Tests
// =============================================================================

#[test]
fn test_valid_parent_node_id() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "vm-web"
node_type = "logical"
parent_node_id = "proxmox-host"
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_ok(), "Valid parent_node_id should work");

    let config = result.unwrap();
    assert_eq!(config.node.parent_node_id, Some("proxmox-host".to_string()));
}

#[test]
fn test_invalid_parent_node_id() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "vm-web"
parent_node_id = "Invalid Parent"
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_err(), "Invalid parent_node_id should fail");

    let err = result.unwrap_err().to_string();
    assert!(err.contains("Invalid parent_node_id"));
}

#[test]
fn test_no_parent_node_id() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "standalone"
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_ok(), "No parent_node_id should work");

    let config = result.unwrap();
    assert!(config.node.parent_node_id.is_none());
}

// =============================================================================
// Error Cases
// =============================================================================

#[test]
fn test_invalid_toml_syntax() {
    let config_content = "invalid = [toml";

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_err(), "Invalid TOML should fail");
}

#[test]
fn test_missing_required_api_url() {
    let config_content = r#"
[api]
# Missing url

[node]
node_id = "testnode"
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_err(), "Missing API URL should fail");
}

#[test]
fn test_missing_node_section() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"
# Missing [node] section
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_err(), "Missing node section should fail");
}

#[test]
fn test_missing_node_id() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
# Missing node_id
class = "compute"
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_err(), "Missing node_id should fail");
}

#[test]
fn test_missing_config_file() {
    let result = AgentConfig::load(std::path::Path::new("/nonexistent/config.toml"));
    assert!(result.is_err(), "Loading missing file should fail");
}

#[test]
fn test_empty_config_file() {
    let config_content = "";

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_err(), "Empty config file should fail");
}

// =============================================================================
// Default Values Tests
// =============================================================================

#[test]
fn test_default_timeout() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert_eq!(config.api.timeout_seconds, 30);
}

#[test]
fn test_default_retries() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert_eq!(config.api.retries, 3);
}

#[test]
fn test_default_class() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert_eq!(config.node.class, "compute");
}

#[test]
fn test_default_node_type() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert_eq!(config.node.node_type, "physical");
}

#[test]
fn test_default_collection_level() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert_eq!(config.collection.level, "neutral");
}

#[test]
fn test_default_collectors() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();

    // Default collectors: hardware, network, storage, software, services
    assert_eq!(config.collection.collectors.len(), 5);
    assert!(config
        .collection
        .collectors
        .contains(&"services".to_string()));
    assert!(config
        .collection
        .collectors
        .contains(&"hardware".to_string()));
    assert!(config
        .collection
        .collectors
        .contains(&"network".to_string()));
    assert!(config
        .collection
        .collectors
        .contains(&"storage".to_string()));
    assert!(config
        .collection
        .collectors
        .contains(&"software".to_string()));
}

#[test]
fn test_default_schedule_interval() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert_eq!(config.schedule.interval_seconds, 86400); // 24 hours
}

#[test]
fn test_default_schedule_enabled() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert!(config.schedule.enabled);
}

#[test]
fn test_default_on_startup() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert!(config.schedule.on_startup);
}

#[test]
fn test_default_include_packages() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert!(config.collection.include_packages);
}

#[test]
fn test_default_include_users() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert!(config.collection.include_users);
}

// =============================================================================
// Override Default Values Tests
// =============================================================================

#[test]
fn test_override_schedule_enabled() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"

[schedule]
enabled = false
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert!(!config.schedule.enabled);
}

#[test]
fn test_override_include_packages() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"

[collection]
include_packages = false
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert!(!config.collection.include_packages);
}

// =============================================================================
// Edge Cases
// =============================================================================

#[test]
fn test_config_files_paths() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"

[collection]
config_files = [
    "/etc/nginx/nginx.conf",
    "/etc/mysql/my.cnf",
    "/home/user/.bashrc"
]
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert_eq!(config.collection.config_files.len(), 3);
    assert!(config
        .collection
        .config_files
        .contains(&"/etc/nginx/nginx.conf".to_string()));
}

#[test]
fn test_optional_fields_all_none() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();

    assert!(config.node.kind.is_none());
    assert!(config.node.display_name.is_none());
    assert!(config.node.description.is_none());
    assert!(config.node.parent_node_id.is_none());
}

#[test]
fn test_optional_fields_all_set() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
kind = "bare-metal"
display_name = "Test Server"
description = "A test server for unit tests"
parent_node_id = "rack-server"
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();

    assert_eq!(config.node.kind, Some("bare-metal".to_string()));
    assert_eq!(config.node.display_name, Some("Test Server".to_string()));
    assert_eq!(
        config.node.description,
        Some("A test server for unit tests".to_string())
    );
    assert_eq!(config.node.parent_node_id, Some("rack-server".to_string()));
}

#[test]
fn test_large_interval() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"

[schedule]
interval_seconds = 604800
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert_eq!(config.schedule.interval_seconds, 604800); // 1 week
}

#[test]
fn test_small_interval() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"

[schedule]
interval_seconds = 60
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert_eq!(config.schedule.interval_seconds, 60);
}

#[test]
fn test_api_url_with_trailing_slash() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1/"

[node]
node_id = "testnode"
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert_eq!(config.api.url, "http://localhost:8080/api/v1/");
}

#[test]
fn test_https_api_url() {
    let config_content = r#"
[api]
url = "https://api.hydra.example.com/api/v1"

[node]
node_id = "testnode"
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert_eq!(config.api.url, "https://api.hydra.example.com/api/v1");
}

#[test]
fn test_api_url_with_port() {
    let config_content = r#"
[api]
url = "http://192.168.1.100:3000/api/v1"

[node]
node_id = "testnode"
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert_eq!(config.api.url, "http://192.168.1.100:3000/api/v1");
}

// =============================================================================
// Agent Tier Validation Tests
// =============================================================================

#[test]
fn test_default_tier() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert_eq!(config.node.tier, AgentTier::Normal);
    assert_eq!(config.node.tier.to_string(), "normal");
}

#[test]
fn test_valid_tiers() {
    let tiers = vec![
        ("lite", AgentTier::Lite),
        ("normal", AgentTier::Normal),
        ("max", AgentTier::Max),
    ];

    for (tier_str, expected) in tiers {
        let config_content = format!(
            r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
tier = "{}"
"#,
            tier_str
        );

        let temp_file = write_config(&config_content);
        let result = AgentConfig::load(temp_file.path());
        assert!(
            result.is_ok(),
            "Tier '{}' should be valid, but got: {:?}",
            tier_str,
            result.err()
        );
        assert_eq!(result.unwrap().node.tier, expected);
    }
}

#[test]
fn test_invalid_tier() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
tier = "ultra"
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(
        result.is_err(),
        "Invalid tier 'ultra' should fail TOML parsing"
    );
}

#[test]
fn test_tier_in_full_config() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"
timeout_seconds = 60

[node]
node_id = "hypervisor-01"
class = "compute"
tier = "max"
node_type = "physical"
kind = "bare-metal"
display_name = "Hypervisor 01"
tags = ["infra", "hypervisor"]

[collection]
level = "deep"
collectors = ["hardware", "network", "storage", "software"]

[schedule]
enabled = true
interval_seconds = 3600
"#;

    let temp_file = write_config(config_content);
    let config = AgentConfig::load(temp_file.path()).unwrap();
    assert_eq!(config.node.tier, AgentTier::Max);
    assert_eq!(config.node.tier.to_string(), "max");
    assert_eq!(config.node.node_id, "hypervisor-01");
    assert_eq!(config.node.class, "compute");
}

#[test]
fn test_tier_display_trait() {
    assert_eq!(AgentTier::Lite.to_string(), "lite");
    assert_eq!(AgentTier::Normal.to_string(), "normal");
    assert_eq!(AgentTier::Max.to_string(), "max");
}

#[test]
fn test_server_enabled_requires_max_tier() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
tier = "normal"

[server]
enabled = true
bind_address = "0.0.0.0"
advertise_address = "192.168.1.10"
tls_enabled = false
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(result.is_err(), "server.enabled should require max tier");
    assert!(result
        .unwrap_err()
        .to_string()
        .contains("requires node.tier = \"max\""));
}

#[test]
fn test_server_enabled_requires_advertise_address() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
tier = "max"

[server]
enabled = true
bind_address = "0.0.0.0"
tls_enabled = false
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(
        result.is_err(),
        "server.enabled should require advertise_address"
    );
    assert!(result
        .unwrap_err()
        .to_string()
        .contains("server.advertise_address is required"));
}

#[test]
fn test_server_enabled_rejects_wildcard_advertise_address() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
tier = "max"

[server]
enabled = true
bind_address = "0.0.0.0"
advertise_address = "0.0.0.0"
tls_enabled = false
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(
        result.is_err(),
        "Wildcard advertise_address should be rejected"
    );
    assert!(result
        .unwrap_err()
        .to_string()
        .contains("Wildcard or unspecified addresses are not allowed"));
}

#[test]
fn test_server_enabled_accepts_hostname_advertise_address() {
    let config_content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
tier = "max"

[server]
enabled = true
bind_address = "0.0.0.0"
advertise_address = "agent.internal.example"
tls_enabled = false
"#;

    let temp_file = write_config(config_content);
    let result = AgentConfig::load(temp_file.path());
    assert!(
        result.is_ok(),
        "Hostname advertise_address should be accepted for reachable control endpoints"
    );
}
