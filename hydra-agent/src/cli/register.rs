//! Register command for creating agent system accounts.
//!
//! Creates an agent sub-account under the logged-in admin/operator user.
//! The agent account is used for API authentication when collecting profiles.
//!
//! Flow per Some Updates.md:
//! 1. User logs in via `hydra-agent login` (admin/operator)
//! 2. User runs `hydra-agent register [--username X] [--password Y]` (both optional)
//! 3. Agent CLI generates username/password locally if not provided
//! 4. Agent calls POST /auth/register with credentials
//! 5. On success, agent auto-logins as the agent user
//! 6. Agent creates API key (90 day expiry) using agent JWT
//! 7. Agent saves credentials AND API key to vault AFTER successful registration

use anyhow::{anyhow, Context, Result};
use clap::Args;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tracing::{debug, info};

use crate::config::AgentConfig;
use crate::utils::{generate_agent_password, generate_agent_username, API_KEY_DEFAULT_EXPIRY_DAYS};
use crate::vault::{AgentCredentials, ApiKeyData, Vault};

/// Register command arguments
#[derive(Args, Debug)]
pub struct RegisterArgs {
    /// Registration token (alternative to session-based registration)
    #[arg(short, long)]
    pub token: Option<String>,

    /// Custom agent username (defaults to auto-generated)
    #[arg(long, alias = "id")]
    pub username: Option<String>,

    /// Custom agent password (defaults to auto-generated)
    #[arg(long, alias = "pwd")]
    pub password: Option<String>,

    /// Override existing registration (unregister and re-register)
    #[arg(short, long)]
    pub override_registration: bool,

    /// Show current registration status
    #[arg(long)]
    pub status: bool,

    /// Clear registration (reset agent) - local only, doesn't delete from API
    #[arg(long)]
    pub clear: bool,
}

/// Registration response from API (simplified per Some Updates.md)
/// API no longer returns password or api_key - agent generates/creates these
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct RegisterResponse {
    user_id: String,
    username: String,
    role: String,
    parent_user_id: String,
    created_at: String,
}

/// Login response from /auth/login
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct LoginResponse {
    access_token: String,
    #[allow(dead_code)]
    refresh_token: String,
    #[allow(dead_code)]
    token_type: String,
    #[allow(dead_code)]
    expires_in: u64,
}

/// Login request for /auth/login
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct LoginRequest {
    username: String,
    password: String,
}

/// API key creation request for /auth/apikeys
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

