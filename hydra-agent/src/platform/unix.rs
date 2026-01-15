//! Unix-specific platform implementations.
//!
//! Provides Unix implementations for:
//! - File permissions (chmod)
//! - Credential encryption (file-based security)
//! - Service management (systemd)

use super::{CredentialEncryption, FilePermissions};
use anyhow::{Context, Result};
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;

/// Unix file permissions implementation
pub struct UnixPermissions;

impl FilePermissions for UnixPermissions {
    fn set_owner_only(&self, path: &PathBuf) -> Result<()> {
        fs::set_permissions(path, fs::Permissions::from_mode(0o600))
            .with_context(|| format!("Failed to set permissions 0600 on {:?}", path))?;
        Ok(())
    }

    fn set_dir_owner_only(&self, path: &PathBuf) -> Result<()> {
        fs::set_permissions(path, fs::Permissions::from_mode(0o700))
            .with_context(|| format!("Failed to set permissions 0700 on {:?}", path))?;
        Ok(())
    }

    fn is_secure(&self, path: &PathBuf) -> Result<bool> {
        let metadata = fs::metadata(path)
            .with_context(|| format!("Failed to get metadata for {:?}", path))?;
        let mode = metadata.permissions().mode();

        // Check if file is only accessible by owner (mode & 0o077 should be 0)
        Ok((mode & 0o077) == 0)
    }
}

/// Unix credential encryption implementation.
/// On Unix, we rely on file permissions for security rather than encryption.
/// The vault files are stored with 0600 permissions.
pub struct UnixEncryption;

impl CredentialEncryption for UnixEncryption {
    fn encrypt(&self, data: &[u8]) -> Result<Vec<u8>> {
        // On Unix, we don't encrypt - we rely on file permissions
        // Just return the data as-is (the vault handles secure storage)
        Ok(data.to_vec())
    }

    fn decrypt(&self, data: &[u8]) -> Result<Vec<u8>> {
        // On Unix, no decryption needed
        Ok(data.to_vec())
    }

    fn is_available(&self) -> bool {
        // Unix file-based security is always available
        true
    }
}

/// Systemd service management
#[cfg(target_os = "linux")]
pub mod systemd {
    use anyhow::{anyhow, Result};
    use std::process::Command;

    /// Unit file template for hydra-agent
    pub const UNIT_FILE_TEMPLATE: &str = r#"[Unit]
Description=Hydra Agent - Infrastructure Profiler
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/hydra-agent run
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=hydra-agent

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/cv/hydra /var/log/hydra
PrivateTmp=true

[Install]
WantedBy=multi-user.target
"#;

    /// Install systemd service unit
    pub fn install_service() -> Result<()> {
        let unit_path = "/etc/systemd/system/hydra-agent.service";

        std::fs::write(unit_path, UNIT_FILE_TEMPLATE)
            .map_err(|e| anyhow!("Failed to write unit file: {}", e))?;

        // Reload systemd
        Command::new("systemctl")
            .args(["daemon-reload"])
            .status()
            .map_err(|e| anyhow!("Failed to reload systemd: {}", e))?;

        Ok(())
    }

    /// Enable and start the service
    pub fn enable_service() -> Result<()> {
        Command::new("systemctl")
            .args(["enable", "hydra-agent"])
            .status()
            .map_err(|e| anyhow!("Failed to enable service: {}", e))?;

        Command::new("systemctl")
            .args(["start", "hydra-agent"])
            .status()
            .map_err(|e| anyhow!("Failed to start service: {}", e))?;

        Ok(())
    }

    /// Stop and disable the service
    pub fn disable_service() -> Result<()> {
        let _ = Command::new("systemctl")
            .args(["stop", "hydra-agent"])
            .status();

        let _ = Command::new("systemctl")
            .args(["disable", "hydra-agent"])
            .status();

        Ok(())
    }

