//! Tests for platform abstraction module.
//!
//! Tests cover:
//! - Platform detection
//! - Path resolution (default paths, custom paths)
//! - File permissions (platform-specific)
//! - Home directory expansion

use hydra_agent::platform::{paths, Platform};
use std::path::PathBuf;

// =============================================================================
// Platform Detection Tests
// =============================================================================

#[test]
fn test_platform_current_not_unknown() {
    let platform = Platform::current();
    assert_ne!(platform, Platform::Unknown, "Platform should be detected");
}

#[test]
#[cfg(target_os = "linux")]
fn test_platform_is_linux() {
    assert_eq!(Platform::current(), Platform::Linux);
}

#[test]
#[cfg(target_os = "macos")]
fn test_platform_is_macos() {
    assert_eq!(Platform::current(), Platform::MacOS);
}

#[test]
#[cfg(target_os = "windows")]
fn test_platform_is_windows() {
    assert_eq!(Platform::current(), Platform::Windows);
}

#[test]
#[cfg(target_os = "freebsd")]
fn test_platform_is_freebsd() {
    assert_eq!(Platform::current(), Platform::FreeBSD);
}

// =============================================================================
// Platform Classification Tests
// =============================================================================

#[test]
fn test_platform_is_unix() {
    #[cfg(unix)]
    {
        let platform = Platform::current();
        assert!(
            platform.is_unix(),
            "Unix platform should report is_unix() = true"
        );
        assert!(
            !platform.is_windows(),
            "Unix platform should report is_windows() = false"
        );
    }
}

#[test]
fn test_platform_is_windows_check() {
    #[cfg(windows)]
    {
        let platform = Platform::current();
        assert!(
            platform.is_windows(),
            "Windows platform should report is_windows() = true"
        );
        assert!(
            !platform.is_unix(),
            "Windows platform should report is_unix() = false"
        );
    }
}

#[test]
fn test_linux_is_unix() {
    assert!(Platform::Linux.is_unix());
    assert!(!Platform::Linux.is_windows());
}

#[test]
fn test_macos_is_unix() {
    assert!(Platform::MacOS.is_unix());
    assert!(!Platform::MacOS.is_windows());
}

#[test]
fn test_windows_is_not_unix() {
    assert!(!Platform::Windows.is_unix());
    assert!(Platform::Windows.is_windows());
}

#[test]
fn test_freebsd_is_unix() {
    assert!(Platform::FreeBSD.is_unix());
    assert!(!Platform::FreeBSD.is_windows());
}

#[test]
fn test_openbsd_is_unix() {
    assert!(Platform::OpenBSD.is_unix());
    assert!(!Platform::OpenBSD.is_windows());
}

#[test]
fn test_netbsd_is_unix() {
    assert!(Platform::NetBSD.is_unix());
    assert!(!Platform::NetBSD.is_windows());
}

#[test]
fn test_unknown_is_neither() {
    assert!(!Platform::Unknown.is_unix());
    assert!(!Platform::Unknown.is_windows());
}

// =============================================================================
// Platform Name Tests
// =============================================================================

#[test]
fn test_platform_names() {
    assert_eq!(Platform::Linux.name(), "linux");
    assert_eq!(Platform::MacOS.name(), "macos");
    assert_eq!(Platform::Windows.name(), "windows");
    assert_eq!(Platform::FreeBSD.name(), "freebsd");
    assert_eq!(Platform::OpenBSD.name(), "openbsd");
    assert_eq!(Platform::NetBSD.name(), "netbsd");
    assert_eq!(Platform::Unknown.name(), "unknown");
}

#[test]
fn test_platform_display() {
    assert_eq!(format!("{}", Platform::Linux), "linux");
    assert_eq!(format!("{}", Platform::MacOS), "macos");
    assert_eq!(format!("{}", Platform::Windows), "windows");
}

// =============================================================================
// Default Path Tests
// =============================================================================

