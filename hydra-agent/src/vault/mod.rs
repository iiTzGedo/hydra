//! Credential vault for secure storage of authentication data.
//!
//! The vault stores credentials with platform-specific paths:
//! - Unix: `/var/cv/hydra/`
//! - Windows: `C:\ProgramData\Hydra\vault\`
//!
//! Files in the vault:
//! - `.creds` - Agent credentials (username, password, user_id)
//! - `.apikey` - API key details
//! - `.session` - Current JWT session (for logged-in admin/operator)
//!
//! ## Environment Variable Caching
//!
//! Credentials can be cached in environment variables for quick access:
//! - `HYDRA_API_KEY` - API key for authentication
//! - `HYDRA_AGENT_USER` - Agent username
//! - `HYDRA_AGENT_PWD` - Agent password
//!
//! When reading credentials, environment variables are checked first before
//! falling back to vault files. This enables faster access in service contexts.

use anyhow::{Context, Result};
use base64::engine::general_purpose::STANDARD as BASE64_STANDARD;
use base64::Engine;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::RwLock;
use tracing::{debug, info, warn};

use crate::platform::paths;
use crate::platform::{self, EncryptedPayload};

/// Environment variable names for credential caching
pub const ENV_API_KEY: &str = "HYDRA_API_KEY";
pub const ENV_AGENT_USER: &str = "HYDRA_AGENT_USER";
pub const ENV_AGENT_PWD: &str = "HYDRA_AGENT_PWD";
const VAULT_FILE_VERSION: u8 = 1;
const LEGACY_VAULT_RESET_MESSAGE: &str =
    "Vault data is corrupted or uses an unsupported legacy format. Remove the local vault files and re-register the agent.";

#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;

/// Get the default vault directory path for the current platform
pub fn default_vault_dir() -> PathBuf {
    paths::default_vault_dir()
}

/// Default vault directory path (for backwards compatibility)
pub const VAULT_DIR: &str = {
    #[cfg(unix)]
    {
        "/var/cv/hydra"
    }
    #[cfg(windows)]
    {
        r"C:\ProgramData\Hydra\vault"
    }
};

/// Agent credentials stored after registration
#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AgentCredentials {
    /// Agent user ID
    pub user_id: String,
    /// Agent username (e.g., agent-ABC12345)
    pub username: String,
    /// Agent password (auto-generated)
    pub password: Option<String>,
    /// Parent user ID who created this agent
    pub parent_user_id: String,
    /// When the agent was created
    pub created_at: String,
}

impl std::fmt::Debug for AgentCredentials {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("AgentCredentials")
            .field("user_id", &self.user_id)
            .field("username", &self.username)
            .field("password", &"[REDACTED]")
            .field("parent_user_id", &self.parent_user_id)
            .field("created_at", &self.created_at)
            .finish()
    }
}

/// API key stored for authentication
#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ApiKeyData {
    /// API key value (hyk_agent_...)
    pub api_key: String,
    /// API key ID for reference
    pub api_key_id: String,
    /// When the API key expires
    pub expires_at: Option<String>,
    /// Node ID this key is associated with (if any)
    pub node_id: Option<String>,
    /// When the key was created/stored
    pub stored_at: String,
    /// When the key was last rotated (renewed), if ever. Tracks credential
    /// rotation locally so the agent can report/observe its rotation history.
    #[serde(default)]
    pub rotated_at: Option<String>,
}

impl std::fmt::Debug for ApiKeyData {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ApiKeyData")
            .field("api_key", &"[REDACTED]")
            .field("api_key_id", &self.api_key_id)
            .field("expires_at", &self.expires_at)
            .field("node_id", &self.node_id)
            .field("stored_at", &self.stored_at)
            .finish()
    }
}

/// JWT session for logged-in admin/operator user
#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionData {
    /// Access token (JWT)
    pub access_token: String,
    /// Refresh token
    pub refresh_token: String,
    /// Token type (Bearer)
    pub token_type: String,
    /// When the access token expires (Unix timestamp)
    pub expires_at: i64,
    /// Username of the logged-in user
    pub username: String,
    /// User ID
    pub user_id: String,
    /// User role
    pub role: String,
}

