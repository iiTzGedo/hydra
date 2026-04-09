//! Plugin detection for locally available infrastructure.
//!
//! Provides passive detection of plugin targets (Docker, Podman, etc.)
//! by checking for well-known sockets, files, and ports.

use serde::{Deserialize, Serialize};
use std::path::Path;

/// Result of a plugin detection probe.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DetectionResult {
    /// Plugin identifier this detection targets.
    pub plugin_id: String,
    /// Whether the target was detected as available.
    pub available: bool,
    /// Detection method used (e.g. "socket-check", "port-check", "file-check").
    pub method: String,
    /// Additional details about the detection (e.g. the path or port checked).
    pub details: Option<String>,
}

/// Check if a Unix socket exists at the given path.
pub fn check_socket(path: &str) -> bool {
    Path::new(path).exists()
}

/// Check if a file exists at the given path.
pub fn check_file(path: &str) -> bool {
    Path::new(path).exists()
}

/// Check if a TCP port is accepting connections on localhost.
pub async fn check_port(port: u16) -> bool {
    tokio::net::TcpStream::connect(format!("127.0.0.1:{}", port))
        .await
        .is_ok()
}

/// Run all built-in plugin detection probes.
///
/// Returns detection results for each known plugin target.
/// This is a passive, read-only operation with no side effects.
pub fn detect_all() -> Vec<DetectionResult> {
    let mut results = Vec::new();

    // Docker detection via Unix socket
    results.push(DetectionResult {
        plugin_id: "plg::docker".to_string(),
        available: check_socket("/var/run/docker.sock"),
        method: "socket-check".to_string(),
        details: Some("/var/run/docker.sock".to_string()),
    });

    // Podman detection via user socket
    let podman_socket = format!(
        "/run/user/{}/podman/podman.sock",
        std::env::var("UID").unwrap_or_else(|_| "1000".to_string())
    );
    results.push(DetectionResult {
        plugin_id: "plg::podman".to_string(),
        available: check_socket(&podman_socket),
        method: "socket-check".to_string(),
        details: Some(podman_socket),
    });

    results
}
