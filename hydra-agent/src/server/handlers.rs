//! HTTP handler functions for all control server endpoints.

use axum::{extract::State, http::StatusCode, response::IntoResponse, Json};
use std::io::Write;
use std::time::Instant;
use tempfile::NamedTempFile;
use tracing::info;

use crate::api::PollCommand;
use crate::api::PollCommandTarget;
use crate::executor::agent_handler;
use crate::executor::CommandExecutor;

use super::models::*;
use super::state::AppState;

/// Serialize a value to JSON, returning a 500 error response on failure.
fn json_response<T: serde::Serialize>(
    status: StatusCode,
    value: &T,
) -> (StatusCode, Json<serde_json::Value>) {
    match serde_json::to_value(value) {
        Ok(v) => (status, Json(v)),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(serde_json::json!({
                "error": { "code": "SERIALIZATION_ERROR", "message": e.to_string() }
            })),
        ),
    }
}

// =============================================================================
// GET /health — Full implementation
// =============================================================================

/// Returns agent health and status information.
pub async fn health(State(state): State<AppState>) -> Json<HealthResponse> {
    let config = state.config.read().await;
    let uptime = state.start_time.elapsed().as_secs();

    Json(HealthResponse {
        status: "ok".to_string(),
        node_id: config.node.node_id.clone(),
        tier: config.node.tier.to_string(),
        version: env!("CARGO_PKG_VERSION").to_string(),
        uptime_seconds: uptime,
        capabilities: vec![
            "profile".to_string(),
            "poll-execute".to_string(),
            "direct-execute".to_string(),
            "probe".to_string(),
            "config".to_string(),
            "update".to_string(),
        ],
    })
}

// =============================================================================
// POST /execute — Full implementation
// =============================================================================

/// Accepts a command execution request for synchronous direct execution on max-tier agents.
///
/// Converts the request into a PollCommand, dispatches via the executor engine,
/// and returns the result inline.
pub async fn execute(
    State(state): State<AppState>,
    Json(request): Json<ExecuteRequest>,
) -> impl IntoResponse {
    // Derive category and action from the registry_id (e.g., "reg::service::restart")
    let parts: Vec<&str> = request.registry_id.split("::").collect();
    let (category, action) = if parts.len() == 3 {
        (parts[1].to_string(), parts[2].to_string())
    } else {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({
                "commandId": request.command_id,
                "status": "failed",
                "error": format!("Invalid registryId format: '{}'", request.registry_id),
            })),
        );
    };

    let timeout_secs = request.timeout_seconds.unwrap_or(60);

    // Build a PollCommand from the ExecuteRequest
    let poll_cmd = PollCommand {
        command_id: request.command_id.clone(),
        registry_id: Some(request.registry_id.clone()),
        command_type: category,
        action,
        target: PollCommandTarget {
            node_id: request.target.node_id,
            service_id: request.target.service_id,
        },
        parameters: request.parameters,
        timeout_seconds: timeout_secs,
    };

    let start = Instant::now();
    let executor = CommandExecutor::new(
        state.config.clone(),
        state.start_time,
        state.api_client.clone(),
        Some(state.config_path.clone()),
        state.vault.clone(),
        state.plugin_state.clone(),
    );
    let result = executor.execute(&poll_cmd).await;
    let duration_ms = start.elapsed().as_millis() as u64;

    let status_str = if result.success {
        "completed"
    } else {
        "failed"
    };

    let response = ExecuteResponse {
        command_id: request.command_id,
        status: status_str.to_string(),
        result: ExecuteResultData {
            success: result.success,
            output: result.output,
            exit_code: result.exit_code,
            error: result.error,
            data: result.data,
        },
        duration_ms,
    };

    json_response(StatusCode::OK, &response)
}

// =============================================================================
// POST /probe — Full implementation
// =============================================================================

