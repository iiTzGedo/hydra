//! Upgrade command for self-updating the hydra-agent binary.
//!
//! Provides commands to check for updates, list available versions,
//! upgrade to a new version, and rollback to a previous version.
//!
//! The upgrade flow:
//! 1. Check for updates from the API
//! 2. Detect or use provided target platform
//! 3. Download new binary to temp file
//! 4. Verify SHA256 checksum
//! 5. Backup current binary
//! 6. Stop service (if systemd)
//! 7. Replace binary
//! 8. Set permissions (Unix: 0o755)
//! 9. Start service (unless --no-restart)
//! 10. Verify new version
//! 11. Clean up temp files
//! 12. On failure at steps 7-9: auto-rollback

use anyhow::{anyhow, Context, Result};
use clap::{Args, Subcommand};
use reqwest::Client;
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::cmp::Ordering;
use std::path::{Path, PathBuf};
use std::time::Duration;
use tracing::{debug, info, warn};

use crate::config::AgentConfig;
use crate::vault::Vault;

/// Current agent version from Cargo.toml
const CURRENT_VERSION: &str = env!("CARGO_PKG_VERSION");

/// Upgrade command arguments
#[derive(Args, Debug)]
pub struct UpgradeArgs {
    #[command(subcommand)]
    pub command: Option<UpgradeCommand>,

    /// Target version (default: latest)
    #[arg(long = "target-version")]
    pub target_version: Option<String>,

    /// Target platform (auto-detected if not specified)
    #[arg(long)]
    pub target: Option<String>,

    /// Storage source
    #[arg(long, default_value = "binary")]
    pub source: String,

    /// Don't restart the service after upgrade
    #[arg(long)]
    pub no_restart: bool,

    /// Force reinstall even if already on latest
    #[arg(long)]
    pub force: bool,
}

/// Upgrade subcommands
#[derive(Subcommand, Debug)]
pub enum UpgradeCommand {
    /// Check if an update is available
    Check,
    /// List available versions
    List,
    /// Rollback to the previous version
    Rollback,
}

/// Version information returned from the API
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct VersionEntry {
    version: String,
    #[allow(dead_code)]
    target: Option<String>,
    #[allow(dead_code)]
    source: Option<String>,
}

/// API response wrapper for version listing
#[derive(Debug, Deserialize)]
struct VersionsApiResponse {
    data: Vec<VersionEntry>,
}

/// Information about an available update
#[derive(Debug)]
struct VersionInfo {
    /// Latest available version
    latest: String,
    /// Currently installed version
    current: String,
    /// Whether an update is available
    update_available: bool,
}

/// Execute the upgrade command
pub async fn execute(args: UpgradeArgs, config: &AgentConfig, vault: &Vault) -> Result<()> {
    match &args.command {
        Some(UpgradeCommand::Check) => {
            let info = check_for_updates(config, vault, &args.source).await?;
            print_version_check(&info);
            Ok(())
        }
        Some(UpgradeCommand::List) => {
            list_versions(config, vault, &args.source).await
        }
        Some(UpgradeCommand::Rollback) => {
            rollback()
        }
        None => {
            perform_upgrade(args, config, vault).await
        }
    }
}