#[test]
fn test_default_paths_system() {
    let paths = paths::Paths::system_defaults();

    // Config file should have a path
    assert!(!paths.config_file.as_os_str().is_empty());

    // Vault dir should have a path
    assert!(!paths.vault_dir.as_os_str().is_empty());

    // Log dir should have a path
    assert!(!paths.log_dir.as_os_str().is_empty());

    // Bin dir should have a path
    assert!(!paths.bin_dir.as_os_str().is_empty());
}

#[test]
#[cfg(unix)]
fn test_unix_default_paths() {
    let paths = paths::Paths::system_defaults();

    assert!(paths.config_file.to_string_lossy().contains("/etc/hydra"));
    assert!(paths.vault_dir.to_string_lossy().contains("/var/cv/hydra"));
    assert!(paths.log_dir.to_string_lossy().contains("/var/log/hydra"));
    assert!(paths.bin_dir.to_string_lossy().contains("/usr/local/bin"));
}

#[test]
#[cfg(windows)]
fn test_windows_default_paths() {
    let paths = paths::Paths::system_defaults();

    assert!(paths.config_file.to_string_lossy().contains("ProgramData"));
    assert!(paths.vault_dir.to_string_lossy().contains("vault"));
    assert!(paths.log_dir.to_string_lossy().contains("logs"));
}

#[test]
fn test_default_trait() {
    let paths1 = paths::Paths::default();
    let paths2 = paths::Paths::system_defaults();

    assert_eq!(paths1.config_file, paths2.config_file);
    assert_eq!(paths1.vault_dir, paths2.vault_dir);
}

// =============================================================================
// Custom Base Directory Tests
// =============================================================================

#[test]
fn test_custom_base_dir() {
    let base = PathBuf::from("/tmp/hydra-test");
    let paths = paths::Paths::with_base_dir(&base);

    assert_eq!(paths.config_file, base.join("agent.toml"));
    assert_eq!(paths.config_dir, base);
    assert_eq!(paths.vault_dir, base.join("vault"));
    assert_eq!(paths.log_dir, base.join("logs"));
    assert_eq!(paths.bin_dir, base.join("bin"));
}

#[test]
fn test_custom_base_dir_nested() {
    let base = PathBuf::from("/opt/custom/hydra/config");
    let paths = paths::Paths::with_base_dir(&base);

    assert_eq!(
        paths.config_file,
        PathBuf::from("/opt/custom/hydra/config/agent.toml")
    );
}

#[test]
fn test_custom_base_dir_relative() {
    let base = PathBuf::from("./test-config");
    let paths = paths::Paths::with_base_dir(&base);

    assert_eq!(paths.config_file, PathBuf::from("./test-config/agent.toml"));
}

// =============================================================================
// Vault File Path Tests
// =============================================================================

#[test]
fn test_vault_file_path() {
    let paths = paths::Paths::system_defaults();

    let creds = paths.vault_file(".creds");
    assert!(creds.to_string_lossy().ends_with(".creds"));
    assert!(creds.starts_with(&paths.vault_dir));
}

#[test]
fn test_vault_file_apikey() {
    let paths = paths::Paths::system_defaults();

    let apikey = paths.vault_file(".apikey");
    assert!(apikey.to_string_lossy().ends_with(".apikey"));
}

#[test]
fn test_vault_file_session() {
    let paths = paths::Paths::system_defaults();

    let session = paths.vault_file(".session");
    assert!(session.to_string_lossy().ends_with(".session"));
}

#[test]
fn test_vault_file_custom_name() {
    let paths = paths::Paths::system_defaults();

    let custom = paths.vault_file("custom-file.json");
    assert!(custom.to_string_lossy().ends_with("custom-file.json"));
}

// =============================================================================
// Log File Path Tests
// =============================================================================

#[test]
fn test_log_file_path() {
    let paths = paths::Paths::system_defaults();

    let log = paths.log_file("agent.log");
    assert!(log.to_string_lossy().ends_with("agent.log"));
    assert!(log.starts_with(&paths.log_dir));
}

#[test]
fn test_log_file_custom_name() {
    let paths = paths::Paths::system_defaults();

    let log = paths.log_file("profile-collection.log");
    assert!(log.to_string_lossy().ends_with("profile-collection.log"));
}

