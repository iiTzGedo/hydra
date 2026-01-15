//! Service command for managing the agent as a system service.
//!
//! Provides commands to install, start, stop, and manage the hydra-agent
//! as a systemd service (on Linux) or other service managers.

use anyhow::{anyhow, Context, Result};
use clap::{Args, Subcommand};
use std::path::PathBuf;
use tracing::info;

/// Service command arguments
#[derive(Args, Debug)]
pub struct ServiceArgs {
    #[command(subcommand)]
    pub command: ServiceCommand,
}

/// Service runtime mode
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum ServiceRuntime {
    /// Systemd service (default on Linux)
    #[default]
    Systemd,
    /// Docker container
    Docker,
    /// Cron job (no daemon)
    Cron,
}

#[derive(Subcommand, Debug)]
pub enum ServiceCommand {
    /// Activate (install) the agent as a system service
    Activate {
        /// Installation directory for the binary
        #[arg(long, default_value = "/usr/local/bin")]
        install_dir: PathBuf,

        /// Don't start the service after activation
        #[arg(long)]
        no_start: bool,

        /// Create 'hydra' alias symlink
        #[arg(long)]
        with_alias: bool,

        /// Setup as Docker service instead of systemd
        #[arg(short, long)]
        docker: bool,

        /// Setup as cron job with specified schedule (e.g., "0 */6 * * *" for every 6 hours)
        #[arg(short, long, value_name = "CRON_EXPR")]
        cron: Option<String>,
    },

    /// Deactivate (uninstall) the agent system service
    Deactivate {
        /// Also remove configuration files and vault data
        #[arg(long)]
        purge: bool,
    },

    /// Start the agent service
    Start,

    /// Stop the agent service
    Stop,

    /// Restart the agent service
    Restart,

    /// Show service status
    Status,

    /// Enable service to start on boot
    Enable,

    /// Disable service from starting on boot
    Disable,

    /// View service logs
    Logs {
        /// Number of lines to show
        #[arg(short = 'n', long, default_value = "50")]
        lines: u32,

        /// Follow log output
        #[arg(short, long)]
        follow: bool,
    },

    /// Run the agent in foreground (for debugging)
    Run {
        /// Run once and exit (don't schedule)
        #[arg(long)]
        once: bool,
    },
}

/// Execute the service command
pub fn execute(args: &ServiceArgs, config_path: &PathBuf) -> Result<()> {
    match &args.command {
        ServiceCommand::Activate {
            install_dir,
            no_start,
            with_alias,
            docker,
            cron,
        } => {
            // Determine runtime mode
            let runtime = if *docker {
                ServiceRuntime::Docker
            } else if cron.is_some() {
                ServiceRuntime::Cron
            } else {
                ServiceRuntime::Systemd
            };
            activate_service(install_dir, config_path, *no_start, *with_alias, runtime, cron.as_deref())
        }
        ServiceCommand::Deactivate { purge } => deactivate_service(*purge),
        ServiceCommand::Start => start_service(),
        ServiceCommand::Stop => stop_service(),
        ServiceCommand::Restart => restart_service(),
        ServiceCommand::Status => show_status(),
        ServiceCommand::Enable => enable_service(),
        ServiceCommand::Disable => disable_service(),
        ServiceCommand::Logs { lines, follow } => show_logs(*lines, *follow),
        ServiceCommand::Run { once: _ } => {
            // This is a placeholder - actual run logic is in main.rs
            // This just signals that we want to run
            Err(anyhow!("Use 'hydra-agent run' instead of 'hydra-agent service run'"))
        }
    }
}

/// Check if running as root (Unix only)
fn check_root() -> Result<()> {
    #[cfg(unix)]
    {
        if !nix::unistd::Uid::effective().is_root() {
            return Err(anyhow!(
                "This command requires root privileges. Use 'sudo hydra-agent service ...'"
            ));
        }
    }
    Ok(())
}

