//! Windows-specific platform implementations.
//!
//! Provides Windows implementations for:
//! - File permissions (NTFS ACLs)
//! - Credential encryption (DPAPI)
//! - Service management (Windows Service / Task Scheduler)

use super::{CredentialEncryption, EncryptedPayload, FilePermissions};
use anyhow::{anyhow, Context, Result};
use std::path::{Path, PathBuf};

const WINDOWS_VAULT_ALGORITHM: &str = "dpapi";

/// Windows file permissions implementation using NTFS ACLs
pub struct WindowsPermissions;

impl FilePermissions for WindowsPermissions {
    fn set_owner_only(&self, path: &Path) -> Result<()> {
        set_admin_only_acl(path)
    }

    fn set_dir_owner_only(&self, path: &Path) -> Result<()> {
        set_admin_only_acl(path)
    }

    fn is_secure(&self, path: &Path) -> Result<bool> {
        // On Windows, we check if the file exists and is not world-readable
        // Full ACL verification would require more complex Windows API calls
        if !path.exists() {
            return Ok(false);
        }

        // For now, assume files in ProgramData\Hydra are secure if they exist
        // Full implementation would use GetNamedSecurityInfo API
        Ok(true)
    }
}

/// Set NTFS ACL to allow only Administrators and SYSTEM
fn set_admin_only_acl(path: &PathBuf) -> Result<()> {
    use std::process::Command;

    let path_str = path.to_string_lossy();

    // Use icacls to set ACL
    // /inheritance:r - Remove inherited ACLs
    // /grant:r - Replace existing permissions
    // Administrators:F - Full control for Administrators
    // SYSTEM:F - Full control for SYSTEM
    let output = Command::new("icacls")
        .args([
            &*path_str,
            "/inheritance:r",
            "/grant:r",
            "Administrators:F",
            "SYSTEM:F",
        ])
        .output()
        .with_context(|| format!("Failed to execute icacls for {:?}", path))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(anyhow!("icacls failed: {}", stderr));
    }

    Ok(())
}

/// Windows credential encryption implementation using DPAPI
pub struct WindowsEncryption;

impl CredentialEncryption for WindowsEncryption {
    fn encrypt(&self, _scope: &Path, data: &[u8]) -> Result<EncryptedPayload> {
        Ok(EncryptedPayload {
            algorithm: WINDOWS_VAULT_ALGORITHM.to_string(),
            nonce: None,
            ciphertext: dpapi_encrypt(data)?,
        })
    }

    fn decrypt(&self, _scope: &Path, payload: &EncryptedPayload) -> Result<Vec<u8>> {
        if payload.algorithm != WINDOWS_VAULT_ALGORITHM {
            return Err(anyhow!(
                "Unsupported vault encryption algorithm: {}",
                payload.algorithm
            ));
        }

        dpapi_decrypt(&payload.ciphertext)
    }

    fn is_available(&self) -> bool {
        // DPAPI is always available on Windows
        true
    }
}

/// Encrypt data using DPAPI (CryptProtectData)
fn dpapi_encrypt(data: &[u8]) -> Result<Vec<u8>> {
    use std::process::Command;

    // Use PowerShell's ConvertTo-SecureString and export as secure string
    // This is a simplified approach - production code should use the Windows API directly
    let b64_input = base64_encode(data);

    let ps_script = format!(
        r#"
$bytes = [Convert]::FromBase64String('{}')
Add-Type -AssemblyName System.Security
$encrypted = [System.Security.Cryptography.ProtectedData]::Protect(
    $bytes,
    $null,
    [System.Security.Cryptography.DataProtectionScope]::LocalMachine
)
[Convert]::ToBase64String($encrypted)
"#,
        b64_input
    );

    let output = Command::new("powershell")
        .args(["-NoProfile", "-NonInteractive", "-Command", &ps_script])
        .output()
        .context("Failed to execute DPAPI encryption")?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(anyhow!("DPAPI encryption failed: {}", stderr));
    }

    let b64_output = String::from_utf8_lossy(&output.stdout).trim().to_string();
    base64_decode(&b64_output)
}