    /// Uninstall the service
    pub fn uninstall_service() -> Result<()> {
        disable_service()?;

        let unit_path = "/etc/systemd/system/hydra-agent.service";
        if std::path::Path::new(unit_path).exists() {
            std::fs::remove_file(unit_path)
                .map_err(|e| anyhow!("Failed to remove unit file: {}", e))?;
        }

        // Reload systemd
        Command::new("systemctl")
            .args(["daemon-reload"])
            .status()
            .map_err(|e| anyhow!("Failed to reload systemd: {}", e))?;

        Ok(())
    }

    /// Get service status
    pub fn service_status() -> Result<String> {
        let output = Command::new("systemctl")
            .args(["status", "hydra-agent"])
            .output()
            .map_err(|e| anyhow!("Failed to get service status: {}", e))?;

        Ok(String::from_utf8_lossy(&output.stdout).to_string())
    }
}

/// Launchd service management for macOS
#[cfg(target_os = "macos")]
pub mod launchd {
    use anyhow::{anyhow, Result};
    use std::process::Command;

    /// Plist template for hydra-agent
    pub const PLIST_TEMPLATE: &str = r#"<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.hydra.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/hydra-agent</string>
        <string>run</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>/var/log/hydra/agent.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/hydra/agent.error.log</string>
</dict>
</plist>
"#;

    /// Install launchd service
    pub fn install_service() -> Result<()> {
        let plist_path = "/Library/LaunchDaemons/com.hydra.agent.plist";

        std::fs::write(plist_path, PLIST_TEMPLATE)
            .map_err(|e| anyhow!("Failed to write plist file: {}", e))?;

        Ok(())
    }

    /// Load and start the service
    pub fn enable_service() -> Result<()> {
        let plist_path = "/Library/LaunchDaemons/com.hydra.agent.plist";

        Command::new("launchctl")
            .args(["load", plist_path])
            .status()
            .map_err(|e| anyhow!("Failed to load service: {}", e))?;

        Ok(())
    }

    /// Unload and stop the service
    pub fn disable_service() -> Result<()> {
        let plist_path = "/Library/LaunchDaemons/com.hydra.agent.plist";

        let _ = Command::new("launchctl")
            .args(["unload", plist_path])
            .status();

        Ok(())
    }

    /// Uninstall the service
    pub fn uninstall_service() -> Result<()> {
        disable_service()?;

        let plist_path = "/Library/LaunchDaemons/com.hydra.agent.plist";
        if std::path::Path::new(plist_path).exists() {
            std::fs::remove_file(plist_path)
                .map_err(|e| anyhow!("Failed to remove plist file: {}", e))?;
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn test_unix_permissions() {
        let temp_dir = TempDir::new().unwrap();
        let test_file = temp_dir.path().join("test.txt");
        std::fs::write(&test_file, "test").unwrap();

        let perms = UnixPermissions;
        perms.set_owner_only(&test_file).unwrap();

        let metadata = std::fs::metadata(&test_file).unwrap();
        let mode = metadata.permissions().mode();
        assert_eq!(mode & 0o777, 0o600);
    }

    #[test]
    fn test_unix_encryption() {
        let enc = UnixEncryption;
        let data = b"secret data";

        let encrypted = enc.encrypt(data).unwrap();
        let decrypted = enc.decrypt(&encrypted).unwrap();

        assert_eq!(decrypted, data);
    }

    #[test]
    fn test_is_secure() {
        let temp_dir = TempDir::new().unwrap();
        let test_file = temp_dir.path().join("secure.txt");
        std::fs::write(&test_file, "test").unwrap();

        let perms = UnixPermissions;

        // Set to insecure (world readable)
        std::fs::set_permissions(&test_file, std::fs::Permissions::from_mode(0o644)).unwrap();
        assert!(!perms.is_secure(&test_file).unwrap());

        // Set to secure (owner only)
        perms.set_owner_only(&test_file).unwrap();
        assert!(perms.is_secure(&test_file).unwrap());
    }
}