/// Perform the full upgrade flow
async fn perform_upgrade(args: UpgradeArgs, config: &AgentConfig, vault: &Vault) -> Result<()> {
    println!();
    println!("Hydra Agent Upgrade");
    println!("===================");
    println!();

    let target_version = if let Some(ref v) = args.target_version {
        v.clone()
    } else {
        let info = check_for_updates(config, vault, &args.source).await?;
        if !info.update_available && !args.force {
            println!("Already running the latest version ({})", info.current);
            println!("Use --force to reinstall the current version.");
            return Ok(());
        }
        if info.update_available {
            println!("Update available: {} -> {}", info.current, info.latest);
        } else {
            println!("Force reinstalling version {}", info.current);
        }
        info.latest
    };

    let target = match args.target {
        Some(ref t) => t.clone(),
        None => detect_target()?,
    };

    println!("  Version: {}", target_version);
    println!("  Target:  {}", target);
    println!("  Source:  {}", args.source);
    println!();

    info!("Downloading hydra-agent v{} for {}...", target_version, target);
    println!("Downloading binary...");

    let temp_path = download_binary(config, vault, &target, &target_version, &args.source).await?;
    info!("Binary downloaded to {}", temp_path.display());
    println!("Download complete.");

    println!("Backing up current binary...");
    let backup_path = backup_current_binary()?;
    info!("Current binary backed up to {}", backup_path.display());
    println!("Backup created at {}", backup_path.display());

    let service_was_running = stop_service_if_running();

    println!("Replacing binary...");
    if let Err(e) = replace_binary(&temp_path) {
        warn!("Failed to replace binary: {}", e);
        println!("ERROR: Failed to replace binary, rolling back...");
        if let Err(rb_err) = rollback() {
            println!("CRITICAL: Rollback also failed: {}", rb_err);
            println!("Manual intervention required. Backup at: {}", backup_path.display());
        }
        if service_was_running && !args.no_restart {
            let _ = restart_service_impl();
        }
        return Err(e);
    }
    println!("Binary replaced.");

    if service_was_running && !args.no_restart {
        println!("Restarting service...");
        if let Err(e) = restart_service_impl() {
            warn!("Failed to restart service: {}", e);
            println!("WARNING: Failed to restart service, rolling back...");
            if let Err(rb_err) = rollback() {
                println!("CRITICAL: Rollback also failed: {}", rb_err);
                println!("Manual intervention required. Backup at: {}", backup_path.display());
            } else {
                let _ = restart_service_impl();
            }
            return Err(e);
        }
        println!("Service restarted.");
    } else if !args.no_restart {
        debug!("Service was not running, skipping restart");
    } else {
        println!("Skipping service restart (--no-restart)");
    }

    println!("Verifying installation...");
    match verify_version(&target_version) {
        Ok(true) => {
            println!("Version verified: {}", target_version);
        }
        Ok(false) => {
            warn!("Version mismatch after upgrade");
            println!("WARNING: Version verification could not confirm the upgrade.");
            println!("The binary was replaced but the reported version may differ.");
        }
        Err(e) => {
            debug!("Version verification failed: {}", e);
            println!("WARNING: Could not verify version (this is normal during self-upgrade).");
        }
    }

    if temp_path.exists() {
        let _ = std::fs::remove_file(&temp_path);
        debug!("Cleaned up temp file: {}", temp_path.display());
    }

    println!();
    println!("Upgrade complete: {} -> {}", CURRENT_VERSION, target_version);
    println!();

    // Report successful upgrade (best-effort)
    if let Ok(api_client) = crate::api::ApiClient::new(config, vault) {
        if let Err(e) = api_client
            .report_event(
                "agent_upgraded",
                &format!("Agent upgraded: {}", config.node.node_id),
                &format!(
                    "Agent on node {} upgraded from {} to {}",
                    config.node.node_id, CURRENT_VERSION, target_version
                ),
                Some(serde_json::json!({
                    "nodeId": config.node.node_id,
                    "oldVersion": CURRENT_VERSION,
                    "newVersion": target_version,
                    "target": target,
                })),
            )
            .await
        {
            warn!("Failed to report upgrade event: {}", e);
        }
    }

    Ok(())
}

/// Check for available updates from the API
async fn check_for_updates(config: &AgentConfig, vault: &Vault, source: &str) -> Result<VersionInfo> {
    let client = build_http_client(config)?;
    let api_key = get_api_key(vault)?;

    let url = format!("{}/agent/versions?source={}", config.api.url, source);
    debug!("Checking for updates at: {}", url);

    let response = client
        .get(&url)
        .header("X-API-Key", &api_key)
        .send()
        .await
        .context("Failed to check for updates")?;

    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        return Err(anyhow!(
            "Failed to check for updates: HTTP {} - {}",
            status,
            body
        ));
    }

    let versions_response: VersionsApiResponse = response
        .json()
        .await
        .context("Failed to parse versions response")?;

    if versions_response.data.is_empty() {
        return Err(anyhow!("No versions available from the API"));
    }

    // Find the latest version by sorting
    let mut versions: Vec<String> = versions_response
        .data
        .iter()
        .map(|v| v.version.clone())
        .collect();

    versions.sort_by(|a, b| compare_versions(a, b));
    let latest = versions.last().cloned().unwrap_or_default();

    let update_available = compare_versions(&latest, CURRENT_VERSION) == Ordering::Greater;

    Ok(VersionInfo {
        latest,
        current: CURRENT_VERSION.to_string(),
        update_available,
    })
}

