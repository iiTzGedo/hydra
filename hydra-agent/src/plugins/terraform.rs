//! Terraform plugin handler.
//!
//! Executes Terraform commands via the local CLI.

use serde_json::Value;

use crate::executor::process::run_command;
use crate::executor::CommandResult;
use crate::plugins::PluginState;

/// Execute a Terraform plugin command.
pub async fn execute(
    action: &str,
    parameters: &Option<Value>,
    timeout_secs: u64,
    _plugin_state: &PluginState,
) -> CommandResult {
    match action {
        "plan" => tf_plan(parameters, timeout_secs).await,
        "apply" => tf_apply(parameters, timeout_secs).await,
        "destroy" => tf_destroy(parameters, timeout_secs).await,
        "state-list" => tf_state_list(parameters, timeout_secs).await,
        "output" => tf_output(parameters, timeout_secs).await,
        other => CommandResult::error(&format!("Unknown terraform action: '{}'", other)),
    }
}

async fn tf_plan(parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let mut args = vec!["plan", "-json", "-input=false"];
    if let Some(var_file) = get_param_str(parameters, "varFile") {
        args.push("-var-file");
        args.push(var_file);
    }
    if let Some(target) = get_param_str(parameters, "target") {
        args.push("-target");
        args.push(target);
    }
    let chdir = get_chdir_arg(parameters);
    let mut full_args: Vec<&str> = Vec::new();
    if let Some(ref dir) = chdir {
        full_args.extend_from_slice(&["-chdir", dir]);
    }
    full_args.extend_from_slice(&args);
    run_command("terraform", &full_args, timeout_secs).await
}

async fn tf_apply(parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let mut args = vec!["apply", "-json", "-input=false", "-auto-approve"];
    if let Some(var_file) = get_param_str(parameters, "varFile") {
        args.push("-var-file");
        args.push(var_file);
    }
    let chdir = get_chdir_arg(parameters);
    let mut full_args: Vec<&str> = Vec::new();
    if let Some(ref dir) = chdir {
        full_args.extend_from_slice(&["-chdir", dir]);
    }
    full_args.extend_from_slice(&args);
    run_command("terraform", &full_args, timeout_secs).await
}

async fn tf_destroy(parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let mut args = vec!["destroy", "-json", "-input=false", "-auto-approve"];
    if let Some(target) = get_param_str(parameters, "target") {
        args.push("-target");
        args.push(target);
    }
    let chdir = get_chdir_arg(parameters);
    let mut full_args: Vec<&str> = Vec::new();
    if let Some(ref dir) = chdir {
        full_args.extend_from_slice(&["-chdir", dir]);
    }
    full_args.extend_from_slice(&args);
    run_command("terraform", &full_args, timeout_secs).await
}

async fn tf_state_list(parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let chdir = get_chdir_arg(parameters);
    let mut args: Vec<&str> = Vec::new();
    if let Some(ref dir) = chdir {
        args.extend_from_slice(&["-chdir", dir]);
    }
    args.extend_from_slice(&["state", "list"]);
    run_command("terraform", &args, timeout_secs).await
}

async fn tf_output(parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let chdir = get_chdir_arg(parameters);
    let mut args: Vec<&str> = Vec::new();
    if let Some(ref dir) = chdir {
        args.extend_from_slice(&["-chdir", dir]);
    }
    args.extend_from_slice(&["output", "-json"]);
    run_command("terraform", &args, timeout_secs).await
}

fn get_param_str<'a>(parameters: &'a Option<Value>, key: &str) -> Option<&'a str> {
    parameters.as_ref().and_then(|p| p.get(key)).and_then(|v| v.as_str())
}

fn get_chdir_arg(parameters: &Option<Value>) -> Option<String> {
    get_param_str(parameters, "workingDir").map(String::from)
}
