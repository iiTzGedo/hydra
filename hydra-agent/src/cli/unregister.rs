//! Unregister command for removing agent registration from Hydra.
//!
//! Unregisters the agent system account from the Hydra API and clears
//! local vault credentials. Requires admin/operator authentication.

use anyhow::{anyhow, Context, Result};
use clap::Args;
use reqwest::Client;
use serde::Deserialize;
use std::io::{self, Write};
use std::time::Duration;
use tracing::{debug, info};

use crate::config::AgentConfig;
use crate::vault::Vault;

/// Unregister command arguments
#[derive(Args, Debug)]
pub struct UnregisterArgs {
    /// Force unregister without confirmation prompt
    #[arg(short, long)]
    pub force: bool,

    /// Keep local vault credentials (only unregister from API)
    #[arg(long)]
    pub keep_local: bool,
}

#[derive(Debug, Deserialize)]
struct ApiError {
    error: ApiErrorDetail,
}

#[derive(Debug, Deserialize)]
struct ApiErrorDetail {
    code: String,
    message: String,
}

/// Execute the unregister command
pub async fn execute(args: &UnregisterArgs, config: &AgentConfig, vault: &Vault) -> Result<()> {
    let creds = match vault.load_agent_credentials()? {
        Some(c) => c,
        None => {
            println!("No agent registration found.");
            println!("Nothing to unregister.");
            return Ok(());
        }
    };

    println!();
    println!("Agent Unregistration");
    println!("====================");
    println!();
    println!("Agent ID: {}", creds.username);
    println!();

    if !args.force {
        println!("WARNING: This will:");
        println!("  - Delete the agent system account from Hydra");
        if !args.keep_local {
            println!("  - Clear all local credentials from the vault");
        }
        println!();
        print!("Are you sure you want to unregister this agent? (y/N): ");
        io::stdout().flush()?;

        let mut input = String::new();
        io::stdin().read_line(&mut input)?;
        let confirmed = input.trim().to_lowercase();

        if confirmed != "y" && confirmed != "yes" {
            println!("Unregistration cancelled.");
            return Ok(());
        }
        println!();
    }

    let session = vault.load_session()?;
    let access_token = match session {
        Some(s) => {
            let now = chrono::Utc::now().timestamp();
            if s.expires_at <= now {
                println!("Your session has expired.");
                prompt_admin_login(config, vault).await?
            } else if s.role != "admin" && s.role != "operator" {
                println!("Unregistration requires admin or operator privileges.");
                println!("Current session: {} ({})", s.username, s.role);
                prompt_admin_login(config, vault).await?
            } else {
                info!("Using existing session: {} ({})", s.username, s.role);
                s.access_token
            }
        }
        None => {
            println!("Unregistration requires admin or operator login.");
            prompt_admin_login(config, vault).await?
        }
    };

    info!("Unregistering agent '{}' from Hydra...", creds.username);
    delete_agent_user(config, &creds.user_id, &access_token).await?;

    if !args.keep_local {
        vault.delete_agent_credentials()?;
        vault.delete_api_key()?;
        vault.delete_node_registration()?;
        info!("Cleared local vault credentials");
    }

    println!();
    println!("✓ Agent unregistered successfully!");
    println!();
    if args.keep_local {
        println!("Local credentials kept. Run 'hydra-agent register --clear' to remove them.");
    } else {
        println!("All agent credentials have been cleared.");
        println!("To re-register, run 'hydra-agent register'.");
    }

    Ok(())
}

/// Prompt for admin/operator login and return access token
async fn prompt_admin_login(config: &AgentConfig, vault: &Vault) -> Result<String> {
    println!();
    print!("Username: ");
    io::stdout().flush()?;
    let mut username = String::new();
    io::stdin().read_line(&mut username)?;
    let username = username.trim().to_string();

    if username.is_empty() {
        return Err(anyhow!("Username is required"));
    }

    let password = rpassword::prompt_password("Password: ")
        .context("Failed to read password")?;

    if password.is_empty() {
        return Err(anyhow!("Password is required"));
    }

    info!("Logging in as {}...", username);

    let client = Client::builder()
        .timeout(Duration::from_secs(30))
        .build()
        .context("Failed to create HTTP client")?;

    let login_url = format!("{}/auth/login", config.api.url);

    #[derive(serde::Serialize)]
    #[serde(rename_all = "camelCase")]
    struct LoginRequest {
        username: String,
        password: String,
    }

    #[derive(serde::Deserialize)]
    #[serde(rename_all = "camelCase")]
    struct LoginResponse {
        access_token: String,
        refresh_token: String,
        token_type: String,
        expires_in: u64,
        user: UserInfo,
    }

    #[derive(serde::Deserialize)]
    #[serde(rename_all = "camelCase")]
    struct UserInfo {
        user_id: String,
        username: String,
        role: String,
    }

    let request = LoginRequest { username: username.clone(), password };

    let response = client
        .post(&login_url)
        .json(&request)
        .send()
        .await
        .context("Failed to send login request")?;

    if !response.status().is_success() {
        let error: ApiError = response.json().await.unwrap_or_else(|_| ApiError {
            error: ApiErrorDetail {
                code: "UNKNOWN".to_string(),
                message: "Login failed".to_string(),
            },
        });
        return Err(anyhow!(
            "Login failed: {} - {}",
            error.error.code,
            error.error.message
        ));
    }

    let login_response: LoginResponse = response
        .json()
        .await
        .context("Failed to parse login response")?;

    if login_response.user.role != "admin" && login_response.user.role != "operator" {
        return Err(anyhow!(
            "Unregistration requires admin or operator role. Current: {}",
            login_response.user.role
        ));
    }

    let expires_at = chrono::Utc::now().timestamp() + login_response.expires_in as i64;
    let session = crate::vault::SessionData {
        access_token: login_response.access_token.clone(),
        refresh_token: login_response.refresh_token,
        token_type: login_response.token_type,
        expires_at,
        username: login_response.user.username,
        user_id: login_response.user.user_id,
        role: login_response.user.role,
    };
    vault.save_session(&session)?;

    info!("Login successful");
    Ok(login_response.access_token)
}

/// Delete agent user from Hydra API
async fn delete_agent_user(config: &AgentConfig, user_id: &str, access_token: &str) -> Result<()> {
    let client = Client::builder()
        .timeout(Duration::from_secs(30))
        .build()
        .context("Failed to create HTTP client")?;

    let delete_url = format!("{}/users/{}", config.api.url, user_id);
    debug!("Deleting agent user: {}", delete_url);

    let response = client
        .delete(&delete_url)
        .bearer_auth(access_token)
        .send()
        .await
        .context("Failed to send delete request")?;

    if !response.status().is_success() {
        let status = response.status();
        let error: ApiError = response.json().await.unwrap_or_else(|_| ApiError {
            error: ApiErrorDetail {
                code: status.as_str().to_string(),
                message: "Failed to delete agent user".to_string(),
            },
        });
        return Err(anyhow!(
            "Failed to unregister agent: {} - {}",
            error.error.code,
            error.error.message
        ));
    }

    Ok(())
}
