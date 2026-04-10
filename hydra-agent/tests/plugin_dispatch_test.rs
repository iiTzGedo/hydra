//! Integration tests for plugin command dispatch on the agent side.
//!
//! Verifies:
//! - Action prefix routing to the correct plugin handler
//! - Unknown plugin prefix error handling
//! - Malformed action format error handling
//! - PluginState config storage and retrieval
//! - Docker plugin argument construction
//! - Docker plugin missing required parameter handling

use serde_json::json;

use hydra_agent::executor::CommandResult;
use hydra_agent::plugins::{execute, PluginConfig, PluginState};

// =============================================================================
// Helpers
// =============================================================================

fn empty_state() -> PluginState {
    PluginState::new()
}

/// Assert that a CommandResult is an error containing the expected substring.
fn assert_error_contains(result: &CommandResult, expected: &str) {
    assert!(
        !result.success,
        "Expected error result but got success: {:?}",
        result
    );
    let error_msg = result.error.as_deref().unwrap_or("");
    assert!(
        error_msg.contains(expected),
        "Expected error containing '{}', got: '{}'",
        expected,
        error_msg
    );
}

// =============================================================================
// Test 1: Plugin dispatch routes to Docker
// =============================================================================

#[tokio::test]
async fn test_plugin_dispatch_routes_to_docker() {
    // docker::list-containers should route to the docker handler.
    // Since the actual docker CLI is not available in tests, it will return
    // an error from run_command, but the important thing is it does NOT return
    // "Unknown plugin" or "Invalid plugin action format" errors.
    let state = empty_state();
    let params = Some(json!({"all": true}));
    let result = execute("docker::list-containers", &params, 5, &state).await;

    // The result will fail (no docker binary in CI) but should NOT be
    // "Unknown plugin" or "Invalid plugin action format"
    if !result.success {
        let err = result.error.as_deref().unwrap_or("");
        assert!(
            !err.contains("Unknown plugin"),
            "Should route to docker, not return unknown plugin error"
        );
        assert!(
            !err.contains("Invalid plugin action format"),
            "Should parse docker::list-containers correctly"
        );
    }
}

// =============================================================================
// Test 2: Unknown plugin prefix returns error
// =============================================================================

#[tokio::test]
async fn test_unknown_plugin_prefix_returns_error() {
    let state = empty_state();
    let params: Option<serde_json::Value> = None;
    let result = execute("unknown::action", &params, 5, &state).await;

    assert_error_contains(&result, "Unknown plugin: 'unknown'");
}

// =============================================================================
// Test 3: Malformed action (no :: separator) returns error
// =============================================================================

#[tokio::test]
async fn test_malformed_action_no_separator() {
    let state = empty_state();
    let params: Option<serde_json::Value> = None;
    let result = execute("noprefix", &params, 5, &state).await;

    assert_error_contains(&result, "Invalid plugin action format");
    assert_error_contains(&result, "expected 'plugin::action'");
}

// =============================================================================
// Test 4: All six plugins route correctly
// =============================================================================

#[tokio::test]
async fn test_all_six_plugins_route_correctly() {
    let state = empty_state();
    let params: Option<serde_json::Value> = None;

    let prefixes = vec![
        ("docker", "list-containers"),
        ("proxmox", "list-vms"),
        ("ha", "list-entities"),
        ("prometheus", "targets"),
        ("ansible", "list-inventory"),
        ("terraform", "state-list"),
    ];

    for (prefix, action) in prefixes {
        let full_action = format!("{}::{}", prefix, action);
        let result = execute(&full_action, &params, 5, &state).await;

        // Each plugin should be routed correctly (no "Unknown plugin" error).
        // The command may fail due to missing binaries/config, but the dispatch
        // itself should be correct.
        if !result.success {
            let err = result.error.as_deref().unwrap_or("");
            assert!(
                !err.contains("Unknown plugin"),
                "Plugin '{}' should be recognized, got: {}",
                prefix,
                err
            );
            assert!(
                !err.contains("Invalid plugin action format"),
                "Action '{}' should parse correctly, got: {}",
                full_action,
                err
            );
        }
    }
}

// =============================================================================
// Test 5: PluginState config storage and retrieval
// =============================================================================