/// Print version check results
fn print_version_check(info: &VersionInfo) {
    println!();
    println!("Version Check");
    println!("=============");
    println!("  Current: {}", info.current);
    println!("  Latest:  {}", info.latest);
    println!();
    if info.update_available {
        println!("An update is available!");
        println!("Run 'hydra-agent upgrade' to update to v{}", info.latest);
    } else {
        println!("You are running the latest version.");
    }
    println!();
}

/// Detect the current platform target string
fn detect_target() -> Result<String> {
    let os = std::env::consts::OS;
    let arch = std::env::consts::ARCH;

    let target_os = match os {
        "linux" => "linux",
        "macos" => "darwin",
        "windows" => "windows",
        "freebsd" => "freebsd",
        other => return Err(anyhow!("Unsupported operating system: {}", other)),
    };

    let target_arch = match arch {
        "x86_64" => "amd64",
        "aarch64" => "arm64",
        "arm" => "armv7",
        other => return Err(anyhow!("Unsupported architecture: {}", other)),
    };

    Ok(format!("{}-{}", target_os, target_arch))
}

/// Download a binary from the API and verify its checksum
async fn download_binary(
    config: &AgentConfig,
    vault: &Vault,
    target: &str,
    version: &str,
    source: &str,
) -> Result<PathBuf> {
    let client = build_http_client(config)?;
    let api_key = get_api_key(vault)?;

    let url = format!(
        "{}/agent/download?source={}&target={}&version={}",
        config.api.url, source, target, version
    );
    debug!("Downloading binary from: {}", url);

    let response = client
        .get(&url)
        .header("X-API-Key", &api_key)
        .send()
        .await
        .context("Failed to download binary")?;

    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        return Err(anyhow!(
            "Failed to download binary: HTTP {} - {}",
            status,
            body
        ));
    }

    // Get expected checksum from response header
    let expected_checksum = response
        .headers()
        .get("X-Checksum-SHA256")
        .and_then(|v| v.to_str().ok())
        .map(|s| s.to_lowercase());

    debug!("Expected checksum: {:?}", expected_checksum);

    // Read the response body
    let bytes = response
        .bytes()
        .await
        .context("Failed to read binary download response")?;

    if bytes.is_empty() {
        return Err(anyhow!("Downloaded binary is empty"));
    }

    info!("Downloaded {} bytes", bytes.len());

    // Verify checksum if provided
    if let Some(expected) = &expected_checksum {
        let mut hasher = Sha256::new();
        hasher.update(&bytes);
        let computed: String = hasher
            .finalize()
            .iter()
            .map(|b| format!("{:02x}", b))
            .collect();

        if computed != *expected {
            return Err(anyhow!(
                "Checksum mismatch: expected {}, got {}",
                expected,
                computed
            ));
        }
        info!("SHA256 checksum verified: {}", computed);
    } else {
        warn!("No checksum header in response, skipping verification");
    }

    // Write to temp file
    let temp_dir = std::env::temp_dir();
    let temp_filename = format!("hydra-agent-{}-{}.tmp", version, target);
    let temp_path = temp_dir.join(temp_filename);

    std::fs::write(&temp_path, &bytes)
        .with_context(|| format!("Failed to write temp file: {}", temp_path.display()))?;

    debug!("Binary saved to {}", temp_path.display());

    Ok(temp_path)
}

