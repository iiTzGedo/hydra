//! Request and response types for the embedded control server.

use serde::{Deserialize, Serialize};

// =============================================================================
// Health
// =============================================================================

/// Response from GET /health
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HealthResponse {
    pub status: String,
    pub node_id: String,
    pub tier: String,
    pub version: String,
    pub uptime_seconds: u64,
    pub capabilities: Vec<String>,
}

// =============================================================================
// Execute
// =============================================================================

/// Request body for POST /execute
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExecuteRequest {
    pub command_id: String,
    pub registry_id: String,
    pub target: ExecuteTarget,
    pub parameters: Option<serde_json::Value>,
    pub timeout_seconds: Option<u64>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExecuteTarget {
    pub node_id: String,
    pub service_id: Option<String>,
}

/// Response from POST /execute
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ExecuteResponse {
    pub command_id: String,
    pub status: String,
    pub exit_code: Option<i32>,
    pub stdout: Option<String>,
    pub stderr: Option<String>,
    pub duration_ms: Option<u64>,
}

// =============================================================================
// Probe
// =============================================================================

/// Request body for POST /probe
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProbeRequest {
    pub probe_type: String,
    pub targets: Vec<String>,
    pub options: Option<serde_json::Value>,
}

/// Response from POST /probe
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProbeResponse {
    pub probe_type: String,
    pub status: String,
    pub results: Vec<serde_json::Value>,
    pub duration_ms: u64,
}

// =============================================================================
// Config
// =============================================================================

/// Request body for POST /config
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConfigUpdateRequest {
    pub merge: serde_json::Value,
}

/// Response from POST /config
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ConfigUpdateResponse {
    pub status: String,
    pub updated_sections: Vec<String>,
    pub restart_required: bool,
}

// =============================================================================
// Update
// =============================================================================

/// Request body for POST /update
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateRequest {
    pub target_version: Option<String>,
    pub source: Option<String>,
}

/// Response from POST /update
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateResponse {
    pub status: String,
    pub current_version: String,
    pub target_version: Option<String>,
    pub message: String,
}

// =============================================================================
// Error
// =============================================================================

/// Standard error response for control server endpoints.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ErrorResponse {
    pub error: ErrorDetail,
}

/// Error detail within an ErrorResponse.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ErrorDetail {
    pub code: String,
    pub message: String,
}

impl ErrorResponse {
    pub fn new(code: &str, message: &str) -> Self {
        Self {
            error: ErrorDetail {
                code: code.to_string(),
                message: message.to_string(),
            },
        }
    }
}