/// Activate (install) the agent as a system service
fn activate_service(
    install_dir: &PathBuf,
    config_path: &PathBuf,
    no_start: bool,
    with_alias: bool,
    runtime: ServiceRuntime,
    cron_expr: Option<&str>,
) -> Result<()> {
    use std::fs;
    #[cfg(unix)]
    use std::os::unix::fs::PermissionsExt;

    // Docker mode doesn't require root for activation
    if runtime != ServiceRuntime::Docker {
        check_root()?;
    }

    let runtime_name = match runtime {
        ServiceRuntime::Systemd => "systemd service",
        ServiceRuntime::Docker => "Docker container",
        ServiceRuntime::Cron => "cron job",
    };
    info!("Activating hydra-agent as {}...", runtime_name);

    // Get the current binary path
    let current_exe = std::env::current_exe().context("Failed to get current executable path")?;
    let target_exe = install_dir.join("hydra-agent");

    // Create install directory (not needed for Docker)
    if runtime != ServiceRuntime::Docker {
        fs::create_dir_all(install_dir)
            .with_context(|| format!("Failed to create directory: {}", install_dir.display()))?;

        // Copy binary if not already in place
        if current_exe != target_exe {
            fs::copy(&current_exe, &target_exe)
                .with_context(|| format!("Failed to copy binary to {}", target_exe.display()))?;

            #[cfg(unix)]
            fs::set_permissions(&target_exe, fs::Permissions::from_mode(0o755))?;

            info!("Installed binary to {}", target_exe.display());
        }

        // Create alias symlink if requested
        if with_alias {
            let alias_path = install_dir.join("hydra");
            if alias_path.exists() {
                fs::remove_file(&alias_path)?;
            }
            #[cfg(unix)]
            std::os::unix::fs::symlink(&target_exe, &alias_path)
                .with_context(|| format!("Failed to create alias at {}", alias_path.display()))?;
            info!("Created alias: hydra -> hydra-agent");
        }
    }

    // Setup based on runtime mode
    match runtime {
        ServiceRuntime::Systemd => {
            #[cfg(target_os = "linux")]
            {
                install_systemd_unit(install_dir, config_path)?;
                if !no_start {
                    start_service()?;
                }
            }

            #[cfg(not(target_os = "linux"))]
            {
                return Err(anyhow!("Systemd service installation is only supported on Linux"));
            }
        }
        ServiceRuntime::Docker => {
            setup_docker_service(config_path)?;
            if !no_start {
                start_docker_service()?;
            }
        }
        ServiceRuntime::Cron => {
            let expr = cron_expr.ok_or_else(|| anyhow!("Cron expression is required for cron mode"))?;
            setup_cron_job(install_dir, config_path, expr)?;
        }
    }

    println!();
    println!("✓ Service activated successfully!");
    println!("  Runtime: {}", runtime_name);
    if runtime != ServiceRuntime::Docker {
        println!("  Binary: {}", target_exe.display());
    }
    println!("  Config: {}", config_path.display());
    if with_alias && runtime != ServiceRuntime::Docker {
        println!("  Alias: hydra -> hydra-agent");
    }
    if let Some(expr) = cron_expr {
        println!("  Schedule: {}", expr);
    }
    println!();

    Ok(())
}

