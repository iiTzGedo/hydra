//! Comprehensive tests for the credential vault.
//!
//! Tests cover:
//! - Agent credentials CRUD operations
//! - API key operations and expiration handling
//! - Session management and validity checks
//! - Node registration data
//! - Environment variable caching
//! - Auth header generation
//! - Error handling and edge cases

use chrono::{Duration, Utc};
use hydra_agent::vault::{
    AgentCredentials, ApiKeyData, NodeRegistrationData, SessionData, Vault, ENV_AGENT_PWD,
    ENV_AGENT_USER, ENV_API_KEY,
};
use std::env;
use std::sync::{Mutex, MutexGuard, OnceLock};
use tempfile::TempDir;

// =============================================================================
// Helper Functions
// =============================================================================

fn create_test_vault() -> (TempDir, Vault) {
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let vault = Vault::new(temp_dir.path());
    (temp_dir, vault)
}

fn sample_agent_credentials() -> AgentCredentials {
    AgentCredentials {
        user_id: "user_abc123".to_string(),
        username: "agent-TESTNODE01".to_string(),
        password: Some("super_secret_password_123".to_string()),
        parent_user_id: "user_admin456".to_string(),
        created_at: "2024-01-15T10:30:00Z".to_string(),
    }
}

fn sample_api_key(expires_in_days: Option<i64>) -> ApiKeyData {
    let expires_at = expires_in_days.map(|days| (Utc::now() + Duration::days(days)).to_rfc3339());

    ApiKeyData {
        api_key: "hyk_agent_test_key_xyz789".to_string(),
        api_key_id: "key_test123".to_string(),
        expires_at,
        node_id: Some("test-node-01".to_string()),
        stored_at: Utc::now().to_rfc3339(),
    }
}

fn sample_session(expires_in_seconds: i64) -> SessionData {
    SessionData {
        access_token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test_payload".to_string(),
        refresh_token: "refresh_token_abc123".to_string(),
        token_type: "Bearer".to_string(),
        expires_at: Utc::now().timestamp() + expires_in_seconds,
        username: "admin".to_string(),
        user_id: "user_admin123".to_string(),
        role: "admin".to_string(),
    }
}

fn sample_node_registration() -> NodeRegistrationData {
    NodeRegistrationData {
        node_id: "test-node-01".to_string(),
        registered_at: "2024-01-15T10:30:00Z".to_string(),
        registered_by: "admin".to_string(),
        status: "active".to_string(),
    }
}

// Clean up environment variables before/after tests
fn cleanup_env() {
    env::remove_var(ENV_API_KEY);
    env::remove_var(ENV_AGENT_USER);
    env::remove_var(ENV_AGENT_PWD);
}

fn env_lock() -> MutexGuard<'static, ()> {
    static ENV_LOCK: OnceLock<Mutex<()>> = OnceLock::new();
    let mutex = ENV_LOCK.get_or_init(|| Mutex::new(()));
    // Recover from poisoned lock (a prior test may have panicked)
    match mutex.lock() {
        Ok(guard) => guard,
        Err(poisoned) => poisoned.into_inner(),
    }
}

// =============================================================================
// Agent Credentials Tests
// =============================================================================

#[test]
fn test_agent_credentials_save_and_load() {
    let (_temp_dir, vault) = create_test_vault();
    let creds = sample_agent_credentials();

    // Save credentials
    vault
        .save_agent_credentials(&creds)
        .expect("Should save credentials");
    assert!(vault.has_agent_credentials());

    // Load and verify
    let loaded = vault
        .load_agent_credentials()
        .expect("Should load")
        .expect("Should have credentials");

    assert_eq!(loaded.user_id, creds.user_id);
    assert_eq!(loaded.username, creds.username);
    assert_eq!(loaded.password, creds.password);
    assert_eq!(loaded.parent_user_id, creds.parent_user_id);
    assert_eq!(loaded.created_at, creds.created_at);
}

