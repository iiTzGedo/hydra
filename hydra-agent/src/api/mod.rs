//! API client for communicating with the Hydra API.

use anyhow::{anyhow, Context, Result};
use reqwest::{Client, StatusCode};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::time::Duration;
use tracing::{debug, info, warn};

use crate::collectors::Profile;
use crate::config::AgentConfig;
use crate::utils::{
    generate_agent_password, generate_agent_username, API_KEY_DEFAULT_EXPIRY_DAYS,
    API_KEY_RENEWAL_THRESHOLD_DAYS,
};
use crate::vault::{AgentCredentials, ApiKeyData, NodeRegistrationData, Vault};

/// API client for Hydra API communication.
pub struct ApiClient {
    client: Client,
    config: AgentConfig,
    vault: Vault,
}

/// Node registration request sent to /nodes/register
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct NodeRegistrationRequest {
    node_id: String,
    #[serde(rename = "class")]
    node_class: String,
    #[serde(rename = "type")]
    node_type: String,
    #[serde(rename = "agentTier")]
    tier: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    kind: Option<String>,
    display_name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    description: Option<String>,
    tags: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    parent_node_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    server_address: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    server_port: Option<u16>,
    #[serde(skip_serializing_if = "Option::is_none")]
    server_tls_enabled: Option<bool>,
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

/// API key creation request for /auth/apikeys
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct CreateApiKeyRequest {
    name: String,
    permissions: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    expires_at: Option<String>,
}

/// API key creation response from /auth/apikeys
#[allow(dead_code)]
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct CreateApiKeyResponse {
    key_id: String,
    key: String,
    name: String,
    expires_at: Option<String>,
    created_at: String,
}

/// Agent registration response from /auth/register (role=agent).
///
/// The API no longer returns api_key or password - the agent creates and manages these locally.
#[allow(dead_code)]
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AgentRegistrationResponse {
    user_id: String,
    username: String,
    parent_user_id: String,
    role: String,
    created_at: String,
}

/// Node registration response from /nodes/register (returned directly, not wrapped in data)
/// Note: Some endpoints use SuccessResponse wrapper, others return directly
#[allow(dead_code)]
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
    /// Server secret for max-tier agents (returned once by the API)
    #[serde(default)]
    agent_server_secret: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ProfileMeta {
    version: String,
    profile_hash: String,
    section_fingerprints: HashMap<String, Vec<String>>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProfileSubmitResponse {
    pub profile_id: String,
    pub version: String,
}

/// A command received from polling the API.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PollCommand {
    pub command_id: String,
    pub registry_id: Option<String>,
    #[serde(rename = "type")]
    pub command_type: String,
    pub action: String,
    pub target: PollCommandTarget,
    pub parameters: Option<serde_json::Value>,
    pub timeout_seconds: u64,
}

/// Target of a polled command.
#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PollCommandTarget {
    pub node_id: String,
    pub service_id: Option<String>,
}

/// Payload for submitting a command result back to the API.
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CommandResultPayload {
    pub success: bool,
    pub output: Option<String>,
    pub exit_code: Option<i32>,
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<serde_json::Value>,
}