/// Get the installed binary path based on platform
fn installed_binary_path() -> PathBuf {
    #[cfg(unix)]
    {
        PathBuf::from("/usr/local/bin/hydra-agent")
    }
    #[cfg(windows)]
    {
        PathBuf::from(r"C:\Program Files\Hydra\hydra-agent.exe")
    }
}

/// Get the backup binary path based on platform
fn backup_binary_path() -> PathBuf {
    #[cfg(unix)]
    {
        PathBuf::from("/usr/local/bin/hydra-agent.backup")
    }
    #[cfg(windows)]
    {
        PathBuf::from(r"C:\Program Files\Hydra\hydra-agent.exe.backup")
    }
}

/// Backup the current binary
fn backup_current_binary() -> Result<PathBuf> {
    let current = installed_binary_path();
    let backup = backup_binary_path();

    if !current.exists() {
        let current_exe = std::env::current_exe()
            .context("Failed to get current executable path")?;
        info!(
            "Installed path {} not found, backing up running executable: {}",
            current.display(),
            current_exe.display()
        );
        std::fs::copy(&current_exe, &backup).with_context(|| {
            format!(
                "Failed to backup {} to {}",
                current_exe.display(),
                backup.display()
            )
        })?;
    } else {
        std::fs::copy(&current, &backup).with_context(|| {
            format!(
                "Failed to backup {} to {}",
                current.display(),
                backup.display()
            )
        })?;
    }

    info!("Backed up binary to {}", backup.display());
    Ok(backup)
}

/// Replace the installed binary with the new one
fn replace_binary(new_binary: &Path) -> Result<()> {
    let target = installed_binary_path();

    if let Some(parent) = target.parent() {
        std::fs::create_dir_all(parent).with_context(|| {
            format!("Failed to create directory: {}", parent.display())
        })?;
    }

    std::fs::copy(new_binary, &target).with_context(|| {
        format!(
            "Failed to copy new binary from {} to {}",
            new_binary.display(),
            target.display()
        )
    })?;

    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(&target, std::fs::Permissions::from_mode(0o755))
            .with_context(|| format!("Failed to set permissions on {}", target.display()))?;
    }

    info!("Replaced binary at {}", target.display());
    Ok(())
}

/// Check if the systemd service is running and stop it
/// Returns true if the service was running
fn stop_service_if_running() -> bool {
    #[cfg(target_os = "linux")]
    {
        use std::process::Command;

        let active = Command::new("systemctl")
            .args(["is-active", "hydra-agent.service"])
            .output();

        match active {
            Ok(output) => {
                let state = String::from_utf8_lossy(&output.stdout).trim().to_string();
                if state == "active" {
                    info!("Stopping hydra-agent service...");
                    let stop_result = Command::new("systemctl")
                        .args(["stop", "hydra-agent.service"])
                        .status();

                    match stop_result {
                        Ok(status) if status.success() => {
                            info!("Service stopped");
                            return true;
                        }
                        Ok(_) => {
                            warn!("Failed to stop service (non-zero exit)");
                            return true; // Was running, even if stop failed
                        }
                        Err(e) => {
                            warn!("Failed to execute systemctl stop: {}", e);
                            return true;
                        }
                    }
                }
            }
            Err(e) => {
                debug!("systemctl not available or service not found: {}", e);
            }
        }
    }

    #[cfg(not(target_os = "linux"))]
    {
        debug!("Service management not available on this platform");
    }

    false
}

/// Restart the systemd service
fn restart_service_impl() -> Result<()> {
    #[cfg(target_os = "linux")]
    {
        use std::process::Command;

        let status = Command::new("systemctl")
            .args(["start", "hydra-agent.service"])
            .status()
            .context("Failed to start hydra-agent service")?;

        if !status.success() {
            return Err(anyhow!("systemctl start hydra-agent.service failed"));
        }

        info!("Service started");
        return Ok(());
    }

    #[cfg(not(target_os = "linux"))]
    {
        debug!("Service management not available on this platform");
        Ok(())
    }
}