#[test]
fn test_agent_credentials_delete() {
    let (_temp_dir, vault) = create_test_vault();
    let creds = sample_agent_credentials();

    vault.save_agent_credentials(&creds).expect("Should save");
    assert!(vault.has_agent_credentials());

    vault.delete_agent_credentials().expect("Should delete");
    assert!(!vault.has_agent_credentials());

    let loaded = vault.load_agent_credentials().expect("Should not error");
    assert!(loaded.is_none());
}

#[test]
fn test_agent_credentials_without_password() {
    let (_temp_dir, vault) = create_test_vault();
    let creds = AgentCredentials {
        user_id: "user_123".to_string(),
        username: "agent-NOPASS".to_string(),
        password: None,
        parent_user_id: "user_admin".to_string(),
        created_at: "2024-01-01T00:00:00Z".to_string(),
    };

    vault.save_agent_credentials(&creds).expect("Should save");
    let loaded = vault
        .load_agent_credentials()
        .expect("Should load")
        .expect("Should have credentials");

    assert!(loaded.password.is_none());
}

#[test]
fn test_agent_credentials_update() {
    let (_temp_dir, vault) = create_test_vault();
    let mut creds = sample_agent_credentials();

    vault.save_agent_credentials(&creds).expect("Should save");

    // Update credentials
    creds.password = Some("new_password_456".to_string());
    vault.save_agent_credentials(&creds).expect("Should update");

    let loaded = vault
        .load_agent_credentials()
        .expect("Should load")
        .expect("Should have credentials");
    assert_eq!(loaded.password, Some("new_password_456".to_string()));
}

// =============================================================================
// API Key Tests
// =============================================================================

#[test]
fn test_api_key_save_and_load() {
    let (_temp_dir, vault) = create_test_vault();
    let api_key = sample_api_key(Some(90));

    vault.save_api_key(&api_key).expect("Should save API key");
    assert!(vault.has_api_key());

    let loaded = vault
        .load_api_key()
        .expect("Should load")
        .expect("Should have API key");

    assert_eq!(loaded.api_key, api_key.api_key);
    assert_eq!(loaded.api_key_id, api_key.api_key_id);
    assert_eq!(loaded.node_id, api_key.node_id);
}

#[test]
fn test_api_key_delete() {
    let (_temp_dir, vault) = create_test_vault();
    let api_key = sample_api_key(Some(90));

    vault.save_api_key(&api_key).expect("Should save");
    assert!(vault.has_api_key());

    vault.delete_api_key().expect("Should delete");
    assert!(!vault.has_api_key());
}

#[test]
fn test_api_key_not_expired() {
    let (_temp_dir, vault) = create_test_vault();
    // Expires in 90 days
    let api_key = sample_api_key(Some(90));

    vault.save_api_key(&api_key).expect("Should save");

    assert!(!vault.is_api_key_expired().expect("Should check expiry"));
}

#[test]
fn test_api_key_expired() {
    let (_temp_dir, vault) = create_test_vault();
    // Already expired (negative days)
    let api_key = sample_api_key(Some(-1));

    vault.save_api_key(&api_key).expect("Should save");

    assert!(vault.is_api_key_expired().expect("Should check expiry"));
}

#[test]
fn test_api_key_no_expiry() {
    let (_temp_dir, vault) = create_test_vault();
    // No expiry set
    let api_key = sample_api_key(None);

    vault.save_api_key(&api_key).expect("Should save");

    // No expiry means never expires
    assert!(!vault.is_api_key_expired().expect("Should check expiry"));
}

#[test]
fn test_api_key_expires_within_threshold() {
    let (_temp_dir, vault) = create_test_vault();

    // Expires in 5 days
    let api_key = sample_api_key(Some(5));
    vault.save_api_key(&api_key).expect("Should save");

    // Should expire within 7 days
    assert!(vault.api_key_expires_within(7).expect("Should check"));

    // Should NOT expire within 3 days
    assert!(!vault.api_key_expires_within(3).expect("Should check"));
}