/// Poll response wrapper from the API.
#[derive(Debug, Deserialize)]
struct PollResponseData {
    commands: Vec<PollCommand>,
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

fn profile_meta_path(vault_dir: &Path) -> PathBuf {
    vault_dir.join("profile_meta.json")
}

fn load_profile_meta(path: &Path) -> Result<Option<ProfileMeta>> {
    if !path.exists() {
        return Ok(None);
    }

    let contents = std::fs::read_to_string(path)
        .with_context(|| format!("Failed to read profile meta file: {}", path.display()))?;

    let meta: ProfileMeta = serde_json::from_str(&contents)
        .with_context(|| format!("Failed to parse profile meta file: {}", path.display()))?;

    Ok(Some(meta))
}

fn save_profile_meta(path: &Path, meta: &ProfileMeta) -> Result<()> {
    let contents = serde_json::to_string_pretty(meta)?;
    std::fs::write(path, contents)
        .with_context(|| format!("Failed to write profile meta file: {}", path.display()))?;
    Ok(())
}

fn canonical_json(value: &Value) -> String {
    match value {
        Value::Object(map) => {
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            let mut entries = Vec::new();
            for key in keys {
                let key_json = serde_json::to_string(key).unwrap_or_else(|_| "\"\"".to_string());
                let value_json = canonical_json(&map[key]);
                entries.push(format!("{}:{}", key_json, value_json));
            }
            format!("{{{}}}", entries.join(","))
        }
        Value::Array(values) => {
            let items: Vec<String> = values.iter().map(canonical_json).collect();
            format!("[{}]", items.join(","))
        }
        _ => serde_json::to_string(value).unwrap_or_else(|_| "null".to_string()),
    }
}

fn sha256_hex(input: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(input.as_bytes());
    let digest = hasher.finalize();
    digest.iter().map(|b| format!("{:02x}", b)).collect()
}

fn hash_section<T: Serialize>(section: &T) -> Result<String> {
    let value = serde_json::to_value(section)?;
    let json = canonical_json(&value);
    let hex = sha256_hex(&json);
    Ok(hex.chars().take(16).collect())
}

fn compute_section_fingerprints(profile: &Profile) -> Result<HashMap<String, Vec<String>>> {
    let mut fingerprints = HashMap::new();

    if let Some(hardware) = &profile.hardware {
        fingerprints.insert("hardware".to_string(), vec![hash_section(hardware)?]);
    }
    if let Some(network) = &profile.network {
        fingerprints.insert("network".to_string(), vec![hash_section(network)?]);
    }
    if let Some(storage) = &profile.storage {
        fingerprints.insert("storage".to_string(), vec![hash_section(storage)?]);
    }
    if let Some(software) = &profile.software {
        fingerprints.insert("software".to_string(), vec![hash_section(software)?]);
    }

    Ok(fingerprints)
}

fn compute_profile_hash(fingerprints: &HashMap<String, Vec<String>>) -> String {
    let mut sections: Vec<&String> = fingerprints.keys().collect();
    sections.sort();

    let mut all_hashes = Vec::new();
    for section in sections {
        let mut hashes = fingerprints.get(section).cloned().unwrap_or_default();
        hashes.sort();
        all_hashes.extend(hashes);
    }

    let combined = all_hashes.join(":");
    sha256_hex(&combined)
}

fn section_weight(section: &str) -> f64 {
    match section {
        "hardware" => 0.30,
        "configs" => 0.25,
        "software" => 0.20,
        "storage" => 0.15,
        "network" => 0.10,
        _ => 0.10,
    }
}

fn increment_version(previous: &str, position: usize) -> Result<String> {
    let parts: Vec<&str> = previous.split('-').collect();
    if parts.len() != 2 || !parts[0].starts_with('E') {
        return Err(anyhow!("Invalid version format: {}", previous));
    }

    let epoch: u32 = parts[0][1..].parse()?;
    let components: Vec<&str> = parts[1].split('.').collect();
    if components.len() != 4 {
        return Err(anyhow!("Invalid version format: {}", previous));
    }

    let mut values: Vec<u32> = components
        .iter()
        .map(|c| u32::from_str_radix(c, 16))
        .collect::<std::result::Result<Vec<_>, _>>()
        .context("Invalid hex version component")?;

    if position >= values.len() {
        return Err(anyhow!("Invalid version position"));
    }

    values[position] += 1;

    let mut epoch = epoch;
    for i in (0..values.len()).rev() {
        if values[i] > 15 {
            values[i] = 0;
            if i > 0 {
                values[i - 1] += 1;
            } else {
                epoch += 1;
                values = vec![0, 0, 0, 0];
                break;
            }
        }
    }

    for value in values.iter_mut().skip(position + 1) {
        *value = 0;
    }

    let hex_components: Vec<String> = values.iter().map(|v| format!("{:X}", v)).collect();
    Ok(format!("E{}-{}", epoch, hex_components.join(".")))
}

fn compute_profile_version(
    previous: Option<&ProfileMeta>,
    current_fingerprints: &HashMap<String, Vec<String>>,
    profile_hash: &str,
) -> Result<String> {
    if let Some(prev) = previous {
        if prev.profile_hash == profile_hash {
            return Ok(prev.version.clone());
        }
    }

    if previous.is_none() {
        return Ok("E0-0.0.0.1".to_string());
    }

    let prev_meta = previous.expect("previous is guaranteed Some after is_none() check above");
    let mut total_diff = 0.0;

    let mut all_sections: HashSet<String> = HashSet::new();
    all_sections.extend(prev_meta.section_fingerprints.keys().cloned());
    all_sections.extend(current_fingerprints.keys().cloned());

    for section in all_sections {
        let prev_hashes = prev_meta
            .section_fingerprints
            .get(&section)
            .cloned()
            .unwrap_or_default();
        let curr_hashes = current_fingerprints
            .get(&section)
            .cloned()
            .unwrap_or_default();

        let prev_set: HashSet<String> = prev_hashes.into_iter().collect();
        let curr_set: HashSet<String> = curr_hashes.into_iter().collect();

        if prev_set != curr_set {
            let union: HashSet<String> = prev_set.union(&curr_set).cloned().collect();
            let intersection: HashSet<String> = prev_set.intersection(&curr_set).cloned().collect();
            let union_size = union.len() as f64;
            let intersection_size = intersection.len() as f64;
            if union_size > 0.0 {
                let jaccard = 1.0 - (intersection_size / union_size);
                total_diff += jaccard * section_weight(&section);
            }
        }
    }

    let position = if total_diff > 0.75 {
        0
    } else if total_diff > 0.50 {
        1
    } else if total_diff > 0.25 {
        2
    } else {
        3
    };

    increment_version(&prev_meta.version, position)
}

impl ApiClient {
    /// Create a new API client.
    pub fn new(config: &AgentConfig, vault: &Vault) -> Result<Self> {
        let client = Client::builder()
            .timeout(Duration::from_secs(config.api.timeout_seconds))
            .build()
            .context("Failed to create HTTP client")?;

        Ok(Self {
            client,
            config: config.clone(),
            vault: vault.clone(),
        })
    }