impl std::fmt::Debug for SessionData {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SessionData")
            .field("access_token", &"[REDACTED]")
            .field("refresh_token", &"[REDACTED]")
            .field("token_type", &self.token_type)
            .field("expires_at", &self.expires_at)
            .field("username", &self.username)
            .field("user_id", &self.user_id)
            .field("role", &self.role)
            .finish()
    }
}

/// Node registration data
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct NodeRegistrationData {
    /// Registered node ID
    pub node_id: String,
    /// When the node was registered
    pub registered_at: String,
    /// Who registered the node
    pub registered_by: String,
    /// Node status
    pub status: String,
}

/// Server secret for authenticating API-to-agent control requests (max-tier only).
///
/// Generated by the Hydra API during max-tier node registration and returned once.
/// The agent stores this secret and validates it on every incoming control request.
#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ServerSecretData {
    /// The bearer token secret (hsk_api_...)
    pub secret: String,
    /// When the secret was stored
    pub stored_at: String,
}

impl std::fmt::Debug for ServerSecretData {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ServerSecretData")
            .field("secret", &"[REDACTED]")
            .field("stored_at", &self.stored_at)
            .finish()
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct VaultEnvelope {
    version: u8,
    algorithm: String,
    nonce: Option<String>,
    ciphertext: String,
}

/// Credential vault for secure storage.
///
/// Uses a thread-safe in-memory cache instead of `env::set_var` for
/// credential caching, which is unsound in multi-threaded tokio runtimes.
pub struct Vault {
    /// Base directory for vault storage
    base_path: PathBuf,
    /// Thread-safe credential cache (replaces env::set_var)
    cache: RwLock<HashMap<String, String>>,
}

impl Clone for Vault {
    fn clone(&self) -> Self {
        let cache_data = self.cache.read().map(|g| g.clone()).unwrap_or_default();
        Self {
            base_path: self.base_path.clone(),
            cache: RwLock::new(cache_data),
        }
    }
}

impl Default for Vault {
    fn default() -> Self {
        Self::new(VAULT_DIR)
    }
}

impl Vault {
    /// Create a new vault instance with the specified base path
    pub fn new<P: AsRef<Path>>(path: P) -> Self {
        Self {
            base_path: path.as_ref().to_path_buf(),
            cache: RwLock::new(HashMap::new()),
        }
    }

    /// Ensure vault directory exists with proper permissions
    pub fn ensure_directory(&self) -> Result<()> {
        if !self.base_path.exists() {
            fs::create_dir_all(&self.base_path).with_context(|| {
                format!(
                    "Failed to create vault directory: {}",
                    self.base_path.display()
                )
            })?;

            #[cfg(unix)]
            {
                fs::set_permissions(&self.base_path, fs::Permissions::from_mode(0o700))?;
            }

            #[cfg(windows)]
            {
                use crate::platform::windows::WindowsPermissions;
                use crate::platform::FilePermissions;
                let perms = WindowsPermissions;
                if let Err(e) = perms.set_dir_owner_only(&self.base_path) {
                    warn!("Failed to set Windows ACL on vault directory: {}", e);
                }
            }

            info!("Created vault directory: {}", self.base_path.display());
        }

        Ok(())
    }

    /// Get the path to a file in the vault
    fn file_path(&self, filename: &str) -> PathBuf {
        self.base_path.join(filename)
    }

    /// Get vault base path (for related metadata files)
    pub fn base_path(&self) -> PathBuf {
        self.base_path.clone()
    }

    /// Write data to a vault file with proper permissions
    fn write_file<T: Serialize>(&self, filename: &str, data: &T) -> Result<()> {
        self.ensure_directory()?;

        let path = self.file_path(filename);
        let plaintext = serde_json::to_vec(data)?;
        let encrypted = platform::encryption().encrypt(&self.base_path, &plaintext)?;
        let envelope = VaultEnvelope {
            version: VAULT_FILE_VERSION,
            algorithm: encrypted.algorithm,
            nonce: encrypted.nonce.map(|nonce| BASE64_STANDARD.encode(nonce)),
            ciphertext: BASE64_STANDARD.encode(encrypted.ciphertext),
        };
        let contents = serde_json::to_vec_pretty(&envelope)?;

        fs::write(&path, &contents)
            .with_context(|| format!("Failed to write vault file: {}", path.display()))?;

        #[cfg(unix)]
        {
            fs::set_permissions(&path, fs::Permissions::from_mode(0o600))?;
        }

        #[cfg(windows)]
        {
            use crate::platform::windows::WindowsPermissions;
            use crate::platform::FilePermissions;
            let perms = WindowsPermissions;
            if let Err(e) = perms.set_owner_only(&path) {
                warn!("Failed to set Windows ACL on vault file: {}", e);
            }
        }

        debug!("Wrote vault file: {}", path.display());
        Ok(())
    }