/// Accepts a network probe request and performs bounded subnet probing.
pub async fn probe(Json(request): Json<ProbeRequest>) -> impl IntoResponse {
    match agent_handler::execute_probe_request(
        &request.probe_type,
        request.targets,
        request.options,
    )
    .await
    {
        Ok(result) => {
            let response = ProbeResponse {
                probe_type: request.probe_type,
                status: "completed".to_string(),
                results: result
                    .hosts
                    .into_iter()
                    .map(|host| serde_json::to_value(host).unwrap_or(serde_json::Value::Null))
                    .collect(),
                duration_ms: result.duration_ms,
            };
            json_response(StatusCode::OK, &response)
        }
        Err(error) => json_response(
            StatusCode::BAD_REQUEST,
            &ErrorResponse::new("PROBE_VALIDATION_ERROR", &error),
        ),
    }
}

// =============================================================================
// POST /config — Full implementation (TOML merge)
// =============================================================================

/// Updates agent configuration by merging provided sections into the existing config.
pub async fn config_update(
    State(state): State<AppState>,
    Json(request): Json<ConfigUpdateRequest>,
) -> Result<Json<ConfigUpdateResponse>, impl IntoResponse> {
    use std::fs;

    // Read the current config file as raw TOML for surgical merge
    let config_contents = match fs::read_to_string(&state.config_path) {
        Ok(c) => c,
        Err(e) => {
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse::new(
                    "CONFIG_READ_ERROR",
                    &format!("Failed to read config file: {}", e),
                )),
            ));
        }
    };

    let mut doc = match config_contents.parse::<toml_edit::DocumentMut>() {
        Ok(d) => d,
        Err(e) => {
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse::new(
                    "CONFIG_PARSE_ERROR",
                    &format!("Failed to parse config: {}", e),
                )),
            ));
        }
    };

    // Convert the merge payload (JSON) to TOML items and merge
    let merge_obj = match request.merge.as_object() {
        Some(obj) => obj,
        None => {
            return Err((
                StatusCode::BAD_REQUEST,
                Json(ErrorResponse::new(
                    "INVALID_MERGE",
                    "merge field must be a JSON object with TOML section keys",
                )),
            ));
        }
    };

    let mut updated_sections = Vec::new();

    for (section_key, section_value) in merge_obj {
        // Convert the JSON value to a TOML string, then parse as TOML
        let toml_str = match serde_json::to_string(section_value) {
            Ok(s) => s,
            Err(e) => {
                return Err((
                    StatusCode::BAD_REQUEST,
                    Json(ErrorResponse::new(
                        "INVALID_SECTION",
                        &format!("Failed to serialize section '{}': {}", section_key, e),
                    )),
                ));
            }
        };

        // For nested objects, we need to convert JSON to TOML value format
        if let Some(obj) = section_value.as_object() {
            let table = doc
                .entry(section_key)
                .or_insert(toml_edit::Item::Table(toml_edit::Table::new()));
            if let Some(table) = table.as_table_mut() {
                for (k, v) in obj {
                    let toml_value = json_to_toml_value(v);
                    table[k.as_str()] = toml_value;
                }
            }
            updated_sections.push(section_key.clone());
        } else {
            return Err((
                StatusCode::BAD_REQUEST,
                Json(ErrorResponse::new(
                    "INVALID_SECTION",
                    &format!(
                        "Section '{}' must be an object, got: {}",
                        section_key, toml_str
                    ),
                )),
            ));
        }
    }

    let config_dir = match state.config_path.parent() {
        Some(dir) => dir,
        None => {
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse::new(
                    "CONFIG_PATH_ERROR",
                    "Config path has no parent directory",
                )),
            ));
        }
    };

    let new_contents = doc.to_string();
    let mut temp_file = match NamedTempFile::new_in(config_dir) {
        Ok(file) => file,
        Err(e) => {
            return Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ErrorResponse::new(
                    "CONFIG_TEMPFILE_ERROR",
                    &format!("Failed to create temp config file: {}", e),
                )),
            ));
        }
    };

    if let Err(e) = temp_file.write_all(new_contents.as_bytes()) {
        return Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse::new(
                "CONFIG_WRITE_ERROR",
                &format!("Failed to write config: {}", e),
            )),
        ));
    }
    if let Err(e) = temp_file.flush() {
        return Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse::new(
                "CONFIG_WRITE_ERROR",
                &format!("Failed to flush temp config: {}", e),
            )),
        ));
    }

    // Validate the updated config before replacing the live file.
    let new_config = match crate::config::AgentConfig::load(temp_file.path()) {
        Ok(config) => config,
        Err(e) => {
            return Err((
                StatusCode::BAD_REQUEST,
                Json(ErrorResponse::new(
                    "CONFIG_VALIDATION_ERROR",
                    &format!("Config update is invalid: {}", e),
                )),
            ));
        }
    };

    if let Err(e) = temp_file.persist(&state.config_path) {
        return Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ErrorResponse::new(
                "CONFIG_WRITE_ERROR",
                &format!("Failed to replace config file: {}", e.error),
            )),
        ));
    }

    let mut config = state.config.write().await;
    *config = new_config;
    info!(sections = ?updated_sections, "Configuration updated via /config endpoint");

    Ok(Json(ConfigUpdateResponse {
        status: "updated".to_string(),
        updated_sections,
        restart_required: true,
    }))
}

