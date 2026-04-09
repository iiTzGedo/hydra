//! Prometheus plugin handler.
//!
//! All Prometheus commands are API-proxied: the agent calls the
//! Prometheus HTTP API using the configured URL.

use serde_json::Value;

use crate::executor::CommandResult;
use crate::plugins::PluginState;

/// Execute a Prometheus plugin command.
pub async fn execute(
    action: &str,
    parameters: &Option<Value>,
    _timeout_secs: u64,
    plugin_state: &PluginState,
) -> CommandResult {
    let config = match plugin_state.get_config("plg::prometheus") {
        Some(c) if c.enabled => &c.config,
        _ => return CommandResult::error("Prometheus plugin not configured or disabled"),
    };

    let base_url = match config.get("url").and_then(|v| v.as_str()) {
        Some(url) => url.trim_end_matches('/'),
        None => return CommandResult::error("Prometheus URL not configured"),
    };

    match action {
        "query" => {
            let query = match get_param_str(parameters, "query") {
                Some(q) => q,
                None => return CommandResult::error("Missing required parameter: query"),
            };
            api_get(base_url, &format!("/api/v1/query?query={}", urlencoding(query))).await
        }
        "query-range" => {
            let query = match get_param_str(parameters, "query") {
                Some(q) => q,
                None => return CommandResult::error("Missing required parameter: query"),
            };
            let start = get_param_str(parameters, "start").unwrap_or("now-1h");
            let end = get_param_str(parameters, "end").unwrap_or("now");
            let step = get_param_str(parameters, "step").unwrap_or("60s");
            api_get(
                base_url,
                &format!(
                    "/api/v1/query_range?query={}&start={}&end={}&step={}",
                    urlencoding(query),
                    urlencoding(start),
                    urlencoding(end),
                    urlencoding(step),
                ),
            )
            .await
        }
        "targets" => api_get(base_url, "/api/v1/targets").await,
        "alerts" => api_get(base_url, "/api/v1/alerts").await,
        "rules" => api_get(base_url, "/api/v1/rules").await,
        other => CommandResult::error(&format!("Unknown prometheus action: '{}'", other)),
    }
}

fn get_param_str<'a>(parameters: &'a Option<Value>, key: &str) -> Option<&'a str> {
    parameters.as_ref().and_then(|p| p.get(key)).and_then(|v| v.as_str())
}

/// Simple percent-encoding for query parameters.
fn urlencoding(s: &str) -> String {
    s.replace('%', "%25")
        .replace(' ', "%20")
        .replace('&', "%26")
        .replace('=', "%3D")
        .replace('+', "%2B")
        .replace('{', "%7B")
        .replace('}', "%7D")
}

async fn api_get(base_url: &str, path: &str) -> CommandResult {
    let url = format!("{}{}", base_url, path);
    match reqwest::Client::new().get(&url).send().await {
        Ok(resp) => {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            if status.is_success() {
                CommandResult {
                    success: true,
                    output: Some(body),
                    exit_code: Some(0),
                    error: None,
                    data: None,
                }
            } else {
                CommandResult::error(&format!("Prometheus API error {}: {}", status, body))
            }
        }
        Err(e) => CommandResult::error(&format!("Prometheus API request failed: {}", e)),
    }
}
