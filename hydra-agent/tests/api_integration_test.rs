//! Integration tests for the API client using wiremock.
//!
//! Tests HTTP communication between the agent and the Hydra API:
//! - Profile submission (success, retry on failure, 401 key refresh)
//! - Login flow
//! - Registration with token
//! - Registration with credentials
//! - Event reporting
//! - Error handling (4xx, 5xx, network errors)

use chrono::{Duration, Utc};
use serde_json::json;
use std::collections::HashMap;
use tempfile::TempDir;
use wiremock::matchers::{body_json, header, method, path};
use wiremock::{Mock, MockServer, ResponseTemplate};

use hydra_agent::api::ApiClient;
use hydra_agent::collectors::Profile;
use hydra_agent::config::{
    AgentConfig, AgentTier, ApiConfig, CollectionConfig, NodeConfig, ScheduleConfig, ServerConfig,
};
use hydra_agent::vault::{AgentCredentials, ApiKeyData, Vault};

// =============================================================================
// Helpers
// =============================================================================

fn create_test_config(api_url: &str) -> AgentConfig {
    AgentConfig {
        api: ApiConfig {
            url: api_url.to_string(),
            timeout_seconds: 5,
            retries: 2,
        },
        node: NodeConfig {
            node_id: "test-node-01".to_string(),
            class: "compute".to_string(),
            tier: AgentTier::Normal,
            node_type: "physical".to_string(),
            kind: Some("bare-metal".to_string()),
            display_name: Some("Test Node 01".to_string()),
            description: Some("Integration test node".to_string()),
            tags: vec!["test".to_string()],
            parent_node_id: None,
        },
        collection: CollectionConfig {
            level: "neutral".to_string(),
            collectors: vec![
                "hardware".to_string(),
                "network".to_string(),
                "storage".to_string(),
                "software".to_string(),
            ],
            include_packages: true,
            include_users: true,
            config_files: vec![],
        },
        schedule: ScheduleConfig {
            enabled: false,
            interval_seconds: 3600,
            on_startup: false,
            poll_interval_seconds: 30,
        },
        server: ServerConfig::default(),
    }
}

fn create_test_vault(temp_dir: &TempDir) -> Vault {
    Vault::new(temp_dir.path())
}

fn seed_vault_with_api_key(vault: &Vault) {
    let api_key = ApiKeyData {
        api_key: "hyk_test_key_abc123".to_string(),
        api_key_id: "key_test_001".to_string(),
        expires_at: Some((Utc::now() + Duration::days(30)).to_rfc3339()),
        node_id: Some("test-node-01".to_string()),
        stored_at: Utc::now().to_rfc3339(),
    };
    vault
        .save_api_key(&api_key)
        .expect("Failed to seed API key");
}

fn seed_vault_with_credentials(vault: &Vault) {
    let creds = AgentCredentials {
        user_id: "user_agent_001".to_string(),
        username: "agent-test-node-01".to_string(),
        password: Some("test_agent_password".to_string()),
        parent_user_id: "user_admin_001".to_string(),
        created_at: "2024-01-01T00:00:00Z".to_string(),
    };
    vault
        .save_agent_credentials(&creds)
        .expect("Failed to seed credentials");
}

fn build_client(server: &MockServer, temp_dir: &TempDir) -> (ApiClient, Vault) {
    let config = create_test_config(&server.uri());
    build_client_with_config(config, temp_dir)
}

fn build_client_with_config(config: AgentConfig, temp_dir: &TempDir) -> (ApiClient, Vault) {
    let vault = create_test_vault(temp_dir);
    let client = ApiClient::new(&config, &vault).expect("Failed to create API client");
    (client, vault)
}

fn empty_profile() -> Profile {
    Profile {
        node_id: "test-node-01".to_string(),
        version: String::new(),
        collected_at: Utc::now(),
        agent_version: "0.1.0".to_string(),
        agent_tier: "normal".to_string(),
        collection_level: "neutral".to_string(),
        hardware: None,
        network: None,
        storage: None,
        software: None,
        metadata: HashMap::new(),
    }
}

// =============================================================================
// Profile Submission Tests
// =============================================================================

