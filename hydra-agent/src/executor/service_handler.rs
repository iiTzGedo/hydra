//! Service command handler.
//!
//! Handles the 7 service commands: start, stop, restart, reload, logs, inspect, update.
//! Routes to the appropriate backend (systemd or docker) based on the runtime parameter.

use serde_json::Value;
use tracing::info;

use super::process::{run_command, validate_service_name};
use super::CommandResult;

fn validate_image_reference(image: &str) -> Result<(), String> {
    use std::sync::OnceLock;
    static RE: OnceLock<regex::Regex> = OnceLock::new();
    let re = RE.get_or_init(|| {
        regex::Regex::new(r"^[a-zA-Z0-9][a-zA-Z0-9._/@:\-]{0,254}$")
            .expect("valid image reference regex")
    });

    if image.is_empty() || image.len() > 255 {
        return Err("Image reference must be 1-255 characters".to_string());
    }

    if !re.is_match(image) {
        return Err(format!(
            "Invalid image reference '{}': must match [a-zA-Z0-9._/@:-]",
            image
        ));
    }

    Ok(())
}

/// Execute a service command.
///
/// # Arguments
/// * `action` - The service action (start, stop, restart, reload, logs, inspect, update)
/// * `parameters` - Command parameters containing `name`, `runtime`, and action-specific options
/// * `timeout_secs` - Maximum execution time
pub async fn execute(action: &str, parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let params = match parameters {
        Some(p) => p,
        None => {
            return CommandResult::error(
                "Service commands require parameters with at least 'name'",
            );
        }
    };

    let name = match params.get("name").and_then(|v| v.as_str()) {
        Some(n) => n,
        None => {
            return CommandResult::error("Missing required parameter 'name' (service/unit name)");
        }
    };

    if let Err(e) = validate_service_name(name) {
        return CommandResult::error(&e);
    }

    let runtime = params
        .get("runtime")
        .and_then(|v| v.as_str())
        .unwrap_or("systemd");

    info!(
        action = action,
        service = name,
        runtime = runtime,
        "Executing service command"
    );

    match runtime {
        "systemd" => execute_systemd(action, name, params, timeout_secs).await,
        "docker" => execute_docker(action, name, params, timeout_secs).await,
        "podman" => execute_podman(action, name, params, timeout_secs).await,
        other => CommandResult::error(&format!("Unsupported runtime: {}", other)),
    }
}

/// Execute a systemd service command.
async fn execute_systemd(
    action: &str,
    service: &str,
    params: &Value,
    timeout_secs: u64,
) -> CommandResult {
    match action {
        "start" | "stop" | "restart" | "reload" => {
            run_command("systemctl", &[action, service], timeout_secs).await
        }
        "logs" => {
            let lines = params
                .get("lines")
                .and_then(|v| v.as_u64())
                .unwrap_or(100)
                .min(10_000)
                .to_string();

            run_command(
                "journalctl",
                &["-u", service, "-n", &lines, "--no-pager"],
                timeout_secs,
            )
            .await
        }
        "inspect" => run_command("systemctl", &["show", service], timeout_secs).await,
        "update" => CommandResult::error("'update' is not supported for systemd services"),
        other => CommandResult::error(&format!("Unknown service action: {}", other)),
    }
}

/// Execute a docker container command.
async fn execute_docker(
    action: &str,
    container: &str,
    params: &Value,
    timeout_secs: u64,
) -> CommandResult {
    match action {
        "start" | "stop" | "restart" => {
            run_command("docker", &[action, container], timeout_secs).await
        }
        "reload" => {
            // Docker doesn't have a native reload — send HUP signal
            run_command("docker", &["kill", "-s", "HUP", container], timeout_secs).await
        }
        "logs" => {
            let lines = params
                .get("lines")
                .and_then(|v| v.as_u64())
                .unwrap_or(100)
                .min(10_000)
                .to_string();

            run_command(
                "docker",
                &["logs", "--tail", &lines, container],
                timeout_secs,
            )
            .await
        }
        "inspect" => run_command("docker", &["inspect", container], timeout_secs).await,
        "update" => {
            // Pull the latest image if specified, then restart
            let image = params.get("image").and_then(|v| v.as_str());
            match image {
                Some(img) => {
                    if let Err(e) = validate_image_reference(img) {
                        return CommandResult::error(&format!("Invalid image name: {}", e));
                    }
                    let pull_result = run_command("docker", &["pull", img], timeout_secs).await;
                    if !pull_result.success {
                        return pull_result;
                    }
                    run_command("docker", &["restart", container], timeout_secs).await
                }
                None => {
                    CommandResult::error("'update' for docker requires 'image' parameter to pull")
                }
            }
        }
        other => CommandResult::error(&format!("Unknown service action: {}", other)),
    }
}

/// Execute a podman container command (mirrors docker interface).
async fn execute_podman(
    action: &str,
    container: &str,
    params: &Value,
    timeout_secs: u64,
) -> CommandResult {
    match action {
        "start" | "stop" | "restart" => {
            run_command("podman", &[action, container], timeout_secs).await
        }
        "reload" => run_command("podman", &["kill", "-s", "HUP", container], timeout_secs).await,
        "logs" => {
            let lines = params
                .get("lines")
                .and_then(|v| v.as_u64())
                .unwrap_or(100)
                .min(10_000)
                .to_string();

            run_command(
                "podman",
                &["logs", "--tail", &lines, container],
                timeout_secs,
            )
            .await
        }
        "inspect" => run_command("podman", &["inspect", container], timeout_secs).await,
        "update" => {
            let image = params.get("image").and_then(|v| v.as_str());
            match image {
                Some(img) => {
                    if let Err(e) = validate_image_reference(img) {
                        return CommandResult::error(&format!("Invalid image name: {}", e));
                    }
                    let pull_result = run_command("podman", &["pull", img], timeout_secs).await;
                    if !pull_result.success {
                        return pull_result;
                    }
                    run_command("podman", &["restart", container], timeout_secs).await
                }
                None => {
                    CommandResult::error("'update' for podman requires 'image' parameter to pull")
                }
            }
        }
        other => CommandResult::error(&format!("Unknown service action: {}", other)),
    }
}
