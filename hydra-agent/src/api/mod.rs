//! API client for communicating with the Hydra API.

use anyhow::{anyhow, Context, Result};
use reqwest::{Client, StatusCode};
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tracing::{debug, info, warn};

use crate::collectors::Profile;
use crate::config::{AgentConfig, Credentials};

/// API client for Hydra API communication.
pub struct ApiClient {
    client: Client,
    config: AgentConfig,
    credentials: Option<Credentials>,
}

/// Node registration request sent to /node/register
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct NodeRegistrationRequest {
    node_id: String,
    #[serde(rename = "class")]
    node_class: String,
    #[serde(rename = "type")]
    node_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    kind: Option<String>,
    display_name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    description: Option<String>,
    tags: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    parent_node_id: Option<String>,
}

/// Login request for /auth/login
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct LoginRequest {
    username: String,
    password: String,
}

/// Login response from /auth/login (returned directly, not wrapped in data)
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

/// Node registration response from /node/register (returned directly, not wrapped in data)
/// Note: Some endpoints use SuccessResponse wrapper, others return directly
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct DirectNodeRegistrationResponse {
    node_id: String,
    api_key: String,
    api_key_id: String,
    registered_by: String,
    registered_at: String,
    #[allow(dead_code)]
    status: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProfileSubmitResponse {
    pub profile_id: String,
    pub version: String,
}

#[derive(Debug, Deserialize)]
struct ApiResponse<T> {
    data: T,
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

impl ApiClient {
    /// Create a new API client.
    pub fn new(config: &AgentConfig) -> Result<Self> {
        let client = Client::builder()
            .timeout(Duration::from_secs(config.api.timeout_seconds))
            .build()
            .context("Failed to create HTTP client")?;

        // Try to load existing credentials
        let credentials = Credentials::load(&config.api.credentials_file).ok();

        Ok(Self {
            client,
            config: config.clone(),
            credentials,
        })
    }

    /// Build the node registration request from config.
    fn build_registration_request(&self) -> NodeRegistrationRequest {
        NodeRegistrationRequest {
            node_id: self.config.node.node_id.clone(),
            node_class: self.config.node.class.clone(),
            node_type: self.config.node.node_type.clone(),
            kind: self.config.node.kind.clone(),
            display_name: self
                .config
                .node
                .display_name
                .clone()
                .unwrap_or_else(|| self.config.node.node_id.clone()),
            description: self.config.node.description.clone(),
            tags: self.config.node.tags.clone(),
            parent_node_id: self.config.node.parent_node_id.clone(),
        }
    }

    /// Save registration response as credentials (from direct response).
    fn save_credentials_from_direct(&self, response: &DirectNodeRegistrationResponse) -> Result<()> {
        let credentials = Credentials {
            api_key: response.api_key.clone(),
            api_key_id: response.api_key_id.clone(),
            node_id: response.node_id.clone(),
            created_at: response.registered_at.clone(),
        };

        credentials.save(&self.config.api.credentials_file)?;
        info!(node_id = %response.node_id, "Credentials saved");
        Ok(())
    }

    /// Register the node using a registration token.
    /// The token is passed via X-Registration-Token header and allows
    /// instant registration without user authentication.
    pub async fn register_with_token(&self, registration_token: &str) -> Result<()> {
        let url = format!("{}/node/register", self.config.api.url);
        let request = self.build_registration_request();

        debug!(?request, "Sending registration request with token");

        let response = self
            .client
            .post(&url)
            .header("X-Registration-Token", registration_token)
            .json(&request)
            .send()
            .await
            .context("Failed to send registration request")?;

        if !response.status().is_success() {
            let error: ApiError = response.json().await?;
            return Err(anyhow!(
                "Registration failed: {} - {}",
                error.error.code,
                error.error.message
            ));
        }

        // Node registration response is returned directly, not wrapped in data
        let result: DirectNodeRegistrationResponse = response.json().await?;
        self.save_credentials_from_direct(&result)?;

        info!(node_id = %result.node_id, "Registration with token successful");
        Ok(())
    }

    /// Register the node using user credentials.
    /// This first logs in to get an access token, then registers the node.
    pub async fn register_with_credentials(&self, username: &str, password: &str) -> Result<()> {
        // Step 1: Login to get access token
        let login_url = format!("{}/auth/login", self.config.api.url);
        let login_request = LoginRequest {
            username: username.to_string(),
            password: password.to_string(),
        };

        debug!("Logging in as user: {}", username);

        let login_response = self
            .client
            .post(&login_url)
            .json(&login_request)
            .send()
            .await
            .context("Failed to send login request")?;

        if !login_response.status().is_success() {
            let error: ApiError = login_response.json().await?;
            return Err(anyhow!(
                "Login failed: {} - {}",
                error.error.code,
                error.error.message
            ));
        }

        // Login response is returned directly, not wrapped in data
        let login_result: LoginResponse = login_response.json().await?;
        info!("Login successful, registering node...");

        // Step 2: Register node using access token
        let register_url = format!("{}/node/register", self.config.api.url);
        let request = self.build_registration_request();

        debug!(?request, "Sending registration request with user token");

        let response = self
            .client
            .post(&register_url)
            .bearer_auth(&login_result.access_token)
            .json(&request)
            .send()
            .await
            .context("Failed to send registration request")?;

        if !response.status().is_success() {
            let error: ApiError = response.json().await?;
            return Err(anyhow!(
                "Node registration failed: {} - {}",
                error.error.code,
                error.error.message
            ));
        }

        // Node registration response is returned directly, not wrapped in data
        let result: DirectNodeRegistrationResponse = response.json().await?;
        self.save_credentials_from_direct(&result)?;

        info!(
            node_id = %result.node_id,
            registered_by = %result.registered_by,
            "Registration with credentials successful"
        );
        Ok(())
    }

    /// Submit a profile to the API.
    /// Uses X-API-Key header for authentication.
    pub async fn submit_profile(&self, profile: &Profile) -> Result<ProfileSubmitResponse> {
        let url = format!("{}/profiles", self.config.api.url);

        let credentials = self
            .credentials
            .as_ref()
            .ok_or_else(|| anyhow!("No credentials found. Run with --register first."))?;

        let mut retries = self.config.api.retries;
        let mut last_error: Option<anyhow::Error> = None;

        while retries > 0 {
            let response = self
                .client
                .post(&url)
                .header("X-API-Key", &credentials.api_key)
                .json(profile)
                .send()
                .await;

            match response {
                Ok(resp) if resp.status().is_success() => {
                    let result: ApiResponse<ProfileSubmitResponse> = resp.json().await?;
                    return Ok(result.data);
                }
                Ok(resp) if resp.status() == StatusCode::UNAUTHORIZED => {
                    // API key is invalid or revoked - need to re-register
                    return Err(anyhow!(
                        "API key authentication failed. The key may have been revoked. Re-register the agent."
                    ));
                }
                Ok(resp) => {
                    let error: ApiError = resp.json().await?;
                    last_error = Some(anyhow!(
                        "API error: {} - {}",
                        error.error.code,
                        error.error.message
                    ));
                }
                Err(e) => {
                    last_error = Some(e.into());
                }
            }

            retries -= 1;
            if retries > 0 {
                warn!(retries_left = retries, "Request failed, retrying...");
                tokio::time::sleep(Duration::from_secs(2)).await;
            }
        }

        Err(last_error.unwrap_or_else(|| anyhow!("Unknown error")))
    }
}
