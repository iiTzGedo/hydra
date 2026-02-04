//! Login command for authenticating as admin/operator or agent.
//!
//! Authenticates with the Hydra API and stores the session in the vault.
//! Used for performing privileged operations like agent registration.
//!
//! Flow:
//! - Default login: Prompts for username/password (for admin/operator)
//! - `--agent`: Uses agent credentials from vault (recovery after failed auto-login)
//! - If agent is registered and no flags provided, prompts user to choose

use anyhow::{anyhow, Context, Result};
use clap::Args;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::io::{self, Write};
use std::time::Duration;
use tracing::{debug, info};

use crate::config::AgentConfig;
use crate::utils::API_KEY_DEFAULT_EXPIRY_DAYS;
use crate::vault::{ApiKeyData, SessionData, Vault};

/// Login command arguments
#[derive(Args, Debug)]
pub struct LoginArgs {
    /// Username (admin or operator)
    #[arg(short, long)]
    pub username: Option<String>,

    /// Password
    #[arg(short, long)]
    pub password: Option<String>,

    /// Login using agent credentials from vault (recovery for failed auto-login)
    #[arg(short, long)]
    pub agent: bool,

    /// Force recreate API key even if a valid one exists (use with --agent)
    #[arg(short, long)]
    pub force: bool,

    /// Refresh existing session instead of new login
    #[arg(short, long)]
    pub refresh: bool,

    /// Show current session status
    #[arg(long)]
    pub status: bool,