    /// Build the node registration request from config.
    fn build_registration_request(&self) -> NodeRegistrationRequest {
        use crate::config::AgentTier;

        let (server_address, server_port, server_tls_enabled) =
            if self.config.node.tier == AgentTier::Max && self.config.server.enabled {
                (
                    self.config.server.advertise_address.clone(),
                    Some(self.config.server.port),
                    Some(self.config.server.tls_enabled),
                )
            } else {
                (None, None, None)
            };

        NodeRegistrationRequest {
            node_id: self.config.node.node_id.clone(),
            node_class: self.config.node.class.clone(),
            node_type: self.config.node.node_type.clone(),
            tier: self.config.node.tier.to_string(),
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
            server_address,
            server_port,
            server_tls_enabled,
        }
    }

    /// Save registration response as credentials (from direct response).
    #[allow(dead_code)]
    fn save_credentials_from_direct(
        &self,
        response: &DirectNodeRegistrationResponse,
    ) -> Result<()> {
        let api_key = ApiKeyData {
            api_key: response.api_key.clone(),
            api_key_id: response.api_key_id.clone(),
            expires_at: None,
            node_id: Some(response.node_id.clone()),
            stored_at: chrono::Utc::now().to_rfc3339(),
        };

        self.vault.save_api_key(&api_key)?;
        info!(node_id = %response.node_id, "API key saved to vault");
        Ok(())
    }

    /// Save agent registration response as credentials (password from local generation).
    /// Per Some Updates.md: API no longer returns api_key or password.
    fn save_credentials_from_agent(
        &self,
        response: &AgentRegistrationResponse,
        password: &str,
    ) -> Result<()> {
        let creds = AgentCredentials {
            user_id: response.user_id.clone(),
            username: response.username.clone(),
            password: Some(password.to_string()),
            parent_user_id: response.parent_user_id.clone(),
            created_at: response.created_at.clone(),
        };
        self.vault.save_agent_credentials(&creds)?;
        info!(
            node_id = %self.config.node.node_id,
            agent_username = %response.username,
            "Agent credentials saved to vault"
        );
        Ok(())
    }

    /// Save API key from CreateApiKeyResponse (agent creates its own key).
    fn save_api_key_from_response(&self, response: &CreateApiKeyResponse) -> Result<()> {
        let api_key = ApiKeyData {
            api_key: response.key.clone(),
            api_key_id: response.key_id.clone(),
            expires_at: response.expires_at.clone(),
            node_id: Some(self.config.node.node_id.clone()),
            stored_at: chrono::Utc::now().to_rfc3339(),
        };
        self.vault.save_api_key(&api_key)?;
        info!("API key saved to vault");
        Ok(())
    }