#[tokio::test]
async fn test_submit_profile_success() {
    let server = MockServer::start().await;
    let temp_dir = TempDir::new().unwrap();
    let (client, vault) = build_client(&server, &temp_dir);
    seed_vault_with_api_key(&vault);

    Mock::given(method("POST"))
        .and(path("/profiles"))
        .and(header("X-API-Key", "hyk_test_key_abc123"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "data": {
                "profileId": "prof_test_001",
                "version": "E0-0.0.0.1"
            }
        })))
        .expect(1)
        .mount(&server)
        .await;

    let profile = empty_profile();
    let result = client.submit_profile(&profile).await;
    assert!(result.is_ok());
    let response = result.unwrap();
    assert_eq!(response.profile_id, "prof_test_001");
    assert_eq!(response.version, "E0-0.0.0.1");
}

#[tokio::test]
async fn test_submit_profile_retries_on_server_error() {
    let server = MockServer::start().await;
    let temp_dir = TempDir::new().unwrap();
    let (client, vault) = build_client(&server, &temp_dir);
    seed_vault_with_api_key(&vault);

    // First request fails with 500, second succeeds
    Mock::given(method("POST"))
        .and(path("/profiles"))
        .respond_with(ResponseTemplate::new(500).set_body_json(json!({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Temporary failure"
            }
        })))
        .up_to_n_times(1)
        .expect(1)
        .mount(&server)
        .await;

    Mock::given(method("POST"))
        .and(path("/profiles"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "data": {
                "profileId": "prof_retry_001",
                "version": "E0-0.0.0.1"
            }
        })))
        .expect(1)
        .mount(&server)
        .await;

    let profile = empty_profile();
    let result = client.submit_profile(&profile).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_submit_profile_401_refreshes_api_key() {
    let server = MockServer::start().await;
    let temp_dir = TempDir::new().unwrap();
    let (client, vault) = build_client(&server, &temp_dir);
    seed_vault_with_api_key(&vault);
    seed_vault_with_credentials(&vault);

    // First profile request returns 401
    Mock::given(method("POST"))
        .and(path("/profiles"))
        .and(header("X-API-Key", "hyk_test_key_abc123"))
        .respond_with(ResponseTemplate::new(401).set_body_json(json!({
            "error": {
                "code": "UNAUTHORIZED",
                "message": "API key expired"
            }
        })))
        .up_to_n_times(1)
        .expect(1)
        .mount(&server)
        .await;

    // Login for key refresh
    Mock::given(method("POST"))
        .and(path("/auth/login"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "accessToken": "jwt_refreshed_token",
            "refreshToken": "refresh_token",
            "tokenType": "Bearer",
            "expiresIn": 3600
        })))
        .expect(1)
        .mount(&server)
        .await;

    // API key creation
    Mock::given(method("POST"))
        .and(path("/auth/apikeys"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "keyId": "key_new_001",
            "key": "hyk_refreshed_key_xyz",
            "name": "hydra-agent-test-node-01",
            "expiresAt": (Utc::now() + Duration::days(90)).to_rfc3339(),
            "createdAt": Utc::now().to_rfc3339()
        })))
        .expect(1)
        .mount(&server)
        .await;

    // Retry with new key succeeds
    Mock::given(method("POST"))
        .and(path("/profiles"))
        .and(header("X-API-Key", "hyk_refreshed_key_xyz"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "data": {
                "profileId": "prof_after_refresh",
                "version": "E0-0.0.0.1"
            }
        })))
        .expect(1)
        .mount(&server)
        .await;

    let profile = empty_profile();
    let result = client.submit_profile(&profile).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_submit_profile_fails_after_all_retries() {
    let server = MockServer::start().await;
    let temp_dir = TempDir::new().unwrap();
    let config = create_test_config(&server.uri());
    let vault = create_test_vault(&temp_dir);
    seed_vault_with_api_key(&vault);
    let client = ApiClient::new(&config, &vault).unwrap();

    // All requests fail
    Mock::given(method("POST"))
        .and(path("/profiles"))
        .respond_with(ResponseTemplate::new(500).set_body_json(json!({
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Server unavailable"
            }
        })))
        .expect(2) // matches retries config
        .mount(&server)
        .await;

    let profile = empty_profile();
    let result = client.submit_profile(&profile).await;
    assert!(result.is_err());
    assert!(result
        .unwrap_err()
        .to_string()
        .contains("Server unavailable"));
}

