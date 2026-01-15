//! Hydra Agent - Lightweight infrastructure profiler
//!
//! Collects system profiles and submits them to the Hydra API.

use anyhow::{Context, Result};
use clap::Parser;
use std::path::PathBuf;
use tracing::{info, warn, Level};
use tracing_subscriber::FmtSubscriber;

use hydra_agent::api;
use hydra_agent::cli::{self, Cli, Commands, OperatingMode};
use hydra_agent::collectors;
use hydra_agent::config::AgentConfig;
use hydra_agent::vault::Vault;

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

    // Create vault instance
    let vault = Vault::default();

    // Check for dev mode
    let is_dev_mode = cli.mode == OperatingMode::Dev;
    if is_dev_mode {
        info!("Running in development mode (no API calls)");
    }

    // Handle commands
    match cli.command {
        Some(Commands::Login(args)) => {
            if is_dev_mode {
                return dev_mode_login(&args);
            }
            let config = load_config(&cli.config)?;
            cli::login::execute(&args, &config, &vault).await
        }
        Some(Commands::Register(args)) => {
            if is_dev_mode {
                return dev_mode_register(&args);
            }
            let config = load_config(&cli.config)?;
            cli::register::execute(&args, &config, &vault).await
        }
        Some(Commands::Config(args)) => {
            let ctx = cli::config::ConfigContext {
                config_path: &cli.config,
                vault: Some(&vault),
                live_mode: !is_dev_mode,
            };
            cli::config::execute(&args, &ctx).await
        }
        Some(Commands::Node(args)) => {
            if is_dev_mode {
                return dev_mode_node(&args);
            }
            let config = load_config(&cli.config)?;
            cli::node::execute(&args, &config, &vault).await
        }
        Some(Commands::Service(args)) => cli::service::execute(&args, &cli.config),
        Some(Commands::Run { once }) => {
            if is_dev_mode {
                return dev_mode_run(&cli.config, once).await;
            }
            run_agent(&cli.config, &vault, once).await
        }
        Some(Commands::Status) => show_status(&cli.config, &vault),
        Some(Commands::Install {
            install_dir,
            config_dir,
            log_dir,
            no_systemd,
            no_start,
        }) => install_service(&install_dir, &config_dir, &log_dir, no_systemd, no_start),
        Some(Commands::Uninstall { purge }) => uninstall_service(purge),
        None => {
            // Legacy mode: check for legacy flags
            if cli.register {
                warn!("Using legacy --register flag. Consider using 'hydra-agent register' instead.");
                let config = load_config(&cli.config)?;
                if let Some(token) = cli.token {
                    cli::register::execute(
                        &cli::register::RegisterArgs {
                            token: Some(token),
                            username: None,
                            password: None,
                            status: false,
                            clear: false,
                        },
                        &config,
                        &vault,
                    )
                    .await
                } else {
                    // Legacy credential-based registration not directly supported,
                    // they should use login + register workflow
                    return Err(anyhow::anyhow!(
                        "Please use 'hydra-agent login' followed by 'hydra-agent register'"
                    ));
                }
            } else {
                if cli.once {
                    warn!("Using legacy --once flag. Consider using 'hydra-agent run --once' instead.");
                }
                if is_dev_mode {
                    return dev_mode_run(&cli.config, cli.once).await;
                }
                run_agent(&cli.config, &vault, cli.once).await
            }
        }
    }
}

/// Load configuration file
fn load_config(config_path: &PathBuf) -> Result<AgentConfig> {
    AgentConfig::load(config_path).with_context(|| {
        format!(
            "Failed to load configuration from {}",
            config_path.display()
        )
    })
}

/// Run the agent (collect and submit profiles)
async fn run_agent(config_path: &PathBuf, vault: &Vault, once: bool) -> Result<()> {
    info!("Starting hydra-agent v{}", env!("CARGO_PKG_VERSION"));

    // Load configuration
    let config = load_config(config_path)?;
    info!(node_id = %config.node.node_id, "Configuration loaded");

    // Verify authentication data is available (ApiClient will refresh keys if needed)
    if !vault.has_agent_credentials() && !vault.has_api_key() {
        return Err(anyhow::anyhow!(
            "No authentication available. Run 'hydra-agent register' first."
        ));
    }

    // Create API client
    let client = api::ApiClient::new(&config, vault)?;

    // Collect profile
    info!("Collecting system profile...");
    let profile = collectors::collect_profile(&config).await?;
    info!(sections = ?profile.sections(), "Profile collected");

    // Submit profile
    info!("Submitting profile to API...");
    let result = client.submit_profile(&profile).await?;
    info!(
        profile_id = %result.profile_id,
        version = %result.version,
        "Profile submitted successfully"
    );

    if !once {
        // TODO: Implement scheduling
        info!("Scheduling not yet implemented. Use --once for single collection.");
    }

    Ok(())
}