    /// Save node registration metadata from /nodes/register.
    fn save_node_registration_from_response(
        &self,
        response: &DirectNodeRegistrationResponse,
    ) -> Result<()> {
        let registration = NodeRegistrationData {
            node_id: response.node_id.clone(),
            registered_at: response.registered_at.clone(),
            registered_by: response.registered_by.clone(),
            status: response.status.clone(),
        };
        self.vault.save_node_registration(&registration)?;
        info!(node_id = %response.node_id, "Node registration saved to vault");
        Ok(())
    }

    /// Create API key for agent using its JWT.
    async fn create_agent_api_key(
        &self,
        username: &str,
        access_token: &str,
    ) -> Result<CreateApiKeyResponse> {
        let api_key_url = format!("{}/auth/apikeys", self.config.api.url);

        let expires_at =
            (chrono::Utc::now() + chrono::Duration::days(API_KEY_DEFAULT_EXPIRY_DAYS)).to_rfc3339();

        let request = CreateApiKeyRequest {
            name: format!("{}-api-key", username),
            permissions: Vec::new(),
            expires_at: Some(expires_at),
        };

        debug!("Creating API key for agent: {}", username);

        let response = self
            .client
            .post(&api_key_url)
            .bearer_auth(access_token)
            .json(&request)
            .send()
            .await
            .context("Failed to send API key creation request")?;

        if !response.status().is_success() {
            let error: ApiError = response.json().await?;
            return Err(anyhow!(
                "API key creation failed: {} - {}",
                error.error.code,
                error.error.message
            ));
        }

        let api_key_response: CreateApiKeyResponse = response.json().await?;
        info!("API key created successfully");
        Ok(api_key_response)
    }

    async fn ensure_api_key(&self) -> Result<String> {
        if let Some(api_key) = self.vault.get_api_key()? {
            let expiring = self
                .vault
                .api_key_expires_within(API_KEY_RENEWAL_THRESHOLD_DAYS)?;
            if !expiring {
                return Ok(api_key);
            }
            warn!("API key expiring soon, renewing...");
        }

        self.refresh_api_key().await?;
        self.vault
            .get_api_key()?
            .ok_or_else(|| anyhow!("API key unavailable after refresh"))
    }

    async fn refresh_api_key(&self) -> Result<()> {
        let creds = self
            .vault
            .load_agent_credentials()?
            .ok_or_else(|| anyhow!("Agent credentials not found in vault"))?;

        let password = creds
            .password
            .clone()
            .ok_or_else(|| anyhow!("Agent password not available. Re-register the agent."))?;

        let access_token = self.login_as_agent(&creds.username, &password).await?;

        let expires_at =
            (chrono::Utc::now() + chrono::Duration::days(API_KEY_DEFAULT_EXPIRY_DAYS)).to_rfc3339();

        let request = CreateApiKeyRequest {
            name: format!("hydra-agent-{}", self.config.node.node_id),
            permissions: Vec::new(),
            expires_at: Some(expires_at),
        };

        let url = format!("{}/auth/apikeys", self.config.api.url);
        let response = self
            .client
            .post(&url)
            .bearer_auth(&access_token)
            .json(&request)
            .send()
            .await
            .context("Failed to create API key")?;

        if !response.status().is_success() {
            let error: ApiError = response.json().await?;
            return Err(anyhow!(
                "API key creation failed: {} - {}",
                error.error.code,
                error.error.message
            ));
        }

        let result: CreateApiKeyResponse = response.json().await?;
        let api_key = ApiKeyData {
            api_key: result.key,
            api_key_id: result.key_id,
            expires_at: result.expires_at,
            node_id: Some(self.config.node.node_id.clone()),
            stored_at: chrono::Utc::now().to_rfc3339(),
        };

        self.vault.save_api_key(&api_key)?;
        info!("API key refreshed and stored in vault");
        Ok(())
    }

    async fn login_as_agent(&self, username: &str, password: &str) -> Result<String> {
        let login_url = format!("{}/auth/login?source=agent", self.config.api.url);
        let request = LoginRequest {
            username: username.to_string(),
            password: password.to_string(),
        };

        let response = self
            .client
            .post(&login_url)
            .json(&request)
            .send()
            .await
            .context("Failed to login as agent")?;

        if !response.status().is_success() {
            let error: ApiError = response.json().await?;
            return Err(anyhow!(
                "Agent login failed: {} - {}",
                error.error.code,
                error.error.message
            ));
        }

        let login_response: LoginResponse = response.json().await?;
        Ok(login_response.access_token)
    }