    /// Logout (clear session)
    #[arg(long)]
    pub logout: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct LoginRequest {
    username: String,
    password: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct LoginResponse {
    access_token: String,
    refresh_token: String,
    token_type: String,
    expires_in: u64,
    user: UserInfo,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct UserInfo {
    user_id: String,
    username: String,
    role: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct RefreshRequest {
    refresh_token: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct RefreshResponse {
    access_token: String,
    expires_in: u64,
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

/// Execute the login command
pub async fn execute(args: &LoginArgs, config: &AgentConfig, vault: &Vault) -> Result<()> {
    if args.logout {
        return logout(vault);
    }

    if args.status {
        return show_status(vault);
    }

    if args.refresh {
        return refresh_session(config, vault).await;
    }

    if args.agent {
        return login_with_agent_credentials(config, vault, args.force).await;
    }

    if args.username.is_none() && vault.has_agent_credentials() {
        return prompt_login_choice(args, config, vault).await;
    }

    login_user(args, config, vault).await
}

/// Prompt user to choose between user login and agent login
async fn prompt_login_choice(args: &LoginArgs, config: &AgentConfig, vault: &Vault) -> Result<()> {
    let creds = vault.load_agent_credentials()?
        .ok_or_else(|| anyhow!("Agent credentials missing from vault. Re-register with 'hydra-agent register'."))?;

    println!();
    println!("Agent '{}' is registered with Hydra.", creds.username);
    println!();
    println!("Login as:");
    println!("  [u] User (admin/operator) - for privileged operations");
    println!("  [a] Agent - verify/renew API key for this agent");
    println!();
    print!("Choice (u/a): ");
    io::stdout().flush()?;

    let mut input = String::new();
    io::stdin().read_line(&mut input)?;
    let choice = input.trim().to_lowercase();

    match choice.as_str() {
        "a" | "agent" => {
            login_with_agent_credentials(config, vault, args.force).await
        }
        "u" | "user" | "" => {
            login_user(args, config, vault).await
        }
        _ => {
            Err(anyhow!("Invalid choice. Use 'u' for user login or 'a' for agent login."))
        }
    }
}

/// Login using agent credentials stored in vault (recovery mode)
async fn login_with_agent_credentials(config: &AgentConfig, vault: &Vault, force: bool) -> Result<()> {
    let creds = vault.load_agent_credentials()?
        .ok_or_else(|| anyhow!("No agent credentials found in vault. Register first with 'hydra-agent register'."))?;

    let has_valid_api_key = vault.has_api_key() && !vault.is_api_key_expired()?;

    if has_valid_api_key && !force {
        let api_key_data = vault.load_api_key()?
            .ok_or_else(|| anyhow!("API key data missing from vault despite key check passing."))?;
        println!();
        println!("Agent '{}' already has a valid API key.", creds.username);
        println!("  API Key ID: {}", api_key_data.api_key_id);
        if let Some(expires) = &api_key_data.expires_at {
            println!("  Expires: {}", expires);
        }
        println!();
        println!("The agent is ready to collect and submit profiles.");
        println!("No new API key created (existing key is still valid).");
        println!();
        println!("To force recreate the API key, use: hydra-agent login -a -f");
        return Ok(());
    }

    if force && has_valid_api_key {
        info!("Force flag set - recreating API key");
    }

    let password = creds.password.as_ref()
        .ok_or_else(|| anyhow!("Agent password not stored in vault. Cannot perform recovery login."))?;

    info!("Logging in as agent '{}'...", creds.username);

    let client = Client::builder()
        .timeout(Duration::from_secs(30))
        .build()
        .context("Failed to create HTTP client")?;

    // Use source=agent to allow system account login
    let login_url = format!("{}/auth/login?source=agent", config.api.url);
    let request = LoginRequest {
        username: creds.username.clone(),
        password: password.clone(),
    };

    debug!("Sending agent login request to {}", login_url);

    let response = client
        .post(&login_url)
        .json(&request)
        .send()
        .await
        .context("Failed to send login request")?;

    if !response.status().is_success() {
        let error: ApiError = response.json().await
            .unwrap_or_else(|_| ApiError {
                error: ApiErrorDetail {
                    code: "UNKNOWN".to_string(),
                    message: "Agent login failed".to_string(),
                }
            });
        return Err(anyhow!(
            "Agent login failed: {} - {}",
            error.error.code,
            error.error.message
        ));
    }

    let login_response: LoginResponse = response.json().await
        .context("Failed to parse login response")?;

    info!("Agent logged in successfully, creating API key...");

    let api_key = create_agent_api_key(&client, config, &creds.username, &login_response.access_token).await?;

    let api_key_data = ApiKeyData {
        api_key: api_key.key,
        api_key_id: api_key.key_id,
        expires_at: api_key.expires_at,
        node_id: Some(config.node.node_id.clone()),
        stored_at: chrono::Utc::now().to_rfc3339(),
    };
    vault.save_api_key(&api_key_data)?;

    println!();
    println!("✓ Agent login successful!");
    println!("  Agent: {}", creds.username);
    println!("  API Key: {} (stored in vault)", api_key_data.api_key_id);
    if let Some(expires) = &api_key_data.expires_at {
        println!("  Expires: {}", expires);
    }
    println!();
    println!("The agent is ready to collect and submit profiles.");

    Ok(())
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct CreateApiKeyRequest {
    name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    roles: Option<Vec<String>>,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    permissions: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    expires_at: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct CreateApiKeyResponse {
    key_id: String,
    key: String,
    expires_at: Option<String>,
}

/// Create API key for agent using its JWT
async fn create_agent_api_key(
    client: &Client,
    config: &AgentConfig,
    username: &str,
    access_token: &str,
) -> Result<CreateApiKeyResponse> {
    let api_key_url = format!("{}/auth/apikeys", config.api.url);

    let expires_at = (chrono::Utc::now() + chrono::Duration::days(API_KEY_DEFAULT_EXPIRY_DAYS))
        .to_rfc3339();

    let request = CreateApiKeyRequest {
        name: format!("{}-api-key", username),
        roles: Some(vec!["agent".to_string()]),
        permissions: vec![],
        expires_at: Some(expires_at),
    };

    debug!("Creating API key for agent: {}", username);

    let response = client
        .post(&api_key_url)
        .bearer_auth(access_token)
        .json(&request)
        .send()
        .await
        .context("Failed to send API key creation request")?;

    if !response.status().is_success() {
        let error: ApiError = response.json().await.unwrap_or_else(|_| ApiError {
            error: ApiErrorDetail {
                code: "UNKNOWN".to_string(),
                message: "API key creation failed".to_string(),
            },
        });
        return Err(anyhow!(
            "API key creation failed: {} - {}",
            error.error.code,
            error.error.message
        ));
    }

    let api_key_response: CreateApiKeyResponse = response
        .json()
        .await
        .context("Failed to parse API key response")?;

    info!("API key created successfully");
    Ok(api_key_response)
}

/// Perform user login with username/password
async fn login_user(args: &LoginArgs, config: &AgentConfig, vault: &Vault) -> Result<()> {
    let username = match &args.username {
        Some(u) => u.clone(),
        None => {
            print!("Username: ");
            io::stdout().flush()?;
            let mut input = String::new();
            io::stdin().read_line(&mut input)?;
            input.trim().to_string()
        }
    };

    if username.is_empty() {
        return Err(anyhow!("Username is required"));
    }

    let password = match &args.password {
        Some(p) => p.clone(),
        None => {
            rpassword::prompt_password("Password: ")
                .context("Failed to read password")?
        }
    };

    if password.is_empty() {
        return Err(anyhow!("Password is required"));
    }

    info!("Logging in as {}...", username);

    let client = Client::builder()
        .timeout(Duration::from_secs(30))
        .build()
        .context("Failed to create HTTP client")?;

    let login_url = format!("{}/auth/login", config.api.url);
    let request = LoginRequest {
        username: username.clone(),
        password,
    };

    debug!("Sending login request to {}", login_url);

    let response = client
        .post(&login_url)
        .json(&request)
        .send()
        .await
        .context("Failed to send login request")?;

    if !response.status().is_success() {
        let error: ApiError = response.json().await
            .unwrap_or_else(|_| ApiError {
                error: ApiErrorDetail {
                    code: "UNKNOWN".to_string(),
                    message: "Login failed".to_string(),
                }
            });
        return Err(anyhow!(
            "Login failed: {} - {}",
            error.error.code,
            error.error.message
        ));
    }

    let login_response: LoginResponse = response.json().await
        .context("Failed to parse login response")?;

    let expires_at = chrono::Utc::now().timestamp() + login_response.expires_in as i64;

    let session = SessionData {
        access_token: login_response.access_token,
        refresh_token: login_response.refresh_token,
        token_type: login_response.token_type,
        expires_at,
        username: login_response.user.username,
        user_id: login_response.user.user_id,
        role: login_response.user.role.clone(),
    };

    vault.save_session(&session)?;

    println!();
    println!("✓ Login successful!");
    println!("  User: {} ({})", session.username, session.role);
    println!("  Session expires: {}",
        chrono::DateTime::from_timestamp(expires_at, 0)
            .map(|dt| dt.format("%Y-%m-%d %H:%M:%S UTC").to_string())
            .unwrap_or_else(|| "unknown".to_string())
    );
    println!();
    println!("You can now run 'hydra-agent register' to create an agent account.");

    Ok(())
}

/// Refresh an existing session
async fn refresh_session(config: &AgentConfig, vault: &Vault) -> Result<()> {
    let session = vault.load_session()?
        .ok_or_else(|| anyhow!("No existing session found. Please login first."))?;

    info!("Refreshing session for {}...", session.username);

    let client = Client::builder()
        .timeout(Duration::from_secs(30))
        .build()
        .context("Failed to create HTTP client")?;

    let refresh_url = format!("{}/auth/refresh", config.api.url);
    let request = RefreshRequest {
        refresh_token: session.refresh_token.clone(),
    };

    let response = client
        .post(&refresh_url)
        .json(&request)
        .send()
        .await
        .context("Failed to send refresh request")?;

    if !response.status().is_success() {
        vault.delete_session()?;
        return Err(anyhow!(
            "Session refresh failed. Session has been cleared. Please login again."
        ));
    }

    let refresh_response: RefreshResponse = response.json().await
        .context("Failed to parse refresh response")?;

    let expires_at = chrono::Utc::now().timestamp() + refresh_response.expires_in as i64;

    let updated_session = SessionData {
        access_token: refresh_response.access_token,
        refresh_token: session.refresh_token,
        token_type: session.token_type,
        expires_at,
        username: session.username.clone(),
        user_id: session.user_id,
        role: session.role,
    };

    vault.save_session(&updated_session)?;

    println!();
    println!("✓ Session refreshed!");
    println!("  User: {}", updated_session.username);
    println!("  New expiration: {}",
        chrono::DateTime::from_timestamp(expires_at, 0)
            .map(|dt| dt.format("%Y-%m-%d %H:%M:%S UTC").to_string())
            .unwrap_or_else(|| "unknown".to_string())
    );

    Ok(())
}

/// Show current session status
fn show_status(vault: &Vault) -> Result<()> {
    println!();
    println!("Login Session Status");
    println!("====================");

    match vault.load_session()? {
        Some(session) => {
            let now = chrono::Utc::now().timestamp();
            let is_valid = session.expires_at > now;
            let remaining = session.expires_at - now;

            println!("  Status: {}", if is_valid { "Active" } else { "Expired" });
            println!("  User: {} ({})", session.username, session.role);
            println!("  User ID: {}", session.user_id);

            if is_valid {
                let hours = remaining / 3600;
                let minutes = (remaining % 3600) / 60;
                println!("  Expires in: {}h {}m", hours, minutes);
            } else {
                println!("  Expired: {}s ago", -remaining);
            }

            println!();
            if !is_valid {
                println!("Session has expired. Run 'hydra-agent login --refresh' or login again.");
            }
        }
        None => {
            println!("  Status: Not logged in");
            println!();
            println!("Run 'hydra-agent login' to authenticate.");
        }
    }

    Ok(())
}

/// Clear session (logout)
fn logout(vault: &Vault) -> Result<()> {
    if vault.has_session() {
        vault.delete_session()?;
        println!("✓ Logged out successfully.");
    } else {
        println!("No active session to log out from.");
    }
    Ok(())
}