#[test]
fn test_api_key_missing_returns_expired() {
    let (_temp_dir, vault) = create_test_vault();

    // No API key saved
    assert!(!vault.has_api_key());

    // Missing API key is considered "expired" for convenience
    assert!(vault.is_api_key_expired().expect("Should check"));
    assert!(vault.api_key_expires_within(30).expect("Should check"));
}

// =============================================================================
// Session Tests
// =============================================================================

#[test]
fn test_session_save_and_load() {
    let (_temp_dir, vault) = create_test_vault();
    let session = sample_session(3600); // Expires in 1 hour

    vault.save_session(&session).expect("Should save session");
    assert!(vault.has_session());

    let loaded = vault
        .load_session()
        .expect("Should load")
        .expect("Should have session");

    assert_eq!(loaded.access_token, session.access_token);
    assert_eq!(loaded.refresh_token, session.refresh_token);
    assert_eq!(loaded.username, session.username);
    assert_eq!(loaded.role, session.role);
}

#[test]
fn test_session_delete() {
    let (_temp_dir, vault) = create_test_vault();
    let session = sample_session(3600);

    vault.save_session(&session).expect("Should save");
    assert!(vault.has_session());

    vault.delete_session().expect("Should delete");
    assert!(!vault.has_session());
}

#[test]
fn test_session_valid() {
    let (_temp_dir, vault) = create_test_vault();
    // Expires in 2 hours
    let session = sample_session(7200);

    vault.save_session(&session).expect("Should save");

    assert!(vault.is_session_valid().expect("Should check validity"));
}

#[test]
fn test_session_expired() {
    let (_temp_dir, vault) = create_test_vault();
    // Already expired (negative seconds)
    let session = sample_session(-100);

    vault.save_session(&session).expect("Should save");

    assert!(!vault.is_session_valid().expect("Should check validity"));
}

#[test]
fn test_session_expiring_soon() {
    let (_temp_dir, vault) = create_test_vault();
    // Expires in 30 seconds (less than 60s threshold)
    let session = sample_session(30);

    vault.save_session(&session).expect("Should save");

    // Should be invalid because < 60 seconds remaining
    assert!(!vault.is_session_valid().expect("Should check validity"));
}

#[test]
fn test_get_valid_access_token() {
    let (_temp_dir, vault) = create_test_vault();
    let session = sample_session(3600);

    vault.save_session(&session).expect("Should save");

    let token = vault.get_valid_access_token().expect("Should get token");
    assert!(token.is_some());
    assert_eq!(token.unwrap(), session.access_token);
}

#[test]
fn test_get_valid_access_token_expired() {
    let (_temp_dir, vault) = create_test_vault();
    let session = sample_session(-100);

    vault.save_session(&session).expect("Should save");

    let token = vault.get_valid_access_token().expect("Should get token");
    assert!(token.is_none());
}

#[test]
fn test_get_valid_access_token_missing() {
    let (_temp_dir, vault) = create_test_vault();

    let token = vault.get_valid_access_token().expect("Should get token");
    assert!(token.is_none());
}

// =============================================================================
// Node Registration Tests
// =============================================================================

#[test]
fn test_node_registration_save_and_load() {
    let (_temp_dir, vault) = create_test_vault();
    let reg = sample_node_registration();

    vault.save_node_registration(&reg).expect("Should save");
    assert!(vault.has_node_registration());

    let loaded = vault
        .load_node_registration()
        .expect("Should load")
        .expect("Should have registration");

    assert_eq!(loaded.node_id, reg.node_id);
    assert_eq!(loaded.registered_at, reg.registered_at);
    assert_eq!(loaded.registered_by, reg.registered_by);
    assert_eq!(loaded.status, reg.status);
}