/// Convert a serde_json::Value to a toml_edit::Item.
fn json_to_toml_value(value: &serde_json::Value) -> toml_edit::Item {
    match value {
        serde_json::Value::String(s) => toml_edit::value(s.as_str()),
        serde_json::Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                toml_edit::value(i)
            } else if let Some(f) = n.as_f64() {
                toml_edit::value(f)
            } else {
                toml_edit::value(n.to_string().as_str())
            }
        }
        serde_json::Value::Bool(b) => toml_edit::value(*b),
        serde_json::Value::Array(arr) => {
            let mut toml_arr = toml_edit::Array::new();
            for item in arr {
                match item {
                    serde_json::Value::String(s) => {
                        toml_arr.push(s.as_str());
                    }
                    serde_json::Value::Number(n) => {
                        if let Some(i) = n.as_i64() {
                            toml_arr.push(i);
                        } else if let Some(f) = n.as_f64() {
                            toml_arr.push(f);
                        }
                    }
                    serde_json::Value::Bool(b) => {
                        toml_arr.push(*b);
                    }
                    _ => {}
                }
            }
            toml_edit::value(toml_arr)
        }
        serde_json::Value::Object(_) => {
            // Nested objects become inline tables
            let mut table = toml_edit::InlineTable::new();
            if let Some(obj) = value.as_object() {
                for (k, v) in obj {
                    if let Ok(val) = json_to_toml_value(v).into_value() {
                        table.insert(k, val);
                    }
                }
            }
            toml_edit::value(table)
        }
        serde_json::Value::Null => toml_edit::value(""),
    }
}

// =============================================================================
// POST /update — Full implementation (triggers agent upgrade)
// =============================================================================

/// Triggers an agent self-update. The response is sent before the binary swap begins.
pub async fn update(
    State(state): State<AppState>,
    Json(request): Json<UpdateRequest>,
) -> impl IntoResponse {
    let Some(vault) = state.vault.clone() else {
        return json_response(
            StatusCode::INTERNAL_SERVER_ERROR,
            &ErrorResponse::new(
                "VAULT_UNAVAILABLE",
                "Agent update requires vault access on the control server",
            ),
        );
    };

    let config = state.config.read().await.clone();
    match crate::cli::upgrade::schedule_upgrade(
        config,
        vault,
        request.target_version.clone(),
        request.source.clone(),
    )
    .await
    {
        Ok(accepted) => json_response(
            StatusCode::ACCEPTED,
            &UpdateResponse {
                status: "accepted".to_string(),
                current_version: accepted.current_version,
                target_version: accepted.target_version,
                message: accepted.message,
            },
        ),
        Err(error) => json_response(
            StatusCode::CONFLICT,
            &ErrorResponse::new(
                "UPDATE_REJECTED",
                &format!("Unable to schedule agent update: {}", error),
            ),
        ),
    }
}

// =============================================================================
// GET /metrics — Prometheus metrics (max-tier deep integration)
// =============================================================================

