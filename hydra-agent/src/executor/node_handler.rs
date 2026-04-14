//! Node command handler.
//!
//! Handles node-level commands: reboot, shutdown, suspend, update-system, set-hostname.
//! These commands operate on the host system and typically require root privileges.

use serde_json::Value;
use tracing::info;

use super::process::{run_command, validate_hostname};
use super::CommandResult;

/// Execute a node command.
///
/// # Arguments
/// * `action` - The node action (reboot, shutdown, update-system, set-hostname)
/// * `parameters` - Command parameters (action-specific options)
/// * `timeout_secs` - Maximum execution time
pub async fn execute(action: &str, parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    info!(action = action, "Executing node command");

    match action {
        "reboot" => execute_reboot(timeout_secs).await,
        "shutdown" => execute_shutdown(timeout_secs).await,
        "suspend" => execute_suspend(timeout_secs).await,
        "update-system" => execute_system_update(timeout_secs).await,
        "set-hostname" => execute_set_hostname(parameters, timeout_secs).await,
        other => CommandResult::error(&format!("Unknown node action: {}", other)),
    }
}

/// Reboot the system.
#[cfg(target_os = "linux")]
async fn execute_reboot(timeout_secs: u64) -> CommandResult {
    run_command("shutdown", &["-r", "now"], timeout_secs).await
}

#[cfg(not(target_os = "linux"))]
async fn execute_reboot(_timeout_secs: u64) -> CommandResult {
    CommandResult::error("Reboot is only supported on Linux")
}

/// Shut down the system.
#[cfg(target_os = "linux")]
async fn execute_shutdown(timeout_secs: u64) -> CommandResult {
    run_command("shutdown", &["-h", "now"], timeout_secs).await
}

#[cfg(not(target_os = "linux"))]
async fn execute_shutdown(_timeout_secs: u64) -> CommandResult {
    CommandResult::error("Shutdown is only supported on Linux")
}

/// Suspend the system to RAM.
#[cfg(target_os = "linux")]
async fn execute_suspend(timeout_secs: u64) -> CommandResult {
    run_command("systemctl", &["suspend"], timeout_secs).await
}

#[cfg(not(target_os = "linux"))]
async fn execute_suspend(_timeout_secs: u64) -> CommandResult {
    CommandResult::error("Suspend is only supported on Linux")
}

/// Update system packages.
///
/// Detects the distribution via `/etc/os-release` and runs the appropriate
/// package manager commands.
#[cfg(target_os = "linux")]
async fn execute_system_update(timeout_secs: u64) -> CommandResult {
    let distro = detect_distro().await;

    match distro.as_str() {
        "debian" | "ubuntu" | "linuxmint" | "pop" | "elementary" | "zorin" => {
            info!(distro = distro.as_str(), "Running apt-based system update");
            let update = run_command("apt-get", &["update", "-y"], timeout_secs).await;
            if !update.success {
                return update;
            }
            run_command(
                "apt-get",
                &["upgrade", "-y", "--no-install-recommends"],
                timeout_secs,
            )
            .await
        }
        "fedora" | "rhel" | "centos" | "rocky" | "almalinux" | "ol" => {
            info!(distro = distro.as_str(), "Running dnf-based system update");
            run_command("dnf", &["upgrade", "-y"], timeout_secs).await
        }
        "opensuse" | "sles" | "opensuse-leap" | "opensuse-tumbleweed" => {
            info!(
                distro = distro.as_str(),
                "Running zypper-based system update"
            );
            run_command("zypper", &["update", "-y"], timeout_secs).await
        }
        "arch" | "manjaro" | "endeavouros" => {
            info!(
                distro = distro.as_str(),
                "Running pacman-based system update"
            );
            run_command("pacman", &["-Syu", "--noconfirm"], timeout_secs).await
        }
        "alpine" => {
            info!("Running apk-based system update");
            let update = run_command("apk", &["update"], timeout_secs).await;
            if !update.success {
                return update;
            }
            run_command("apk", &["upgrade"], timeout_secs).await
        }
        _ => {
            // Fallback: try apt-get, then dnf
            info!(
                distro = distro.as_str(),
                "Unknown distro, attempting apt-get then dnf"
            );
            let apt_result = run_command("apt-get", &["update", "-y"], 10).await;
            if apt_result.success {
                return run_command(
                    "apt-get",
                    &["upgrade", "-y", "--no-install-recommends"],
                    timeout_secs,
                )
                .await;
            }
            let dnf_result = run_command("dnf", &["upgrade", "-y"], timeout_secs).await;
            if dnf_result.success {
                return dnf_result;
            }
            CommandResult::error(&format!(
                "Could not determine package manager for distro '{}'",
                distro
            ))
        }
    }
}

#[cfg(not(target_os = "linux"))]
async fn execute_system_update(_timeout_secs: u64) -> CommandResult {
    CommandResult::error("System update is only supported on Linux")
}

/// Set the system hostname.
async fn execute_set_hostname(parameters: &Option<Value>, timeout_secs: u64) -> CommandResult {
    let params = match parameters {
        Some(p) => p,
        None => {
            return CommandResult::error("set-hostname requires parameters with 'hostname'");
        }
    };

    let hostname = match params.get("hostname").and_then(|v| v.as_str()) {
        Some(h) => h,
        None => {
            return CommandResult::error("Missing required parameter 'hostname'");
        }
    };

    if let Err(e) = validate_hostname(hostname) {
        return CommandResult::error(&e);
    }

    #[cfg(target_os = "linux")]
    {
        run_command("hostnamectl", &["set-hostname", hostname], timeout_secs).await
    }

    #[cfg(not(target_os = "linux"))]
    {
        let _ = (hostname, timeout_secs);
        CommandResult::error("set-hostname is only supported on Linux")
    }
}

/// Detect the Linux distribution by reading /etc/os-release.
#[cfg(target_os = "linux")]
async fn detect_distro() -> String {
    match tokio::fs::read_to_string("/etc/os-release").await {
        Ok(content) => {
            for line in content.lines() {
                if let Some(id) = line.strip_prefix("ID=") {
                    return id.trim_matches('"').to_lowercase();
                }
            }
            "unknown".to_string()
        }
        Err(_) => "unknown".to_string(),
    }
}
