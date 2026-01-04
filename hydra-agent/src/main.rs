//! Hydra Agent - Lightweight infrastructure profiler
//!
//! Collects system profiles and submits them to the Hydra API.

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use std::path::PathBuf;
use tracing::{info, warn, Level};
use tracing_subscriber::FmtSubscriber;

use hydra_agent::api;
use hydra_agent::collectors;
use hydra_agent::config::AgentConfig;

#[derive(Parser)]
#[command(name = "hydra-agent")]
#[command(about = "Hydra infrastructure profiling agent")]
#[command(version)]
#[command(propagate_version = true)]
struct Cli {
    /// Verbose output
    #[arg(short = 'V', long, global = true)]
    verbose: bool,

    #[command(subcommand)]
    command: Option<Commands>,

    // Legacy flat args for backwards compatibility
    /// Path to configuration file (legacy, use subcommands instead)
    #[arg(short, long, default_value = "/etc/hydra/agent.toml", global = true)]
    config: PathBuf,

    /// Run once and exit (legacy, use 'run --once' instead)
    #[arg(long, hide = true)]
    once: bool,

    /// Register this node with the API (legacy)
    #[arg(long, hide = true)]
    register: bool,

    /// Registration token (legacy)
    #[arg(long, hide = true)]
    token: Option<String>,

    /// Username for registration (legacy)
    #[arg(short, long, hide = true)]
    username: Option<String>,

    /// Password for registration (legacy)
    #[arg(short, long, hide = true)]
    password: Option<String>,
}

#[derive(Subcommand)]
enum Commands {
    /// Run the agent (collect and submit profiles)
    Run {
        /// Run once and exit (don't schedule)
        #[arg(long)]
        once: bool,
    },

    /// Register this node with the Hydra API
    Register {
        /// API base URL
        #[arg(long, env = "HYDRA_API_URL")]
        api_url: Option<String>,

        /// Registration token (for instant registration without user credentials)
        #[arg(long)]
        token: Option<String>,

        /// Username for registration (alternative to --token)
        #[arg(short, long)]
        username: Option<String>,

        /// Password for registration (used with --username)
        #[arg(short, long)]
        password: Option<String>,
    },

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
        /// Also remove configuration files
        #[arg(long)]
        purge: bool,
    },

    /// Show agent status
    Status,
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();

    // Initialize logging
    let level = if cli.verbose { Level::DEBUG } else { Level::INFO };
    let subscriber = FmtSubscriber::builder()
        .with_max_level(level)
        .json()
        .finish();
    tracing::subscriber::set_global_default(subscriber)?;

    match cli.command {
        Some(Commands::Run { once }) => {
            run_agent(&cli.config, once).await
        }
        Some(Commands::Register { api_url, token, username, password }) => {
            register_node(&cli.config, api_url, token, username, password).await
        }
        Some(Commands::Install { install_dir, config_dir, log_dir, no_systemd, no_start }) => {
            install_service(&install_dir, &config_dir, &log_dir, no_systemd, no_start)
        }
        Some(Commands::Uninstall { purge }) => {
            uninstall_service(purge)
        }
        Some(Commands::Status) => {
            show_status(&cli.config)
        }
        None => {
            // Legacy mode: check for legacy flags
            if cli.register {
                warn!("Using legacy --register flag. Consider using 'hydra-agent register' instead.");
                register_node(&cli.config, None, cli.token, cli.username, cli.password).await
            } else {
                if cli.once {
                    warn!("Using legacy --once flag. Consider using 'hydra-agent run --once' instead.");
                }
                run_agent(&cli.config, cli.once).await
            }
        }
    }
}

async fn run_agent(config_path: &PathBuf, once: bool) -> Result<()> {
    info!("Starting hydra-agent v{}", env!("CARGO_PKG_VERSION"));

    // Load configuration
    let config = AgentConfig::load(config_path)?;
    info!(node_id = %config.node.node_id, "Configuration loaded");

    // Create API client
    let client = api::ApiClient::new(&config)?;

    // Collect profile
    info!("Collecting system profile...");
    let profile = collectors::collect_profile(&config).await?;
    info!(
        sections = ?profile.sections(),
        "Profile collected"
    );

    // Submit profile
    info!("Submitting profile to API...");
    let result = client.submit_profile(&profile).await?;
    info!(
        profile_id = %result.profile_id,
        version = %result.version,
        "Profile submitted successfully"
    );

    if !once {
        // TODO: Implement scheduling in Phase 1.7 continuation
        info!("Scheduling not yet implemented. Use --once for single collection.");
    }

    Ok(())
}

