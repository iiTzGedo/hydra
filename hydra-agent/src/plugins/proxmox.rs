//! Proxmox VE plugin handler.
//!
//! Executes Proxmox commands via local CLI tools (`qm`, `pct`, `pvesh`)
//! when running on a PVE node, or returns informational errors when not available.

use serde_json::Value;

use crate::executor::process::run_command;
use crate::executor::CommandResult;
use crate::plugins::PluginState;

/// Execute a Proxmox plugin command.
pub async fn execute(
    action: &str,
    parameters: &Option<Value>,
    timeout_secs: u64,
    _plugin_state: &PluginState,
) -> CommandResult {
    match action {
        "list-vms" => list_vms(timeout_secs).await,
        "vm-status" => vm_status(parameters, timeout_secs).await,
        "start-vm" => vm_action("start", parameters, timeout_secs).await,
        "stop-vm" => vm_action("stop", parameters, timeout_secs).await,
        "snapshot" => snapshot(parameters, timeout_secs).await,
        "list-storage" => list_storage(timeout_secs).await,
        other => CommandResult::error(&format!("Unknown proxmox action: '{}'", other)),
    }
}

async fn list_vms(timeout_secs: u64) -> CommandResult {
    // Try qm first (QEMU VMs), then pct (LXC containers)
    let qm = run_command("qm", &["list"], timeout_secs).await;
    let pct = run_command("pct", &["list"], timeout_secs).await;

    let mut output = String::new();
    if let Some(ref qm_out) = qm.output {
        output.push_str("=== QEMU VMs ===\n");
        output.push_str(qm_out);
    }
    if let Some(ref pct_out) = pct.output {
        if !output.is_empty() {
            output.push('\n');
        }
        output.push_str("=== LXC Containers ===\n");
        output.push_str(pct_out);
    }

    if output.is_empty() {
        return CommandResult::error("Neither qm nor pct available on this node");
    }

    CommandResult {
        success: true,
        output: Some(output),
        exit_code: Some(0),
        error: None,
        data: None,
    }
}

async fn vm_status(parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let vmid = match extract_vmid(parameters) {
        Some(id) => id,
        None => return CommandResult::error("Missing required parameter: vmid"),
    };
    let vm_type = extract_vm_type(parameters);
    let cmd = if vm_type == "lxc" { "pct" } else { "qm" };
    run_command(cmd, &["status", &vmid], timeout_secs).await
}

async fn vm_action(action: &str, parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let vmid = match extract_vmid(parameters) {
        Some(id) => id,
        None => return CommandResult::error("Missing required parameter: vmid"),
    };
    let vm_type = extract_vm_type(parameters);
    let cmd = if vm_type == "lxc" { "pct" } else { "qm" };
    run_command(cmd, &[action, &vmid], timeout_secs).await
}

async fn snapshot(parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let vmid = match extract_vmid(parameters) {
        Some(id) => id,
        None => return CommandResult::error("Missing required parameter: vmid"),
    };
    let snap_name = parameters
        .as_ref()
        .and_then(|p| p.get("name"))
        .and_then(|v| v.as_str())
        .unwrap_or("hydra-snapshot");
    let vm_type = extract_vm_type(parameters);
    let cmd = if vm_type == "lxc" { "pct" } else { "qm" };
    run_command(cmd, &["snapshot", &vmid, snap_name], timeout_secs).await
}

async fn list_storage(timeout_secs: u64) -> CommandResult {
    run_command("pvesh", &["get", "/storage", "--output-format", "json"], timeout_secs).await
}

fn extract_vmid(parameters: &Option<Value>) -> Option<String> {
    parameters
        .as_ref()
        .and_then(|p| p.get("vmid"))
        .and_then(|v| v.as_u64().map(|n| n.to_string()).or_else(|| v.as_str().map(String::from)))
}

fn extract_vm_type(parameters: &Option<Value>) -> &str {
    parameters
        .as_ref()
        .and_then(|p| p.get("vmType"))
        .and_then(|v| v.as_str())
        .unwrap_or("qemu")
}