#[test]
fn test_node_registration_delete() {
    let (_temp_dir, vault) = create_test_vault();
    let reg = sample_node_registration();

    vault.save_node_registration(&reg).expect("Should save");
    vault.delete_node_registration().expect("Should delete");

    assert!(!vault.has_node_registration());
}

// =============================================================================
// Environment Variable Tests
// =============================================================================

#[test]
fn test_get_api_key_from_env() {
    let _guard = env_lock();
    cleanup_env();
    let (_temp_dir, vault) = create_test_vault();

    // Set env var
    env::set_var(ENV_API_KEY, "hyk_env_test_key");

    let api_key = vault.get_api_key().expect("Should get API key");
    assert!(api_key.is_some());
    assert_eq!(api_key.unwrap(), "hyk_env_test_key");

    cleanup_env();
}

#[test]
fn test_get_api_key_fallback_to_vault() {
    let _guard = env_lock();
    cleanup_env();
    let (_temp_dir, vault) = create_test_vault();

    // Save API key to vault (not in env)
    let api_key = sample_api_key(Some(90));
    vault.save_api_key(&api_key).expect("Should save");

    let retrieved = vault.get_api_key().expect("Should get API key");
    assert!(retrieved.is_some());
    assert_eq!(retrieved.unwrap(), api_key.api_key);

    cleanup_env();
}

#[test]
fn test_get_api_key_env_takes_precedence() {
    let _guard = env_lock();
    cleanup_env();
    let (_temp_dir, vault) = create_test_vault();

    // Save different API key to vault
    let vault_key = sample_api_key(Some(90));
    vault.save_api_key(&vault_key).expect("Should save");

    // Set different key in env
    env::set_var(ENV_API_KEY, "hyk_env_override");

    let retrieved = vault.get_api_key().expect("Should get API key");
    assert_eq!(retrieved.unwrap(), "hyk_env_override");

    cleanup_env();
}

#[test]
fn test_get_agent_username_from_env() {
    let _guard = env_lock();
    cleanup_env();
    let (_temp_dir, vault) = create_test_vault();

    env::set_var(ENV_AGENT_USER, "agent-ENV123");

    let username = vault.get_agent_username().expect("Should get username");
    assert_eq!(username.unwrap(), "agent-ENV123");

    cleanup_env();
}

#[test]
fn test_get_agent_password_from_env() {
    let _guard = env_lock();
    cleanup_env();
    let (_temp_dir, vault) = create_test_vault();

    env::set_var(ENV_AGENT_PWD, "env_secret_pwd");

    let password = vault.get_agent_password().expect("Should get password");
    assert_eq!(password.unwrap(), "env_secret_pwd");

    cleanup_env();
}

#[test]
fn test_export_to_env() {
    let _guard = env_lock();
    cleanup_env();
    let (_temp_dir, vault) = create_test_vault();

    // Save credentials and API key
    let creds = sample_agent_credentials();
    let api_key = sample_api_key(Some(90));

    vault
        .save_agent_credentials(&creds)
        .expect("Should save creds");
    vault.save_api_key(&api_key).expect("Should save API key");

    // Export to env
    let exported = vault.export_to_env().expect("Should export");

    // Verify the exported vector contains the expected values
    // (Checking the vector is more reliable than checking env vars in parallel tests)
    assert!(
        !exported.is_empty(),
        "Should export at least some variables"
    );
    assert!(
        exported.len() >= 2,
        "Should export at least user and password"
    );

    // Check that the expected values are in the exported vector
    let exported_map: std::collections::HashMap<_, _> = exported.into_iter().collect();

    assert!(
        exported_map.contains_key(ENV_AGENT_USER),
        "Should export agent username"
    );
    assert_eq!(
        exported_map.get(ENV_AGENT_USER),
        Some(&creds.username),
        "Exported username should match"
    );

    // Password should be exported if present
    if let Some(pwd) = creds.password {
        assert!(
            exported_map.contains_key(ENV_AGENT_PWD),
            "Should export agent password"
        );
        assert_eq!(
            exported_map.get(ENV_AGENT_PWD),
            Some(&pwd),
            "Exported password should match"
        );
    }

    // API key should be exported since it's not expired
    assert!(
        exported_map.contains_key(ENV_API_KEY),
        "Should export API key"
    );
    assert_eq!(
        exported_map.get(ENV_API_KEY),
        Some(&api_key.api_key),
        "Exported API key should match"
    );

    cleanup_env();
}

