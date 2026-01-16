//! Tests for CLI argument parsing and command structure.
//!
//! Tests cover:
//! - CLI argument parsing
//! - OperatingMode selection (dev, live)
//! - Command structure validation
//! - Help generation

use hydra_agent::cli::{Cli, Commands, OperatingMode};
use clap::Parser;

// =============================================================================
// OperatingMode Parsing Tests
// =============================================================================

#[test]
fn test_mode_default_is_live() {
    let cli = Cli::try_parse_from(["hydra-agent", "status"]).unwrap();
    assert_eq!(cli.mode, OperatingMode::Live);
}

#[test]
fn test_mode_explicit_live() {
    let cli = Cli::try_parse_from(["hydra-agent", "--mode", "live", "status"]).unwrap();
    assert_eq!(cli.mode, OperatingMode::Live);
}

#[test]
fn test_mode_dev() {
    let cli = Cli::try_parse_from(["hydra-agent", "--mode", "dev"]).unwrap();
    assert_eq!(cli.mode, OperatingMode::Dev);
}

#[test]
fn test_mode_short_flag() {
    let cli = Cli::try_parse_from(["hydra-agent", "-m", "dev"]).unwrap();
    assert_eq!(cli.mode, OperatingMode::Dev);
}

#[test]
fn test_mode_invalid() {
    let result = Cli::try_parse_from(["hydra-agent", "--mode", "invalid"]);
    assert!(result.is_err(), "Invalid mode should fail parsing");
}

// =============================================================================
// Config Path Tests
// =============================================================================

#[test]
fn test_config_default_path() {
    let cli = Cli::try_parse_from(["hydra-agent", "status"]).unwrap();
    // Default config path should be set
    assert!(!cli.config.as_os_str().is_empty());
}

#[test]
fn test_config_custom_path() {
    let cli = Cli::try_parse_from([
        "hydra-agent",
        "--config", "/custom/path/agent.toml",
        "status"
    ]).unwrap();
    assert_eq!(cli.config.to_string_lossy(), "/custom/path/agent.toml");
}

#[test]
fn test_config_short_flag() {
    let cli = Cli::try_parse_from([
        "hydra-agent",
        "-c", "/etc/hydra/custom.toml",
        "status"
    ]).unwrap();
    assert_eq!(cli.config.to_string_lossy(), "/etc/hydra/custom.toml");
}

// =============================================================================
// Login Command Tests
// =============================================================================

#[test]
fn test_login_command_basic() {
    let cli = Cli::try_parse_from(["hydra-agent", "login"]).unwrap();
    assert!(matches!(cli.command, Some(Commands::Login(_))));
}

#[test]
fn test_login_with_username() {
    let cli = Cli::try_parse_from([
        "hydra-agent", "login",
        "-u", "admin"
    ]).unwrap();

    if let Some(Commands::Login(args)) = cli.command {
        assert_eq!(args.username, Some("admin".to_string()));
    } else {
        panic!("Expected Login command");
    }
}

#[test]
fn test_login_with_password() {
    let cli = Cli::try_parse_from([
        "hydra-agent", "login",
        "-u", "admin",
        "-p", "secret"
    ]).unwrap();

    if let Some(Commands::Login(args)) = cli.command {
        assert_eq!(args.username, Some("admin".to_string()));
        assert_eq!(args.password, Some("secret".to_string()));
    } else {
        panic!("Expected Login command");
    }
}

#[test]
fn test_login_agent_flag() {
    let cli = Cli::try_parse_from(["hydra-agent", "login", "--agent"]).unwrap();

    if let Some(Commands::Login(args)) = cli.command {
        assert!(args.agent);
    } else {
        panic!("Expected Login command");
    }
}

#[test]
fn test_login_agent_short_flag() {
    let cli = Cli::try_parse_from(["hydra-agent", "login", "-a"]).unwrap();

    if let Some(Commands::Login(args)) = cli.command {
        assert!(args.agent);
    } else {
        panic!("Expected Login command");
    }
}

