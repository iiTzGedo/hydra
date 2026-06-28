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
use hydra_agent::config::{AgentConfig, AgentTier};
use hydra_agent::executor::CommandExecutor;
use hydra_agent::instance_lock;
use hydra_agent::server;
use hydra_agent::vault::Vault;

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();

    let level = if cli.verbose {
        Level::DEBUG
    } else {
        Level::INFO
    };
    let subscriber = FmtSubscriber::builder()
        .with_max_level(level)
        .json()
        .finish();
    tracing::subscriber::set_global_default(subscriber)?;

    let vault = Vault::default();

    let is_dev_mode = cli.mode == OperatingMode::Dev;
    if is_dev_mode {
        info!("Running in development mode (no API calls)");
    }

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
        Some(Commands::Unregister(args)) => {
            if is_dev_mode {
                return dev_mode_unregister(&args);
            }
            let config = load_config(&cli.config)?;
            cli::unregister::execute(&args, &config, &vault).await
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
        Some(Commands::Bootstrap(args)) => {
            if is_dev_mode {
                return Err(anyhow::anyhow!(
                    "Bootstrap requires live mode (it registers and profiles against the API)"
                ));
            }
            let config = load_config(&cli.config)?;
            cli::bootstrap::execute(&args, &config, &cli.config, &vault).await
        }
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
        Some(Commands::Upgrade(args)) => {
            let config = load_config(&cli.config)?;
            cli::upgrade::execute(args, &config, &vault).await
        }
        None => {
            if is_dev_mode {
                return dev_mode_run(&cli.config, true).await;
            }
            use clap::CommandFactory;
            Cli::command().print_help()?;
            println!();
            Ok(())
        }
    }
}

/// Loads the agent configuration from the specified path.
///
/// # Arguments
///
/// * `config_path` - Path to the TOML configuration file
///
/// # Returns
///
/// The parsed agent configuration.
///
/// # Errors
///
/// Returns an error if the configuration file cannot be read or parsed.
fn load_config(config_path: &std::path::Path) -> Result<AgentConfig> {
    AgentConfig::load(config_path).with_context(|| {
        format!(
            "Failed to load configuration from {}",
            config_path.display()
        )
    })
}

