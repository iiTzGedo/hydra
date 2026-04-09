//! Docker Engine plugin handler.
//!
//! Executes Docker commands via the Docker CLI on the local host.

use serde_json::Value;

use crate::executor::process::run_command;
use crate::executor::CommandResult;
use crate::plugins::PluginState;

/// Execute a Docker plugin command.
pub async fn execute(
    action: &str,
    parameters: &Option<Value>,
    timeout_secs: u64,
    _plugin_state: &PluginState,
) -> CommandResult {
    match action {
        "list-containers" => list_containers(parameters, timeout_secs).await,
        "container-stats" => container_stats(parameters, timeout_secs).await,
        "pull-image" => pull_image(parameters, timeout_secs).await,
        "compose-up" => compose_up(parameters, timeout_secs).await,
        "compose-down" => compose_down(parameters, timeout_secs).await,
        "prune" => prune(timeout_secs).await,
        other => CommandResult::error(&format!("Unknown docker action: '{}'", other)),
    }
}

async fn list_containers(parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let mut args = vec!["ps", "--format", "{{json .}}"];
    let all = parameters
        .as_ref()
        .and_then(|p| p.get("all"))
        .and_then(|v| v.as_bool())
        .unwrap_or(true);
    if all {
        args.insert(1, "-a");
    }
    run_command("docker", &args, timeout_secs).await
}

async fn container_stats(parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let mut args = vec!["stats", "--no-stream", "--format", "{{json .}}"];
    if let Some(container_id) = parameters
        .as_ref()
        .and_then(|p| p.get("containerId"))
        .and_then(|v| v.as_str())
    {
        args.push(container_id);
    }
    run_command("docker", &args, timeout_secs).await
}

async fn pull_image(parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let image = match parameters
        .as_ref()
        .and_then(|p| p.get("image"))
        .and_then(|v| v.as_str())
    {
        Some(img) => img,
        None => return CommandResult::error("Missing required parameter: image"),
    };
    run_command("docker", &["pull", image], timeout_secs).await
}

async fn compose_up(parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let mut args = vec!["compose"];
    if let Some(file) = parameters
        .as_ref()
        .and_then(|p| p.get("file"))
        .and_then(|v| v.as_str())
    {
        args.extend_from_slice(&["-f", file]);
    }
    args.extend_from_slice(&["up", "-d"]);
    run_command("docker", &args, timeout_secs).await
}

async fn compose_down(parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let mut args = vec!["compose"];
    if let Some(file) = parameters
        .as_ref()
        .and_then(|p| p.get("file"))
        .and_then(|v| v.as_str())
    {
        args.extend_from_slice(&["-f", file]);
    }
    args.push("down");
    run_command("docker", &args, timeout_secs).await
}

async fn prune(timeout_secs: u64) -> CommandResult {
    run_command("docker", &["system", "prune", "-f"], timeout_secs).await
}