#[test]
fn test_login_force_flag() {
    let cli = Cli::try_parse_from(["hydra-agent", "login", "-a", "-f"]).unwrap();

    if let Some(Commands::Login(args)) = cli.command {
        assert!(args.agent);
        assert!(args.force);
    } else {
        panic!("Expected Login command");
    }
}

#[test]
fn test_login_refresh_flag() {
    let cli = Cli::try_parse_from(["hydra-agent", "login", "--refresh"]).unwrap();

    if let Some(Commands::Login(args)) = cli.command {
        assert!(args.refresh);
    } else {
        panic!("Expected Login command");
    }
}

#[test]
fn test_login_status_flag() {
    let cli = Cli::try_parse_from(["hydra-agent", "login", "--status"]).unwrap();

    if let Some(Commands::Login(args)) = cli.command {
        assert!(args.status);
    } else {
        panic!("Expected Login command");
    }
}

#[test]
fn test_login_logout_flag() {
    let cli = Cli::try_parse_from(["hydra-agent", "login", "--logout"]).unwrap();

    if let Some(Commands::Login(args)) = cli.command {
        assert!(args.logout);
    } else {
        panic!("Expected Login command");
    }
}

// =============================================================================
// Register Command Tests
// =============================================================================

#[test]
fn test_register_command_basic() {
    let cli = Cli::try_parse_from(["hydra-agent", "register"]).unwrap();
    assert!(matches!(cli.command, Some(Commands::Register(_))));
}

#[test]
fn test_register_with_token() {
    let cli = Cli::try_parse_from([
        "hydra-agent", "register",
        "--token", "reg_abc123"
    ]).unwrap();

    if let Some(Commands::Register(args)) = cli.command {
        assert_eq!(args.token, Some("reg_abc123".to_string()));
    } else {
        panic!("Expected Register command");
    }
}

#[test]
fn test_register_with_username() {
    let cli = Cli::try_parse_from([
        "hydra-agent", "register",
        "--username", "custom-agent"
    ]).unwrap();

    if let Some(Commands::Register(args)) = cli.command {
        assert_eq!(args.username, Some("custom-agent".to_string()));
    } else {
        panic!("Expected Register command");
    }
}

#[test]
fn test_register_override_flag() {
    let cli = Cli::try_parse_from(["hydra-agent", "register", "-o"]).unwrap();

    if let Some(Commands::Register(args)) = cli.command {
        assert!(args.override_registration);
    } else {
        panic!("Expected Register command");
    }
}

#[test]
fn test_register_status_flag() {
    let cli = Cli::try_parse_from(["hydra-agent", "register", "--status"]).unwrap();

    if let Some(Commands::Register(args)) = cli.command {
        assert!(args.status);
    } else {
        panic!("Expected Register command");
    }
}

#[test]
fn test_register_clear_flag() {
    let cli = Cli::try_parse_from(["hydra-agent", "register", "--clear"]).unwrap();

    if let Some(Commands::Register(args)) = cli.command {
        assert!(args.clear);
    } else {
        panic!("Expected Register command");
    }
}

// =============================================================================
// Unregister Command Tests
// =============================================================================

#[test]
fn test_unregister_command_basic() {
    let cli = Cli::try_parse_from(["hydra-agent", "unregister"]).unwrap();
    assert!(matches!(cli.command, Some(Commands::Unregister(_))));
}

#[test]
fn test_unregister_force_flag() {
    let cli = Cli::try_parse_from(["hydra-agent", "unregister", "--force"]).unwrap();

    if let Some(Commands::Unregister(args)) = cli.command {
        assert!(args.force);
    } else {
        panic!("Expected Unregister command");
    }
}

// =============================================================================
// Node Command Tests
// =============================================================================

#[test]
fn test_node_command_register() {
    let cli = Cli::try_parse_from(["hydra-agent", "node", "register"]).unwrap();
    assert!(matches!(cli.command, Some(Commands::Node(_))));
}

