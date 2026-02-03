//! Command-line interface for hydra-agent.
//!
//! Provides subcommands for agent operations:
//! - [`login`] - Authenticate as admin/operator
//! - [`register`] - Register agent system account
//! - [`unregister`] - Unregister agent from Hydra
//! - [`config`] - Manage configuration
//! - [`node`] - Node management operations
//! - [`service`] - Service lifecycle management

pub mod config;
pub mod login;
pub mod node;
pub mod register;
pub mod service;
pub mod unregister;
pub mod upgrade;

use clap::{Parser, Subcommand, ValueEnum};
use std::path::PathBuf;

/// Operating mode for the agent.
#[derive(Debug, Clone, Copy, PartialEq, Eq, ValueEnum, Default)]
pub enum OperatingMode {
    /// Normal operation with API communication
    #[default]
    Live,
    /// Development mode - no API calls, local output only
    Dev,
}

/// Hydra Agent CLI.
#[derive(Parser)]
#[command(name = "hydra-agent")]
#[command(author, version, about, long_about = None)]
#[command(propagate_version = true)]
pub struct Cli {
    /// Enable verbose output (debug logging)
    #[arg(short = 'v', long, global = true)]
    pub verbose: bool,

    /// Create 'hydra' alias (symlink) for hydra-agent
    #[arg(short = 'a', long)]
    pub aliased: bool,

    /// Path to configuration file
    #[arg(short = 'c', long, default_value = "/etc/hydra/agent.toml", env = "HYDRA_CONFIG")]
    pub config: PathBuf,

    /// Operating mode (live = API mode, dev = local output only)
    #[arg(short = 'm', long, value_enum, default_value_t = OperatingMode::Live)]
    pub mode: OperatingMode,

    #[command(subcommand)]
    pub command: Option<Commands>,
}

/// Available CLI subcommands.
#[derive(Subcommand)]
pub enum Commands {
    /// Authenticate as admin/operator to perform privileged operations
    Login(login::LoginArgs),

    /// Register agent system account with the Hydra API
    Register(register::RegisterArgs),

    /// Unregister agent from Hydra (removes agent account)
    Unregister(unregister::UnregisterArgs),

    /// Manage agent configuration
    Config(config::ConfigArgs),

    /// Node management operations
    Node(node::NodeArgs),

    /// Service lifecycle management
    Service(service::ServiceArgs),

    /// Run profile collection
    Run {
        /// Run once and exit (don't schedule)
        #[arg(long)]
        once: bool,
    },

    /// Show agent status
    Status,

    /// Install the agent as a system service
    Install {
        /// Installation directory for the binary
        #[arg(long, default_value = "/usr/local/bin")]
        install_dir: PathBuf,

        /// Configuration directory
        #[arg(long, default_value = "/etc/hydra")]
        config_dir: PathBuf,

        /// Log directory
        #[arg(long, default_value = "/var/log/hydra")]
        log_dir: PathBuf,

        /// Skip systemd service installation
        #[arg(long)]
        no_systemd: bool,

        /// Don't start the service after installation
        #[arg(long)]
        no_start: bool,
    },

    /// Uninstall the agent system service
    Uninstall {
        /// Also remove configuration files and vault
        #[arg(long)]
        purge: bool,
    },

    /// Upgrade the agent to a newer version
    Upgrade(upgrade::UpgradeArgs),
}