#[test]
fn test_clear_env_cache() {
    let _guard = env_lock();
    cleanup_env();
    let (_temp_dir, vault) = create_test_vault();

    // Populate cache via export_to_env
    let creds = sample_agent_credentials();
    let api_key = sample_api_key(Some(90));
    vault.save_agent_credentials(&creds).expect("save");
    vault.save_api_key(&api_key).expect("save");
    vault.export_to_env().expect("export");

    // Verify cache is populated
    assert!(vault.has_env_credentials());

    // Clear cache (no longer touches process env vars)
    vault.clear_env_cache();

    // Cache should be empty now
    assert!(!vault.has_env_credentials());

    cleanup_env();
}

#[test]
fn test_has_env_credentials() {
    let _guard = env_lock();
    cleanup_env();
    let (_temp_dir, vault) = create_test_vault();

    assert!(!vault.has_env_credentials());

    // Populate via export_to_env (cache-based)
    let api_key = sample_api_key(Some(90));
    vault.save_api_key(&api_key).expect("save");
    vault.export_to_env().expect("export");

    assert!(vault.has_env_credentials());

    cleanup_env();
}

// =============================================================================
// Auth Header Tests
// =============================================================================

#[test]
fn test_get_auth_header_api_key() {
    let _guard = env_lock();
    cleanup_env();
    let (_temp_dir, vault) = create_test_vault();

    let api_key = sample_api_key(Some(90));
    vault.save_api_key(&api_key).expect("Should save");

    let header = vault.get_auth_header().expect("Should get header");
    assert!(header.is_some());

    let (name, value) = header.unwrap();
    assert_eq!(name, "X-API-Key");
    assert_eq!(value, api_key.api_key);

    cleanup_env();
}

#[test]
fn test_get_auth_header_session_fallback() {
    let _guard = env_lock();
    cleanup_env();
    let (_temp_dir, vault) = create_test_vault();

    // No API key, but valid session
    let session = sample_session(3600);
    vault.save_session(&session).expect("Should save");

    let header = vault.get_auth_header().expect("Should get header");
    assert!(header.is_some());

    let (name, value) = header.unwrap();
    assert_eq!(name, "Authorization");
    assert!(value.starts_with("Bearer "));

    cleanup_env();
}

#[test]
fn test_get_auth_header_api_key_preferred() {
    let _guard = env_lock();
    cleanup_env();
    let (_temp_dir, vault) = create_test_vault();

    // Both API key and session available
    let api_key = sample_api_key(Some(90));
    let session = sample_session(3600);
    vault.save_api_key(&api_key).expect("Should save API key");
    vault.save_session(&session).expect("Should save session");

    let header = vault.get_auth_header().expect("Should get header");
    let (name, _) = header.unwrap();

    // API key should be preferred
    assert_eq!(name, "X-API-Key");

    cleanup_env();
}

#[test]
fn test_get_auth_header_none_available() {
    let _guard = env_lock();
    cleanup_env();
    let (_temp_dir, vault) = create_test_vault();

    let header = vault.get_auth_header().expect("Should not error");
    assert!(header.is_none());

    cleanup_env();
}

// =============================================================================
// Clear All Tests
// =============================================================================