// =============================================================================
// Event Reporting Tests
// =============================================================================

#[tokio::test]
async fn test_report_event_success() {
    let server = MockServer::start().await;
    let temp_dir = TempDir::new().unwrap();
    let (client, vault) = build_client(&server, &temp_dir);
    seed_vault_with_api_key(&vault);

    Mock::given(method("POST"))
        .and(path("/agent/report"))
        .and(header("X-API-Key", "hyk_test_key_abc123"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "status": "accepted"
        })))
        .expect(1)
        .mount(&server)
        .await;

    let result = client
        .report_event(
            "profile_submitted",
            "Profile collected",
            "Profile E0-0.0.0.1 submitted successfully",
            Some(json!({"nodeId": "test-node-01", "version": "E0-0.0.0.1"})),
        )
        .await;

    assert!(result.is_ok());
}

#[tokio::test]
async fn test_report_event_graceful_on_failure() {
    let server = MockServer::start().await;
    let temp_dir = TempDir::new().unwrap();
    let (client, vault) = build_client(&server, &temp_dir);
    seed_vault_with_api_key(&vault);

    Mock::given(method("POST"))
        .and(path("/agent/report"))
        .respond_with(ResponseTemplate::new(500))
        .expect(1)
        .mount(&server)
        .await;

    // report_event is best-effort - should not propagate errors
    let result = client
        .report_event("test_event", "Test", "Should not fail", None)
        .await;

    assert!(result.is_ok());
}

#[tokio::test]
async fn test_report_event_skips_when_no_api_key() {
    let server = MockServer::start().await;
    let temp_dir = TempDir::new().unwrap();
    let (client, _vault) = build_client(&server, &temp_dir);
    // Don't seed API key or credentials

    // No HTTP request should be made
    Mock::given(method("POST"))
        .and(path("/agent/report"))
        .respond_with(ResponseTemplate::new(200))
        .expect(0)
        .mount(&server)
        .await;

    let result = client.report_event("test", "Test", "No key", None).await;

    assert!(result.is_ok());
}

// =============================================================================
// Registration Tests
// =============================================================================

