//! Command-line interface for hydra-agent.
//!
//! Provides a modular CLI structure with subcommands for various operations:
//! - `login` - Authenticate as admin/operator
//! - `register` - Register agent system account
//! - `config` - Manage configuration
//! - `node` - Node management operations
//! - `service` - Service lifecycle management
//! - `run` - Run profile collection (legacy compatibility)
//! - `status` - Show agent status

pub mod login;
pub mod register;
pub mod config;
pub mod node;
pub mod service;

use clap::{Parser, Subcommand, ValueEnum};
use std::path::PathBuf;

/// Operating mode for the agent
#[derive(Debug, Clone, Copy, PartialEq, Eq, ValueEnum, Default)]
pub enum OperatingMode {
    /// Normal operation with API communication
    #[default]
    Live,
    /// Development mode - no API calls, local output only
    Dev,
}

/// Hydra Agent - Infrastructure profiling agent
#[derive(Parser)]
#[command(name = "hydra-agent")]
#[command(author, version, about, long_about = None)]
#[command(propagate_version = true)]
pub struct Cli {
    /// Enable verbose output (debug logging)
    #[arg(short = 'V', long, global = true)]
    pub verbose: bool,

    /// Create 'hydra' alias (symlink) during install
    #[arg(short = 'a', long, global = true)]
    pub aliased: bool,

    /// Path to configuration file
    #[arg(short, long, default_value = "/etc/hydra/agent.toml", global = true, env = "HYDRA_CONFIG")]
    pub config: PathBuf,

    /// Operating mode
    #[arg(short, long, value_enum, default_value_t = OperatingMode::Live, global = true)]
    pub mode: OperatingMode,

    #[command(subcommand)]
    pub command: Option<Commands>,

    // ==================== Legacy flags (hidden, for backward compatibility) ====================

    /// Run once and exit (legacy, use 'run --once')
    #[arg(long, hide = true)]
    pub once: bool,

    /// Register with the API (legacy, use 'register' command)
    #[arg(long, hide = true)]
    pub register: bool,

    /// Registration token (legacy)
    #[arg(long, hide = true)]
    pub token: Option<String>,

    /// Username (legacy)
    #[arg(short, long, hide = true)]
    pub username: Option<String>,

    /// Password (legacy)
    #[arg(short, long, hide = true)]
    pub password: Option<String>,
}

#[derive(Subcommand)]
pub enum Commands {
    /// Authenticate as admin/operator to perform privileged operations
    Login(login::LoginArgs),

    /// Register agent system account with the Hydra API
    Register(register::RegisterArgs),

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
}
