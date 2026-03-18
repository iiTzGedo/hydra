//! Single-instance enforcement using PID files with stale-lock detection.
//!
//! Ensures only one hydra-agent process runs per machine. On startup:
//! 1. Check for existing PID file
//! 2. If PID file exists, verify the process is still running
//! 3. If the process is running, abort with a clear error
//! 4. If the process is dead (stale lock), remove the PID file and continue
//! 5. Write our own PID to the file
//! 6. On Unix/Linux, also check if hydra-agent is running as a systemd service

use anyhow::{anyhow, Context, Result};
use std::fs;
use std::path::{Path, PathBuf};
use tracing::{debug, info, warn};

use crate::platform::paths::defaults;

/// Get the default PID file path for the current platform.
pub fn default_pid_path() -> PathBuf {
    PathBuf::from(defaults::PID_FILE)
}

/// Enforce that only one agent instance is running.
///
/// Checks for an existing PID file, verifies whether the process is alive,
/// and either aborts (if running) or cleans up the stale lock (if dead).
/// On success, writes the current process PID to the file.
///
/// Returns the PID file path for later cleanup.
pub fn enforce_single_instance(pid_path: &Path) -> Result<()> {
    // Read existing PID file if present
    if pid_path.exists() {
        let contents = fs::read_to_string(pid_path)
            .with_context(|| format!("Failed to read PID file: {}", pid_path.display()))?;

        if let Ok(pid) = contents.trim().parse::<u32>() {
            if process_is_running(pid) {
                return Err(anyhow!(
                    "Another hydra-agent instance is already running (PID {}). \
                     Only one agent is permitted per machine. \
                     Stop the existing instance first.",
                    pid
                ));
            }

            // Stale PID file — process is not running
            warn!(
                stale_pid = pid,
                "Found stale PID file (process {} is not running). Removing.", pid
            );
            fs::remove_file(pid_path).with_context(|| {
                format!("Failed to remove stale PID file: {}", pid_path.display())
            })?;
        } else {
            // PID file contains garbage — remove it
            warn!("PID file contains invalid content. Removing.");
            fs::remove_file(pid_path).with_context(|| {
                format!("Failed to remove invalid PID file: {}", pid_path.display())
            })?;
        }
    }

    // On Linux, also check systemd service status
    #[cfg(target_os = "linux")]
    {
        if let Some(msg) = check_systemd_service() {
            return Err(anyhow!(msg));
        }
    }

    // Write our PID
    write_pid_file(pid_path)?;

    info!(
        pid = std::process::id(),
        pid_file = %pid_path.display(),
        "Instance lock acquired"
    );

    Ok(())
}

/// Remove the PID file on shutdown.
pub fn release_instance_lock(pid_path: &Path) {
    if pid_path.exists() {
        match fs::remove_file(pid_path) {
            Ok(_) => debug!(pid_file = %pid_path.display(), "Instance lock released"),
            Err(e) => warn!("Failed to remove PID file on shutdown: {}", e),
        }
    }
}

/// Write the current process PID to the PID file.
fn write_pid_file(pid_path: &Path) -> Result<()> {
    // Ensure parent directory exists
    if let Some(parent) = pid_path.parent() {
        if !parent.exists() {
            fs::create_dir_all(parent)
                .with_context(|| format!("Failed to create PID directory: {}", parent.display()))?;
        }
    }

    let pid = std::process::id();
    fs::write(pid_path, pid.to_string())
        .with_context(|| format!("Failed to write PID file: {}", pid_path.display()))?;

    // Restrict permissions on Unix
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = fs::set_permissions(pid_path, fs::Permissions::from_mode(0o644));
    }

    Ok(())
}