#[tokio::test]
async fn test_register_with_token_success() {
    let server = MockServer::start().await;
    let temp_dir = TempDir::new().unwrap();
    let (client, _vault) = build_client(&server, &temp_dir);

    // Agent registration
    Mock::given(method("POST"))
        .and(path("/auth/register"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "userId": "user_agent_new",
            "username": "agent-test-node-01",
            "parentUserId": "user_admin_001",
            "role": "agent",
            "createdAt": Utc::now().to_rfc3339()
        })))
        .expect(1)
        .mount(&server)
        .await;

    // Agent login
    Mock::given(method("POST"))
        .and(path("/auth/login"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "accessToken": "jwt_agent_token",
            "refreshToken": "refresh_token",
            "tokenType": "Bearer",
            "expiresIn": 3600
        })))
        .expect(1)
        .mount(&server)
        .await;

    // API key creation
    Mock::given(method("POST"))
        .and(path("/auth/apikeys"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "keyId": "key_new_001",
            "key": "hyk_new_agent_key",
            "name": "agent-test-api-key",
            "expiresAt": (Utc::now() + Duration::days(90)).to_rfc3339(),
            "createdAt": Utc::now().to_rfc3339()
        })))
        .expect(1)
        .mount(&server)
        .await;

    // Node registration
    Mock::given(method("POST"))
        .and(path("/nodes/register"))
        .and(header("X-API-Key", "hyk_new_agent_key"))
        .and(body_json(json!({
            "nodeId": "test-node-01",
            "class": "compute",
            "type": "physical",
            "agentTier": "normal",
            "kind": "bare-metal",
            "displayName": "Test Node 01",
            "description": "Integration test node",
            "tags": ["test"]
        })))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "nodeId": "test-node-01",
            "apiKey": "hyk_node_key",
            "apiKeyId": "key_node_001",
            "registeredBy": "user_agent_new",
            "registeredAt": Utc::now().to_rfc3339(),
            "status": "active"
        })))
        .expect(1)
        .mount(&server)
        .await;

    let result = client.register_with_token("reg_test_token_123").await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_register_with_token_max_tier_publishes_server_metadata_and_stores_secret() {
    let server = MockServer::start().await;
    let temp_dir = TempDir::new().unwrap();
    let mut config = create_test_config(&server.uri());
    config.node.tier = AgentTier::Max;
    config.server.enabled = true;
    config.server.bind_address = "0.0.0.0".to_string();
    config.server.advertise_address = Some("192.168.1.10".to_string());
    config.server.port = 9100;
    config.server.tls_enabled = true;
    let (client, vault) = build_client_with_config(config, &temp_dir);

    Mock::given(method("POST"))
        .and(path("/auth/register"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "userId": "user_agent_new",
            "username": "agent-test-node-01",
            "parentUserId": "user_admin_001",
            "role": "agent",
            "createdAt": Utc::now().to_rfc3339()
        })))
        .expect(1)
        .mount(&server)
        .await;

    Mock::given(method("POST"))
        .and(path("/auth/login"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "accessToken": "jwt_agent_token",
            "refreshToken": "refresh_token",
            "tokenType": "Bearer",
            "expiresIn": 3600
        })))
        .expect(1)
        .mount(&server)
        .await;

    Mock::given(method("POST"))
        .and(path("/auth/apikeys"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "keyId": "key_new_001",
            "key": "hyk_new_agent_key",
            "name": "agent-test-api-key",
            "expiresAt": (Utc::now() + Duration::days(90)).to_rfc3339(),
            "createdAt": Utc::now().to_rfc3339()
        })))
        .expect(1)
        .mount(&server)
        .await;

    Mock::given(method("POST"))
        .and(path("/nodes/register"))
        .and(header("X-API-Key", "hyk_new_agent_key"))
        .and(body_json(json!({
            "nodeId": "test-node-01",
            "class": "compute",
            "type": "physical",
            "agentTier": "max",
            "kind": "bare-metal",
            "displayName": "Test Node 01",
            "description": "Integration test node",
            "tags": ["test"],
            "serverAddress": "192.168.1.10",
            "serverPort": 9100,
            "serverTlsEnabled": true
        })))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "nodeId": "test-node-01",
            "apiKey": "hyk_node_key",
            "apiKeyId": "key_node_001",
            "registeredBy": "user_agent_new",
            "registeredAt": Utc::now().to_rfc3339(),
            "status": "active",
            "agentServerSecret": "hsk_api_secret_123"
        })))
        .expect(1)
        .mount(&server)
        .await;

    let result = client.register_with_token("reg_test_token_123").await;
    assert!(result.is_ok());

    let server_secret = vault.load_server_secret().unwrap().unwrap();
    assert_eq!(server_secret.secret, "hsk_api_secret_123");
}

#[tokio::test]
async fn test_register_with_token_agent_registration_fails() {
    let server = MockServer::start().await;
    let temp_dir = TempDir::new().unwrap();
    let (client, _vault) = build_client(&server, &temp_dir);

    // Agent registration fails
    Mock::given(method("POST"))
        .and(path("/auth/register"))
        .respond_with(ResponseTemplate::new(400).set_body_json(json!({
            "error": {
                "code": "INVALID_TOKEN",
                "message": "Registration token is invalid or expired"
            }
        })))
        .expect(1)
        .mount(&server)
        .await;

    // report_event may be called (best-effort, no API key yet so it'll skip)
    Mock::given(method("POST"))
        .and(path("/agent/report"))
        .respond_with(ResponseTemplate::new(200))
        .mount(&server)
        .await;

    let result = client.register_with_token("invalid_token").await;
    assert!(result.is_err());
    assert!(result.unwrap_err().to_string().contains("INVALID_TOKEN"));
}