#[test]
fn test_node_command_status() {
    let cli = Cli::try_parse_from(["hydra-agent", "node", "status"]).unwrap();
    assert!(matches!(cli.command, Some(Commands::Node(_))));
}

#[test]
fn test_node_command_info() {
    let cli = Cli::try_parse_from(["hydra-agent", "node", "info"]).unwrap();
    assert!(matches!(cli.command, Some(Commands::Node(_))));
}

#[test]
fn test_node_command_update() {
    let cli = Cli::try_parse_from(["hydra-agent", "node", "update"]).unwrap();
    assert!(matches!(cli.command, Some(Commands::Node(_))));
}

#[test]
fn test_node_command_unregister() {
    let cli = Cli::try_parse_from(["hydra-agent", "node", "unregister"]).unwrap();
    assert!(matches!(cli.command, Some(Commands::Node(_))));
}

// =============================================================================
// Config Command Tests
// =============================================================================

#[test]
fn test_config_command_list() {
    let cli = Cli::try_parse_from(["hydra-agent", "config", "list"]).unwrap();
    assert!(matches!(cli.command, Some(Commands::Config(_))));
}

#[test]
fn test_config_command_init() {
    let cli = Cli::try_parse_from(["hydra-agent", "config", "init"]).unwrap();
    assert!(matches!(cli.command, Some(Commands::Config(_))));
}

#[test]
fn test_config_command_validate() {
    let cli = Cli::try_parse_from(["hydra-agent", "config", "validate"]).unwrap();
    assert!(matches!(cli.command, Some(Commands::Config(_))));
}

// =============================================================================
// Service Command Tests
// =============================================================================

#[test]
fn test_service_command_activate() {
    let cli = Cli::try_parse_from(["hydra-agent", "service", "activate"]).unwrap();
    assert!(matches!(cli.command, Some(Commands::Service(_))));
}

#[test]
fn test_service_command_deactivate() {
    let cli = Cli::try_parse_from(["hydra-agent", "service", "deactivate"]).unwrap();
    assert!(matches!(cli.command, Some(Commands::Service(_))));
}

#[test]
fn test_service_command_status() {
    let cli = Cli::try_parse_from(["hydra-agent", "service", "status"]).unwrap();
    assert!(matches!(cli.command, Some(Commands::Service(_))));
}

// =============================================================================
// Run Command Tests
// =============================================================================

#[test]
fn test_run_command_basic() {
    let cli = Cli::try_parse_from(["hydra-agent", "run"]).unwrap();
    assert!(matches!(cli.command, Some(Commands::Run { .. })));
}

#[test]
fn test_run_command_once() {
    let cli = Cli::try_parse_from(["hydra-agent", "run", "--once"]).unwrap();

    if let Some(Commands::Run { once }) = cli.command {
        assert!(once);
    } else {
        panic!("Expected Run command");
    }
}

// =============================================================================
// Status Command Tests
// =============================================================================

#[test]
fn test_status_command() {
    let cli = Cli::try_parse_from(["hydra-agent", "status"]).unwrap();
    assert!(matches!(cli.command, Some(Commands::Status)));
}

// =============================================================================
// Install Command Tests
// =============================================================================

#[test]
fn test_install_command_basic() {
    let cli = Cli::try_parse_from(["hydra-agent", "install"]).unwrap();
    assert!(matches!(cli.command, Some(Commands::Install { .. })));
}

#[test]
fn test_install_command_custom_dirs() {
    let cli = Cli::try_parse_from([
        "hydra-agent", "install",
        "--install-dir", "/opt/hydra/bin",
        "--config-dir", "/opt/hydra/etc",
        "--log-dir", "/opt/hydra/log"
    ]).unwrap();

    if let Some(Commands::Install { install_dir, config_dir, log_dir, .. }) = cli.command {
        assert_eq!(install_dir.to_string_lossy(), "/opt/hydra/bin");
        assert_eq!(config_dir.to_string_lossy(), "/opt/hydra/etc");
        assert_eq!(log_dir.to_string_lossy(), "/opt/hydra/log");
    } else {
        panic!("Expected Install command");
    }
}