    /// Register the agent and node using a registration token.
    /// Per Some Updates.md: Generate credentials locally, register, login, create API key.
    pub async fn register_with_token(&self, registration_token: &str) -> Result<()> {
        let agent_username = generate_agent_username();
        let agent_password = generate_agent_password();
        debug!("Generated agent credentials: {}", agent_username);

        let agent_url = format!("{}/auth/register", self.config.api.url);
        let agent_response = self
            .client
            .post(&agent_url)
            .json(&serde_json::json!({
                "role": "agent",
                "username": agent_username,
                "password": agent_password,
                "registrationToken": registration_token,
            }))
            .send()
            .await
            .context("Failed to send agent registration request")?;

        if !agent_response.status().is_success() {
            let error: ApiError = agent_response.json().await?;
            let err_msg = format!(
                "Agent registration failed: {} - {}",
                error.error.code, error.error.message
            );

            let _ = self
                .report_event(
                    "agent_registration_failed",
                    &format!("Agent registration failed: {}", self.config.node.node_id),
                    &err_msg,
                    Some(serde_json::json!({
                        "nodeId": self.config.node.node_id,
                        "error": err_msg,
                        "phase": "agent_registration",
                    })),
                )
                .await;

            return Err(anyhow!(err_msg));
        }

        let agent_result: AgentRegistrationResponse = agent_response.json().await?;
        info!("Agent registered successfully, logging in...");

        let access_token = self
            .login_as_agent(&agent_username, &agent_password)
            .await?;

        let api_key_response = self
            .create_agent_api_key(&agent_username, &access_token)
            .await?;

        self.save_credentials_from_agent(&agent_result, &agent_password)?;
        self.save_api_key_from_response(&api_key_response)?;

        let register_url = format!("{}/nodes/register", self.config.api.url);
        let request = self.build_registration_request();

        debug!(?request, "Registering node with agent API key");

        let response = self
            .client
            .post(&register_url)
            .header("X-API-Key", &api_key_response.key)
            .json(&request)
            .send()
            .await
            .context("Failed to send node registration request")?;

        if !response.status().is_success() {
            let error: ApiError = response.json().await?;
            let err_msg = format!(
                "Node registration failed: {} - {}",
                error.error.code, error.error.message
            );

            // API key is stored in vault at this point, so we can report
            let _ = self
                .report_event(
                    "agent_registration_failed",
                    &format!("Node registration failed: {}", self.config.node.node_id),
                    &err_msg,
                    Some(serde_json::json!({
                        "nodeId": self.config.node.node_id,
                        "error": err_msg,
                        "phase": "node_registration",
                    })),
                )
                .await;

            return Err(anyhow!(err_msg));
        }

        let result: DirectNodeRegistrationResponse = response.json().await?;
        self.save_node_registration_from_response(&result)?;

        // Save server secret for max-tier agents
        if let Some(secret) = &result.agent_server_secret {
            use crate::vault::ServerSecretData;
            self.vault.save_server_secret(&ServerSecretData {
                secret: secret.clone(),
                stored_at: chrono::Utc::now().to_rfc3339(),
            })?;
            info!("Server secret saved to vault");
        }

        info!(node_id = %result.node_id, "Registration with token successful");
        Ok(())
    }