// =============================================================================
// Binary Path Tests
// =============================================================================

#[test]
#[cfg(unix)]
fn test_binary_path_unix() {
    let paths = paths::Paths::system_defaults();

    let binary = paths.binary("hydra-agent");
    assert!(binary.to_string_lossy().ends_with("hydra-agent"));
    assert!(!binary.to_string_lossy().ends_with(".exe"));
}

#[test]
#[cfg(windows)]
fn test_binary_path_windows() {
    let paths = paths::Paths::system_defaults();

    let binary = paths.binary("hydra-agent");
    assert!(binary.to_string_lossy().ends_with("hydra-agent.exe"));
}

// =============================================================================
// Default Path Function Tests
// =============================================================================

#[test]
fn test_default_config_file_fn() {
    let path = paths::default_config_file();
    assert!(!path.as_os_str().is_empty());

    #[cfg(unix)]
    assert_eq!(path, PathBuf::from("/etc/hydra/agent.toml"));

    #[cfg(windows)]
    assert!(path.to_string_lossy().contains("agent.toml"));
}

#[test]
fn test_default_config_dir_fn() {
    let path = paths::default_config_dir();
    assert!(!path.as_os_str().is_empty());

    #[cfg(unix)]
    assert_eq!(path, PathBuf::from("/etc/hydra"));
}

#[test]
fn test_default_vault_dir_fn() {
    let path = paths::default_vault_dir();
    assert!(!path.as_os_str().is_empty());

    #[cfg(unix)]
    assert_eq!(path, PathBuf::from("/var/cv/hydra"));
}

#[test]
fn test_default_log_dir_fn() {
    let path = paths::default_log_dir();
    assert!(!path.as_os_str().is_empty());

    #[cfg(unix)]
    assert_eq!(path, PathBuf::from("/var/log/hydra"));
}

#[test]
fn test_default_bin_dir_fn() {
    let path = paths::default_bin_dir();
    assert!(!path.as_os_str().is_empty());

    #[cfg(unix)]
    assert_eq!(path, PathBuf::from("/usr/local/bin"));
}

// =============================================================================
// Path Resolution Tests
// =============================================================================

#[test]
fn test_resolve_path_absolute() {
    let resolved = paths::resolve_path("/etc/hydra/agent.toml");
    assert_eq!(resolved, PathBuf::from("/etc/hydra/agent.toml"));
}

#[test]
fn test_resolve_path_relative() {
    let resolved = paths::resolve_path("./config/agent.toml");
    assert_eq!(resolved, PathBuf::from("./config/agent.toml"));
}

#[test]
fn test_resolve_path_home_expansion() {
    // Set HOME for test
    let original_home = std::env::var("HOME").ok();

    #[cfg(unix)]
    {
        std::env::set_var("HOME", "/home/testuser");
        let resolved = paths::resolve_path("~/hydra/agent.toml");
        assert_eq!(resolved, PathBuf::from("/home/testuser/hydra/agent.toml"));
    }

    #[cfg(windows)]
    {
        std::env::set_var("USERPROFILE", "C:\\Users\\testuser");
        let resolved = paths::resolve_path("~/hydra/agent.toml");
        assert_eq!(
            resolved,
            PathBuf::from("C:\\Users\\testuser/hydra/agent.toml")
        );
    }

    // Restore original HOME
    if let Some(home) = original_home {
        std::env::set_var("HOME", home);
    }
}

#[test]
fn test_resolve_path_no_home_prefix() {
    let resolved = paths::resolve_path("/opt/hydra/config");
    assert_eq!(resolved, PathBuf::from("/opt/hydra/config"));
}

#[test]
#[cfg(unix)]
fn test_resolve_path_env_var() {
    std::env::set_var("HYDRA_TEST_DIR", "/opt/hydra");
    let resolved = paths::resolve_path("$HYDRA_TEST_DIR/config");
    assert_eq!(resolved, PathBuf::from("/opt/hydra/config"));
    std::env::remove_var("HYDRA_TEST_DIR");
}