/// Rollback to the backup binary
fn rollback() -> Result<()> {
    let backup = backup_binary_path();
    let target = installed_binary_path();

    if !backup.exists() {
        return Err(anyhow!(
            "No backup found at {}. Cannot rollback.",
            backup.display()
        ));
    }

    println!();
    println!("Rolling back...");

    let service_was_running = stop_service_if_running();

    std::fs::copy(&backup, &target).with_context(|| {
        format!(
            "Failed to restore backup from {} to {}",
            backup.display(),
            target.display()
        )
    })?;

    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(&target, std::fs::Permissions::from_mode(0o755))
            .with_context(|| format!("Failed to set permissions on {}", target.display()))?;
    }

    info!("Restored binary from backup");

    if service_was_running {
        if let Err(e) = restart_service_impl() {
            warn!("Failed to restart service after rollback: {}", e);
            println!("WARNING: Could not restart service. Start manually with:");
            println!("  sudo systemctl start hydra-agent.service");
        } else {
            println!("Service restarted with previous version.");
        }
    }

    println!("Rollback complete. Restored previous binary from {}", backup.display());
    println!();

    Ok(())
}

/// List available versions from the API
async fn list_versions(config: &AgentConfig, vault: &Vault, source: &str) -> Result<()> {
    let client = build_http_client(config)?;
    let api_key = get_api_key(vault)?;

    let url = format!("{}/agent/versions?source={}", config.api.url, source);
    debug!("Fetching versions from: {}", url);

    let response = client
        .get(&url)
        .header("X-API-Key", &api_key)
        .send()
        .await
        .context("Failed to fetch versions")?;

    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        return Err(anyhow!(
            "Failed to list versions: HTTP {} - {}",
            status,
            body
        ));
    }

    let versions_response: VersionsApiResponse = response
        .json()
        .await
        .context("Failed to parse versions response")?;

    println!();
    println!("Available Versions");
    println!("==================");
    println!();

    if versions_response.data.is_empty() {
        println!("  No versions available.");
    } else {
        let mut version_map: std::collections::BTreeMap<String, Vec<String>> =
            std::collections::BTreeMap::new();

        for entry in &versions_response.data {
            let targets = version_map
                .entry(entry.version.clone())
                .or_default();
            if let Some(ref t) = entry.target {
                if !targets.contains(t) {
                    targets.push(t.clone());
                }
            }
        }

        let mut sorted_versions: Vec<String> = version_map.keys().cloned().collect();
        sorted_versions.sort_by(|a, b| compare_versions(a, b));
        sorted_versions.reverse();

        for version in &sorted_versions {
            let is_current = version == CURRENT_VERSION;
            let marker = if is_current { " (installed)" } else { "" };
            let targets = version_map.get(version).cloned().unwrap_or_default();

            println!("  {}{}", version, marker);
            if !targets.is_empty() {
                println!("    Targets: {}", targets.join(", "));
            }
        }
    }

    println!();
    println!("Current version: {}", CURRENT_VERSION);
    println!();

    Ok(())
}

/// Compare two semantic version strings (e.g., "0.1.0" vs "0.2.1")
fn compare_versions(v1: &str, v2: &str) -> Ordering {
    // Strip leading 'v' if present
    let v1 = v1.strip_prefix('v').unwrap_or(v1);
    let v2 = v2.strip_prefix('v').unwrap_or(v2);

    let parts1: Vec<u64> = v1
        .split('.')
        .filter_map(|p| {
            // Handle pre-release suffixes like "1.0.0-alpha"
            let numeric = p.split('-').next().unwrap_or(p);
            numeric.parse().ok()
        })
        .collect();

    let parts2: Vec<u64> = v2
        .split('.')
        .filter_map(|p| {
            let numeric = p.split('-').next().unwrap_or(p);
            numeric.parse().ok()
        })
        .collect();

    let max_len = parts1.len().max(parts2.len());

    for i in 0..max_len {
        let p1 = parts1.get(i).copied().unwrap_or(0);
        let p2 = parts2.get(i).copied().unwrap_or(0);

        match p1.cmp(&p2) {
            Ordering::Equal => continue,
            other => return other,
        }
    }

    // If numeric parts are equal, check for pre-release suffixes
    // A version with a pre-release tag is considered less than one without
    let has_pre1 = v1.contains('-');
    let has_pre2 = v2.contains('-');

    match (has_pre1, has_pre2) {
        (true, false) => Ordering::Less,
        (false, true) => Ordering::Greater,
        _ => Ordering::Equal,
    }
}