/// Show agent status including vault status
fn show_status(config_path: &PathBuf, vault: &Vault) -> Result<()> {
    #[cfg(target_os = "linux")]
    use std::process::Command;

    println!();
    println!("Hydra Agent Status");
    println!("==================");
    println!();

    // Version info
    println!("Version: {}", env!("CARGO_PKG_VERSION"));
    println!();

    // Service status (Linux only)
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

    // Config file
    if config_path.exists() {
        println!("Config: {}", config_path.display());
        if let Ok(config) = load_config(config_path) {
            println!("  Node ID: {}", config.node.node_id);
            println!("  API URL: {}", config.api.url);
        }
    } else {
        println!("Config: not found ({})", config_path.display());
    }

    println!();

    // Vault status
    let vault_status = vault.status();
    print!("{}", vault_status);

    // Recent logs (Linux only)
    #[cfg(target_os = "linux")]
    {
        let logs = Command::new("journalctl")
            .args([
                "-u",
                "hydra-agent.service",
                "-n",
                "5",
                "--no-pager",
                "-o",
                "short",
            ])
            .output();

        if let Ok(output) = logs {
            if !output.stdout.is_empty() {
                println!();
                println!("Recent logs:");
                println!("{}", String::from_utf8_lossy(&output.stdout));
            }
        }
    }

    Ok(())
}

// ==================== Development Mode Functions ====================

/// Dev mode login - simulates login without API call
fn dev_mode_login(args: &cli::login::LoginArgs) -> Result<()> {

    if args.status {
        println!();
        println!("[DEV MODE] Login Session Status");
        println!("================================");
        println!("  Status: Simulated active session");
        println!("  User: dev-admin (admin)");
        println!("  Expires: Never (dev mode)");
        return Ok(());
    }

    if args.logout {
        println!("[DEV MODE] Logged out (simulated)");
        return Ok(());
    }

    if args.refresh {
        println!("[DEV MODE] Session refreshed (simulated)");
        return Ok(());
    }

    let username = args.username.clone().unwrap_or_else(|| "dev-admin".to_string());

    println!();
    println!("[DEV MODE] Login simulated (no API call)");
    println!("  User: {} (admin)", username);
    println!("  Access Token: dev_token_simulated");
    println!();
    println!("In dev mode, authentication is bypassed for local testing.");

    Ok(())
}

/// Dev mode register - simulates registration without API call
fn dev_mode_register(args: &cli::register::RegisterArgs) -> Result<()> {
    if args.status {
        println!();
        println!("[DEV MODE] Agent Registration Status");
        println!("====================================");
        println!("  Status: Simulated registered");
        println!("  Username: agent-DEV12345");
        println!("  User ID: dev_user_123");
        return Ok(());
    }

    if args.clear {
        println!("[DEV MODE] Registration cleared (simulated)");
        return Ok(());
    }

    println!();
    println!("[DEV MODE] Registration simulated (no API call)");
    println!("  Username: agent-DEV12345");
    println!("  User ID: dev_user_123");
    println!("  Role: agent");
    println!("  API Key: hyk_agent_dev_simulated");
    println!();
    println!("In dev mode, registration is bypassed for local testing.");

    Ok(())
}

/// Dev mode node - simulates node operations without API call
fn dev_mode_node(args: &cli::node::NodeArgs) -> Result<()> {
    use cli::node::NodeCommand;

    match &args.command {
        NodeCommand::Register { node_id, .. } => {
            let id = node_id.clone().unwrap_or_else(|| "dev-node".to_string());
            println!();
            println!("[DEV MODE] Node registration simulated (no API call)");
            println!("  Node ID: {}", id);
            println!("  Status: active");
        }
        NodeCommand::Status => {
            println!();
            println!("[DEV MODE] Node Status");
            println!("======================");
            println!("  Status: Simulated registered");
            println!("  Node ID: dev-node");
        }
        NodeCommand::Info => {
            println!();
            println!("[DEV MODE] Node Information");
            println!("===========================");
            println!("  Node ID: dev-node");
            println!("  Class: compute");
            println!("  Type: physical");
            println!("  Status: active");
        }
        NodeCommand::Unregister => {
            println!("[DEV MODE] Node unregistered (simulated)");
        }
        NodeCommand::Update { .. } => {
            println!("[DEV MODE] Node updated (simulated)");
        }
    }

    Ok(())
}