    /// Register the agent and node using user credentials.
    /// Per Some Updates.md: Login, generate agent credentials locally, register, login as agent, create API key.
    pub async fn register_with_credentials(&self, username: &str, password: &str) -> Result<()> {
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

        let login_result: LoginResponse = login_response.json().await?;
        info!("Login successful, registering agent...");

        let agent_username = generate_agent_username();
        let agent_password = generate_agent_password();
        debug!("Generated agent credentials: {}", agent_username);

        let agent_url = format!("{}/auth/register", self.config.api.url);
        let agent_response = self
            .client
            .post(&agent_url)
            .bearer_auth(&login_result.access_token)
            .json(&serde_json::json!({
                "role": "agent",
                "username": agent_username,
                "password": agent_password,
            }))
            .send()
            .await
            .context("Failed to send agent registration request")?;

        if !agent_response.status().is_success() {
            let error: ApiError = agent_response.json().await?;
            let err_msg = format!(
                "Agent registration failed: {} - {}",
                error.error.code, error.error.message
            );

            let _ = self
                .report_event(
                    "agent_registration_failed",
                    &format!("Agent registration failed: {}", self.config.node.node_id),
                    &err_msg,
                    Some(serde_json::json!({
                        "nodeId": self.config.node.node_id,
                        "error": err_msg,
                        "phase": "agent_registration",
                    })),
                )
                .await;

            return Err(anyhow!(err_msg));
        }

        let agent_result: AgentRegistrationResponse = agent_response.json().await?;
        info!("Agent registered successfully, logging in as agent...");

        let access_token = self
            .login_as_agent(&agent_username, &agent_password)
            .await?;

        let api_key_response = self
            .create_agent_api_key(&agent_username, &access_token)
            .await?;

        self.save_credentials_from_agent(&agent_result, &agent_password)?;
        self.save_api_key_from_response(&api_key_response)?;

        let register_url = format!("{}/nodes/register", self.config.api.url);
        let request = self.build_registration_request();

        debug!(?request, "Registering node with agent API key");

        let response = self
            .client
            .post(&register_url)
            .header("X-API-Key", &api_key_response.key)
            .json(&request)
            .send()
            .await
            .context("Failed to send registration request")?;

        if !response.status().is_success() {
            let error: ApiError = response.json().await?;
            let err_msg = format!(
                "Node registration failed: {} - {}",
                error.error.code, error.error.message
            );

            // API key is stored in vault at this point, so we can report
            let _ = self
                .report_event(
                    "agent_registration_failed",
                    &format!("Node registration failed: {}", self.config.node.node_id),
                    &err_msg,
                    Some(serde_json::json!({
                        "nodeId": self.config.node.node_id,
                        "error": err_msg,
                        "phase": "node_registration",
                    })),
                )
                .await;

            return Err(anyhow!(err_msg));
        }

        let result: DirectNodeRegistrationResponse = response.json().await?;
        self.save_node_registration_from_response(&result)?;

        // Save server secret for max-tier agents
        if let Some(secret) = &result.agent_server_secret {
            use crate::vault::ServerSecretData;
            self.vault.save_server_secret(&ServerSecretData {
                secret: secret.clone(),
                stored_at: chrono::Utc::now().to_rfc3339(),
            })?;
            info!("Server secret saved to vault");
        }

        info!(
            node_id = %result.node_id,
            registered_by = %result.registered_by,
            "Registration with credentials successful"
        );
        Ok(())
    }

    /// Report an event to the Hydra API for notification emission.
    ///
    /// Used to report failures and state changes (profile failures,
    /// registration failures, successful profiles, upgrades) so the
    /// notification system can alert operators.
    ///
    /// This is best-effort: errors are logged but do not propagate.
    pub async fn report_event(
        &self,
        event_type: &str,
        title: &str,
        message: &str,
        details: Option<Value>,
    ) -> Result<()> {
        let url = format!("{}/agent/report", self.config.api.url);

        let api_key = match self.ensure_api_key().await {
            Ok(key) => key,
            Err(e) => {
                warn!("Cannot report event (no API key): {}", e);
                return Ok(());
            }
        };

        let mut body = serde_json::json!({
            "eventType": event_type,
            "title": title,
            "message": message,
            "nodeId": self.config.node.node_id,
        });

        if let Some(d) = details {
            body["details"] = d;
        }

        let response = self
            .client
            .post(&url)
            .header("X-API-Key", &api_key)
            .json(&body)
            .send()
            .await;

        match response {
            Ok(resp) if resp.status().is_success() => {
                debug!(event_type = event_type, "Event reported successfully");
            }
            Ok(resp) => {
                let status = resp.status();
                warn!(
                    event_type = event_type,
                    status = %status,
                    "Event report returned non-success status"
                );
            }
            Err(e) => {
                warn!(
                    event_type = event_type,
                    error = %e,
                    "Failed to report event"
                );
            }
        }

        Ok(())
    }

