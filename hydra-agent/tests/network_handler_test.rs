//! Tests for the network discovery execution handler.
//!
//! These tests verify request parsing, error handling, and response construction
//! for the network handler without requiring actual network access.

use std::io::Write;
use std::sync::Arc;

use hydra_agent::config::AgentConfig;
use hydra_agent::executor::network_handler;
use serde_json::json;
use tempfile::NamedTempFile;
use tokio::sync::RwLock;

fn make_config() -> Arc<RwLock<AgentConfig>> {
    let content = r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "test-node"
class = "compute"
node_type = "physical"

[collection]
level = "neutral"

[schedule]
enabled = false
"#;
    let mut temp = NamedTempFile::new().expect("create temp file");
    temp.write_all(content.as_bytes())
        .expect("write config");
    let config = AgentConfig::load(temp.path()).expect("load config");
    Arc::new(RwLock::new(config))
}

// =============================================================================
// Error Handling: Missing / Malformed Parameters
// =============================================================================

#[tokio::test]
async fn test_missing_parameters_returns_error() {
    let config = make_config();
    let result = network_handler::execute(&None, 10, config).await;
    assert!(!result.success);
    assert!(result.error.is_some());
    let err = result.error.unwrap();
    assert!(
        err.contains("requires"),
        "Error should mention requirements: {err}"
    );
}

#[tokio::test]
async fn test_non_object_parameters_returns_error() {
    let config = make_config();
    let params = Some(json!("not-an-object"));
    let result = network_handler::execute(&params, 10, config).await;
    assert!(!result.success);
    assert!(result.error.is_some());
}

#[tokio::test]
async fn test_missing_scan_id_returns_error() {
    let config = make_config();
    let params = Some(json!({
        "targets": ["192.168.1.0/24"]
    }));
    let result = network_handler::execute(&params, 10, config).await;
    assert!(!result.success);
    let err = result.error.unwrap();
    assert!(
        err.contains("scanId"),
        "Error should mention missing scanId: {err}"
    );
}

#[tokio::test]
async fn test_missing_targets_returns_error() {
    let config = make_config();
    let params = Some(json!({
        "scanId": "scan-1"
    }));
    let result = network_handler::execute(&params, 10, config).await;
    assert!(!result.success);
    let err = result.error.unwrap();
    assert!(
        err.contains("CIDR") || err.contains("target"),
        "Error should mention missing targets: {err}"
    );
}

// =============================================================================
// Error Handling: Invalid CIDR
// =============================================================================

#[tokio::test]
async fn test_invalid_cidr_address_returns_error() {
    let config = make_config();
    let params = Some(json!({
        "scanId": "scan-bad-cidr",
        "targets": ["not-a-cidr"]
    }));
    let result = network_handler::execute(&params, 5, config).await;
    assert!(!result.success);
    assert!(result.error.is_some());
}

#[tokio::test]
async fn test_cidr_prefix_too_broad_returns_error() {
    let config = make_config();
    // /8 is way too broad (<16 prefix check)
    let params = Some(json!({
        "scanId": "scan-broad",
        "targets": ["10.0.0.0/8"]
    }));
    let result = network_handler::execute(&params, 5, config).await;
    assert!(!result.success);
    let err = result.error.unwrap();
    assert!(
        err.contains("not allowed") || err.contains("prefix"),
        "Error should mention prefix restriction: {err}"
    );
}

#[tokio::test]
async fn test_cidr_prefix_above_32_returns_error() {
    let config = make_config();
    let params = Some(json!({
        "scanId": "scan-bad-prefix",
        "targets": ["192.168.1.0/33"]
    }));
    let result = network_handler::execute(&params, 5, config).await;
    assert!(!result.success);
}

// =============================================================================
// Valid Request with Unreachable Hosts (no open ports)
// =============================================================================

#[tokio::test]
async fn test_scan_unreachable_host_returns_success_with_no_results() {
    let config = make_config();
    // /32 = single host, RFC 5737 TEST-NET-2 (unreachable)
    let params = Some(json!({
        "scanId": "scan-unreachable",
        "targets": ["198.51.100.1/32"]
    }));
    let result = network_handler::execute(&params, 3, config).await;
    assert!(result.success);
    assert!(result.output.is_some());
    assert!(result.data.is_some());
    let data = result.data.unwrap();
    assert_eq!(data["scanId"], "scan-unreachable");
    assert_eq!(data["summary"]["hostsScanned"], 1);
    assert_eq!(data["summary"]["hostsAlive"], 0);
}

// =============================================================================
// targetSpecs format (object targets with networkId)
// =============================================================================

#[tokio::test]
async fn test_target_specs_format() {
    let config = make_config();
    let params = Some(json!({
        "scanId": "scan-specs",
        "targetSpecs": [
            {"subnet": "198.51.100.1/32", "networkId": "net-1"}
        ],
        "methods": ["tcp_port"],
        "portTier": "tier1",
    }));
    let result = network_handler::execute(&params, 3, config).await;
    assert!(result.success);
    let data = result.data.unwrap();
    assert_eq!(data["scanId"], "scan-specs");
}

// =============================================================================
// CommandResult::error helper
// =============================================================================

#[test]
fn test_command_result_error_helper() {
    let result = hydra_agent::executor::CommandResult::error("test error message");
    assert!(!result.success);
    assert!(result.output.is_none());
    assert!(result.exit_code.is_none());
    assert_eq!(result.error.as_deref(), Some("test error message"));
    assert!(result.data.is_none());
}

// =============================================================================
// Protocol Discovery Integration (mDNS + SSDP) — Wave 4
// =============================================================================

#[tokio::test]
async fn test_scan_with_iot_protocols_enabled_does_not_error() {
    // Enables multicast discovery; scans TEST-NET-2 so no real hosts reply.
    // The goal: confirm the orchestration runs end-to-end, the scan
    // succeeds, and the result structure is intact even when multicast
    // returns nothing (or fails to bind on minimal CI hosts).
    let config = make_config();
    let params = Some(json!({
        "scanId": "scan-iot",
        "targetSpecs": [
            {"subnet": "198.51.100.1/32", "networkId": "net-1"}
        ],
        "methods": ["tcp_port"],
        "portTier": "tier1",
        "includeIoTProtocols": true,
        "timeoutSeconds": 4,
    }));
    let result = network_handler::execute(&params, 5, config).await;
    assert!(result.success, "scan should succeed, got {:?}", result.error);
    let data = result.data.expect("scan should return data");
    assert_eq!(data["scanId"], "scan-iot");
    assert_eq!(data["summary"]["hostsAlive"], 0);
    // ``results`` is a list (may be empty); never missing.
    assert!(data.get("results").and_then(|v| v.as_array()).is_some());
}

#[tokio::test]
async fn test_scan_with_iot_protocols_disabled_skips_multicast() {
    // With includeIoTProtocols=false, the scan must run fast (no multicast
    // budget) and still produce a valid result envelope.
    let config = make_config();
    let params = Some(json!({
        "scanId": "scan-no-iot",
        "targetSpecs": [
            {"subnet": "198.51.100.1/32", "networkId": "net-1"}
        ],
        "methods": ["tcp_port"],
        "portTier": "tier1",
        "includeIoTProtocols": false,
    }));
    let start = std::time::Instant::now();
    let result = network_handler::execute(&params, 3, config).await;
    let elapsed = start.elapsed();
    assert!(result.success);
    // A 1-host scan with no multicast budget should complete in well under
    // the 5s multicast cap.
    assert!(
        elapsed.as_secs() < 4,
        "scan without IoT protocols took {:?}, expected < 4s",
        elapsed
    );
}
