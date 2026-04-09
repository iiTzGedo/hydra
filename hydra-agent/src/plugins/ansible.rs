//! Ansible plugin handler.
//!
//! Executes Ansible commands via the local CLI tools (ansible-playbook, ansible, etc.).

use serde_json::Value;

use crate::executor::process::run_command;
use crate::executor::CommandResult;
use crate::plugins::PluginState;

/// Execute an Ansible plugin command.
pub async fn execute(
    action: &str,
    parameters: &Option<Value>,
    timeout_secs: u64,
    _plugin_state: &PluginState,
) -> CommandResult {
    match action {
        "run-playbook" => run_playbook(parameters, timeout_secs).await,
        "run-module" => run_module(parameters, timeout_secs).await,
        "list-inventory" => list_inventory(parameters, timeout_secs).await,
        "galaxy-install" => galaxy_install(parameters, timeout_secs).await,
        other => CommandResult::error(&format!("Unknown ansible action: '{}'", other)),
    }
}

async fn run_playbook(parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let playbook = match get_param_str(parameters, "playbook") {
        Some(p) => p,
        None => return CommandResult::error("Missing required parameter: playbook"),
    };

    let mut args: Vec<&str> = vec![playbook];

    if let Some(inventory) = get_param_str(parameters, "inventory") {
        args.extend_from_slice(&["-i", inventory]);
    }
    if let Some(limit) = get_param_str(parameters, "limit") {
        args.extend_from_slice(&["--limit", limit]);
    }
    if let Some(tags) = get_param_str(parameters, "tags") {
        args.extend_from_slice(&["--tags", tags]);
    }
    if parameters
        .as_ref()
        .and_then(|p| p.get("check"))
        .and_then(|v| v.as_bool())
        .unwrap_or(false)
    {
        args.push("--check");
    }

    run_command("ansible-playbook", &args, timeout_secs).await
}

async fn run_module(parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let module = match get_param_str(parameters, "module") {
        Some(m) => m,
        None => return CommandResult::error("Missing required parameter: module"),
    };
    let pattern = get_param_str(parameters, "pattern").unwrap_or("all");

    let mut args = vec![pattern, "-m", module];

    if let Some(module_args) = get_param_str(parameters, "args") {
        args.extend_from_slice(&["-a", module_args]);
    }
    if let Some(inventory) = get_param_str(parameters, "inventory") {
        args.extend_from_slice(&["-i", inventory]);
    }

    run_command("ansible", &args, timeout_secs).await
}

async fn list_inventory(parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let mut args = vec!["--list"];
    if let Some(inventory) = get_param_str(parameters, "inventory") {
        args.extend_from_slice(&["-i", inventory]);
    }
    run_command("ansible-inventory", &args, timeout_secs).await
}

async fn galaxy_install(parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let name = match get_param_str(parameters, "name") {
        Some(n) => n,
        None => return CommandResult::error("Missing required parameter: name"),
    };
    let kind = get_param_str(parameters, "type").unwrap_or("role");
    run_command("ansible-galaxy", &[kind, "install", name], timeout_secs).await
}

fn get_param_str<'a>(parameters: &'a Option<Value>, key: &str) -> Option<&'a str> {
    parameters.as_ref().and_then(|p| p.get(key)).and_then(|v| v.as_str())
}