    /// Read data from a vault file
    fn read_file<T: for<'de> Deserialize<'de> + Serialize>(
        &self,
        filename: &str,
    ) -> Result<Option<T>> {
        let path = self.file_path(filename);

        if !path.exists() {
            return Ok(None);
        }

        let contents = fs::read(&path)
            .with_context(|| format!("Failed to read vault file: {}", path.display()))?;
        let envelope: VaultEnvelope = match serde_json::from_slice(&contents) {
            Ok(envelope) => envelope,
            Err(envelope_error) => match serde_json::from_slice::<T>(&contents) {
                Ok(legacy_data) => {
                    info!("Migrating legacy plaintext vault file: {}", path.display());
                    self.write_file(filename, &legacy_data).with_context(|| {
                        format!(
                            "Failed to migrate legacy plaintext vault file: {}",
                            path.display()
                        )
                    })?;
                    return Ok(Some(legacy_data));
                }
                Err(_) => {
                    return Err(envelope_error).with_context(|| {
                        format!(
                            "Failed to parse encrypted vault file: {}. {}",
                            path.display(),
                            LEGACY_VAULT_RESET_MESSAGE
                        )
                    });
                }
            },
        };
        if envelope.version != VAULT_FILE_VERSION {
            anyhow::bail!(
                "Unsupported vault file version {} at {}",
                envelope.version,
                path.display()
            );
        }

        let ciphertext = BASE64_STANDARD
            .decode(&envelope.ciphertext)
            .with_context(|| format!("Failed to decode vault ciphertext: {}", path.display()))?;
        let nonce = envelope
            .nonce
            .map(|value| {
                BASE64_STANDARD
                    .decode(&value)
                    .with_context(|| format!("Failed to decode vault nonce: {}", path.display()))
            })
            .transpose()?;
        let payload = EncryptedPayload {
            algorithm: envelope.algorithm,
            nonce,
            ciphertext,
        };
        let plaintext = platform::encryption()
            .decrypt(&self.base_path, &payload)
            .with_context(|| format!("Failed to decrypt vault file: {}", path.display()))?;

        let data: T = serde_json::from_slice(&plaintext)
            .with_context(|| format!("Failed to parse decrypted vault file: {}", path.display()))?;

        Ok(Some(data))
    }

    /// Delete a vault file
    fn delete_file(&self, filename: &str) -> Result<()> {
        let path = self.file_path(filename);

        if path.exists() {
            fs::remove_file(&path)
                .with_context(|| format!("Failed to delete vault file: {}", path.display()))?;
            debug!("Deleted vault file: {}", path.display());
        }

        Ok(())
    }

    /// Save agent credentials
    pub fn save_agent_credentials(&self, creds: &AgentCredentials) -> Result<()> {
        self.write_file(".creds", creds)
    }

    /// Load agent credentials
    pub fn load_agent_credentials(&self) -> Result<Option<AgentCredentials>> {
        self.read_file(".creds")
    }

    /// Check if agent credentials exist
    pub fn has_agent_credentials(&self) -> bool {
        self.file_path(".creds").exists()
    }

    /// Delete agent credentials
    pub fn delete_agent_credentials(&self) -> Result<()> {
        self.delete_file(".creds")
    }

    /// Save API key
    pub fn save_api_key(&self, api_key: &ApiKeyData) -> Result<()> {
        self.write_file(".apikey", api_key)
    }

    /// Load API key
    pub fn load_api_key(&self) -> Result<Option<ApiKeyData>> {
        self.read_file(".apikey")
    }