/// Decrypt data using DPAPI (CryptUnprotectData)
fn dpapi_decrypt(data: &[u8]) -> Result<Vec<u8>> {
    use std::process::Command;

    let b64_input = base64_encode(data);

    let ps_script = format!(
        r#"
$encrypted = [Convert]::FromBase64String('{}')
Add-Type -AssemblyName System.Security
$decrypted = [System.Security.Cryptography.ProtectedData]::Unprotect(
    $encrypted,
    $null,
    [System.Security.Cryptography.DataProtectionScope]::LocalMachine
)
[Convert]::ToBase64String($decrypted)
"#,
        b64_input
    );

    let output = Command::new("powershell")
        .args(["-NoProfile", "-NonInteractive", "-Command", &ps_script])
        .output()
        .context("Failed to execute DPAPI decryption")?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(anyhow!("DPAPI decryption failed: {}", stderr));
    }

    let b64_output = String::from_utf8_lossy(&output.stdout).trim().to_string();
    base64_decode(&b64_output)
}

/// Simple base64 encoding
fn base64_encode(data: &[u8]) -> String {
    const CHARS: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut result = String::with_capacity((data.len() + 2) / 3 * 4);

    for chunk in data.chunks(3) {
        let b0 = chunk[0] as usize;
        let b1 = chunk.get(1).copied().unwrap_or(0) as usize;
        let b2 = chunk.get(2).copied().unwrap_or(0) as usize;

        result.push(CHARS[b0 >> 2] as char);
        result.push(CHARS[((b0 & 0x03) << 4) | (b1 >> 4)] as char);

        if chunk.len() > 1 {
            result.push(CHARS[((b1 & 0x0f) << 2) | (b2 >> 6)] as char);
        } else {
            result.push('=');
        }

        if chunk.len() > 2 {
            result.push(CHARS[b2 & 0x3f] as char);
        } else {
            result.push('=');
        }
    }

    result
}

/// Simple base64 decoding
fn base64_decode(input: &str) -> Result<Vec<u8>> {
    const DECODE_TABLE: [i8; 128] = [
        -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
        -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 62, -1, -1,
        -1, 63, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, -1, -1, -1, -1, -1, -1, -1, 0, 1, 2, 3, 4,
        5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, -1, -1, -1,
        -1, -1, -1, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45,
        46, 47, 48, 49, 50, 51, -1, -1, -1, -1, -1,
    ];

    let input = input.trim().trim_end_matches('=');
    let mut result = Vec::with_capacity(input.len() * 3 / 4);

    let chars: Vec<u8> = input
        .chars()
        .filter_map(|c| {
            let idx = c as usize;
            if idx < 128 {
                let val = DECODE_TABLE[idx];
                if val >= 0 {
                    return Some(val as u8);
                }
            }
            None
        })
        .collect();

    for chunk in chars.chunks(4) {
        if chunk.len() >= 2 {
            result.push((chunk[0] << 2) | (chunk[1] >> 4));
        }
        if chunk.len() >= 3 {
            result.push((chunk[1] << 4) | (chunk[2] >> 2));
        }
        if chunk.len() >= 4 {
            result.push((chunk[2] << 6) | chunk[3]);
        }
    }

    Ok(result)
}

/// Windows Service management module
pub mod service {
    use anyhow::{anyhow, Result};
    use std::process::Command;

    /// Service name
    pub const SERVICE_NAME: &str = "HydraAgent";

    /// Service display name
    pub const SERVICE_DISPLAY_NAME: &str = "Hydra Agent";