/// API key creation response from /auth/apikeys
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct CreateApiKeyResponse {
    key_id: String,
    key: String,
    #[allow(dead_code)]
    name: String,
    expires_at: Option<String>,
    #[allow(dead_code)]
    created_at: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct AgentRegisterRequest {
    role: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    username: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    password: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    registration_token: Option<String>,
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

/// Execute the register command
pub async fn execute(args: &RegisterArgs, config: &AgentConfig, vault: &Vault) -> Result<()> {
    if args.status {
        return show_status(vault);
    }

    if args.clear {
        return clear_registration(vault);
    }

    if args.override_registration {
        return override_registration(config, vault, args).await;
    }

    if vault.has_agent_credentials() {
        let creds = vault.load_agent_credentials()?.ok_or_else(|| {
            anyhow!("Agent credentials file exists but could not be loaded. Check vault integrity.")
        })?;
        let has_valid_api_key = vault.has_api_key() && !vault.is_api_key_expired()?;

        println!();
        println!("Agent is already registered.");
        println!("  Agent ID: {}", creds.username);
        println!("  User ID: {}", creds.user_id);
        if has_valid_api_key {
            println!("  API Key: Valid");
        } else if vault.has_api_key() {
            println!("  API Key: Expired - run 'hydra-agent login -a' to renew");
        } else {
            println!("  API Key: Missing - run 'hydra-agent login -a' to create");
        }

        if !has_valid_api_key {
            println!();
            println!("To authenticate this agent, run:");
            println!("  hydra-agent login -a");
        }

        println!();
        println!("To override this registration and re-register, run:");
        println!("  hydra-agent register -o");
        println!();

        return Ok(());
    }

    if let Some(token) = &args.token {
        register_with_token(token, config, vault, args).await
    } else {
        register_with_session(config, vault, args).await
    }
}

/// Override existing registration (unregister from API and re-register)
/// Requires admin/operator login
async fn override_registration(
    config: &AgentConfig,
    vault: &Vault,
    args: &RegisterArgs,
) -> Result<()> {
    use std::io::{self, Write};

    println!();
    println!("Override Registration");
    println!("=====================");
    println!();
    println!("This will:");
    println!("  1. Delete the current agent account from Hydra API");
    println!("  2. Clear local credentials and API keys");
    println!("  3. Create a new agent account");
    println!();
    println!("This operation requires admin/operator privileges.");
    println!();

    // Check if we have a valid admin/operator session
    let needs_login = if vault.has_session() {
        let session = vault.load_session()?;
        if let Some(s) = session {
            // Check if it's an admin/operator session (not agent)
            if s.role == "agent" {
                println!("Currently logged in as agent. Admin/operator login required.");
                vault.delete_session()?;
                true
            } else if !vault.is_session_valid()? {
                println!("Session expired. Please login again.");
                true
            } else {
                println!("Using existing session: {} ({})", s.username, s.role);
                false
            }
        } else {
            true
        }
    } else {
        true
    };

    // Prompt for admin/operator login if needed
    let session = if needs_login {
        println!();
        prompt_admin_login(config, vault).await?
    } else {
        vault.load_session()?.ok_or_else(|| {
            anyhow!("No active session found. Login first with 'hydra-agent login'.")
        })?
    };

    // Confirm action
    print!("Proceed with override? (y/N): ");
    io::stdout().flush()?;
    let mut input = String::new();
    io::stdin().read_line(&mut input)?;
    if !input.trim().eq_ignore_ascii_case("y") {
        println!("Cancelled.");
        return Ok(());
    }

    // Step 1: Delete agent account from API if it exists
    if vault.has_agent_credentials() {
        let creds = vault.load_agent_credentials()?.ok_or_else(|| {
            anyhow!("Agent credentials file exists but could not be loaded. Check vault integrity.")
        })?;
        info!("Deleting agent account '{}' from API...", creds.username);

        let client = Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .context("Failed to create HTTP client")?;

        let delete_url = format!("{}/auth/users/{}", config.api.url, creds.user_id);
        let response = client
            .delete(&delete_url)
            .header("Authorization", format!("Bearer {}", session.access_token))
            .send()
            .await;

        match response {
            Ok(resp) if resp.status().is_success() => {
                info!("Agent account deleted from API");
            }
            Ok(resp) => {
                // Log but don't fail - account might already be deleted
                debug!(
                    "Failed to delete agent account (status {}), continuing...",
                    resp.status()
                );
            }
            Err(e) => {
                debug!("Failed to contact API for deletion: {}, continuing...", e);
            }
        }
    }

    // Step 2: Clear local credentials
    if vault.has_agent_credentials() {
        vault.delete_agent_credentials()?;
    }
    if vault.has_api_key() {
        vault.delete_api_key()?;
    }
    info!("Local credentials cleared");

    println!();
    println!("✓ Previous registration cleared. Proceeding with new registration...");
    println!();

    // Step 3: Re-register (session is still valid)
    if let Some(token) = &args.token {
        register_with_token(token, config, vault, args).await
    } else {
        // Use the existing session for registration
        register_with_existing_session(&session, config, vault, args).await
    }
}

/// Prompt for admin/operator login
async fn prompt_admin_login(
    config: &AgentConfig,
    vault: &Vault,
) -> Result<crate::vault::SessionData> {
    use std::io::{self, Write};

    print!("Admin/Operator Username: ");
    io::stdout().flush()?;
    let mut username = String::new();
    io::stdin().read_line(&mut username)?;
    let username = username.trim().to_string();

    if username.is_empty() {
        return Err(anyhow!("Username is required"));
    }

    let password = rpassword::prompt_password("Password: ").context("Failed to read password")?;

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

    #[derive(Debug, Deserialize)]
    #[serde(rename_all = "camelCase")]
    struct FullLoginResponse {
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

    let login_response: FullLoginResponse = response
        .json()
        .await
        .context("Failed to parse login response")?;

    if login_response.user.role != "admin" && login_response.user.role != "operator" {
        return Err(anyhow!(
            "Admin or operator role required. Current role: {}",
            login_response.user.role
        ));
    }

    let expires_at = chrono::Utc::now().timestamp() + login_response.expires_in as i64;

    let session = crate::vault::SessionData {
        access_token: login_response.access_token,
        refresh_token: login_response.refresh_token,
        token_type: login_response.token_type,
        expires_at,
        username: login_response.user.username,
        user_id: login_response.user.user_id,
        role: login_response.user.role,
    };

    vault.save_session(&session)?;
    println!("✓ Logged in as {} ({})", session.username, session.role);

    Ok(session)
}

/// Register using an existing valid session (for override flow)
async fn register_with_existing_session(
    session: &crate::vault::SessionData,
    config: &AgentConfig,
    vault: &Vault,
    args: &RegisterArgs,
) -> Result<()> {
    info!(
        "Registering agent using session for {}...",
        session.username
    );

    let username = args.username.clone().unwrap_or_else(|| {
        let generated = generate_agent_username();
        info!("Generated agent username: {}", generated);
        generated
    });
    let password = args.password.clone().unwrap_or_else(|| {
        let generated = generate_agent_password();
        info!("Generated secure password for agent");
        generated
    });

    let client = Client::builder()
        .timeout(Duration::from_secs(30))
        .build()
        .context("Failed to create HTTP client")?;

    let register_url = format!("{}/auth/register", config.api.url);
    let request = AgentRegisterRequest {
        role: "agent".to_string(),
        username: Some(username.clone()),
        password: Some(password.clone()),
        registration_token: None,
    };

    let response = client
        .post(&register_url)
        .header("Authorization", format!("Bearer {}", session.access_token))
        .json(&request)
        .send()
        .await
        .context("Failed to send registration request")?;

    if !response.status().is_success() {
        let error: ApiError = response.json().await.unwrap_or_else(|_| ApiError {
            error: ApiErrorDetail {
                code: "UNKNOWN".to_string(),
                message: "Registration failed".to_string(),
            },
        });
        return Err(anyhow!(
            "Registration failed: {} - {}",
            error.error.code,
            error.error.message
        ));
    }

    let register_response: RegisterResponse = response
        .json()
        .await
        .context("Failed to parse registration response")?;

    info!("Agent registered successfully, logging in...");

    let access_token = login_as_agent(&client, config, &username, &password).await?;

    let api_key_response = create_api_key(&client, config, &username, &access_token).await?;

    save_credentials(vault, &register_response, &password)?;
    save_api_key_from_response(vault, config, &api_key_response)?;

    vault.delete_session()?;
    info!("Cleared admin/operator session - agent now operates with API key");

    print_success(&register_response, &password, Some(&session.username));
    Ok(())
}

/// Register using a registration token (no session required)
/// Per Some Updates.md: Generate credentials locally, register, login, create API key
async fn register_with_token(
    token: &str,
    config: &AgentConfig,
    vault: &Vault,
    args: &RegisterArgs,
) -> Result<()> {
    info!("Registering agent with registration token...");

    let username = args.username.clone().unwrap_or_else(|| {
        let generated = generate_agent_username();
        info!("Generated agent username: {}", generated);
        generated
    });
    let password = args.password.clone().unwrap_or_else(|| {
        let generated = generate_agent_password();
        info!("Generated secure password for agent");
        generated
    });

    let client = Client::builder()
        .timeout(Duration::from_secs(30))
        .build()
        .context("Failed to create HTTP client")?;

    let register_url = format!("{}/auth/register", config.api.url);
    let request = AgentRegisterRequest {
        role: "agent".to_string(),
        username: Some(username.clone()),
        password: Some(password.clone()),
        registration_token: Some(token.to_string()),
    };

    debug!("Sending registration request to {}", register_url);

    let response = client
        .post(&register_url)
        .json(&request)
        .send()
        .await
        .context("Failed to send registration request")?;

    if !response.status().is_success() {
        let error: ApiError = response.json().await.unwrap_or_else(|_| ApiError {
            error: ApiErrorDetail {
                code: "UNKNOWN".to_string(),
                message: "Registration failed".to_string(),
            },
        });
        return Err(anyhow!(
            "Registration failed: {} - {}",
            error.error.code,
            error.error.message
        ));
    }

    let register_response: RegisterResponse = response
        .json()
        .await
        .context("Failed to parse registration response")?;

    info!("Agent registered successfully, logging in...");

    let access_token = login_as_agent(&client, config, &username, &password).await?;

    let api_key_response = create_api_key(&client, config, &username, &access_token).await?;

    save_credentials(vault, &register_response, &password)?;
    save_api_key_from_response(vault, config, &api_key_response)?;

    let logged_out_user = if vault.has_session() {
        let session = vault.load_session()?.map(|s| s.username.clone());
        vault.delete_session()?;
        info!("Cleared admin/operator session - agent now operates with API key");
        session
    } else {
        None
    };

    print_success(&register_response, &password, logged_out_user.as_deref());
    Ok(())
}

/// Register using an existing admin/operator session
/// Per Some Updates.md: Generate credentials locally, register, login, create API key
async fn register_with_session(
    config: &AgentConfig,
    vault: &Vault,
    args: &RegisterArgs,
) -> Result<()> {
    // Check for valid session
    let session = vault
        .load_session()?
        .ok_or_else(|| anyhow!("No active session. Please login first with 'hydra-agent login'"))?;

    if !vault.is_session_valid()? {
        return Err(anyhow!(
            "Session has expired. Please login again with 'hydra-agent login'"
        ));
    }

    let session_username = session.username.clone();
    info!(
        "Registering agent using session for {}...",
        session_username
    );

    let username = args.username.clone().unwrap_or_else(|| {
        let generated = generate_agent_username();
        info!("Generated agent username: {}", generated);
        generated
    });
    let password = args.password.clone().unwrap_or_else(|| {
        let generated = generate_agent_password();
        info!("Generated secure password for agent");
        generated
    });

    let client = Client::builder()
        .timeout(Duration::from_secs(30))
        .build()
        .context("Failed to create HTTP client")?;

    let register_url = format!("{}/auth/register", config.api.url);
    let request = AgentRegisterRequest {
        role: "agent".to_string(),
        username: Some(username.clone()),
        password: Some(password.clone()),
        registration_token: None,
    };

    debug!("Sending registration request to {}", register_url);

    let response = client
        .post(&register_url)
        .header("Authorization", format!("Bearer {}", session.access_token))
        .json(&request)
        .send()
        .await
        .context("Failed to send registration request")?;

    if !response.status().is_success() {
        let error: ApiError = response.json().await.unwrap_or_else(|_| ApiError {
            error: ApiErrorDetail {
                code: "UNKNOWN".to_string(),
                message: "Registration failed".to_string(),
            },
        });
        return Err(anyhow!(
            "Registration failed: {} - {}",
            error.error.code,
            error.error.message
        ));
    }

    let register_response: RegisterResponse = response
        .json()
        .await
        .context("Failed to parse registration response")?;

    info!("Agent registered successfully, logging in...");

    let access_token = login_as_agent(&client, config, &username, &password).await?;

    let api_key_response = create_api_key(&client, config, &username, &access_token).await?;

    save_credentials(vault, &register_response, &password)?;
    save_api_key_from_response(vault, config, &api_key_response)?;

    vault.delete_session()?;
    info!("Cleared admin/operator session - agent now operates with API key");

    print_success(&register_response, &password, Some(&session_username));
    Ok(())
}

/// Login as agent user to get JWT access token
async fn login_as_agent(
    client: &Client,
    config: &AgentConfig,
    username: &str,
    password: &str,
) -> Result<String> {
    // Use source=agent to allow system account login from CLI
    let login_url = format!("{}/auth/login?source=agent", config.api.url);
    let request = LoginRequest {
        username: username.to_string(),
        password: password.to_string(),
    };

    debug!("Logging in as agent user: {}", username);

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
                message: "Agent login failed".to_string(),
            },
        });
        return Err(anyhow!(
            "Agent login failed: {} - {}",
            error.error.code,
            error.error.message
        ));
    }

    let login_response: LoginResponse = response
        .json()
        .await
        .context("Failed to parse login response")?;

    info!("Agent logged in successfully");
    Ok(login_response.access_token)
}

