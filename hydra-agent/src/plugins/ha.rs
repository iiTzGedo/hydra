//! Home Assistant plugin handler.
//!
//! All HA commands are API-proxied: the agent calls the HA REST API
//! using the configured URL and long-lived access token.

use serde_json::Value;

use crate::executor::CommandResult;
use crate::plugins::PluginState;

/// Execute a Home Assistant plugin command.
pub async fn execute(
    action: &str,
    parameters: &Option<Value>,
    _timeout_secs: u64,
    plugin_state: &PluginState,
) -> CommandResult {
    let config = match plugin_state.get_config("plg::homeassistant") {
        Some(c) if c.enabled => &c.config,
        _ => return CommandResult::error("Home Assistant plugin not configured or disabled"),
    };

    let base_url = match config.get("url").and_then(|v| v.as_str()) {
        Some(url) => url.trim_end_matches('/'),
        None => return CommandResult::error("Home Assistant URL not configured"),
    };
    let token = match config.get("token").and_then(|v| v.as_str()) {
        Some(t) => t,
        None => return CommandResult::error("Home Assistant token not configured"),
    };

    match action {
        "list-entities" => api_get(base_url, "/api/states", token).await,
        "get-state" => {
            let entity_id = match get_param_str(parameters, "entityId") {
                Some(id) => id,
                None => return CommandResult::error("Missing required parameter: entityId"),
            };
            api_get(base_url, &format!("/api/states/{}", entity_id), token).await
        }
        "call-service" | "turn-on" | "turn-off" | "toggle" => {
            let (domain, service) = resolve_service(action, parameters);
            let body = parameters
                .as_ref()
                .and_then(|p| p.get("data"))
                .cloned()
                .unwrap_or(Value::Object(serde_json::Map::new()));
            api_post(
                base_url,
                &format!("/api/services/{}/{}", domain, service),
                token,
                &body,
            )
            .await
        }
        other => CommandResult::error(&format!("Unknown HA action: '{}'", other)),
    }
}

fn resolve_service<'a>(action: &'a str, parameters: &'a Option<Value>) -> (&'a str, &'a str) {
    match action {
        "turn-on" => {
            let domain = get_param_str(parameters, "domain").unwrap_or("light");
            (domain, "turn_on")
        }
        "turn-off" => {
            let domain = get_param_str(parameters, "domain").unwrap_or("light");
            (domain, "turn_off")
        }
        "toggle" => {
            let domain = get_param_str(parameters, "domain").unwrap_or("light");
            (domain, "toggle")
        }
        _ => {
            let domain = get_param_str(parameters, "domain").unwrap_or("homeassistant");
            let service = get_param_str(parameters, "service").unwrap_or("check_config");
            (domain, service)
        }
    }
}

fn get_param_str<'a>(parameters: &'a Option<Value>, key: &str) -> Option<&'a str> {
    parameters.as_ref().and_then(|p| p.get(key)).and_then(|v| v.as_str())
}

async fn api_get(base_url: &str, path: &str, token: &str) -> CommandResult {
    let url = format!("{}{}", base_url, path);
    match reqwest::Client::new()
        .get(&url)
        .header("Authorization", format!("Bearer {}", token))
        .send()
        .await
    {
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
                CommandResult::error(&format!("HA API error {}: {}", status, body))
            }
        }
        Err(e) => CommandResult::error(&format!("HA API request failed: {}", e)),
    }
}

async fn api_post(base_url: &str, path: &str, token: &str, body: &Value) -> CommandResult {
    let url = format!("{}{}", base_url, path);
    match reqwest::Client::new()
        .post(&url)
        .header("Authorization", format!("Bearer {}", token))
        .json(body)
        .send()
        .await
    {
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
                CommandResult::error(&format!("HA API error {}: {}", status, body))
            }
        }
        Err(e) => CommandResult::error(&format!("HA API request failed: {}", e)),
    }
}