// =============================================================================
// Paths Clone and Debug Tests
// =============================================================================

#[test]
fn test_paths_clone() {
    let paths1 = paths::Paths::system_defaults();
    let paths2 = paths1.clone();

    assert_eq!(paths1.config_file, paths2.config_file);
    assert_eq!(paths1.vault_dir, paths2.vault_dir);
}

#[test]
fn test_paths_debug() {
    let paths = paths::Paths::system_defaults();
    let debug_str = format!("{:?}", paths);

    assert!(debug_str.contains("config_file"));
    assert!(debug_str.contains("vault_dir"));
}

// =============================================================================
// Platform Clone and Debug Tests
// =============================================================================

#[test]
fn test_platform_clone() {
    let p1 = Platform::Linux;
    let p2 = p1;
    assert_eq!(p1, p2);
}

#[test]
fn test_platform_debug() {
    let debug_str = format!("{:?}", Platform::Linux);
    assert_eq!(debug_str, "Linux");
}

#[test]
fn test_platform_copy() {
    let p1 = Platform::MacOS;
    let p2 = p1; // Copy, not move
    assert_eq!(p1, p2);
}

// =============================================================================
// Edge Cases
// =============================================================================

#[test]
fn test_paths_with_empty_base() {
    let base = PathBuf::from("");
    let paths = paths::Paths::with_base_dir(&base);

    // Should still work, just with empty base
    assert_eq!(paths.config_file, PathBuf::from("agent.toml"));
}

#[test]
fn test_vault_file_with_path_separator() {
    let paths = paths::Paths::system_defaults();

    // Subpath within vault
    let subfile = paths.vault_file("subdir/file.json");
    assert!(subfile.to_string_lossy().contains("subdir"));
}

#[test]
fn test_resolve_path_empty() {
    let resolved = paths::resolve_path("");
    assert_eq!(resolved, PathBuf::from(""));
}

#[test]
fn test_resolve_path_tilde_only() {
    // Just "~" should expand to home directory
    let original_home = std::env::var("HOME").ok();

    #[cfg(unix)]
    {
        std::env::set_var("HOME", "/home/testuser");
        let resolved = paths::resolve_path("~/");
        assert_eq!(resolved, PathBuf::from("/home/testuser/"));
    }

    if let Some(home) = original_home {
        std::env::set_var("HOME", home);
    }
}

// =============================================================================
// File Permissions Tests (Platform-specific)
// =============================================================================

#[test]
fn test_permissions_available() {
    // Just verify we can get a permissions object
    let perms = hydra_agent::platform::permissions();
    // The object should exist
    let _ = perms;
}

#[test]
fn test_encryption_available() {
    let encryption = hydra_agent::platform::encryption();
    // Check if encryption is available (platform-dependent)
    let _is_available = encryption.is_available();
}

// =============================================================================
// Integration Tests
// =============================================================================

#[test]
fn test_paths_consistency() {
    let paths = paths::Paths::system_defaults();

    // Config file should be in config dir
    assert!(
        paths.config_file.starts_with(&paths.config_dir)
            || paths
                .config_file
                .parent()
                .map(|p| p == paths.config_dir)
                .unwrap_or(false)
            || paths.config_file.parent() == Some(paths.config_dir.as_path())
    );

    // Vault files should be in vault dir
    let creds = paths.vault_file(".creds");
    assert!(creds.starts_with(&paths.vault_dir));

    // Log files should be in log dir
    let log = paths.log_file("agent.log");
    assert!(log.starts_with(&paths.log_dir));
}

#[test]
fn test_all_paths_are_absolute_or_configured() {
    let paths = paths::Paths::system_defaults();

    // System defaults should typically be absolute
    #[cfg(unix)]
    {
        assert!(paths.config_file.is_absolute());
        assert!(paths.vault_dir.is_absolute());
        assert!(paths.log_dir.is_absolute());
        assert!(paths.bin_dir.is_absolute());
    }
}