/// Dev mode run - collects profile but outputs locally instead of submitting
async fn dev_mode_run(config_path: &PathBuf, once: bool) -> Result<()> {
    info!("[DEV MODE] Starting hydra-agent v{}", env!("CARGO_PKG_VERSION"));

    // Load configuration
    let config = load_config(config_path)?;
    info!(node_id = %config.node.node_id, "[DEV MODE] Configuration loaded");

    // Collect profile
    info!("[DEV MODE] Collecting system profile...");
    let profile = collectors::collect_profile(&config).await?;
    info!(sections = ?profile.sections(), "[DEV MODE] Profile collected");

    // In dev mode, output profile to stdout as JSON
    println!();
    println!("[DEV MODE] Profile collected (not submitted to API)");
    println!("================================================");
    println!();

    // Pretty print profile summary
    println!("Node: {}", config.node.node_id);
    println!("Class: {}", config.node.class);
    println!("Type: {}", config.node.node_type);
    println!();
    println!("Sections collected:");
    for section in profile.sections() {
        println!("  - {}", section);
    }

    let home_dir = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
    let output_dir = PathBuf::from(home_dir).join("hydra").join("profiles");
    std::fs::create_dir_all(&output_dir).context("Failed to create dev mode output directory")?;

    let timestamp = chrono::Utc::now().format("%Y%m%dT%H%M%SZ");
    let filename = format!("profile-{}-{}.json", config.node.node_id, timestamp);
    let output_path = output_dir.join(filename);

    let json = serde_json::to_string_pretty(&profile)?;
    std::fs::write(&output_path, &json)?;
    println!();
    println!("Full profile saved to: {}", output_path.display());

    if !once {
        info!("[DEV MODE] Scheduling not active in dev mode.");
    }

    Ok(())
}

// ==================== Legacy Install/Uninstall Functions ====================
// These are kept for backward compatibility with 'hydra-agent install/uninstall'
// The new preferred way is 'hydra-agent service activate/deactivate'

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

    warn!("'hydra-agent install' is deprecated. Use 'hydra-agent service activate' instead.");

    info!("Installing hydra-agent as system service...");

    // Check if running as root
    #[cfg(unix)]
    if !nix::unistd::Uid::effective().is_root() {
        return Err(anyhow::anyhow!(
            "This command must be run as root (use sudo)"
        ));
    }

    // Create directories
    fs::create_dir_all(config_dir)
        .with_context(|| format!("Failed to create config dir: {}", config_dir.display()))?;
    fs::create_dir_all(log_dir)
        .with_context(|| format!("Failed to create log dir: {}", log_dir.display()))?;

    // Create vault directory
    let vault_dir = PathBuf::from("/var/cv/hydra");
    fs::create_dir_all(&vault_dir)?;
    #[cfg(unix)]
    fs::set_permissions(&vault_dir, fs::Permissions::from_mode(0o700))?;

    // Set permissions on config dir (750)
    #[cfg(unix)]
    fs::set_permissions(config_dir, fs::Permissions::from_mode(0o750))?;

    info!(
        "Created directories: {}, {}",
        config_dir.display(),
        log_dir.display()
    );

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
ReadWritePaths={} {} /var/cv/hydra

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
    println!("  2. Login: hydra-agent login -u <username>");
    println!("  3. Register agent: hydra-agent register");
    println!("  4. Register node: hydra-agent node register");
    println!("  5. Start service: sudo systemctl start hydra-agent");
    println!();

    Ok(())
}

fn uninstall_service(purge: bool) -> Result<()> {
    use std::fs;
    #[cfg(target_os = "linux")]
    use std::process::Command;

    warn!("'hydra-agent uninstall' is deprecated. Use 'hydra-agent service deactivate' instead.");

    info!("Uninstalling hydra-agent...");

    // Check if running as root
    #[cfg(unix)]
    if !nix::unistd::Uid::effective().is_root() {
        return Err(anyhow::anyhow!(
            "This command must be run as root (use sudo)"
        ));
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

        // Remove vault
        let vault_dir = PathBuf::from("/var/cv/hydra");
        if vault_dir.exists() {
            fs::remove_dir_all(&vault_dir)?;
            info!("Removed {}", vault_dir.display());
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