/// Runs the agent to collect and submit system profiles.
///
/// # Arguments
///
/// * `config_path` - Path to the configuration file
/// * `vault` - Credential vault for authentication
/// * `once` - If true, collect once and exit; otherwise enable scheduling
///
/// # Returns
///
/// Ok on success.
///
/// # Errors
///
/// Returns an error if authentication is unavailable, profile collection fails,
/// or profile submission fails.
async fn run_agent(config_path: &std::path::Path, vault: &Vault, once: bool) -> Result<()> {
    info!("Starting hydra-agent v{}", env!("CARGO_PKG_VERSION"));

    // Enforce single instance — abort if another agent is running
    let pid_path = instance_lock::default_pid_path();
    instance_lock::enforce_single_instance(&pid_path)?;

    let config = load_config(config_path)?;
    info!(node_id = %config.node.node_id, "Configuration loaded");

    if !vault.has_agent_credentials() && !vault.has_api_key() {
        instance_lock::release_instance_lock(&pid_path);
        return Err(anyhow::anyhow!(
            "No authentication available. Run 'hydra-agent register' first."
        ));
    }

    let api_client_arc = std::sync::Arc::new(api::ApiClient::new(&config, vault)?);
    let shared_config = std::sync::Arc::new(tokio::sync::RwLock::new(config.clone()));
    let shared_plugin_state = std::sync::Arc::new(tokio::sync::RwLock::new(
        hydra_agent::plugins::PluginState::new(),
    ));
    let agent_start_time = std::time::Instant::now();

    // Collect profile, reporting failures to notification system
    info!("Collecting system profile...");
    let profile = match collectors::collect_profile(&config).await {
        Ok(p) => {
            info!(sections = ?p.sections(), "Profile collected");
            p
        }
        Err(e) => {
            let err_msg = format!(
                "Profile collection failed on {}: {}",
                config.node.node_id, e
            );
            warn!("{}", err_msg);

            // Report collection failure (best-effort)
            let _ = api_client_arc
                .report_event(
                    "agent_profile_failed",
                    &format!("Profile collection failed: {}", config.node.node_id),
                    &err_msg,
                    Some(serde_json::json!({
                        "nodeId": config.node.node_id,
                        "error": e.to_string(),
                    })),
                )
                .await;

            return Err(e);
        }
    };

    // Submit profile, reporting failures to notification system
    info!("Submitting profile to API...");
    match api_client_arc.submit_profile(&profile).await {
        Ok(result) => {
            info!(
                profile_id = %result.profile_id,
                version = %result.version,
                "Profile submitted successfully"
            );

            // Report successful submission (best-effort)
            let _ = api_client_arc
                .report_event(
                    "agent_profile_submitted",
                    &format!("Profile submitted: {}", config.node.node_id),
                    &format!(
                        "Profile {} (v{}) submitted successfully for node {}",
                        result.profile_id, result.version, config.node.node_id
                    ),
                    Some(serde_json::json!({
                        "nodeId": config.node.node_id,
                        "profileId": result.profile_id,
                        "profileVersion": result.version,
                    })),
                )
                .await;
        }
        Err(e) => {
            let err_msg = format!(
                "Profile submission failed for {}: {}",
                config.node.node_id, e
            );
            warn!("{}", err_msg);

            // Report submission failure (best-effort)
            let _ = api_client_arc
                .report_event(
                    "agent_profile_failed",
                    &format!("Profile submission failed: {}", config.node.node_id),
                    &err_msg,
                    Some(serde_json::json!({
                        "nodeId": config.node.node_id,
                        "error": e.to_string(),
                    })),
                )
                .await;

            return Err(e);
        }
    }

    if !once {
        // Start the embedded control server for max-tier agents
        let server_handle = if config.node.tier == AgentTier::Max && config.server.enabled {
            let app_state = server::build_app_state(
                shared_config.clone(),
                config_path.to_path_buf(),
                vault,
                Some(api_client_arc.clone()),
                agent_start_time,
                shared_plugin_state.clone(),
            )?;

            let (shutdown_tx, shutdown_rx) = tokio::sync::watch::channel(false);
            let shutdown_signal = async move {
                let mut rx = shutdown_rx;
                let _ = rx.changed().await;
            };

            let handle = tokio::spawn(async move {
                if let Err(e) = server::start_server(app_state, shutdown_signal).await {
                    tracing::error!("Control server error: {}", e);
                }
            });

            Some((handle, shutdown_tx))
        } else {
            None
        };

        // Set up command polling for normal/max tier agents
        let should_poll = config.node.tier != AgentTier::Lite;
        let poll_secs = config.schedule.poll_interval_seconds;
        if should_poll {
            info!(poll_interval_seconds = poll_secs, "Command polling enabled");
        }

        // Create the command executor for poll-based execution
        let executor = CommandExecutor::new(
            shared_config,
            agent_start_time,
            Some(api_client_arc.clone()),
            Some(config_path.to_path_buf()),
            Some(vault.clone()),
            shared_plugin_state.clone(),
        );
        let node_id = config.node.node_id.clone();
        // Rebind client reference for the rest of the function
        let client = api_client_arc;

        // Scheduled collection + command poll loop
        if config.schedule.enabled || should_poll {
            let mut collection_interval = tokio::time::interval(std::time::Duration::from_secs(
                config.schedule.interval_seconds,
            ));
            // Skip the first immediate tick (we already collected above)
            collection_interval.tick().await;

            let mut poll_interval =
                tokio::time::interval(std::time::Duration::from_secs(poll_secs));
            // Skip the first immediate tick
            poll_interval.tick().await;

            if config.schedule.enabled {
                info!(
                    interval_seconds = config.schedule.interval_seconds,
                    "Starting scheduled collection loop"
                );
            }

            loop {
                tokio::select! {
                    _ = collection_interval.tick(), if config.schedule.enabled => {
                        info!("Scheduled collection triggered");
                        match collectors::collect_profile(&config).await {
                            Ok(profile) => {
                                info!(sections = ?profile.sections(), "Profile collected (scheduled)");
                                match client.submit_profile(&profile).await {
                                    Ok(result) => {
                                        info!(
                                            profile_id = %result.profile_id,
                                            version = %result.version,
                                            "Scheduled profile submitted"
                                        );
                                    }
                                    Err(e) => {
                                        warn!("Scheduled profile submission failed: {}", e);
                                    }
                                }
                            }
                            Err(e) => {
                                warn!("Scheduled profile collection failed: {}", e);
                            }
                        }
                    }
                    _ = poll_interval.tick(), if should_poll => {
                        poll_and_execute_commands(&client, &executor, &node_id).await;
                    }
                    _ = tokio::signal::ctrl_c() => {
                        info!("Shutdown signal received");
                        break;
                    }
                }
            }
        } else {
            // No scheduling and no polling — just keep the server running until interrupted
            info!("Scheduling and polling disabled. Waiting for shutdown signal...");
            let _ = tokio::signal::ctrl_c().await;
            info!("Shutdown signal received");
        }

        // Signal the server to shut down and wait for it
        if let Some((handle, shutdown_tx)) = server_handle {
            let _ = shutdown_tx.send(true);
            let _ = handle.await;
            info!("Control server stopped");
        }
    }

    // Release the instance lock on clean exit
    instance_lock::release_instance_lock(&pid_path);

    Ok(())
}

