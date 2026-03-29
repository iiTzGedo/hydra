//! Safe process runner for command execution.
//!
//! Provides a validated, timeout-enforced wrapper around `tokio::process::Command`
//! with output size limits to prevent memory exhaustion.

use std::process::Stdio;
use std::time::Duration;

use regex::Regex;
use tokio::io::AsyncReadExt;
use tokio::process::Command;
use tokio::time::timeout;
use tracing::warn;

use super::CommandResult;

/// Maximum output size in bytes (1 MB).
const MAX_OUTPUT_SIZE: usize = 1_048_576;

/// Run a system command with timeout and output capture.
///
/// # Arguments
/// * `program` - The executable to run
/// * `args` - Command arguments
/// * `timeout_secs` - Maximum execution time in seconds
///
/// # Returns
/// A `CommandResult` with captured output, exit code, and success status.
pub async fn run_command(program: &str, args: &[&str], timeout_secs: u64) -> CommandResult {
    let duration = Duration::from_secs(timeout_secs);

    match timeout(duration, execute_process(program, args)).await {
        Ok(result) => result,
        Err(_) => CommandResult {
            success: false,
            output: None,
            exit_code: None,
            error: Some(format!(
                "Command timed out after {} seconds: {} {}",
                timeout_secs,
                program,
                args.join(" ")
            )),
            data: None,
        },
    }
}

/// Execute a process and capture its output.
async fn execute_process(program: &str, args: &[&str]) -> CommandResult {
    let mut child = match Command::new(program)
        .args(args)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true)
        .spawn()
    {
        Ok(child) => child,
        Err(e) => {
            return CommandResult {
                success: false,
                output: None,
                exit_code: None,
                error: Some(format!("Failed to spawn process '{}': {}", program, e)),
                data: None,
            };
        }
    };

    // Read stdout and stderr with size limits
    let mut stdout_buf = Vec::with_capacity(4096);
    let mut stderr_buf = Vec::with_capacity(4096);

    if let Some(mut stdout) = child.stdout.take() {
        let mut limited = (&mut stdout).take(MAX_OUTPUT_SIZE as u64);
        if let Err(e) = limited.read_to_end(&mut stdout_buf).await {
            warn!(error = %e, "Failed to read stdout");
        }
    }

    if let Some(mut stderr) = child.stderr.take() {
        let mut limited = (&mut stderr).take(MAX_OUTPUT_SIZE as u64);
        if let Err(e) = limited.read_to_end(&mut stderr_buf).await {
            warn!(error = %e, "Failed to read stderr");
        }
    }

    let status = match child.wait().await {
        Ok(status) => status,
        Err(e) => {
            return CommandResult {
                success: false,
                output: None,
                exit_code: None,
                error: Some(format!("Failed to wait for process '{}': {}", program, e)),
                data: None,
            };
        }
    };

    let exit_code = status.code();
    let success = status.success();

    // Combine stdout and stderr into a single output string
    let stdout_str = String::from_utf8_lossy(&stdout_buf).into_owned();
    let stderr_str = String::from_utf8_lossy(&stderr_buf).into_owned();

    let output = if stdout_str.is_empty() && stderr_str.is_empty() {
        None
    } else if stderr_str.is_empty() {
        Some(stdout_str)
    } else if stdout_str.is_empty() {
        Some(stderr_str.clone())
    } else {
        Some(format!("{}\n--- stderr ---\n{}", stdout_str, stderr_str))
    };

    let error = if !success {
        Some(stderr_str.trim().chars().take(500).collect::<String>())
    } else {
        None
    };

    CommandResult {
        success,
        output,
        exit_code,
        error,
        data: None,
    }
}

/// Validate a service or unit name against a safe pattern.
///
/// Prevents shell injection by only allowing alphanumeric characters,
/// hyphens, dots, underscores, at-signs, and colons.
pub fn validate_service_name(name: &str) -> Result<(), String> {
    if name.is_empty() || name.len() > 80 {
        return Err("Service name must be 1-80 characters".to_string());
    }

    let re = Regex::new(r"^[a-zA-Z0-9][a-zA-Z0-9._@:\-]{0,79}$").unwrap();
    if !re.is_match(name) {
        return Err(format!(
            "Invalid service name '{}': must match [a-zA-Z0-9._@:-]",
            name
        ));
    }

    Ok(())
}

/// Validate a hostname against a safe pattern.
pub fn validate_hostname(hostname: &str) -> Result<(), String> {
    if hostname.is_empty() || hostname.len() > 253 {
        return Err("Hostname must be 1-253 characters".to_string());
    }

    let re = Regex::new(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$").unwrap();
    if !re.is_match(hostname) {
        return Err(format!("Invalid hostname '{}'", hostname));
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_service_name_valid() {
        assert!(validate_service_name("nginx").is_ok());
        assert!(validate_service_name("sshd.service").is_ok());
        assert!(validate_service_name("docker-compose").is_ok());
        assert!(validate_service_name("user@1000.service").is_ok());
        assert!(validate_service_name("my_service:latest").is_ok());
    }

    #[test]
    fn test_validate_service_name_invalid() {
        assert!(validate_service_name("").is_err());
        assert!(validate_service_name("a".repeat(81).as_str()).is_err());
        assert!(validate_service_name("../etc/passwd").is_err());
        assert!(validate_service_name("nginx; rm -rf /").is_err());
        assert!(validate_service_name("$(whoami)").is_err());
    }

    #[test]
    fn test_validate_hostname_valid() {
        assert!(validate_hostname("myhost").is_ok());
        assert!(validate_hostname("my-host.local").is_ok());
        assert!(validate_hostname("proxmox-01").is_ok());
    }

    #[test]
    fn test_validate_hostname_invalid() {
        assert!(validate_hostname("").is_err());
        assert!(validate_hostname("-invalid").is_err());
        assert!(validate_hostname("a".repeat(254).as_str()).is_err());
    }

    #[tokio::test]
    async fn test_run_command_echo() {
        let result = run_command("echo", &["hello"], 5).await;
        assert!(result.success);
        assert_eq!(result.exit_code, Some(0));
        assert!(result.output.unwrap().contains("hello"));
    }

    #[tokio::test]
    async fn test_run_command_nonexistent() {
        let result = run_command("/nonexistent/binary", &[], 5).await;
        assert!(!result.success);
        assert!(result.error.is_some());
    }

    #[tokio::test]
    async fn test_run_command_timeout() {
        let result = run_command("sleep", &["10"], 1).await;
        assert!(!result.success);
        assert!(result.error.unwrap().contains("timed out"));
    }

    #[tokio::test]
    async fn test_run_command_exit_code() {
        let result = run_command("false", &[], 5).await;
        assert!(!result.success);
        assert_eq!(result.exit_code, Some(1));
    }
}