#[test]
fn test_install_command_no_systemd() {
    let cli = Cli::try_parse_from(["hydra-agent", "install", "--no-systemd"]).unwrap();

    if let Some(Commands::Install { no_systemd, .. }) = cli.command {
        assert!(no_systemd);
    } else {
        panic!("Expected Install command");
    }
}

#[test]
fn test_install_command_no_start() {
    let cli = Cli::try_parse_from(["hydra-agent", "install", "--no-start"]).unwrap();

    if let Some(Commands::Install { no_start, .. }) = cli.command {
        assert!(no_start);
    } else {
        panic!("Expected Install command");
    }
}

// =============================================================================
// Uninstall Command Tests
// =============================================================================

#[test]
fn test_uninstall_command_basic() {
    let cli = Cli::try_parse_from(["hydra-agent", "uninstall"]).unwrap();
    assert!(matches!(cli.command, Some(Commands::Uninstall { .. })));
}

#[test]
fn test_uninstall_command_purge() {
    let cli = Cli::try_parse_from(["hydra-agent", "uninstall", "--purge"]).unwrap();

    if let Some(Commands::Uninstall { purge }) = cli.command {
        assert!(purge);
    } else {
        panic!("Expected Uninstall command");
    }
}

// =============================================================================
// No Command Tests
// =============================================================================

#[test]
fn test_no_command() {
    let cli = Cli::try_parse_from(["hydra-agent"]).unwrap();
    assert!(cli.command.is_none());
}

#[test]
fn test_no_command_with_mode() {
    let cli = Cli::try_parse_from(["hydra-agent", "-m", "dev"]).unwrap();
    assert!(cli.command.is_none());
    assert_eq!(cli.mode, OperatingMode::Dev);
}

// =============================================================================
// OperatingMode Value Tests
// =============================================================================

#[test]
fn test_mode_enum_values() {
    assert_eq!(OperatingMode::Dev, OperatingMode::Dev);
    assert_eq!(OperatingMode::Live, OperatingMode::Live);
    assert_ne!(OperatingMode::Dev, OperatingMode::Live);
}

// =============================================================================
// Combined Flag Tests
// =============================================================================

#[test]
fn test_combined_global_and_command_flags() {
    let cli = Cli::try_parse_from([
        "hydra-agent",
        "-m", "dev",
        "-c", "/custom/config.toml",
        "login",
        "-u", "admin",
        "-a"
    ]).unwrap();

    assert_eq!(cli.mode, OperatingMode::Dev);
    assert_eq!(cli.config.to_string_lossy(), "/custom/config.toml");

    if let Some(Commands::Login(args)) = cli.command {
        assert_eq!(args.username, Some("admin".to_string()));
        assert!(args.agent);
    } else {
        panic!("Expected Login command");
    }
}

// =============================================================================
// Help and Version Tests
// =============================================================================

#[test]
fn test_help_flag_exits() {
    // Help flag should cause parse to fail with a specific error
    let result = Cli::try_parse_from(["hydra-agent", "--help"]);
    assert!(result.is_err());
}

#[test]
fn test_version_flag_exits() {
    // Version flag should cause parse to fail with a specific error
    let result = Cli::try_parse_from(["hydra-agent", "--version"]);
    assert!(result.is_err());
}

// =============================================================================
// Invalid Argument Tests
// =============================================================================

#[test]
fn test_invalid_command() {
    let result = Cli::try_parse_from(["hydra-agent", "invalid-command"]);
    assert!(result.is_err());
}

#[test]
fn test_invalid_flag() {
    let result = Cli::try_parse_from(["hydra-agent", "--invalid-flag"]);
    assert!(result.is_err());
}

#[test]
fn test_missing_flag_value() {
    let result = Cli::try_parse_from(["hydra-agent", "--config"]);
    assert!(result.is_err());
}