#[test]
fn test_plugin_state_receive_and_get_config() {
    let mut state = PluginState::new();

    // Initially empty
    assert!(state.get_config("plg::docker").is_none());

    // Receive a config
    let config = PluginConfig {
        plugin_id: "plg::docker".to_string(),
        config: json!({"socketPath": "/var/run/docker.sock"}),
        enabled: true,
    };
    state.receive_config(config);

    // Should be retrievable
    let retrieved = state.get_config("plg::docker").unwrap();
    assert_eq!(retrieved.plugin_id, "plg::docker");
    assert!(retrieved.enabled);
    assert_eq!(
        retrieved.config["socketPath"],
        "/var/run/docker.sock"
    );

    // Update replaces existing
    let updated = PluginConfig {
        plugin_id: "plg::docker".to_string(),
        config: json!({"socketPath": "/custom/docker.sock", "apiVersion": "1.43"}),
        enabled: false,
    };
    state.receive_config(updated);

    let retrieved = state.get_config("plg::docker").unwrap();
    assert!(!retrieved.enabled);
    assert_eq!(
        retrieved.config["socketPath"],
        "/custom/docker.sock"
    );
    assert_eq!(
        retrieved.config["apiVersion"],
        "1.43"
    );

    // Other plugins remain unaffected
    assert!(state.get_config("plg::proxmox").is_none());

    // Can store multiple plugins
    let proxmox_config = PluginConfig {
        plugin_id: "plg::proxmox".to_string(),
        config: json!({"host": "pve1.local"}),
        enabled: true,
    };
    state.receive_config(proxmox_config);

    assert!(state.get_config("plg::docker").is_some());
    assert!(state.get_config("plg::proxmox").is_some());
    assert_eq!(state.configs.len(), 2);
}

// =============================================================================
// Test 6: Docker list-containers args construction
// =============================================================================

#[tokio::test]
async fn test_docker_list_containers_args() {
    // With all=true (default), docker ps should include -a flag.
    // We can't inspect the exact args without mocking run_command,
    // but we verify the action routes correctly and processes parameters.
    let state = empty_state();

    // Test with explicit all=true
    let params_all = Some(json!({"all": true}));
    let result = execute("docker::list-containers", &params_all, 5, &state).await;
    // Should not be an unknown action error
    if !result.success {
        let err = result.error.as_deref().unwrap_or("");
        assert!(
            !err.contains("Unknown docker action"),
            "list-containers should be a known docker action"
        );
    }

    // Test with all=false
    let params_no_all = Some(json!({"all": false}));
    let result = execute("docker::list-containers", &params_no_all, 5, &state).await;
    if !result.success {
        let err = result.error.as_deref().unwrap_or("");
        assert!(
            !err.contains("Unknown docker action"),
            "list-containers should be a known docker action"
        );
    }
}

// =============================================================================
// Test 7: Docker missing required parameter
// =============================================================================

#[tokio::test]
async fn test_docker_missing_required_param() {
    let state = empty_state();

    // pull-image requires "image" parameter
    let params_empty: Option<serde_json::Value> = None;
    let result = execute("docker::pull-image", &params_empty, 5, &state).await;

    assert_error_contains(&result, "Missing required parameter: image");
}

// =============================================================================
// Additional edge case tests
// =============================================================================

#[tokio::test]
async fn test_docker_unknown_sub_action() {
    let state = empty_state();
    let params: Option<serde_json::Value> = None;
    let result = execute("docker::nonexistent-action", &params, 5, &state).await;

    assert_error_contains(&result, "Unknown docker action: 'nonexistent-action'");
}

#[tokio::test]
async fn test_proxmox_missing_vmid() {
    let state = empty_state();
    let params: Option<serde_json::Value> = None;
    let result = execute("proxmox::vm-status", &params, 5, &state).await;

    assert_error_contains(&result, "Missing required parameter: vmid");
}

#[tokio::test]
async fn test_ha_not_configured() {
    // Home Assistant requires plugin config. Without it, should error.
    let state = empty_state();
    let params: Option<serde_json::Value> = None;
    let result = execute("ha::list-entities", &params, 5, &state).await;

    assert_error_contains(&result, "not configured or disabled");
}

#[tokio::test]
async fn test_prometheus_not_configured() {
    // Prometheus requires plugin config. Without it, should error.
    let state = empty_state();
    let params: Option<serde_json::Value> = None;
    let result = execute("prometheus::targets", &params, 5, &state).await;

    assert_error_contains(&result, "not configured or disabled");
}

#[tokio::test]
async fn test_ansible_missing_playbook() {
    let state = empty_state();
    let params: Option<serde_json::Value> = None;
    let result = execute("ansible::run-playbook", &params, 5, &state).await;

    assert_error_contains(&result, "Missing required parameter: playbook");
}

#[tokio::test]
async fn test_terraform_unknown_sub_action() {
    let state = empty_state();
    let params: Option<serde_json::Value> = None;
    let result = execute("terraform::nonexistent", &params, 5, &state).await;

    assert_error_contains(&result, "Unknown terraform action: 'nonexistent'");
}

#[test]
fn test_empty_plugin_state() {
    let state = PluginState::new();
    assert!(state.configs.is_empty());
    assert!(state.get_config("plg::docker").is_none());
    assert!(state.get_config("").is_none());
    assert!(state.get_config("nonexistent").is_none());
}