    /// Check if API key exists
    pub fn has_api_key(&self) -> bool {
        self.file_path(".apikey").exists()
    }

    /// Delete API key
    pub fn delete_api_key(&self) -> Result<()> {
        self.delete_file(".apikey")
    }

    /// Check if API key is expired
    pub fn is_api_key_expired(&self) -> Result<bool> {
        if let Some(api_key) = self.load_api_key()? {
            if let Some(expires_at) = &api_key.expires_at {
                // Parse ISO 8601 timestamp and compare
                if let Ok(expiry) = chrono::DateTime::parse_from_rfc3339(expires_at) {
                    return Ok(expiry < chrono::Utc::now());
                }
            }
            // No expiry set means never expires
            return Ok(false);
        }
        Ok(true)
    }

    /// Check if API key expires within the given number of days
    pub fn api_key_expires_within(&self, days: i64) -> Result<bool> {
        if let Some(api_key) = self.load_api_key()? {
            if let Some(expires_at) = &api_key.expires_at {
                if let Ok(expiry) = chrono::DateTime::parse_from_rfc3339(expires_at) {
                    let threshold = chrono::Utc::now() + chrono::Duration::days(days);
                    return Ok(expiry < threshold);
                }
            }
            return Ok(false);
        }
        Ok(true)
    }

    /// Save session data
    pub fn save_session(&self, session: &SessionData) -> Result<()> {
        self.write_file(".session", session)
    }

    /// Load session data
    pub fn load_session(&self) -> Result<Option<SessionData>> {
        self.read_file(".session")
    }

    /// Check if session exists
    pub fn has_session(&self) -> bool {
        self.file_path(".session").exists()
    }

    /// Delete session
    pub fn delete_session(&self) -> Result<()> {
        self.delete_file(".session")
    }

    /// Check if current session is valid (not expired)
    pub fn is_session_valid(&self) -> Result<bool> {
        if let Some(session) = self.load_session()? {
            let now = chrono::Utc::now().timestamp();
            // Consider valid if we have at least 60 seconds before expiry
            return Ok(session.expires_at > now + 60);
        }
        Ok(false)
    }

    /// Get access token if session is valid
    pub fn get_valid_access_token(&self) -> Result<Option<String>> {
        if self.is_session_valid()? {
            if let Some(session) = self.load_session()? {
                return Ok(Some(session.access_token));
            }
        }
        Ok(None)
    }

    /// Save node registration data
    pub fn save_node_registration(&self, data: &NodeRegistrationData) -> Result<()> {
        self.write_file(".node", data)
    }

    /// Load node registration data
    pub fn load_node_registration(&self) -> Result<Option<NodeRegistrationData>> {
        self.read_file(".node")
    }

    /// Check if node is registered
    pub fn has_node_registration(&self) -> bool {
        self.file_path(".node").exists()
    }

    /// Delete node registration data
    pub fn delete_node_registration(&self) -> Result<()> {
        self.delete_file(".node")
    }

    /// Save server secret (max-tier only)
    pub fn save_server_secret(&self, data: &ServerSecretData) -> Result<()> {
        self.write_file(".server_secret", data)
    }

    /// Load server secret
    pub fn load_server_secret(&self) -> Result<Option<ServerSecretData>> {
        self.read_file(".server_secret")
    }

    /// Check if server secret exists
    pub fn has_server_secret(&self) -> bool {
        self.file_path(".server_secret").exists()
    }

    /// Delete server secret
    pub fn delete_server_secret(&self) -> Result<()> {
        self.delete_file(".server_secret")
    }

    /// Get the current API key for requests.
    /// Checks in-memory cache first, then environment variable, then vault file.
    pub fn get_api_key(&self) -> Result<Option<String>> {
        // Check thread-safe cache first
        if let Ok(cache) = self.cache.read() {
            if let Some(api_key) = cache.get(ENV_API_KEY) {
                if !api_key.is_empty() {
                    debug!("Using API key from cache");
                    return Ok(Some(api_key.clone()));
                }
            }
        }

        // Fallback to environment variable (set externally, not by us)
        if let Ok(api_key) = env::var(ENV_API_KEY) {
            if !api_key.is_empty() {
                debug!("Using API key from environment variable");
                return Ok(Some(api_key));
            }
        }

        if let Some(api_key) = self.load_api_key()? {
            if !self.is_api_key_expired()? {
                return Ok(Some(api_key.api_key));
            }
            warn!("API key is expired");
        }
        Ok(None)
    }