/// Render the agent's Prometheus metrics exposition.
pub fn render_metrics(node_id: &str, tier: &str, version: &str, uptime_seconds: u64) -> String {
    // Escape label values per the Prometheus exposition format.
    let esc = |v: &str| v.replace('\\', "\\\\").replace('"', "\\\"");
    format!(
        "# HELP hydra_agent_up Whether the agent control server is up.\n\
         # TYPE hydra_agent_up gauge\n\
         hydra_agent_up 1\n\
         # HELP hydra_agent_uptime_seconds Agent control server uptime in seconds.\n\
         # TYPE hydra_agent_uptime_seconds counter\n\
         hydra_agent_uptime_seconds {uptime}\n\
         # HELP hydra_agent_info Agent build and identity information.\n\
         # TYPE hydra_agent_info gauge\n\
         hydra_agent_info{{node_id=\"{node}\",tier=\"{tier}\",version=\"{version}\"}} 1\n",
        uptime = uptime_seconds,
        node = esc(node_id),
        tier = esc(tier),
        version = esc(version),
    )
}

/// Returns agent metrics in Prometheus text exposition format.
///
/// Gated behind `server.metrics_enabled`; returns 404 when disabled so the
/// endpoint is indistinguishable from an unconfigured agent.
pub async fn metrics(State(state): State<AppState>) -> impl IntoResponse {
    let config = state.config.read().await;
    if !config.server.metrics_enabled {
        return (StatusCode::NOT_FOUND, "metrics disabled\n").into_response();
    }
    let body = render_metrics(
        &config.node.node_id,
        &config.node.tier.to_string(),
        env!("CARGO_PKG_VERSION"),
        state.start_time.elapsed().as_secs(),
    );
    (
        StatusCode::OK,
        [("content-type", "text/plain; version=0.0.4")],
        body,
    )
        .into_response()
}

// =============================================================================
// GET /proxy/docker/{*path} — read-only Docker socket proxy (deep integration)
// =============================================================================

/// Validate a proxied Docker API path: must be absolute and free of control
/// characters (defends against request-line / header injection).
fn is_safe_proxy_path(path: &str) -> bool {
    path.starts_with('/')
        && !path.contains("..")
        && path.chars().all(|c| !c.is_control())
}

/// Parsed HTTP response from the Docker socket.
pub struct ProxiedResponse {
    pub status: u16,
    pub body: Vec<u8>,
}

/// Parse a raw HTTP/1.1 response (read to EOF with `Connection: close`),
/// decoding chunked transfer-encoding when present. Pure and unit-tested.
pub fn parse_http_response(raw: &[u8]) -> Result<ProxiedResponse, String> {
    let split = raw
        .windows(4)
        .position(|w| w == b"\r\n\r\n")
        .ok_or_else(|| "malformed response: no header terminator".to_string())?;
    let header_bytes = &raw[..split];
    let body_bytes = &raw[split + 4..];

    let header_text = String::from_utf8_lossy(header_bytes);
    let mut lines = header_text.split("\r\n");
    let status_line = lines.next().unwrap_or("");
    let status = status_line
        .split_whitespace()
        .nth(1)
        .and_then(|s| s.parse::<u16>().ok())
        .ok_or_else(|| "malformed response: no status code".to_string())?;

    let is_chunked = lines.any(|line| {
        let lower = line.to_ascii_lowercase();
        lower.starts_with("transfer-encoding:") && lower.contains("chunked")
    });

    let body = if is_chunked {
        decode_chunked(body_bytes)?
    } else {
        body_bytes.to_vec()
    };

    Ok(ProxiedResponse { status, body })
}

/// Decode an HTTP/1.1 chunked transfer-encoding body.
fn decode_chunked(mut data: &[u8]) -> Result<Vec<u8>, String> {
    let mut out = Vec::new();
    loop {
        let line_end = data
            .windows(2)
            .position(|w| w == b"\r\n")
            .ok_or_else(|| "malformed chunk: no size line".to_string())?;
        let size_str = String::from_utf8_lossy(&data[..line_end]);
        // Chunk size may carry extensions after ';' — ignore them.
        let size_hex = size_str.split(';').next().unwrap_or("").trim();
        let size = usize::from_str_radix(size_hex, 16)
            .map_err(|_| format!("malformed chunk size: {size_hex}"))?;
        data = &data[line_end + 2..];
        if size == 0 {
            break;
        }
        if data.len() < size {
            return Err("truncated chunk body".to_string());
        }
        out.extend_from_slice(&data[..size]);
        // Skip the chunk payload and its trailing CRLF.
        data = data.get(size + 2..).unwrap_or(&[]);
    }
    Ok(out)
}