async fn register_node(
    config_path: &PathBuf,
    api_url: Option<String>,
    token: Option<String>,
    username: Option<String>,
    password: Option<String>,
) -> Result<()> {
    info!("Registering node with Hydra API...");

    // Load configuration
    let config = AgentConfig::load(config_path)?;
    info!(node_id = %config.node.node_id, "Configuration loaded");

    // Override API URL if provided
    let config = if let Some(url) = api_url {
        let mut c = config;
        c.api.url = url;
        c
    } else {
        config
    };

    // Create API client
    let client = api::ApiClient::new(&config)?;

    if let Some(token) = token {
        // Registration with registration token
        client.register_with_token(&token).await?;
    } else if let Some(username) = username {
        // Registration with user credentials
        let password = password.unwrap_or_else(|| {
            // Prompt for password if not provided
            rpassword::prompt_password("Password: ").expect("Failed to read password")
        });
        client.register_with_credentials(&username, &password).await?;
    } else {
        return Err(anyhow::anyhow!(
            "Registration requires either --token or --username/-u and --password/-p"
        ));
    }

    info!("Node registered successfully");
    Ok(())
}

#[allow(unused_variables)]
fn install_service(
    install_dir: &PathBuf,
    config_dir: &PathBuf,
    log_dir: &PathBuf,
    no_systemd: bool,
    no_start: bool,
) -> Result<()> {
    use std::fs;
    #[cfg(unix)]
    use std::os::unix::fs::PermissionsExt;
    #[cfg(target_os = "linux")]
    use std::process::Command;

    info!("Installing hydra-agent as system service...");

    // Check if running as root
    #[cfg(unix)]
    if !nix::unistd::Uid::effective().is_root() {
        return Err(anyhow::anyhow!("This command must be run as root (use sudo)"));
    }

    // Create directories
    fs::create_dir_all(config_dir)
        .with_context(|| format!("Failed to create config dir: {}", config_dir.display()))?;
    fs::create_dir_all(log_dir)
        .with_context(|| format!("Failed to create log dir: {}", log_dir.display()))?;

    // Set permissions on config dir (750)
    #[cfg(unix)]
    fs::set_permissions(config_dir, fs::Permissions::from_mode(0o750))?;

    info!("Created directories: {}, {}", config_dir.display(), log_dir.display());

    // Copy current binary to install dir if it's not already there
    let current_exe = std::env::current_exe()?;
    let target_exe = install_dir.join("hydra-agent");

    if current_exe != target_exe {
        fs::create_dir_all(install_dir)?;
        fs::copy(&current_exe, &target_exe)
            .with_context(|| format!("Failed to copy binary to {}", target_exe.display()))?;
        #[cfg(unix)]
        fs::set_permissions(&target_exe, fs::Permissions::from_mode(0o755))?;
        info!("Installed binary to {}", target_exe.display());
    }

    // Create example config if it doesn't exist
    let config_file = config_dir.join("agent.toml");
    if !config_file.exists() {
        let example_config = r#"# Hydra Agent Configuration
# Edit this file before starting the agent

[node]
node_id = "CHANGE_ME"
class = "compute"
node_type = "physical"
# kind = "bare-metal"
# display_name = "My Server"
# tags = ["production"]

[api]
url = "https://hydra.local/api/v1"
credentials_file = "/etc/hydra/credentials.json"
timeout_seconds = 30
retries = 3

[collection]
level = "neutral"
include_packages = true
include_users = true

[schedule]
enabled = true
interval_seconds = 21600  # 6 hours
on_startup = true
"#;
        fs::write(&config_file, example_config)?;
        #[cfg(unix)]
        fs::set_permissions(&config_file, fs::Permissions::from_mode(0o644))?;
        info!("Created example config at {}", config_file.display());
    }

    // Install systemd service (Linux only)
    #[cfg(target_os = "linux")]
    if !no_systemd {
        let systemd_unit = format!(
            r#"[Unit]
Description=Hydra Infrastructure Agent
Documentation=https://github.com/yourorg/hydra
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={}/hydra-agent run
Restart=on-failure
RestartSec=10
User=root
Environment=HYDRA_CONFIG={}/agent.toml

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths={} {}

[Install]
WantedBy=multi-user.target
"#,
            install_dir.display(),
            config_dir.display(),
            log_dir.display(),
            config_dir.display()
        );

        let service_path = PathBuf::from("/etc/systemd/system/hydra-agent.service");
        fs::write(&service_path, systemd_unit)?;
        info!("Created systemd unit at {}", service_path.display());

        // Reload systemd
        Command::new("systemctl")
            .args(["daemon-reload"])
            .status()
            .context("Failed to reload systemd")?;

        // Enable service
        Command::new("systemctl")
            .args(["enable", "hydra-agent.service"])
            .status()
            .context("Failed to enable service")?;

        info!("Enabled hydra-agent.service");

        if !no_start {
            Command::new("systemctl")
                .args(["start", "hydra-agent.service"])
                .status()
                .context("Failed to start service")?;
            info!("Started hydra-agent.service");
        }
    }

    #[cfg(not(target_os = "linux"))]
    if !no_systemd {
        warn!("Systemd service installation is only supported on Linux");
    }

    println!();
    println!("Installation complete!");
    println!();
    println!("Next steps:");
    println!("  1. Edit configuration: {}", config_file.display());
    println!("  2. Register node: hydra-agent register --api-url <URL> --username <user>");
    println!("  3. Start service: sudo systemctl start hydra-agent");
    println!();

    Ok(())
}