    /// Submit a profile to the API.
    /// Uses X-API-Key header for authentication.
    pub async fn submit_profile(&self, profile: &Profile) -> Result<ProfileSubmitResponse> {
        let url = format!("{}/profiles", self.config.api.url);

        let api_key = self.ensure_api_key().await?;

        let meta_path = profile_meta_path(&self.vault.base_path());
        let previous_meta = load_profile_meta(&meta_path)?;
        let fingerprints = compute_section_fingerprints(profile)?;
        let profile_hash = compute_profile_hash(&fingerprints);
        let version =
            compute_profile_version(previous_meta.as_ref(), &fingerprints, &profile_hash)?;

        let mut payload = profile.clone();
        payload.version = version.clone();

        let mut retries = self.config.api.retries;
        let mut last_error: Option<anyhow::Error> = None;

        while retries > 0 {
            let response = self
                .client
                .post(&url)
                .header("X-API-Key", &api_key)
                .json(&payload)
                .send()
                .await;

            match response {
                Ok(resp) if resp.status().is_success() => {
                    let result: ApiResponse<ProfileSubmitResponse> = resp.json().await?;
                    let meta = ProfileMeta {
                        version,
                        profile_hash,
                        section_fingerprints: fingerprints,
                    };
                    save_profile_meta(&meta_path, &meta)?;
                    return Ok(result.data);
                }
                Ok(resp) if resp.status() == StatusCode::UNAUTHORIZED => {
                    self.refresh_api_key().await?;
                    let refreshed_key = self.ensure_api_key().await?;
                    let retry_resp = self
                        .client
                        .post(&url)
                        .header("X-API-Key", &refreshed_key)
                        .json(&payload)
                        .send()
                        .await;

                    match retry_resp {
                        Ok(retry) if retry.status().is_success() => {
                            let result: ApiResponse<ProfileSubmitResponse> = retry.json().await?;
                            let meta = ProfileMeta {
                                version,
                                profile_hash,
                                section_fingerprints: fingerprints,
                            };
                            save_profile_meta(&meta_path, &meta)?;
                            return Ok(result.data);
                        }
                        Ok(retry) => {
                            let error: ApiError = retry.json().await?;
                            return Err(anyhow!(
                                "API error after key refresh: {} - {}",
                                error.error.code,
                                error.error.message
                            ));
                        }
                        Err(e) => {
                            return Err(anyhow!(e));
                        }
                    }
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

    /// Poll the API for pending commands assigned to this node.
    ///
    /// Returns a list of commands that have been atomically claimed (transitioned
    /// from QUEUED to EXECUTING). The agent is responsible for executing them
    /// and reporting results via `submit_command_result()`.
    pub async fn poll_commands(&self, node_id: &str) -> Result<Vec<PollCommand>> {
        let url = format!("{}/nodes/{}/commands/poll", self.config.api.url, node_id);
        let api_key = self.ensure_api_key().await?;

        let response = self
            .client
            .get(&url)
            .header("X-API-Key", &api_key)
            .send()
            .await
            .context("Failed to poll for commands")?;

        if !response.status().is_success() {
            let status = response.status();
            if status == StatusCode::FORBIDDEN || status == StatusCode::UNAUTHORIZED {
                debug!(
                    "Command poll returned {}: agent may lack commands:poll permission",
                    status
                );
                return Ok(vec![]);
            }
            let error: ApiError = response.json().await?;
            return Err(anyhow!(
                "Command poll failed: {} - {}",
                error.error.code,
                error.error.message
            ));
        }

        let result: ApiResponse<PollResponseData> = response.json().await?;
        Ok(result.data.commands)
    }

    /// Submit the result of a command execution back to the API.
    pub async fn submit_command_result(
        &self,
        node_id: &str,
        command_id: &str,
        result: &CommandResultPayload,
    ) -> Result<()> {
        let url = format!(
            "{}/nodes/{}/commands/{}/result",
            self.config.api.url, node_id, command_id
        );
        let api_key = self.ensure_api_key().await?;

        let response = self
            .client
            .post(&url)
            .header("X-API-Key", &api_key)
            .json(result)
            .send()
            .await
            .context("Failed to submit command result")?;

        if !response.status().is_success() {
            let error: ApiError = response.json().await?;
            return Err(anyhow!(
                "Command result submission failed: {} - {}",
                error.error.code,
                error.error.message
            ));
        }

        debug!(command_id = command_id, "Command result submitted");
        Ok(())
    }
}