/// Create API key for agent using its JWT
async fn create_api_key(
    client: &Client,
    config: &AgentConfig,
    username: &str,
    access_token: &str,
) -> Result<CreateApiKeyResponse> {
    let api_key_url = format!("{}/auth/apikeys", config.api.url);

    let expires_at =
        (chrono::Utc::now() + chrono::Duration::days(API_KEY_DEFAULT_EXPIRY_DAYS)).to_rfc3339();

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

/// Save agent credentials to vault (password from local generation)
fn save_credentials(vault: &Vault, response: &RegisterResponse, password: &str) -> Result<()> {
    let creds = AgentCredentials {
        user_id: response.user_id.clone(),
        username: response.username.clone(),
        password: Some(password.to_string()), // Password generated locally, not from API
        parent_user_id: response.parent_user_id.clone(),
        created_at: response.created_at.clone(),
    };

    vault.save_agent_credentials(&creds)?;
    info!("Saved agent credentials to vault");
    Ok(())
}

/// Save API key from CreateApiKeyResponse (agent creates its own key)
fn save_api_key_from_response(
    vault: &Vault,
    config: &AgentConfig,
    response: &CreateApiKeyResponse,
) -> Result<()> {
    let api_key_data = ApiKeyData {
        api_key: response.key.clone(),
        api_key_id: response.key_id.clone(),
        expires_at: response.expires_at.clone(),
        node_id: Some(config.node.node_id.clone()),
        stored_at: chrono::Utc::now().to_rfc3339(),
    };

    vault.save_api_key(&api_key_data)?;
    info!("Saved API key to vault");
    Ok(())
}

/// Print success message
fn print_success(response: &RegisterResponse, password: &str, logged_out_user: Option<&str>) {
    println!();
    println!("✓ Agent registered successfully!");
    println!("  Username: {}", response.username);
    println!("  User ID: {}", response.user_id);
    println!("  Role: {}", response.role);
    println!("  Parent: {}", response.parent_user_id);
    println!("  API Key: Stored in vault");
    println!("  Password: {}", password);
    println!("  Note: Password and API key are stored in the vault.");
    println!("        The password is needed for API key renewal.");
    println!();

    // Notify about session transition
    if let Some(user) = logged_out_user {
        println!("✓ Auto-transitioned from '{}' session to agent mode.", user);
    }

    println!("The agent is now ready to collect and submit profiles.");
    println!("Next: Run 'hydra-agent node register' to register this machine.");
}

/// Show registration status
fn show_status(vault: &Vault) -> Result<()> {
    println!();
    println!("Agent Registration Status");
    println!("=========================");

    match vault.load_agent_credentials()? {
        Some(creds) => {
            println!("  Status: Registered");
            println!("  Username: {}", creds.username);
            println!("  User ID: {}", creds.user_id);
            println!("  Parent: {}", creds.parent_user_id);
            println!("  Registered: {}", creds.created_at);

            // Check API key status
            if let Some(api_key) = vault.load_api_key()? {
                let expired = vault.is_api_key_expired()?;
                println!(
                    "  API Key: {} ({})",
                    api_key.api_key_id,
                    if expired { "expired" } else { "valid" }
                );
                if let Some(expires) = api_key.expires_at {
                    println!("  API Key Expires: {}", expires);
                }
            } else {
                println!("  API Key: Not configured");
            }
        }
        None => {
            println!("  Status: Not registered");
            println!();
            println!("Run 'hydra-agent register' to create an agent account.");
        }
    }

    println!();
    Ok(())
}

/// Clear registration data
fn clear_registration(vault: &Vault) -> Result<()> {
    if vault.has_agent_credentials() {
        vault.delete_agent_credentials()?;
        vault.delete_api_key()?;
        println!("✓ Agent registration cleared.");
        println!();
        println!("Run 'hydra-agent register' to create a new agent account.");
    } else {
        println!("No agent registration to clear.");
    }
    Ok(())
}