/// Poll the API for pending commands and execute them.
///
/// Commands are polled from `GET /nodes/{nodeId}/commands/poll`. Each received
/// command is dispatched to the executor engine, which routes to the appropriate
/// handler based on command category (service, node, agent). Results are
/// submitted back to the API.
async fn poll_and_execute_commands(
    client: &api::ApiClient,
    executor: &CommandExecutor,
    node_id: &str,
) {
    match client.poll_commands(node_id).await {
        Ok(commands) if commands.is_empty() => {
            // Nothing to do — normal case
        }
        Ok(commands) => {
            info!(count = commands.len(), "Received commands from poll");
            for cmd in commands {
                info!(
                    command_id = %cmd.command_id,
                    command_type = %cmd.command_type,
                    action = %cmd.action,
                    "Executing command"
                );

                let result = executor.execute(&cmd).await;

                let payload = api::CommandResultPayload {
                    success: result.success,
                    output: result.output,
                    exit_code: result.exit_code,
                    error: result.error,
                    data: result.data,
                };

                if let Err(e) = client
                    .submit_command_result(node_id, &cmd.command_id, &payload)
                    .await
                {
                    warn!(
                        command_id = %cmd.command_id,
                        error = %e,
                        "Failed to submit command result"
                    );
                }
            }
        }
        Err(e) => {
            warn!("Command poll failed: {}", e);
        }
    }
}

/// Displays the agent status including service state and vault contents.
///
/// # Arguments
///
/// * `config_path` - Path to the configuration file
/// * `vault` - Credential vault to check status
///
/// # Returns
///
/// Ok on success.
///
/// # Errors
///
/// Returns an error if status cannot be determined.
fn show_status(config_path: &std::path::Path, vault: &Vault) -> Result<()> {
    #[cfg(target_os = "linux")]
    use std::process::Command;

    println!();
    println!("Hydra Agent Status");
    println!("==================");
    println!();

    println!("Version: {}", env!("CARGO_PKG_VERSION"));
    println!();

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

    let vault_status = vault.status();
    print!("{}", vault_status);

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

    let username = args
        .username
        .clone()
        .unwrap_or_else(|| "dev-admin".to_string());

    println!();
    println!("[DEV MODE] Login simulated (no API call)");
    println!("  User: {} (admin)", username);
    println!("  Access Token: dev_token_simulated");
    println!();
    println!("In dev mode, authentication is bypassed for local testing.");

    Ok(())
}

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

fn dev_mode_unregister(args: &cli::unregister::UnregisterArgs) -> Result<()> {
    println!();
    println!("[DEV MODE] Agent Unregistration");
    println!("===============================");
    println!();

    if !args.force {
        println!("Would prompt for confirmation (skipped in dev mode)");
        println!();
    }

    println!("Agent ID: agent-DEV12345");
    println!();
    println!("[DEV MODE] Unregistration simulated (no API call)");
    if args.keep_local {
        println!("  Local credentials kept (--keep-local)");
    } else {
        println!("  Local credentials cleared (simulated)");
    }
    println!();
    println!("In dev mode, unregistration is bypassed for local testing.");

    Ok(())
}