#[test]
fn test_clear_all() {
    let _guard = env_lock();
    cleanup_env();
    let (_temp_dir, vault) = create_test_vault();

    // Save everything
    vault
        .save_agent_credentials(&sample_agent_credentials())
        .expect("Save creds");
    vault
        .save_api_key(&sample_api_key(Some(90)))
        .expect("Save API key");
    vault
        .save_session(&sample_session(3600))
        .expect("Save session");
    vault
        .save_node_registration(&sample_node_registration())
        .expect("Save node reg");

    // Populate cache
    vault.export_to_env().expect("export");

    // Clear all
    vault.clear_all().expect("Should clear all");

    assert!(!vault.has_agent_credentials());
    assert!(!vault.has_api_key());
    assert!(!vault.has_session());
    assert!(!vault.has_node_registration());
    assert!(!vault.has_env_credentials());

    cleanup_env();
}

// =============================================================================
// Vault Status Tests
// =============================================================================

#[test]
fn test_vault_status_empty() {
    let (_temp_dir, vault) = create_test_vault();

    let status = vault.status();

    assert!(!status.has_agent_credentials);
    assert!(!status.has_api_key);
    assert!(!status.has_session);
    assert!(!status.has_node_registration);
    assert!(status.api_key_expired); // Missing = expired
    assert!(!status.session_valid);
}

#[test]
fn test_vault_status_full() {
    let _guard = env_lock();
    cleanup_env();
    let (_temp_dir, vault) = create_test_vault();

    vault
        .save_agent_credentials(&sample_agent_credentials())
        .expect("Save creds");
    vault
        .save_api_key(&sample_api_key(Some(90)))
        .expect("Save API key");
    vault
        .save_session(&sample_session(3600))
        .expect("Save session");
    vault
        .save_node_registration(&sample_node_registration())
        .expect("Save node reg");

    let status = vault.status();

    assert!(status.has_agent_credentials);
    assert!(status.has_api_key);
    assert!(status.has_session);
    assert!(status.has_node_registration);
    assert!(!status.api_key_expired);
    assert!(status.session_valid);

    cleanup_env();
}

#[test]
fn test_vault_status_display() {
    let (_temp_dir, vault) = create_test_vault();

    let status = vault.status();
    let display = format!("{}", status);

    assert!(display.contains("Vault Status:"));
    assert!(display.contains("Agent credentials:"));
    assert!(display.contains("API key:"));
    assert!(display.contains("Session:"));
}

// =============================================================================
// Edge Cases and Error Handling
// =============================================================================

#[test]
fn test_load_missing_credentials() {
    let (_temp_dir, vault) = create_test_vault();

    let result = vault.load_agent_credentials().expect("Should not error");
    assert!(result.is_none());
}

#[test]
fn test_delete_missing_file() {
    let (_temp_dir, vault) = create_test_vault();

    // Should not error when deleting non-existent files
    vault.delete_agent_credentials().expect("Should not error");
    vault.delete_api_key().expect("Should not error");
    vault.delete_session().expect("Should not error");
    vault.delete_node_registration().expect("Should not error");
}

#[test]
fn test_vault_base_path() {
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let vault = Vault::new(temp_dir.path());

    assert_eq!(vault.base_path(), temp_dir.path().to_path_buf());
}

#[test]
fn test_vault_ensure_directory() {
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let vault_path = temp_dir.path().join("new_vault_dir");
    let vault = Vault::new(&vault_path);

    assert!(!vault_path.exists());
    vault.ensure_directory().expect("Should create directory");
    assert!(vault_path.exists());
}

#[test]
fn test_multiple_vault_instances() {
    let temp_dir = TempDir::new().expect("Failed to create temp dir");
    let vault1 = Vault::new(temp_dir.path());
    let vault2 = Vault::new(temp_dir.path());

    // Save with one instance
    vault1
        .save_agent_credentials(&sample_agent_credentials())
        .expect("Save");

    // Load with another instance
    let loaded = vault2
        .load_agent_credentials()
        .expect("Load")
        .expect("Should have creds");

    assert_eq!(loaded.username, "agent-TESTNODE01");
}