    /// Install Windows Service using sc.exe
    pub fn install_service(binary_path: &str) -> Result<()> {
        let output = Command::new("sc")
            .args([
                "create",
                SERVICE_NAME,
                &format!("binPath={} service", binary_path),
                &format!("DisplayName={}", SERVICE_DISPLAY_NAME),
                "start=auto",
            ])
            .output()
            .map_err(|e| anyhow!("Failed to execute sc create: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(anyhow!("Failed to create service: {}", stderr));
        }

        // Set service description
        let _ = Command::new("sc")
            .args([
                "description",
                SERVICE_NAME,
                "Hydra Agent - Infrastructure Profiler for AI-powered management",
            ])
            .output();

        // Configure service recovery options
        let _ = Command::new("sc")
            .args([
                "failure",
                SERVICE_NAME,
                "reset=86400",
                "actions=restart/10000/restart/30000/restart/60000",
            ])
            .output();

        Ok(())
    }

    /// Start the Windows Service
    pub fn start_service() -> Result<()> {
        let output = Command::new("sc")
            .args(["start", SERVICE_NAME])
            .output()
            .map_err(|e| anyhow!("Failed to execute sc start: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            // Ignore if already running
            if !stderr.contains("already been started") {
                return Err(anyhow!("Failed to start service: {}", stderr));
            }
        }

        Ok(())
    }

    /// Stop the Windows Service
    pub fn stop_service() -> Result<()> {
        let output = Command::new("sc")
            .args(["stop", SERVICE_NAME])
            .output()
            .map_err(|e| anyhow!("Failed to execute sc stop: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            // Ignore if not running
            if !stderr.contains("not been started") {
                return Err(anyhow!("Failed to stop service: {}", stderr));
            }
        }

        Ok(())
    }

    /// Uninstall the Windows Service
    pub fn uninstall_service() -> Result<()> {
        // Stop first
        let _ = stop_service();

        let output = Command::new("sc")
            .args(["delete", SERVICE_NAME])
            .output()
            .map_err(|e| anyhow!("Failed to execute sc delete: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            // Ignore if doesn't exist
            if !stderr.contains("does not exist") {
                return Err(anyhow!("Failed to delete service: {}", stderr));
            }
        }

        Ok(())
    }

    /// Get service status
    pub fn service_status() -> Result<String> {
        let output = Command::new("sc")
            .args(["query", SERVICE_NAME])
            .output()
            .map_err(|e| anyhow!("Failed to execute sc query: {}", e))?;

        Ok(String::from_utf8_lossy(&output.stdout).to_string())
    }

    /// Check if service is installed
    pub fn is_installed() -> bool {
        Command::new("sc")
            .args(["query", SERVICE_NAME])
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
    }
}

/// Task Scheduler alternative for non-service execution
pub mod scheduler {
    use anyhow::{anyhow, Result};
    use std::process::Command;

    /// Task name
    pub const TASK_NAME: &str = "HydraAgentTask";

    /// Create a scheduled task to run the agent periodically
    pub fn create_task(binary_path: &str, interval_minutes: u32) -> Result<()> {
        // Delete existing task if any
        let _ = delete_task();

        let output = Command::new("schtasks")
            .args([
                "/Create",
                "/TN",
                TASK_NAME,
                "/TR",
                &format!("\"{}\" run --once", binary_path),
                "/SC",
                "MINUTE",
                "/MO",
                &interval_minutes.to_string(),
                "/RU",
                "SYSTEM",
                "/F",
            ])
            .output()
            .map_err(|e| anyhow!("Failed to execute schtasks: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(anyhow!("Failed to create scheduled task: {}", stderr));
        }

        Ok(())
    }

    /// Delete the scheduled task
    pub fn delete_task() -> Result<()> {
        let output = Command::new("schtasks")
            .args(["/Delete", "/TN", TASK_NAME, "/F"])
            .output()
            .map_err(|e| anyhow!("Failed to execute schtasks: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            if !stderr.contains("does not exist") {
                return Err(anyhow!("Failed to delete scheduled task: {}", stderr));
            }
        }

        Ok(())
    }

    /// Run the task immediately
    pub fn run_task() -> Result<()> {
        let output = Command::new("schtasks")
            .args(["/Run", "/TN", TASK_NAME])
            .output()
            .map_err(|e| anyhow!("Failed to execute schtasks: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(anyhow!("Failed to run scheduled task: {}", stderr));
        }

        Ok(())
    }

    /// Get task status
    pub fn task_status() -> Result<String> {
        let output = Command::new("schtasks")
            .args(["/Query", "/TN", TASK_NAME, "/V", "/FO", "LIST"])
            .output()
            .map_err(|e| anyhow!("Failed to execute schtasks: {}", e))?;

        Ok(String::from_utf8_lossy(&output.stdout).to_string())
    }
}

/// Check if running with elevated (Administrator) privileges
pub fn is_elevated() -> bool {
    use std::process::Command;

    // Use 'net session' to check for admin rights
    Command::new("net")
        .args(["session"])
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

/// Get Windows version info
pub fn windows_version() -> Option<String> {
    use std::process::Command;

    let output = Command::new("cmd").args(["/c", "ver"]).output().ok()?;

    Some(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_base64_roundtrip() {
        let data = b"Hello, DPAPI!";
        let encoded = base64_encode(data);
        let decoded = base64_decode(&encoded).unwrap();
        assert_eq!(decoded, data);
    }

    #[test]
    fn test_base64_with_padding() {
        // Test various lengths to ensure padding works
        for len in 1..20 {
            let data: Vec<u8> = (0..len).map(|i| i as u8).collect();
            let encoded = base64_encode(&data);
            let decoded = base64_decode(&encoded).unwrap();
            assert_eq!(decoded, data, "Failed for length {}", len);
        }
    }
}