/// Setup Docker-based service
fn setup_docker_service(config_path: &PathBuf) -> Result<()> {
    use std::fs;
    use std::process::Command;

    info!("Setting up Docker-based hydra-agent service...");

    // Check if Docker is available
    let docker_check = Command::new("docker")
        .arg("--version")
        .output();

    if docker_check.is_err() {
        return Err(anyhow!("Docker is not installed or not available in PATH"));
    }

    // Create a docker-compose.yml file for easier management
    let compose_dir = PathBuf::from("/etc/hydra");
    fs::create_dir_all(&compose_dir)?;

    let compose_content = format!(r#"# Hydra Agent Docker Service
# Generated by hydra-agent service activate --docker

version: '3.8'

services:
  hydra-agent:
    image: hydra-agent:latest
    container_name: hydra-agent
    restart: unless-stopped
    volumes:
      - {}:/etc/hydra/agent.toml:ro
      - /var/cv/hydra:/var/cv/hydra
    environment:
      - HYDRA_CONFIG=/etc/hydra/agent.toml
    network_mode: host
    privileged: true  # Required for hardware profiling
    command: ["run"]
"#, config_path.display());

    let compose_path = compose_dir.join("docker-compose.yml");
    fs::write(&compose_path, compose_content)?;
    info!("Created docker-compose.yml at {}", compose_path.display());

    println!();
    println!("Docker service configuration created.");
    println!("Note: You need to build or pull the hydra-agent Docker image first.");
    println!();
    println!("To build locally:");
    println!("  docker build -t hydra-agent:latest .");
    println!();
    println!("To start:");
    println!("  cd /etc/hydra && docker-compose up -d");

    Ok(())
}

/// Start Docker service
fn start_docker_service() -> Result<()> {
    use std::process::Command;

    let compose_path = PathBuf::from("/etc/hydra/docker-compose.yml");
    if !compose_path.exists() {
        return Err(anyhow!("Docker compose file not found. Run 'service activate --docker' first."));
    }

    info!("Starting Docker-based hydra-agent service...");

    let status = Command::new("docker-compose")
        .args(["-f", "/etc/hydra/docker-compose.yml", "up", "-d"])
        .status()
        .context("Failed to start docker-compose")?;

    if status.success() {
        println!("✓ Docker service started");
    } else {
        return Err(anyhow!("Failed to start Docker service"));
    }

    Ok(())
}

/// Setup cron job for scheduled execution
fn setup_cron_job(install_dir: &PathBuf, config_path: &PathBuf, cron_expr: &str) -> Result<()> {
    use std::process::Command;

    // Validate cron expression (basic check for 5 fields)
    let parts: Vec<&str> = cron_expr.split_whitespace().collect();
    if parts.len() != 5 {
        return Err(anyhow!(
            "Invalid cron expression '{}'. Expected 5 fields (minute hour day month weekday)",
            cron_expr
        ));
    }

    info!("Setting up cron job with schedule: {}", cron_expr);

    let binary_path = install_dir.join("hydra-agent");
    let cron_line = format!(
        "{} {} run --once -c {} >> /var/log/hydra/cron.log 2>&1\n",
        cron_expr,
        binary_path.display(),
        config_path.display()
    );

    // Create log directory
    std::fs::create_dir_all("/var/log/hydra")?;

    // Use crontab to add the job
    // First, get existing crontab (ignore errors if no crontab exists)
    let existing = Command::new("crontab")
        .arg("-l")
        .output();

    let mut crontab_content = if let Ok(output) = existing {
        if output.status.success() {
            String::from_utf8_lossy(&output.stdout).to_string()
        } else {
            String::new()
        }
    } else {
        String::new()
    };

    // Remove any existing hydra-agent entries
    let filtered: Vec<&str> = crontab_content
        .lines()
        .filter(|line| !line.contains("hydra-agent"))
        .collect();
    crontab_content = filtered.join("\n");
    if !crontab_content.is_empty() && !crontab_content.ends_with('\n') {
        crontab_content.push('\n');
    }

    // Add the new cron line
    crontab_content.push_str(&cron_line);

    // Write new crontab
    let mut child = Command::new("crontab")
        .arg("-")
        .stdin(std::process::Stdio::piped())
        .spawn()
        .context("Failed to update crontab")?;

    if let Some(stdin) = child.stdin.as_mut() {
        use std::io::Write;
        stdin.write_all(crontab_content.as_bytes())?;
    }

    let status = child.wait()?;
    if !status.success() {
        return Err(anyhow!("Failed to install cron job"));
    }

    info!("Cron job installed successfully");
    println!();
    println!("Cron job configured:");
    println!("  Schedule: {}", cron_expr);
    println!("  Command: {} run --once", binary_path.display());
    println!("  Log: /var/log/hydra/cron.log");
    println!();
    println!("To view/edit: crontab -e");
    println!("To remove: crontab -l | grep -v hydra-agent | crontab -");

    Ok(())
}

/// Install systemd unit file
#[cfg(target_os = "linux")]
fn install_systemd_unit(install_dir: &PathBuf, config_path: &PathBuf) -> Result<()> {
    use std::fs;
    use std::process::Command;

    let config_dir = config_path.parent().unwrap_or(std::path::Path::new("/etc/hydra"));
    let log_dir = PathBuf::from("/var/log/hydra");
    let vault_dir = PathBuf::from("/var/cv/hydra");

    // Ensure directories exist
    fs::create_dir_all(&log_dir)?;
    fs::create_dir_all(&vault_dir)?;

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
Environment=HYDRA_CONFIG={}

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths={} {} {}

[Install]
WantedBy=multi-user.target
"#,
        install_dir.display(),
        config_path.display(),
        log_dir.display(),
        config_dir.display(),
        vault_dir.display(),
    );

    let service_path = PathBuf::from("/etc/systemd/system/hydra-agent.service");
    fs::write(&service_path, systemd_unit)
        .with_context(|| format!("Failed to write {}", service_path.display()))?;

    info!("Created systemd unit: {}", service_path.display());

    // Reload systemd daemon
    Command::new("systemctl")
        .args(["daemon-reload"])
        .status()
        .context("Failed to reload systemd")?;

    // Enable the service
    Command::new("systemctl")
        .args(["enable", "hydra-agent.service"])
        .status()
        .context("Failed to enable service")?;

    info!("Enabled hydra-agent.service");

    Ok(())
}