fn dev_mode_node(args: &cli::node::NodeArgs) -> Result<()> {
    use cli::node::NodeCommand;

    if let Some(update) = &args.update {
        println!("[DEV MODE] Node update simulated: {}", update);
        return Ok(());
    }

    match &args.command {
        Some(NodeCommand::Register { node_id, .. }) => {
            let id = node_id.clone().unwrap_or_else(|| "dev-node".to_string());
            println!();
            println!("[DEV MODE] Node registration simulated (no API call)");
            println!("  Node ID: {}", id);
            println!("  Status: active");
        }
        Some(NodeCommand::Status) | None => {
            println!();
            println!("[DEV MODE] Node Status");
            println!("======================");
            println!("  Status: Simulated registered");
            println!("  Node ID: dev-node");
        }
        Some(NodeCommand::Info) => {
            println!();
            println!("[DEV MODE] Node Information");
            println!("===========================");
            println!("  Node ID: dev-node");
            println!("  Class: compute");
            println!("  Type: physical");
            println!("  Status: active");
        }
        Some(NodeCommand::Unregister) => {
            println!("[DEV MODE] Node unregistered (simulated)");
        }
        Some(NodeCommand::Update { .. }) => {
            println!("[DEV MODE] Node updated (simulated)");
        }
    }

    Ok(())
}

async fn dev_mode_run(config_path: &std::path::Path, once: bool) -> Result<()> {
    let home_dir = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
    let output_dir = PathBuf::from(&home_dir).join("hydra").join("profiles");

    println!();
    println!("╔═══════════════════════════════════════════════════════════╗");
    println!("║                  HYDRA AGENT - DEV MODE                   ║");
    println!("╠═══════════════════════════════════════════════════════════╣");
    println!("║  No API connectivity - profiles saved locally            ║");
    println!("║  Output: ~/hydra/profiles/                               ║");
    println!("╚═══════════════════════════════════════════════════════════╝");
    println!();

    info!(
        "[DEV MODE] Starting hydra-agent v{}",
        env!("CARGO_PKG_VERSION")
    );

    let config = load_config(config_path)?;
    info!(node_id = %config.node.node_id, "[DEV MODE] Configuration loaded");

    info!("[DEV MODE] Collecting system profile...");
    let profile = collectors::collect_profile(&config).await?;
    info!(sections = ?profile.sections(), "[DEV MODE] Profile collected");

    println!();
    println!("[DEV MODE] Profile collected successfully");
    println!("=========================================");
    println!();

    println!("Node: {}", config.node.node_id);
    println!("Class: {}", config.node.class);
    println!("Type: {}", config.node.node_type);
    println!();
    println!("Sections collected:");
    for section in profile.sections() {
        println!("  - {}", section);
    }

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

    #[cfg(unix)]
    if !nix::unistd::Uid::effective().is_root() {
        return Err(anyhow::anyhow!(
            "This command must be run as root (use sudo)"
        ));
    }

    fs::create_dir_all(config_dir)
        .with_context(|| format!("Failed to create config dir: {}", config_dir.display()))?;
    fs::create_dir_all(log_dir)
        .with_context(|| format!("Failed to create log dir: {}", log_dir.display()))?;

    let vault_dir = PathBuf::from("/var/cv/hydra");
    fs::create_dir_all(&vault_dir)?;
    #[cfg(unix)]
    fs::set_permissions(&vault_dir, fs::Permissions::from_mode(0o700))?;

    #[cfg(unix)]
    fs::set_permissions(config_dir, fs::Permissions::from_mode(0o750))?;

    info!(
        "Created directories: {}, {}",
        config_dir.display(),
        log_dir.display()
    );

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

        Command::new("systemctl")
            .args(["daemon-reload"])
            .status()
            .context("Failed to reload systemd")?;

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

    #[cfg(unix)]
    if !nix::unistd::Uid::effective().is_root() {
        return Err(anyhow::anyhow!(
            "This command must be run as root (use sudo)"
        ));
    }

    #[cfg(target_os = "linux")]
    {
        let _ = Command::new("systemctl")
            .args(["stop", "hydra-agent.service"])
            .status();

        let _ = Command::new("systemctl")
            .args(["disable", "hydra-agent.service"])
            .status();

        let service_path = PathBuf::from("/etc/systemd/system/hydra-agent.service");
        if service_path.exists() {
            fs::remove_file(&service_path)?;
            info!("Removed {}", service_path.display());
        }

        let _ = Command::new("systemctl").args(["daemon-reload"]).status();
    }

    let binary_path = PathBuf::from("/usr/local/bin/hydra-agent");
    if binary_path.exists() {
        fs::remove_file(&binary_path)?;
        info!("Removed {}", binary_path.display());
    }

    if purge {
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
