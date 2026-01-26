//! Platform-specific path resolution for Hydra Agent.
//!
//! Path mappings:
//! | Purpose       | Unix                        | Windows                           |
//! |---------------|-----------------------------|------------------------------------|
//! | Config        | /etc/hydra/agent.toml       | C:\ProgramData\Hydra\agent.toml   |
//! | Vault         | /var/cv/hydra/              | C:\ProgramData\Hydra\vault\       |
//! | Logs          | /var/log/hydra/             | C:\ProgramData\Hydra\logs\        |
//! | Binary        | /usr/local/bin/             | C:\Program Files\Hydra Agent\     |

use std::path::PathBuf;

/// Default paths for Unix systems
#[cfg(unix)]
pub mod defaults {
    /// Default config file path
    pub const CONFIG_FILE: &str = "/etc/hydra/agent.toml";

    /// Default config directory
    pub const CONFIG_DIR: &str = "/etc/hydra";

    /// Default vault directory (credentials stored here via vault module)
    pub const VAULT_DIR: &str = "/var/cv/hydra";

    /// Default log directory
    pub const LOG_DIR: &str = "/var/log/hydra";

    /// Default binary directory
    pub const BIN_DIR: &str = "/usr/local/bin";
}

/// Default paths for Windows systems
#[cfg(windows)]
pub mod defaults {
    /// Default config file path
    pub const CONFIG_FILE: &str = r"C:\ProgramData\Hydra\agent.toml";

    /// Default config directory
    pub const CONFIG_DIR: &str = r"C:\ProgramData\Hydra";

    /// Default vault directory (credentials stored here via vault module)
    pub const VAULT_DIR: &str = r"C:\ProgramData\Hydra\vault";

    /// Default log directory
    pub const LOG_DIR: &str = r"C:\ProgramData\Hydra\logs";

    /// Default binary directory
    pub const BIN_DIR: &str = r"C:\Program Files\Hydra Agent";
}

/// Paths structure for runtime path resolution
#[derive(Debug, Clone)]
pub struct Paths {
    /// Configuration file path
    pub config_file: PathBuf,

    /// Configuration directory
    pub config_dir: PathBuf,

    /// Vault directory for credentials (managed by vault module)
    pub vault_dir: PathBuf,

    /// Log directory
    pub log_dir: PathBuf,

    /// Binary installation directory
    pub bin_dir: PathBuf,
}

impl Default for Paths {
    fn default() -> Self {
        Self::system_defaults()
    }
}

impl Paths {
    /// Get system default paths for the current platform
    pub fn system_defaults() -> Self {
        Self {
            config_file: PathBuf::from(defaults::CONFIG_FILE),
            config_dir: PathBuf::from(defaults::CONFIG_DIR),
            vault_dir: PathBuf::from(defaults::VAULT_DIR),
            log_dir: PathBuf::from(defaults::LOG_DIR),
            bin_dir: PathBuf::from(defaults::BIN_DIR),
        }
    }

    /// Create paths with a custom base directory (useful for testing)
    pub fn with_base_dir(base: &PathBuf) -> Self {
        Self {
            config_file: base.join("agent.toml"),
            config_dir: base.clone(),
            vault_dir: base.join("vault"),
            log_dir: base.join("logs"),
            bin_dir: base.join("bin"),
        }
    }

    /// Get the vault file path for a specific file
    pub fn vault_file(&self, filename: &str) -> PathBuf {
        self.vault_dir.join(filename)
    }

    /// Get the log file path for a specific log
    pub fn log_file(&self, filename: &str) -> PathBuf {
        self.log_dir.join(filename)
    }

    /// Get the binary path
    pub fn binary(&self, name: &str) -> PathBuf {
        #[cfg(windows)]
        {
            self.bin_dir.join(format!("{}.exe", name))
        }

        #[cfg(not(windows))]
        {
            self.bin_dir.join(name)
        }
    }
}

/// Get the default config file path for the current platform
pub fn default_config_file() -> PathBuf {
    PathBuf::from(defaults::CONFIG_FILE)
}

/// Get the default config directory for the current platform
pub fn default_config_dir() -> PathBuf {
    PathBuf::from(defaults::CONFIG_DIR)
}

/// Get the default vault directory for the current platform
pub fn default_vault_dir() -> PathBuf {
    PathBuf::from(defaults::VAULT_DIR)
}

/// Get the default log directory for the current platform
pub fn default_log_dir() -> PathBuf {
    PathBuf::from(defaults::LOG_DIR)
}

/// Get the default binary directory for the current platform
pub fn default_bin_dir() -> PathBuf {
    PathBuf::from(defaults::BIN_DIR)
}

/// Resolve a path that may contain environment variables or special prefixes
pub fn resolve_path(path: &str) -> PathBuf {
    // Handle home directory expansion
    if path.starts_with("~/") {
        if let Some(home) = dirs::home_dir() {
            return home.join(&path[2..]);
        }
    }

    // Handle environment variable expansion
    #[cfg(unix)]
    if path.starts_with('$') {
        if let Some(pos) = path.find('/') {
            let var_name = &path[1..pos];
            if let Ok(value) = std::env::var(var_name) {
                return PathBuf::from(value).join(&path[pos + 1..]);
            }
        }
    }

    #[cfg(windows)]
    if path.starts_with('%') {
        if let Some(end) = path[1..].find('%') {
            let var_name = &path[1..end + 1];
            if let Ok(value) = std::env::var(var_name) {
                return PathBuf::from(value).join(&path[end + 2..]);
            }
        }
    }

    PathBuf::from(path)
}

/// Platform-specific home directory resolution.
mod dirs {
    use std::path::PathBuf;

    pub fn home_dir() -> Option<PathBuf> {
        #[cfg(unix)]
        {
            std::env::var("HOME").ok().map(PathBuf::from)
        }

        #[cfg(windows)]
        {
            std::env::var("USERPROFILE").ok().map(PathBuf::from)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_paths() {
        let paths = Paths::system_defaults();

        #[cfg(unix)]
        {
            assert!(paths.config_file.to_string_lossy().contains("/etc/hydra"));
            assert!(paths.vault_dir.to_string_lossy().contains("/var/cv/hydra"));
        }

        #[cfg(windows)]
        {
            assert!(paths.config_file.to_string_lossy().contains("ProgramData"));
            assert!(paths.vault_dir.to_string_lossy().contains("vault"));
        }
    }

    #[test]
    fn test_custom_base_dir() {
        let base = PathBuf::from("/tmp/hydra-test");
        let paths = Paths::with_base_dir(&base);

        assert_eq!(paths.config_file, base.join("agent.toml"));
        assert_eq!(paths.vault_dir, base.join("vault"));
    }

    #[test]
    fn test_vault_file() {
        let paths = Paths::system_defaults();
        let creds = paths.vault_file(".creds");

        #[cfg(unix)]
        assert_eq!(creds, PathBuf::from("/var/cv/hydra/.creds"));

        #[cfg(windows)]
        assert!(creds.to_string_lossy().contains("vault"));
    }
}