    /// Get authentication header value (API key or Bearer token).
    /// Checks environment variables first for fast access in service contexts.
    pub fn get_auth_header(&self) -> Result<Option<(String, String)>> {
        if let Some(api_key) = self.get_api_key()? {
            return Ok(Some(("X-API-Key".to_string(), api_key)));
        }

        if let Some(token) = self.get_valid_access_token()? {
            return Ok(Some((
                "Authorization".to_string(),
                format!("Bearer {}", token),
            )));
        }

        Ok(None)
    }

    /// Get agent username from cache, environment, or vault.
    pub fn get_agent_username(&self) -> Result<Option<String>> {
        if let Ok(cache) = self.cache.read() {
            if let Some(username) = cache.get(ENV_AGENT_USER) {
                if !username.is_empty() {
                    debug!("Using agent username from cache");
                    return Ok(Some(username.clone()));
                }
            }
        }

        if let Ok(username) = env::var(ENV_AGENT_USER) {
            if !username.is_empty() {
                debug!("Using agent username from environment variable");
                return Ok(Some(username));
            }
        }

        if let Some(creds) = self.load_agent_credentials()? {
            return Ok(Some(creds.username));
        }
        Ok(None)
    }

    /// Get agent password from cache, environment, or vault.
    pub fn get_agent_password(&self) -> Result<Option<String>> {
        if let Ok(cache) = self.cache.read() {
            if let Some(password) = cache.get(ENV_AGENT_PWD) {
                if !password.is_empty() {
                    debug!("Using agent password from cache");
                    return Ok(Some(password.clone()));
                }
            }
        }

        if let Ok(password) = env::var(ENV_AGENT_PWD) {
            if !password.is_empty() {
                debug!("Using agent password from environment variable");
                return Ok(Some(password));
            }
        }

        if let Some(creds) = self.load_agent_credentials()? {
            return Ok(creds.password);
        }
        Ok(None)
    }

    /// Export credentials to the thread-safe in-memory cache.
    /// Use in service context for fast access. Returns the exported variables.
    pub fn export_to_env(&self) -> Result<Vec<(String, String)>> {
        let mut exported = Vec::new();

        if let Some(api_key_data) = self.load_api_key()? {
            if !self.is_api_key_expired()? {
                exported.push((ENV_API_KEY.to_string(), api_key_data.api_key));
                debug!("Cached API key");
            }
        }

        if let Some(creds) = self.load_agent_credentials()? {
            exported.push((ENV_AGENT_USER.to_string(), creds.username.clone()));
            debug!("Cached agent username");

            if let Some(password) = &creds.password {
                exported.push((ENV_AGENT_PWD.to_string(), password.clone()));
                debug!("Cached agent password");
            }
        }

        // Write all at once to minimize lock contention
        if let Ok(mut cache) = self.cache.write() {
            for (key, value) in &exported {
                cache.insert(key.clone(), value.clone());
            }
        }

        Ok(exported)
    }

    /// Clear credential cache.
    pub fn clear_env_cache(&self) {
        if let Ok(mut cache) = self.cache.write() {
            cache.remove(ENV_API_KEY);
            cache.remove(ENV_AGENT_USER);
            cache.remove(ENV_AGENT_PWD);
        }
        debug!("Cleared credential cache");
    }

    /// Check if credentials are available from cache or environment variables.
    pub fn has_env_credentials(&self) -> bool {
        if let Ok(cache) = self.cache.read() {
            if cache
                .get(ENV_API_KEY)
                .map(|v| !v.is_empty())
                .unwrap_or(false)
            {
                return true;
            }
        }
        env::var(ENV_API_KEY)
            .map(|v| !v.is_empty())
            .unwrap_or(false)
    }

