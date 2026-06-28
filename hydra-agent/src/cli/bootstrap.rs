//! Headless bootstrap command.
//!
//! Performs the full unattended onboarding sequence in one idempotent step:
//! register the agent account (with a registration token), ensure a valid API
//! key, register this node, collect and submit the first profile, and activate
//! the system service for ongoing scheduled collection.
//!
//! This is what the API-generated installer invokes (`hydra-agent bootstrap
//! --token <TOKEN>`) to take a freshly installed binary all the way to a
//! profiled, service-managed node without any interactive steps. Each step is
//! safe to re-run: registration short-circuits if already registered, node
//! registration tolerates the already-registered (409) case, and service
//! activation reinstalls cleanly.

use anyhow::{Context, Result};
use clap::Args;
use std::path::Path;
use tracing::{info, warn};

use crate::api::ApiClient;
use crate::cli::{login, node, register, service};
use crate::collectors;
use crate::config::AgentConfig;
use crate::vault::Vault;

/// Bootstrap command arguments.
#[derive(Args, Debug)]
pub struct BootstrapArgs {
    /// Registration token (user scope) used to register the agent account.
    #[arg(short, long)]
    pub token: String,

    /// Override the node ID from config (default: value in agent.toml).
    #[arg(long)]
    pub node_id: Option<String>,

    /// Node class (compute, networking, iot).
    #[arg(long)]
    pub class: Option<String>,

    /// Node kind (bare-metal, vm, lxc, docker, kubernetes-pod).
    #[arg(long)]
    pub kind: Option<String>,

    /// Installation directory for the service binary.
    #[arg(long, default_value = "/usr/local/bin")]
    pub install_dir: std::path::PathBuf,

    /// Skip installing/activating the system service.
    #[arg(long)]
    pub no_service: bool,

    /// Skip collecting the first profile.
    #[arg(long)]
    pub no_profile: bool,
}

/// Execute the headless bootstrap sequence.
///
/// # Errors
///
/// Returns an error if a required step (agent registration, API key creation,
/// node registration, or — unless `--no-profile` — the first profile
/// collection) fails. Service activation failure is non-fatal: the node is
/// already registered and profiled, so the error is logged and bootstrap still
/// succeeds (the user can re-run `hydra-agent service activate`).
pub async fn execute(
    args: &BootstrapArgs,
    config: &AgentConfig,
    config_path: &Path,
    vault: &Vault,
) -> Result<()> {
    println!();
    println!("Hydra Agent Bootstrap");
    println!("=====================");
    println!("  Node: {}", config.node.node_id);
    println!();

    // 1. Register the agent account. Idempotent: register::execute returns Ok and
    //    prints "already registered" when credentials already exist in the vault.
    info!("[1/5] Registering agent account...");
    let register_args = register::RegisterArgs {
        token: Some(args.token.clone()),
        username: None,
        password: None,
        override_registration: false,
        status: false,
        clear: false,
    };
    register::execute(&register_args, config, vault)
        .await
        .context("agent account registration failed")?;

    // 2. Ensure a usable API key. register_with_token normally creates one, but if
    //    it is missing or expired (e.g. on a re-run), recover it via agent login.
    let api_key_ok = vault.has_api_key() && !vault.is_api_key_expired().unwrap_or(true);
    if !api_key_ok {
        info!("[2/5] Creating agent API key...");
        let login_args = login::LoginArgs {
            username: None,
            password: None,
            agent: true,
            force: false,
            refresh: false,
            status: false,
            logout: false,
        };
        login::execute(&login_args, config, vault)
            .await
            .context("agent login (API key creation) failed")?;
    } else {
        info!("[2/5] Valid API key already present");
    }

    // 3. Register this node. Idempotent: node registration handles the
    //    already-registered (HTTP 409) case gracefully.
    info!("[3/5] Registering node...");
    let node_args = node::NodeArgs {
        update: None,
        command: Some(node::NodeCommand::Register {
            token: None,
            node_id: args.node_id.clone(),
            class: args.class.clone(),
            node_type: None,
            kind: args.kind.clone(),
            display_name: None,
            tags: None,
            force: false,
        }),
    };
    node::execute(&node_args, config, vault)
        .await
        .context("node registration failed")?;

    // 4. Collect and submit the first profile synchronously — before the service
    //    starts — so the single-instance lock never collides and the operator gets
    //    immediate confirmation the node is visible in the web UI.
    if args.no_profile {
        info!("[4/5] Skipping first profile (--no-profile)");
    } else {
        info!("[4/5] Collecting and submitting first profile...");
        collect_and_submit_first_profile(config, vault).await?;
    }

    // 5. Activate the system service for ongoing scheduled collection. Non-fatal:
    //    the node is already registered and profiled at this point.
    if args.no_service {
        info!("[5/5] Skipping service activation (--no-service)");
    } else {
        info!("[5/5] Activating system service...");
        let service_args = service::ServiceArgs {
            cron: None,
            command: Some(service::ServiceCommand::Activate {
                install_dir: args.install_dir.clone(),
                no_start: false,
                with_alias: false,
                docker: false,
                cron: None,
            }),
        };
        if let Err(e) = service::execute(&service_args, config_path) {
            warn!(
                "Service activation failed (node is registered and profiled): {}. \
                 Re-run with 'hydra-agent service activate'.",
                e
            );
        }
    }

    println!();
    println!("Bootstrap complete for node '{}'.", config.node.node_id);
    println!("The node and its profile should now be visible in the Hydra web UI.");
    println!();
    Ok(())
}

/// Collect a profile and submit it once, reporting success/failure as events.
///
/// Mirrors the one-shot collection path of the scheduled run loop so the first
/// profile is captured immediately during onboarding.
async fn collect_and_submit_first_profile(config: &AgentConfig, vault: &Vault) -> Result<()> {
    let api_client = ApiClient::new(config, vault).context("failed to build API client")?;

    let profile = match collectors::collect_profile(config).await {
        Ok(p) => {
            info!(sections = ?p.sections(), "Profile collected");
            p
        }
        Err(e) => {
            let _ = api_client
                .report_event(
                    "agent_profile_failed",
                    &format!("Profile collection failed: {}", config.node.node_id),
                    &format!("Profile collection failed on {}: {}", config.node.node_id, e),
                    Some(serde_json::json!({
                        "nodeId": config.node.node_id,
                        "error": e.to_string(),
                    })),
                )
                .await;
            return Err(e).context("first profile collection failed");
        }
    };

    match api_client.submit_profile(&profile).await {
        Ok(result) => {
            info!(
                profile_id = %result.profile_id,
                version = %result.version,
                "First profile submitted successfully"
            );
            let _ = api_client
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
            Ok(())
        }
        Err(e) => {
            let _ = api_client
                .report_event(
                    "agent_profile_failed",
                    &format!("Profile submission failed: {}", config.node.node_id),
                    &format!("Profile submission failed for {}: {}", config.node.node_id, e),
                    Some(serde_json::json!({
                        "nodeId": config.node.node_id,
                        "error": e.to_string(),
                    })),
                )
                .await;
            Err(e).context("first profile submission failed")
        }
    }
}