/// Check if a process with the given PID is still running.
fn process_is_running(pid: u32) -> bool {
    #[cfg(unix)]
    {
        // Check if /proc/<pid> exists (Linux) or use kill(pid, 0) via nix
        use nix::sys::signal::kill;
        use nix::unistd::Pid;

        // kill with None sends signal 0 — checks process existence without signaling
        match kill(Pid::from_raw(pid as i32), None) {
            Ok(_) => true,                         // Process exists
            Err(nix::errno::Errno::EPERM) => true, // Exists but we lack permission
            Err(_) => false,                       // ESRCH — doesn't exist
        }
    }

    #[cfg(windows)]
    {
        // On Windows, check if /proc/<pid> style doesn't apply.
        // Use std::process::Command to query tasklist.
        use std::process::Command;
        let output = Command::new("tasklist")
            .args(["/FI", &format!("PID eq {}", pid), "/NH"])
            .output();
        match output {
            Ok(out) => {
                let stdout = String::from_utf8_lossy(&out.stdout);
                stdout.contains(&pid.to_string())
            }
            Err(_) => false,
        }
    }

    #[cfg(not(any(unix, windows)))]
    {
        let _ = pid;
        false
    }
}

/// Check if hydra-agent is running as a systemd service (Linux only).
#[cfg(target_os = "linux")]
fn check_systemd_service() -> Option<String> {
    use std::process::Command;

    let output = Command::new("systemctl")
        .args(["is-active", "--quiet", "hydra-agent.service"])
        .status();

    match output {
        Ok(status) if status.success() => Some(
            "Hydra agent is running as a systemd service. \
             Stop it first: systemctl stop hydra-agent"
                .to_string(),
        ),
        _ => None, // Not running or systemctl not available
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn test_no_existing_pid_file() {
        let temp = TempDir::new().unwrap();
        let pid_path = temp.path().join("agent.pid");

        let result = enforce_single_instance(&pid_path);
        assert!(result.is_ok(), "Should succeed when no PID file exists");
        assert!(pid_path.exists(), "PID file should be created");

        let contents = fs::read_to_string(&pid_path).unwrap();
        let pid: u32 = contents.trim().parse().unwrap();
        assert_eq!(pid, std::process::id());
    }

    #[test]
    fn test_stale_pid_file() {
        let temp = TempDir::new().unwrap();
        let pid_path = temp.path().join("agent.pid");

        // Write a PID that is very unlikely to be running
        fs::write(&pid_path, "999999999").unwrap();

        let result = enforce_single_instance(&pid_path);
        assert!(result.is_ok(), "Should succeed when PID file is stale");

        // Should now contain our PID
        let contents = fs::read_to_string(&pid_path).unwrap();
        let pid: u32 = contents.trim().parse().unwrap();
        assert_eq!(pid, std::process::id());
    }

    #[test]
    fn test_running_process_blocks() {
        let temp = TempDir::new().unwrap();
        let pid_path = temp.path().join("agent.pid");

        // Write our own PID (which is definitely running)
        fs::write(&pid_path, std::process::id().to_string()).unwrap();

        let result = enforce_single_instance(&pid_path);
        assert!(result.is_err(), "Should fail when PID is running");
        let err = result.unwrap_err().to_string();
        assert!(
            err.contains("already running"),
            "Error should mention 'already running': {}",
            err
        );
    }

    #[test]
    fn test_invalid_pid_file_contents() {
        let temp = TempDir::new().unwrap();
        let pid_path = temp.path().join("agent.pid");

        fs::write(&pid_path, "not-a-number").unwrap();

        let result = enforce_single_instance(&pid_path);
        assert!(result.is_ok(), "Should succeed when PID file is invalid");
    }

    #[test]
    fn test_release_lock() {
        let temp = TempDir::new().unwrap();
        let pid_path = temp.path().join("agent.pid");

        enforce_single_instance(&pid_path).unwrap();
        assert!(pid_path.exists());

        release_instance_lock(&pid_path);
        assert!(!pid_path.exists(), "PID file should be removed");
    }

    #[test]
    fn test_release_nonexistent_lock() {
        let temp = TempDir::new().unwrap();
        let pid_path = temp.path().join("nonexistent.pid");

        // Should not panic
        release_instance_lock(&pid_path);
    }
}