/// Deactivate (uninstall) the agent service
fn deactivate_service(purge: bool) -> Result<()> {
    use std::fs;

    check_root()?;

    info!("Deactivating hydra-agent service...");

    // Stop and disable service first
    #[cfg(target_os = "linux")]
    {
        use std::process::Command;

        // Stop the service
        let _ = Command::new("systemctl")
            .args(["stop", "hydra-agent.service"])
            .status();

        // Disable the service
        let _ = Command::new("systemctl")
            .args(["disable", "hydra-agent.service"])
            .status();

        // Remove systemd unit
        let service_path = PathBuf::from("/etc/systemd/system/hydra-agent.service");
        if service_path.exists() {
            fs::remove_file(&service_path)?;
            info!("Removed {}", service_path.display());
        }

        // Reload systemd
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

    // Remove alias if exists
    let alias_path = PathBuf::from("/usr/local/bin/hydra");
    if alias_path.exists() && alias_path.is_symlink() {
        fs::remove_file(&alias_path)?;
        info!("Removed alias: {}", alias_path.display());
    }

    if purge {
        // Remove configuration
        let config_dir = PathBuf::from("/etc/hydra");
        if config_dir.exists() {
            fs::remove_dir_all(&config_dir)?;
            info!("Removed {}", config_dir.display());
        }

        // Remove logs
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
    println!("✓ Service deactivated successfully!");
    if !purge {
        println!("  Configuration and vault data preserved. Use --purge to remove.");
    }
    println!();

    Ok(())
}

/// Start the service
fn start_service() -> Result<()> {
    check_root()?;

    #[cfg(target_os = "linux")]
    {
        use std::process::Command;

        let status = Command::new("systemctl")
            .args(["start", "hydra-agent.service"])
            .status()
            .context("Failed to start service")?;

        if status.success() {
            println!("✓ Service started");
        } else {
            return Err(anyhow!("Failed to start service"));
        }
    }

    #[cfg(not(target_os = "linux"))]
    {
        return Err(anyhow!("Service management is only supported on Linux"));
    }

    Ok(())
}

/// Stop the service
fn stop_service() -> Result<()> {
    check_root()?;

    #[cfg(target_os = "linux")]
    {
        use std::process::Command;

        let status = Command::new("systemctl")
            .args(["stop", "hydra-agent.service"])
            .status()
            .context("Failed to stop service")?;

        if status.success() {
            println!("✓ Service stopped");
        } else {
            return Err(anyhow!("Failed to stop service"));
        }
    }

    #[cfg(not(target_os = "linux"))]
    {
        return Err(anyhow!("Service management is only supported on Linux"));
    }

    Ok(())
}

/// Restart the service
fn restart_service() -> Result<()> {
    check_root()?;

    #[cfg(target_os = "linux")]
    {
        use std::process::Command;

        let status = Command::new("systemctl")
            .args(["restart", "hydra-agent.service"])
            .status()
            .context("Failed to restart service")?;

        if status.success() {
            println!("✓ Service restarted");
        } else {
            return Err(anyhow!("Failed to restart service"));
        }
    }

    #[cfg(not(target_os = "linux"))]
    {
        return Err(anyhow!("Service management is only supported on Linux"));
    }

    Ok(())
}

/// Show service status
fn show_status() -> Result<()> {
    println!();
    println!("Service Status");
    println!("==============");

    #[cfg(target_os = "linux")]
    {
        use std::process::Command;

        // Check if unit exists
        let unit_path = PathBuf::from("/etc/systemd/system/hydra-agent.service");
        if !unit_path.exists() {
            println!("  Installed: No");
            println!();
            println!("Run 'hydra-agent service activate' to install the service.");
            return Ok(());
        }

        println!("  Installed: Yes");

        // Check if active
        let active = Command::new("systemctl")
            .args(["is-active", "hydra-agent.service"])
            .output();

        if let Ok(output) = active {
            let state = String::from_utf8_lossy(&output.stdout).trim().to_string();
            println!("  Active: {}", state);
        }

        // Check if enabled
        let enabled = Command::new("systemctl")
            .args(["is-enabled", "hydra-agent.service"])
            .output();

        if let Ok(output) = enabled {
            let state = String::from_utf8_lossy(&output.stdout).trim().to_string();
            println!("  Enabled: {}", state);
        }

        // Get PID if running
        let show = Command::new("systemctl")
            .args(["show", "hydra-agent.service", "--property=MainPID"])
            .output();

        if let Ok(output) = show {
            let pid_line = String::from_utf8_lossy(&output.stdout);
            if let Some(pid) = pid_line.strip_prefix("MainPID=") {
                let pid = pid.trim();
                if pid != "0" {
                    println!("  PID: {}", pid);
                }
            }
        }

        // Get uptime
        let show = Command::new("systemctl")
            .args(["show", "hydra-agent.service", "--property=ActiveEnterTimestamp"])
            .output();

        if let Ok(output) = show {
            let ts_line = String::from_utf8_lossy(&output.stdout);
            if let Some(ts) = ts_line.strip_prefix("ActiveEnterTimestamp=") {
                let ts = ts.trim();
                if !ts.is_empty() {
                    println!("  Since: {}", ts);
                }
            }
        }
    }

    #[cfg(not(target_os = "linux"))]
    {
        println!("  Status: N/A (systemd not available)");
    }

    println!();
    Ok(())
}

/// Enable service to start on boot
fn enable_service() -> Result<()> {
    check_root()?;

    #[cfg(target_os = "linux")]
    {
        use std::process::Command;

        let status = Command::new("systemctl")
            .args(["enable", "hydra-agent.service"])
            .status()
            .context("Failed to enable service")?;

        if status.success() {
            println!("✓ Service enabled (will start on boot)");
        } else {
            return Err(anyhow!("Failed to enable service"));
        }
    }

    #[cfg(not(target_os = "linux"))]
    {
        return Err(anyhow!("Service management is only supported on Linux"));
    }

    Ok(())
}

/// Disable service from starting on boot
fn disable_service() -> Result<()> {
    check_root()?;

    #[cfg(target_os = "linux")]
    {
        use std::process::Command;

        let status = Command::new("systemctl")
            .args(["disable", "hydra-agent.service"])
            .status()
            .context("Failed to disable service")?;

        if status.success() {
            println!("✓ Service disabled (will not start on boot)");
        } else {
            return Err(anyhow!("Failed to disable service"));
        }
    }

    #[cfg(not(target_os = "linux"))]
    {
        return Err(anyhow!("Service management is only supported on Linux"));
    }

    Ok(())
}

/// Show service logs
fn show_logs(lines: u32, follow: bool) -> Result<()> {
    #[cfg(target_os = "linux")]
    {
        use std::process::Command;

        let lines_str = lines.to_string();
        let mut args = vec!["-u", "hydra-agent.service", "-n", &lines_str];

        if follow {
            args.push("-f");
        }

        let status = Command::new("journalctl")
            .args(&args)
            .status()
            .context("Failed to show logs")?;

        if !status.success() {
            return Err(anyhow!("Failed to retrieve logs"));
        }
    }

    #[cfg(not(target_os = "linux"))]
    {
        return Err(anyhow!("Log viewing is only supported on Linux (journalctl)"));
    }

    Ok(())
}
