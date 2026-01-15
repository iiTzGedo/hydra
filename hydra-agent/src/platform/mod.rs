//! Platform abstraction module for cross-platform support.
//!
//! This module provides platform-specific implementations for:
//! - Path resolution (config, vault, logs, binaries)
//! - File permissions and ACLs
//! - Service management
//! - Credential encryption

pub mod paths;

#[cfg(unix)]
pub mod unix;

#[cfg(windows)]
pub mod windows;

use std::path::PathBuf;

/// Current platform identifier
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Platform {
    Linux,
    MacOS,
    Windows,
    FreeBSD,
    OpenBSD,
    NetBSD,
    Unknown,
}

impl Platform {
    /// Detect the current platform at compile time
    pub const fn current() -> Self {
        #[cfg(target_os = "linux")]
        return Platform::Linux;

        #[cfg(target_os = "macos")]
        return Platform::MacOS;

        #[cfg(target_os = "windows")]
        return Platform::Windows;

        #[cfg(target_os = "freebsd")]
        return Platform::FreeBSD;

        #[cfg(target_os = "openbsd")]
        return Platform::OpenBSD;

        #[cfg(target_os = "netbsd")]
        return Platform::NetBSD;

        #[cfg(not(any(
            target_os = "linux",
            target_os = "macos",
            target_os = "windows",
            target_os = "freebsd",
            target_os = "openbsd",
            target_os = "netbsd"
        )))]
        return Platform::Unknown;
    }

    /// Check if running on a Unix-like system
    pub const fn is_unix(&self) -> bool {
        matches!(
            self,
            Platform::Linux
                | Platform::MacOS
                | Platform::FreeBSD
                | Platform::OpenBSD
                | Platform::NetBSD
        )
    }

    /// Check if running on Windows
    pub const fn is_windows(&self) -> bool {
        matches!(self, Platform::Windows)
    }

    /// Get platform name as string
    pub const fn name(&self) -> &'static str {
        match self {
            Platform::Linux => "linux",
            Platform::MacOS => "macos",
            Platform::Windows => "windows",
            Platform::FreeBSD => "freebsd",
            Platform::OpenBSD => "openbsd",
            Platform::NetBSD => "netbsd",
            Platform::Unknown => "unknown",
        }
    }
}

impl std::fmt::Display for Platform {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.name())
    }
}

/// Trait for platform-specific file permission handling
pub trait FilePermissions {
    /// Set file to be readable/writable only by owner (Unix: 0600, Windows: ACL)
    fn set_owner_only(&self, path: &PathBuf) -> anyhow::Result<()>;

    /// Set directory to be accessible only by owner (Unix: 0700, Windows: ACL)
    fn set_dir_owner_only(&self, path: &PathBuf) -> anyhow::Result<()>;

    /// Check if file has secure permissions
    fn is_secure(&self, path: &PathBuf) -> anyhow::Result<bool>;
}

/// Get the appropriate FilePermissions implementation for the current platform
pub fn permissions() -> Box<dyn FilePermissions> {
    #[cfg(unix)]
    {
        Box::new(unix::UnixPermissions)
    }

    #[cfg(windows)]
    {
        Box::new(windows::WindowsPermissions)
    }
}

/// Trait for platform-specific credential encryption
pub trait CredentialEncryption {
    /// Encrypt data using platform-specific method (Unix: file perms, Windows: DPAPI)
    fn encrypt(&self, data: &[u8]) -> anyhow::Result<Vec<u8>>;

    /// Decrypt data using platform-specific method
    fn decrypt(&self, data: &[u8]) -> anyhow::Result<Vec<u8>>;

    /// Check if encryption is available
    fn is_available(&self) -> bool;
}

/// Get the appropriate CredentialEncryption implementation for the current platform
pub fn encryption() -> Box<dyn CredentialEncryption> {
    #[cfg(unix)]
    {
        Box::new(unix::UnixEncryption)
    }

    #[cfg(windows)]
    {
        Box::new(windows::WindowsEncryption)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_platform_detection() {
        let platform = Platform::current();
        assert_ne!(platform, Platform::Unknown);

        #[cfg(target_os = "linux")]
        assert_eq!(platform, Platform::Linux);

        #[cfg(target_os = "macos")]
        assert_eq!(platform, Platform::MacOS);

        #[cfg(target_os = "windows")]
        assert_eq!(platform, Platform::Windows);
    }

    #[test]
    fn test_platform_classification() {
        let platform = Platform::current();

        #[cfg(unix)]
        assert!(platform.is_unix());

        #[cfg(windows)]
        assert!(platform.is_windows());
    }
}
