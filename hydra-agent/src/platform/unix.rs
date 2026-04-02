//! Unix-specific platform implementations.
//!
//! Provides Unix implementations for:
//! - File permissions (chmod)
//! - Credential encryption (AES-GCM with a local vault master key)
//! - Service management (systemd)

use super::{CredentialEncryption, EncryptedPayload, FilePermissions};
use aes_gcm::aead::Aead;
use aes_gcm::{Aes256Gcm, KeyInit, Nonce};
use anyhow::{anyhow, Context, Result};
use rand::random;
use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

const AES_GCM_KEY_LEN: usize = 32;
const AES_GCM_NONCE_LEN: usize = 12;
const UNIX_VAULT_ALGORITHM: &str = "aes-256-gcm";
pub const VAULT_MASTER_KEY_FILE: &str = ".vault-key";

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
        let metadata =
            fs::metadata(path).with_context(|| format!("Failed to get metadata for {:?}", path))?;
        let mode = metadata.permissions().mode();

        // Check if file is only accessible by owner (mode & 0o077 should be 0)
        Ok((mode & 0o077) == 0)
    }
}

fn master_key_path(scope: &Path) -> PathBuf {
    scope.join(VAULT_MASTER_KEY_FILE)
}

fn write_master_key(scope: &Path, key: &[u8; AES_GCM_KEY_LEN]) -> Result<()> {
    let key_path = master_key_path(scope);
    fs::write(&key_path, key)
        .with_context(|| format!("Failed to write vault master key: {}", key_path.display()))?;
    fs::set_permissions(&key_path, fs::Permissions::from_mode(0o600))
        .with_context(|| format!("Failed to secure vault master key: {}", key_path.display()))?;
    Ok(())
}

fn read_master_key(scope: &Path) -> Result<[u8; AES_GCM_KEY_LEN]> {
    let key_path = master_key_path(scope);
    let key = fs::read(&key_path)
        .with_context(|| format!("Failed to read vault master key: {}", key_path.display()))?;
    if key.len() != AES_GCM_KEY_LEN {
        return Err(anyhow!(
            "Invalid vault master key at {}",
            key_path.display()
        ));
    }

    fs::set_permissions(&key_path, fs::Permissions::from_mode(0o600))
        .with_context(|| format!("Failed to secure vault master key: {}", key_path.display()))?;

    let mut key_bytes = [0u8; AES_GCM_KEY_LEN];
    key_bytes.copy_from_slice(&key);
    Ok(key_bytes)
}

fn load_or_create_master_key(scope: &Path) -> Result<[u8; AES_GCM_KEY_LEN]> {
    let key_path = master_key_path(scope);
    if key_path.exists() {
        return read_master_key(scope);
    }

    fs::create_dir_all(scope)
        .with_context(|| format!("Failed to create vault directory: {}", scope.display()))?;
    fs::set_permissions(scope, fs::Permissions::from_mode(0o700))
        .with_context(|| format!("Failed to secure vault directory: {}", scope.display()))?;

    let key_bytes: [u8; AES_GCM_KEY_LEN] = random();
    write_master_key(scope, &key_bytes)?;
    Ok(key_bytes)
}

/// Unix credential encryption implementation using AES-256-GCM.
pub struct UnixEncryption;

impl CredentialEncryption for UnixEncryption {
    fn encrypt(&self, scope: &Path, data: &[u8]) -> Result<EncryptedPayload> {
        let key = load_or_create_master_key(scope)?;
        let cipher = Aes256Gcm::new_from_slice(&key)
            .map_err(|err| anyhow!("Failed to initialize vault cipher: {}", err))?;
        let nonce_bytes: [u8; AES_GCM_NONCE_LEN] = random();
        let nonce = Nonce::from_slice(&nonce_bytes);
        let ciphertext = cipher
            .encrypt(nonce, data)
            .map_err(|_| anyhow!("Failed to encrypt vault data"))?;

        Ok(EncryptedPayload {
            algorithm: UNIX_VAULT_ALGORITHM.to_string(),
            nonce: Some(nonce_bytes.to_vec()),
            ciphertext,
        })
    }

    fn decrypt(&self, scope: &Path, payload: &EncryptedPayload) -> Result<Vec<u8>> {
        if payload.algorithm != UNIX_VAULT_ALGORITHM {
            return Err(anyhow!(
                "Unsupported vault encryption algorithm: {}",
                payload.algorithm
            ));
        }

        let nonce_bytes = payload
            .nonce
            .as_ref()
            .ok_or_else(|| anyhow!("Missing AES-GCM nonce in vault payload"))?;
        if nonce_bytes.len() != AES_GCM_NONCE_LEN {
            return Err(anyhow!("Invalid AES-GCM nonce length in vault payload"));
        }

        let key = read_master_key(scope)?;
        let cipher = Aes256Gcm::new_from_slice(&key)
            .map_err(|err| anyhow!("Failed to initialize vault cipher: {}", err))?;
        let nonce = Nonce::from_slice(nonce_bytes);
        cipher
            .decrypt(nonce, payload.ciphertext.as_ref())
            .map_err(|_| anyhow!("Failed to decrypt vault data"))
    }

    fn is_available(&self) -> bool {
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
        let temp_dir = TempDir::new().unwrap();
        let enc = UnixEncryption;
        let data = b"secret data";

        let encrypted = enc.encrypt(temp_dir.path(), data).unwrap();
        let key_path = temp_dir.path().join(VAULT_MASTER_KEY_FILE);

        assert_eq!(encrypted.algorithm, UNIX_VAULT_ALGORITHM);
        assert_eq!(
            encrypted.nonce.as_ref().map(Vec::len),
            Some(AES_GCM_NONCE_LEN)
        );
        assert_ne!(encrypted.ciphertext, data);
        assert!(key_path.exists());

        let metadata = std::fs::metadata(&key_path).unwrap();
        let mode = metadata.permissions().mode();
        assert_eq!(mode & 0o777, 0o600);

        let decrypted = enc.decrypt(temp_dir.path(), &encrypted).unwrap();

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