fn uninstall_service(purge: bool) -> Result<()> {
    use std::fs;
    #[cfg(target_os = "linux")]
    use std::process::Command;

    info!("Uninstalling hydra-agent...");

    // Check if running as root
    #[cfg(unix)]
    if !nix::unistd::Uid::effective().is_root() {
        return Err(anyhow::anyhow!("This command must be run as root (use sudo)"));
    }

    // Stop and disable service (Linux only)
    #[cfg(target_os = "linux")]
    {
        let _ = Command::new("systemctl")
            .args(["stop", "hydra-agent.service"])
            .status();

        let _ = Command::new("systemctl")
            .args(["disable", "hydra-agent.service"])
            .status();

        // Remove systemd unit
        let service_path = PathBuf::from("/etc/systemd/system/hydra-agent.service");
        if service_path.exists() {
            fs::remove_file(&service_path)?;
            info!("Removed {}", service_path.display());
        }

        let _ = Command::new("systemctl")
            .args(["daemon-reload"])
            .status();
    }

    // Remove binary
    let binary_path = PathBuf::from("/usr/local/bin/hydra-agent");
    if binary_path.exists() {
        fs::remove_file(&binary_path)?;
        info!("Removed {}", binary_path.display());
    }

    if purge {
        // Remove configuration and logs
        let config_dir = PathBuf::from("/etc/hydra");
        if config_dir.exists() {
            fs::remove_dir_all(&config_dir)?;
            info!("Removed {}", config_dir.display());
        }

        let log_dir = PathBuf::from("/var/log/hydra");
        if log_dir.exists() {
            fs::remove_dir_all(&log_dir)?;
            info!("Removed {}", log_dir.display());
        }
    }

    println!();
    println!("Uninstallation complete!");
    if !purge {
        println!("Configuration files preserved. Use --purge to remove them.");
    }
    println!();

    Ok(())
}

fn show_status(config_path: &PathBuf) -> Result<()> {
    #[cfg(target_os = "linux")]
    use std::process::Command;

    println!("Hydra Agent Status");
    println!("==================");
    println!();

    // Check systemd service status (Linux only)
    #[cfg(target_os = "linux")]
    {
        let status = Command::new("systemctl")
            .args(["is-active", "hydra-agent.service"])
            .output();

        match status {
            Ok(output) => {
                let state = String::from_utf8_lossy(&output.stdout).trim().to_string();
                println!("Service: {}", state);
            }
            Err(_) => {
                println!("Service: not installed");
            }
        }
    }

    #[cfg(not(target_os = "linux"))]
    {
        println!("Service: N/A (systemd not available)");
    }

    // Check for config file
    let config_path = if config_path.exists() {
        config_path.clone()
    } else {
        PathBuf::from("/etc/hydra/agent.toml")
    };

    if config_path.exists() {
        println!("Config: {}", config_path.display());

        // Try to load and show node_id
        if let Ok(config) = AgentConfig::load(&config_path) {
            println!("Node ID: {}", config.node.node_id);
            println!("API URL: {}", config.api.url);
        }
    } else {
        println!("Config: not found");
    }

    // Check for credentials
    let creds_path = PathBuf::from("/etc/hydra/credentials.json");
    if creds_path.exists() {
        println!("Credentials: present");
    } else {
        println!("Credentials: not registered");
    }

    println!();

    // Show recent logs if available (Linux only)
    #[cfg(target_os = "linux")]
    {
        let logs = Command::new("journalctl")
            .args(["-u", "hydra-agent.service", "-n", "5", "--no-pager", "-o", "short"])
            .output();

        if let Ok(output) = logs {
            if !output.stdout.is_empty() {
                println!("Recent logs:");
                println!("{}", String::from_utf8_lossy(&output.stdout));
            }
        }
    }

    Ok(())
}