#[tokio::test]
async fn test_register_with_credentials_success() {
    let server = MockServer::start().await;
    let temp_dir = TempDir::new().unwrap();
    let (client, _vault) = build_client(&server, &temp_dir);

    // User login
    Mock::given(method("POST"))
        .and(path("/auth/login"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "accessToken": "jwt_user_token",
            "refreshToken": "refresh_user",
            "tokenType": "Bearer",
            "expiresIn": 3600
        })))
        .mount(&server)
        .await;

    // Agent registration
    Mock::given(method("POST"))
        .and(path("/auth/register"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "userId": "user_agent_cred",
            "username": "agent-cred-node",
            "parentUserId": "user_admin_001",
            "role": "agent",
            "createdAt": Utc::now().to_rfc3339()
        })))
        .expect(1)
        .mount(&server)
        .await;

    // API key creation
    Mock::given(method("POST"))
        .and(path("/auth/apikeys"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "keyId": "key_cred_001",
            "key": "hyk_cred_key",
            "name": "agent-cred-api-key",
            "expiresAt": (Utc::now() + Duration::days(90)).to_rfc3339(),
            "createdAt": Utc::now().to_rfc3339()
        })))
        .expect(1)
        .mount(&server)
        .await;

    // Node registration
    Mock::given(method("POST"))
        .and(path("/nodes/register"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "nodeId": "test-node-01",
            "apiKey": "hyk_node_key",
            "apiKeyId": "key_node_001",
            "registeredBy": "user_agent_cred",
            "registeredAt": Utc::now().to_rfc3339(),
            "status": "active"
        })))
        .expect(1)
        .mount(&server)
        .await;

    let result = client
        .register_with_credentials("admin", "admin_password")
        .await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_poll_commands_and_submit_result_use_typed_contract() {
    let server = MockServer::start().await;
    let temp_dir = TempDir::new().unwrap();
    let (client, vault) = build_client(&server, &temp_dir);
    seed_vault_with_api_key(&vault);

    Mock::given(method("GET"))
        .and(path("/nodes/test-node-01/commands/poll"))
        .and(header("X-API-Key", "hyk_test_key_abc123"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "data": {
                "commands": [
                    {
                        "commandId": "cmd-typed-001",
                        "type": "system",
                        "action": "run",
                        "target": {
                            "nodeId": "test-node-01",
                            "serviceId": null
                        },
                        "parameters": {
                            "command": "uptime"
                        },
                        "timeoutSeconds": 30
                    }
                ]
            }
        })))
        .expect(1)
        .mount(&server)
        .await;

    let commands = client.poll_commands("test-node-01").await.unwrap();
    assert_eq!(commands.len(), 1);
    assert_eq!(commands[0].target.node_id, "test-node-01");
    assert!(commands[0].target.service_id.is_none());
    assert_eq!(commands[0].timeout_seconds, 30);

    Mock::given(method("POST"))
        .and(path("/nodes/test-node-01/commands/cmd-typed-001/result"))
        .and(header("X-API-Key", "hyk_test_key_abc123"))
        .and(body_json(json!({
            "success": false,
            "output": null,
            "exitCode": null,
            "error": "Command execution engine not yet available (requires P2B)"
        })))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "data": {
                "commandId": "cmd-typed-001",
                "status": "failed",
                "completedAt": Utc::now().to_rfc3339()
            }
        })))
        .expect(1)
        .mount(&server)
        .await;

    client
        .submit_command_result(
            "test-node-01",
            "cmd-typed-001",
            &hydra_agent::api::CommandResultPayload {
                success: false,
                output: None,
                exit_code: None,
                error: Some(
                    "Command execution engine not yet available (requires P2B)".to_string(),
                ),
            },
        )
        .await
        .unwrap();
}

#[tokio::test]
async fn test_register_with_credentials_login_fails() {
    let server = MockServer::start().await;
    let temp_dir = TempDir::new().unwrap();
    let (client, _vault) = build_client(&server, &temp_dir);

    Mock::given(method("POST"))
        .and(path("/auth/login"))
        .respond_with(ResponseTemplate::new(401).set_body_json(json!({
            "error": {
                "code": "INVALID_CREDENTIALS",
                "message": "Invalid username or password"
            }
        })))
        .expect(1)
        .mount(&server)
        .await;

    let result = client
        .register_with_credentials("wrong_user", "wrong_pass")
        .await;
    assert!(result.is_err());
    assert!(result
        .unwrap_err()
        .to_string()
        .contains("INVALID_CREDENTIALS"));
}

// =============================================================================
// API Key Management Tests
// =============================================================================

#[tokio::test]
async fn test_submit_profile_no_api_key_fails() {
    let server = MockServer::start().await;
    let temp_dir = TempDir::new().unwrap();
    let (client, _vault) = build_client(&server, &temp_dir);
    // Don't seed API key or credentials

    let profile = empty_profile();
    let result = client.submit_profile(&profile).await;
    assert!(result.is_err());
}