/// Verify that the installed binary reports the expected version
fn verify_version(expected: &str) -> Result<bool> {
    use std::process::Command;

    let binary = installed_binary_path();
    if !binary.exists() {
        return Err(anyhow!("Binary not found at {}", binary.display()));
    }

    let output = Command::new(&binary)
        .arg("--version")
        .output()
        .with_context(|| format!("Failed to run {} --version", binary.display()))?;

    if !output.status.success() {
        return Err(anyhow!("Binary returned non-zero exit code"));
    }

    let version_output = String::from_utf8_lossy(&output.stdout);
    let version_output = version_output.trim();

    debug!("Version output: {}", version_output);

    // The output is typically "hydra-agent X.Y.Z" or just "X.Y.Z"
    Ok(version_output.contains(expected))
}

/// Build an HTTP client with the configured timeout
fn build_http_client(config: &AgentConfig) -> Result<Client> {
    Client::builder()
        .timeout(Duration::from_secs(config.api.timeout_seconds))
        .build()
        .context("Failed to create HTTP client")
}

/// Get the API key from the vault
fn get_api_key(vault: &Vault) -> Result<String> {
    vault
        .get_api_key()?
        .ok_or_else(|| anyhow!(
            "No API key available. Run 'hydra-agent register' first, or set HYDRA_API_KEY."
        ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compare_versions_basic() {
        assert_eq!(compare_versions("0.1.0", "0.1.0"), Ordering::Equal);
        assert_eq!(compare_versions("0.1.0", "0.2.0"), Ordering::Less);
        assert_eq!(compare_versions("0.2.0", "0.1.0"), Ordering::Greater);
        assert_eq!(compare_versions("1.0.0", "0.9.9"), Ordering::Greater);
        assert_eq!(compare_versions("0.1.1", "0.1.0"), Ordering::Greater);
    }

    #[test]
    fn test_compare_versions_with_prefix() {
        assert_eq!(compare_versions("v0.1.0", "0.1.0"), Ordering::Equal);
        assert_eq!(compare_versions("v1.0.0", "v0.9.0"), Ordering::Greater);
    }

    #[test]
    fn test_compare_versions_different_lengths() {
        assert_eq!(compare_versions("1.0", "1.0.0"), Ordering::Equal);
        assert_eq!(compare_versions("1.0.1", "1.0"), Ordering::Greater);
    }

    #[test]
    fn test_compare_versions_prerelease() {
        assert_eq!(compare_versions("1.0.0-alpha", "1.0.0"), Ordering::Less);
        assert_eq!(compare_versions("1.0.0", "1.0.0-beta"), Ordering::Greater);
    }

    #[test]
    fn test_detect_target_runs() {
        // Just verify it doesn't panic - actual value depends on platform
        let result = detect_target();
        assert!(result.is_ok());
        let target = result.unwrap();
        assert!(target.contains('-'), "Target should contain a dash: {}", target);
    }

    #[test]
    fn test_installed_binary_path() {
        let path = installed_binary_path();
        #[cfg(unix)]
        assert_eq!(path, PathBuf::from("/usr/local/bin/hydra-agent"));
        #[cfg(windows)]
        assert_eq!(path, PathBuf::from(r"C:\Program Files\Hydra\hydra-agent.exe"));
    }

    #[test]
    fn test_backup_binary_path() {
        let path = backup_binary_path();
        #[cfg(unix)]
        assert_eq!(path, PathBuf::from("/usr/local/bin/hydra-agent.backup"));
        #[cfg(windows)]
        assert_eq!(path, PathBuf::from(r"C:\Program Files\Hydra\hydra-agent.exe.backup"));
    }
}