    /// Clear all vault data
    pub fn clear_all(&self) -> Result<()> {
        self.delete_agent_credentials()?;
        self.delete_api_key()?;
        self.delete_session()?;
        self.delete_node_registration()?;
        self.delete_server_secret()?;
        #[cfg(unix)]
        {
            let key_path = self.file_path(crate::platform::unix::VAULT_MASTER_KEY_FILE);
            if key_path.exists() {
                fs::remove_file(&key_path).with_context(|| {
                    format!("Failed to delete vault master key: {}", key_path.display())
                })?;
            }
        }
        self.clear_env_cache();
        info!("Cleared all vault data");
        Ok(())
    }

    /// Get vault status summary
    pub fn status(&self) -> VaultStatus {
        VaultStatus {
            has_agent_credentials: self.has_agent_credentials(),
            has_api_key: self.has_api_key(),
            has_session: self.has_session(),
            has_node_registration: self.has_node_registration(),
            has_server_secret: self.has_server_secret(),
            api_key_expired: self.is_api_key_expired().unwrap_or(true),
            session_valid: self.is_session_valid().unwrap_or(false),
            has_env_credentials: self.has_env_credentials(),
        }
    }
}

/// Summary of vault status
#[derive(Debug, Clone)]
pub struct VaultStatus {
    pub has_agent_credentials: bool,
    pub has_api_key: bool,
    pub has_session: bool,
    pub has_node_registration: bool,
    pub has_server_secret: bool,
    pub api_key_expired: bool,
    pub session_valid: bool,
    pub has_env_credentials: bool,
}

impl std::fmt::Display for VaultStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        writeln!(f, "Vault Status:")?;
        writeln!(
            f,
            "  Agent credentials: {}",
            if self.has_agent_credentials {
                "present"
            } else {
                "not found"
            }
        )?;
        writeln!(
            f,
            "  API key: {}",
            if self.has_api_key {
                if self.api_key_expired {
                    "expired"
                } else {
                    "valid"
                }
            } else {
                "not found"
            }
        )?;
        writeln!(
            f,
            "  Session: {}",
            if self.has_session {
                if self.session_valid {
                    "active"
                } else {
                    "expired"
                }
            } else {
                "not found"
            }
        )?;
        writeln!(
            f,
            "  Node registration: {}",
            if self.has_node_registration {
                "registered"
            } else {
                "not registered"
            }
        )?;
        writeln!(
            f,
            "  Server secret: {}",
            if self.has_server_secret {
                "present"
            } else {
                "not found"
            }
        )?;
        writeln!(
            f,
            "  Env cache: {}",
            if self.has_env_credentials {
                "active"
            } else {
                "not cached"
            }
        )?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn test_vault_operations() {
        let temp_dir = TempDir::new().unwrap();
        let vault = Vault::new(temp_dir.path());

        // Test agent credentials
        let creds = AgentCredentials {
            user_id: "user_123".to_string(),
            username: "agent-TEST1234".to_string(),
            password: Some("secret123".to_string()),
            parent_user_id: "user_admin".to_string(),
            created_at: "2024-01-01T00:00:00Z".to_string(),
        };

        vault.save_agent_credentials(&creds).unwrap();
        assert!(vault.has_agent_credentials());

        let loaded = vault.load_agent_credentials().unwrap().unwrap();
        assert_eq!(loaded.username, "agent-TEST1234");

        vault.delete_agent_credentials().unwrap();
        assert!(!vault.has_agent_credentials());
    }

    #[test]
    fn test_api_key_operations() {
        let temp_dir = TempDir::new().unwrap();
        let vault = Vault::new(temp_dir.path());

        let api_key = ApiKeyData {
            api_key: "hyk_agent_test123".to_string(),
            api_key_id: "key_123".to_string(),
            expires_at: Some("2099-12-31T23:59:59Z".to_string()),
            node_id: Some("test-node".to_string()),
            stored_at: "2024-01-01T00:00:00Z".to_string(),
            rotated_at: None,
        };

        vault.save_api_key(&api_key).unwrap();
        assert!(vault.has_api_key());
        assert!(!vault.is_api_key_expired().unwrap());

        let loaded = vault.load_api_key().unwrap().unwrap();
        assert_eq!(loaded.api_key, "hyk_agent_test123");
    }
}