/// Proxies a read-only (GET) request to the Docker daemon's Unix socket.
///
/// Gated behind `server.docker_proxy_enabled` (default off). Only GET requests
/// are proxied, bounding the exposure to Docker's read APIs. Already protected
/// by the control server's bearer-auth middleware.
pub async fn docker_proxy(
    State(state): State<AppState>,
    axum::extract::Path(path): axum::extract::Path<String>,
    raw_query: axum::extract::RawQuery,
) -> impl IntoResponse {
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    use tokio::net::UnixStream;

    let (enabled, socket_path) = {
        let config = state.config.read().await;
        (
            config.server.docker_proxy_enabled,
            config.server.docker_socket_path.clone(),
        )
    };

    if !enabled {
        return (StatusCode::NOT_FOUND, "docker proxy disabled\n").into_response();
    }

    // Reconstruct the Docker API request path (axum strips the leading match).
    let mut request_path = format!("/{}", path);
    if let Some(q) = raw_query.0.as_deref() {
        request_path.push('?');
        request_path.push_str(q);
    }

    if !is_safe_proxy_path(&request_path) {
        return (StatusCode::BAD_REQUEST, "invalid proxy path\n").into_response();
    }

    let mut stream = match UnixStream::connect(&socket_path).await {
        Ok(s) => s,
        Err(e) => {
            return (
                StatusCode::BAD_GATEWAY,
                format!("docker socket unavailable: {e}\n"),
            )
                .into_response();
        }
    };

    let request = format!(
        "GET {request_path} HTTP/1.1\r\nHost: docker\r\nAccept: application/json\r\nConnection: close\r\n\r\n"
    );
    if let Err(e) = stream.write_all(request.as_bytes()).await {
        return (
            StatusCode::BAD_GATEWAY,
            format!("docker request failed: {e}\n"),
        )
            .into_response();
    }

    let mut raw = Vec::new();
    if let Err(e) = stream.read_to_end(&mut raw).await {
        return (
            StatusCode::BAD_GATEWAY,
            format!("docker read failed: {e}\n"),
        )
            .into_response();
    }

    match parse_http_response(&raw) {
        Ok(resp) => {
            let status = StatusCode::from_u16(resp.status).unwrap_or(StatusCode::BAD_GATEWAY);
            (status, [("content-type", "application/json")], resp.body).into_response()
        }
        Err(e) => (
            StatusCode::BAD_GATEWAY,
            format!("malformed docker response: {e}\n"),
        )
            .into_response(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{
        AgentConfig, ApiConfig, CollectionConfig, NodeConfig, ScheduleConfig, ServerConfig,
    };
    use serde_json::json;
    use std::fs;
    use std::sync::Arc;
    use std::time::Instant;
    use tempfile::TempDir;
    use tokio::sync::RwLock;

    #[test]
    fn render_metrics_produces_prometheus_exposition() {
        let out = render_metrics("proxmox-01", "max", "1.2.3", 42);
        assert!(out.contains("hydra_agent_up 1"));
        assert!(out.contains("hydra_agent_uptime_seconds 42"));
        assert!(out.contains(
            "hydra_agent_info{node_id=\"proxmox-01\",tier=\"max\",version=\"1.2.3\"} 1"
        ));
        // Every metric line is preceded by HELP/TYPE comments.
        assert!(out.contains("# TYPE hydra_agent_uptime_seconds counter"));
    }

    #[test]
    fn render_metrics_escapes_label_values() {
        let out = render_metrics("no\"de\\1", "max", "1.0", 0);
        assert!(out.contains("node_id=\"no\\\"de\\\\1\""));
    }

    #[test]
    fn is_safe_proxy_path_rejects_injection_and_traversal() {
        assert!(is_safe_proxy_path("/containers/json"));
        assert!(is_safe_proxy_path("/containers/json?all=true"));
        assert!(!is_safe_proxy_path("containers/json")); // not absolute
        assert!(!is_safe_proxy_path("/../etc/passwd")); // traversal
        assert!(!is_safe_proxy_path("/inject\r\nHost: evil")); // CRLF injection
    }

    #[test]
    fn parse_http_response_handles_content_length() {
        let raw = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 13\r\n\r\n{\"status\":1}\n";
        let resp = parse_http_response(raw).unwrap();
        assert_eq!(resp.status, 200);
        assert_eq!(resp.body, b"{\"status\":1}\n");
    }

    #[test]
    fn parse_http_response_decodes_chunked() {
        // Two chunks "Hello" (5) and " World" (6), terminated by a 0 chunk.
        let raw = b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nHello\r\n6\r\n World\r\n0\r\n\r\n";
        let resp = parse_http_response(raw).unwrap();
        assert_eq!(resp.status, 200);
        assert_eq!(resp.body, b"Hello World");
    }

    #[test]
    fn parse_http_response_rejects_malformed() {
        assert!(parse_http_response(b"no headers here").is_err());
    }

    fn base_config() -> AgentConfig {
        AgentConfig {
            api: ApiConfig {
                url: "http://localhost:8080/api/v1".to_string(),
                timeout_seconds: 30,
                retries: 3,
            },
            node: NodeConfig {
                node_id: "testnode".to_string(),
                class: "compute".to_string(),
                tier: crate::config::AgentTier::Normal,
                node_type: "physical".to_string(),
                kind: None,
                display_name: Some("Test Node".to_string()),
                description: None,
                tags: vec![],
                parent_node_id: None,
            },
            collection: CollectionConfig::default(),
            schedule: ScheduleConfig::default(),
            server: ServerConfig::default(),
        }
    }

    fn config_contents() -> String {
        r#"
[api]
url = "http://localhost:8080/api/v1"

[node]
node_id = "testnode"
"#
        .trim_start()
        .to_string()
    }

    async fn build_state(temp_dir: &TempDir) -> AppState {
        let config_path = temp_dir.path().join("agent.toml");
        fs::write(&config_path, config_contents()).unwrap();
        AppState {
            config: Arc::new(RwLock::new(base_config())),
            config_path,
            server_secret: "test-secret".to_string(),
            start_time: Instant::now(),
            api_client: None,
            vault: None,
            plugin_state: Arc::new(RwLock::new(crate::plugins::PluginState::new())),
        }
    }

    #[tokio::test]
    async fn test_config_update_invalid_does_not_modify_disk() {
        let temp_dir = TempDir::new().unwrap();
        let state = build_state(&temp_dir).await;
        let original = fs::read_to_string(&state.config_path).unwrap();

        let result = config_update(
            State(state.clone()),
            Json(ConfigUpdateRequest {
                merge: json!({
                    "server": {
                        "enabled": true
                    }
                }),
            }),
        )
        .await;

        assert!(result.is_err());
        let response = result.unwrap_err().into_response();
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
        assert_eq!(fs::read_to_string(&state.config_path).unwrap(), original);
    }

    #[tokio::test]
    async fn test_config_update_writes_atomically_and_requires_restart() {
        let temp_dir = TempDir::new().unwrap();
        let state = build_state(&temp_dir).await;

        let result = config_update(
            State(state.clone()),
            Json(ConfigUpdateRequest {
                merge: json!({
                    "schedule": {
                        "interval_seconds": 120
                    }
                }),
            }),
        )
        .await;

        assert!(result.is_ok(), "config update should succeed");
        let response = match result {
            Ok(response) => response.0,
            Err(_) => unreachable!("checked is_ok above"),
        };
        assert!(response.restart_required);
        assert_eq!(response.updated_sections, vec!["schedule".to_string()]);

        let disk_config = crate::config::AgentConfig::load(&state.config_path).unwrap();
        assert_eq!(disk_config.schedule.interval_seconds, 120);

        let memory_config = state.config.read().await;
        assert_eq!(memory_config.schedule.interval_seconds, 120);
    }
}