#[test]
fn test_api_key_with_invalid_expiry_format() {
    let (_temp_dir, vault) = create_test_vault();

    let api_key = ApiKeyData {
        api_key: "hyk_test".to_string(),
        api_key_id: "key_123".to_string(),
        expires_at: Some("invalid-date-format".to_string()),
        node_id: None,
        stored_at: Utc::now().to_rfc3339(),
    };

    vault.save_api_key(&api_key).expect("Should save");

    // Invalid date format should not cause is_api_key_expired to fail
    // but should return some reasonable default
    let _ = vault.is_api_key_expired();
}

#[test]
fn test_special_characters_in_credentials() {
    let (_temp_dir, vault) = create_test_vault();

    let creds = AgentCredentials {
        user_id: "user_with\"quotes".to_string(),
        username: "agent-with-special$chars".to_string(),
        password: Some("p@ssw0rd!#$%^&*()".to_string()),
        parent_user_id: "user_parent".to_string(),
        created_at: "2024-01-01T00:00:00Z".to_string(),
    };

    vault
        .save_agent_credentials(&creds)
        .expect("Should save with special chars");

    let loaded = vault
        .load_agent_credentials()
        .expect("Should load")
        .expect("Should have creds");

    assert_eq!(loaded.password, creds.password);
}

#[test]
fn test_unicode_in_credentials() {
    let (_temp_dir, vault) = create_test_vault();

    let creds = AgentCredentials {
        user_id: "user_unicode_\u{1F600}".to_string(),
        username: "agent-\u{4E2D}\u{6587}".to_string(),
        password: Some("\u{0420}\u{0443}\u{0441}\u{0441}\u{043A}\u{0438}\u{0439}".to_string()),
        parent_user_id: "user_parent".to_string(),
        created_at: "2024-01-01T00:00:00Z".to_string(),
    };

    vault
        .save_agent_credentials(&creds)
        .expect("Should save unicode");

    let loaded = vault
        .load_agent_credentials()
        .expect("Should load")
        .expect("Should have creds");

    assert_eq!(loaded.username, creds.username);
    assert_eq!(loaded.password, creds.password);
}

// =============================================================================
// Serialization Format Tests
// =============================================================================

#[test]
fn test_credentials_json_format() {
    let creds = sample_agent_credentials();
    let json = serde_json::to_value(&creds).expect("Should serialize");

    // Verify camelCase
    assert!(json.get("userId").is_some());
    assert!(json.get("username").is_some());
    assert!(json.get("password").is_some());
    assert!(json.get("parentUserId").is_some());
    assert!(json.get("createdAt").is_some());

    // Verify NO snake_case
    assert!(json.get("user_id").is_none());
    assert!(json.get("parent_user_id").is_none());
    assert!(json.get("created_at").is_none());
}

#[test]
fn test_api_key_json_format() {
    let api_key = sample_api_key(Some(90));
    let json = serde_json::to_value(&api_key).expect("Should serialize");

    // Verify camelCase
    assert!(json.get("apiKey").is_some());
    assert!(json.get("apiKeyId").is_some());
    assert!(json.get("expiresAt").is_some());
    assert!(json.get("nodeId").is_some());
    assert!(json.get("storedAt").is_some());
}

#[test]
fn test_session_json_format() {
    let session = sample_session(3600);
    let json = serde_json::to_value(&session).expect("Should serialize");

    // Verify camelCase
    assert!(json.get("accessToken").is_some());
    assert!(json.get("refreshToken").is_some());
    assert!(json.get("tokenType").is_some());
    assert!(json.get("expiresAt").is_some());
    assert!(json.get("userId").is_some());
}

#[test]
fn test_node_registration_json_format() {
    let reg = sample_node_registration();
    let json = serde_json::to_value(&reg).expect("Should serialize");

    // Verify camelCase
    assert!(json.get("nodeId").is_some());
    assert!(json.get("registeredAt").is_some());
    assert!(json.get("registeredBy").is_some());
    assert!(json.get("status").is_some());
}
