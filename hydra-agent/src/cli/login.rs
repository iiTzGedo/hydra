//! Login command for authenticating as admin/operator.
//!
//! Authenticates with the Hydra API and stores the session in the vault.
//! Used for performing privileged operations like agent registration.

use anyhow::{anyhow, Context, Result};
use clap::Args;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::io::{self, Write};
use std::time::Duration;
use tracing::{debug, info};

use crate::config::AgentConfig;
use crate::vault::{SessionData, Vault};

/// Login command arguments
#[derive(Args, Debug)]
pub struct LoginArgs {
    /// Username (admin or operator)
    #[arg(short, long)]
    pub username: Option<String>,

    /// Password
    #[arg(short, long)]
    pub password: Option<String>,

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
    // Handle logout
    if args.logout {
        return logout(vault);
    }

    // Handle status check
    if args.status {
        return show_status(vault);
    }

    // Handle refresh
    if args.refresh {
        return refresh_session(config, vault).await;
    }

    // Perform login
    login(args, config, vault).await
}

/// Perform login with username/password
async fn login(args: &LoginArgs, config: &AgentConfig, vault: &Vault) -> Result<()> {
    // Get username - prompt if not provided
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

    // Get password - prompt securely if not provided
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

    // Calculate expiration timestamp
    let expires_at = chrono::Utc::now().timestamp() + login_response.expires_in as i64;

    // Save session to vault
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
        // Session refresh failed - clear session and prompt for re-login
        vault.delete_session()?;
        return Err(anyhow!(
            "Session refresh failed. Session has been cleared. Please login again."
        ));
    }

    let refresh_response: RefreshResponse = response.json().await
        .context("Failed to parse refresh response")?;

    // Calculate new expiration timestamp
    let expires_at = chrono::Utc::now().timestamp() + refresh_response.expires_in as i64;

    // Update session with new access token
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
