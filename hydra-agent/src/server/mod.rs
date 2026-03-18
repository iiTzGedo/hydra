//! Embedded HTTP control server for max-tier agents.
//!
//! When enabled, the server accepts authenticated requests from the Hydra API
//! for synchronous command execution, health checks, network probing,
//! configuration updates, and agent upgrades.
//!
//! All endpoints require a valid `Authorization: Bearer <secret>` header.

pub mod auth;
pub mod handlers;
pub mod models;
pub mod state;

use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;
use std::time::Instant;

use anyhow::{anyhow, Context, Result};
use axum::{middleware, routing, Router};
use tokio::sync::RwLock;
use tower_http::trace::TraceLayer;
use tracing::info;

use crate::config::AgentConfig;
use crate::vault::Vault;
use state::AppState;

fn ensure_tls_crypto_provider() {
    let _ = rustls::crypto::aws_lc_rs::default_provider().install_default();
}

/// Create the axum router with all control endpoints and auth middleware.
fn create_router(state: AppState) -> Router {
    Router::new()
        .route("/health", routing::get(handlers::health))
        .route("/execute", routing::post(handlers::execute))
        .route("/probe", routing::post(handlers::probe))
        .route("/config", routing::post(handlers::config_update))
        .route("/update", routing::post(handlers::update))
        .layer(middleware::from_fn_with_state(
            state.clone(),
            auth::auth_middleware,
        ))
        .layer(TraceLayer::new_for_http())
        .with_state(state)
}

/// Build the AppState from config and vault.
pub fn build_app_state(
    config: AgentConfig,
    config_path: PathBuf,
    vault: &Vault,
) -> Result<AppState> {
    let secret_data = vault.load_server_secret()?.ok_or_else(|| {
        anyhow!(
            "Max-tier agent requires a server secret. \
                 Re-register the node to receive a server secret from the API."
        )
    })?;

    Ok(AppState {
        config: Arc::new(RwLock::new(config)),
        config_path,
        server_secret: secret_data.secret,
        start_time: Instant::now(),
    })
}

/// Start the embedded control server (plain TCP or TLS).
///
/// This function blocks until the server is shut down via the provided
/// shutdown future. Call it from `tokio::spawn()` to run concurrently
/// with the collection loop.
pub async fn start_server(
    state: AppState,
    shutdown: impl std::future::Future<Output = ()> + Send + 'static,
) -> Result<()> {
    let config = state.config.read().await;
    let addr: SocketAddr = format!("{}:{}", config.server.bind_address, config.server.port)
        .parse()
        .with_context(|| {
            format!(
                "Invalid server address: {}:{}",
                config.server.bind_address, config.server.port
            )
        })?;
    let tls_enabled = config.server.tls_enabled;
    let tls_cert = config.server.tls_cert_file.clone();
    let tls_key = config.server.tls_key_file.clone();
    drop(config);

    let app = create_router(state);

    if tls_enabled {
        ensure_tls_crypto_provider();

        let cert_path = tls_cert
            .as_deref()
            .ok_or_else(|| anyhow!("TLS cert path is required when TLS is enabled"))?;
        let key_path = tls_key
            .as_deref()
            .ok_or_else(|| anyhow!("TLS key path is required when TLS is enabled"))?;

        let tls_config = axum_server::tls_rustls::RustlsConfig::from_pem_file(cert_path, key_path)
            .await
            .with_context(|| {
                format!(
                    "Failed to load TLS config from {} / {}",
                    cert_path, key_path
                )
            })?;

        info!(%addr, "Control server starting (TLS enabled)");

        let handle = axum_server::Handle::new();
        let shutdown_handle = handle.clone();
        tokio::spawn(async move {
            shutdown.await;
            shutdown_handle.graceful_shutdown(Some(Duration::from_secs(5)));
        });

        axum_server::bind_rustls(addr, tls_config)
            .handle(handle)
            .serve(app.into_make_service())
            .await?;
    } else {
        info!(%addr, "Control server starting (TLS disabled — development mode)");

        let listener = tokio::net::TcpListener::bind(addr).await?;
        axum::serve(listener, app)
            .with_graceful_shutdown(shutdown)
            .await?;
    }

    info!("Control server shut down");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{
        AgentConfig, AgentTier, ApiConfig, CollectionConfig, NodeConfig, ScheduleConfig,
        ServerConfig,
    };
    use tempfile::TempDir;
    use tokio::time::{timeout, Duration};

    const TEST_CERT: &str = r#"-----BEGIN CERTIFICATE-----
MIIDCTCCAfGgAwIBAgIUTxzv5GSDI4q7kBpiV7Qa7QSJYU0wDQYJKoZIhvcNAQEL
BQAwFDESMBAGA1UEAwwJbG9jYWxob3N0MB4XDTI2MDMxNzIzMjc0OVoXDTI2MDMx
ODIzMjc0OVowFDESMBAGA1UEAwwJbG9jYWxob3N0MIIBIjANBgkqhkiG9w0BAQEF
AAOCAQ8AMIIBCgKCAQEAw0za6dlNTVVUHYgJFAq8ZwZyFP7g8J35pd3V+WzfqnoY
Gmitl5sTWq9jq+yGEpzdN7hV1l9akd4o7tiOW1274VHORYaZ5nWUMIdw21L7dTjd
aeF1/1pMVXuTTnbHfBXmbhS/a4RoCmWgu/OHH9wLRShGJwMqE+ErDk0SlrEQFYfv
Z3/rnujkPe74kXeGo6r0Wt9J29yMJvjXSYECzGvG39IVk0BVKplpV1Ib6sRguqeo
/V/qbLw1BJQyBW1hedh9UAPmYCfJEpAM+gREynsG/J220X2oZqPOUHGQzBYJeF6Z
hBMjAmTXQ5Qrpwdz0SemOvpJb4nVlys+sIEnKdPeEwIDAQABo1MwUTAdBgNVHQ4E
FgQUEmeVWPBdpMQ8a051h8uoUYU9ZkowHwYDVR0jBBgwFoAUEmeVWPBdpMQ8a051
h8uoUYU9ZkowDwYDVR0TAQH/BAUwAwEB/zANBgkqhkiG9w0BAQsFAAOCAQEAaPft
xWLF1flsclnY5bWpxnkVgJng0hTrZ0/x++OBoF0/97b59ai/smNdbrTEx/vd66vj
wGF3/gxCSrvcNiNY3ekhHhSYtHSwE31kCrFZC2bKaICWVIlLIlppnHrrS9L3+ynN
E+WwFyInu9mET3lZWGrUesynkyqetCYvvzv7eQM1uiqiDJ/TNIM2p6+w1ZqCLcto
mNw80X48srwc5J+adsMBHQ/bmAInbvTDN3bQoIWxl+L+T3R9J9d6XNQeiw25LH+8
dEupZf2C/1EGTaTvX3WDHzmcz/OmUlkTz8UQHP2Fsl2at8AHCajENzxrK1paDH0R
gP99BfqqGWfUDJw8qA==
-----END CERTIFICATE-----
"#;
    const TEST_KEY: &str = r#"-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDDTNrp2U1NVVQd
iAkUCrxnBnIU/uDwnfml3dX5bN+qehgaaK2XmxNar2Or7IYSnN03uFXWX1qR3iju
2I5bXbvhUc5FhpnmdZQwh3DbUvt1ON1p4XX/WkxVe5NOdsd8FeZuFL9rhGgKZaC7
84cf3AtFKEYnAyoT4SsOTRKWsRAVh+9nf+ue6OQ97viRd4ajqvRa30nb3Iwm+NdJ
gQLMa8bf0hWTQFUqmWlXUhvqxGC6p6j9X+psvDUElDIFbWF52H1QA+ZgJ8kSkAz6
BETKewb8nbbRfahmo85QcZDMFgl4XpmEEyMCZNdDlCunB3PRJ6Y6+klvidWXKz6w
gScp094TAgMBAAECggEAAjwD+nfRUpGyPuqg5xiw453W22HTywKVa7r2GLRSenWf
om7MAHThq7mXAidiv0CUW1sIlHzmhzYrrCcHslu/dCNVYr6FoXyyaKrB3r199Y5F
MBObZRwPgRXKBehA2xuxQJqFTPMLUlWCTT8COTksKooz7ylpfCDnS+Ftsu+Bx8qr
C11U4iXAa6wszmD/E3amfMgvNguhEtAw3/EpJFeOD7k8kvs6s566o/NZL7hetec9
dAiZ93/pEjR6KGSBWKFXrCYhUSMl0eMeX6Jv7anlpNWKCG0fdKFE0Wm8weuTOxJg
7YIRTzodAU7Q5czw97KwuYDzaAwMHQuhb2SiYIQekQKBgQDqEu1FNOv2i4KZX48z
Ro0iJ15ZWJheiVa+NnaU/wiZ4tC9z5pOPfFqQ19++h9bB9uE9zh80nl2e6Gz3HYG
pP43jzzEY90GGI45X3E3ZO0nQLPVnL37RlfKpLUqRqPN6SAHQH8OsUJFYl32piWJ
hgWH8kN7LXVUCEer2hWOez8ROQKBgQDVmCNH9pyAGqhMWQRHBr9r6e8GzUeZETN5
TM/CVu9vaiYDUoMUbf1+Nrrsk/xAOk/J143+BCSF4BI2luX8Rs73hSlUhpofvQ1t
ychX0cK+jR9tLBFaT2olbq5vsxxM3vvf7x7GwqDFCCq9p/AOooF9B+i4dELwj8d1
kaRg0odFqwKBgQDILAlmjrxfqay01qiSk/nrxDkGNSKQbeiVX+QGxRao6vPR7rCp
yoUid5057FJWOaD706Ml86RVs6J0OstgIUcZYk/4LuJ77RHrdHhQg+nfEJD500IQ
mXZIYJRhI+m/FGcEbJ57hREEXvu2Cx28vrUKLh6RPy3AABiymRyoLTOg2QKBgFRt
k5yRdWEJqHatRQySNT4BtRK6N8/gRblvzDukQ3aFvcrYZanApE+scIytHiuBISLG
ioDawFkOrgRX90aV8p9SSnj3z5o2D0XTWdakula5z69GmQFanLl5G4hZgxk7ltH4
YfDs48GeLc7TwAb44zg51Rp8Ei2ml4/4ZsJC1WeLAoGBAKvcPYYzMbKZmrbBXHuH
xLsNYFSNBTovTjoLfiqjDzFhxMCVHWAdpddP8/LJWERVauoQ8Z0BVnqK1zItRYtT
Z/BPQFKZgJEWippfDtIQPht9iT3UjlelhXq7h+7s77Z/qst3jU7lCkqhDUW1myjH
ak58eJJ5Ro104TSDawOK1p40
-----END PRIVATE KEY-----
"#;

    #[tokio::test]
    async fn test_tls_server_honors_shutdown_signal() {
        let temp_dir = TempDir::new().unwrap();
        let cert_path = temp_dir.path().join("cert.pem");
        let key_path = temp_dir.path().join("key.pem");
        let config_path = temp_dir.path().join("agent.toml");
        std::fs::write(&cert_path, TEST_CERT).unwrap();
        std::fs::write(&key_path, TEST_KEY).unwrap();
        std::fs::write(
            &config_path,
            "[api]\nurl = \"http://localhost:8080/api/v1\"\n[node]\nnode_id = \"testnode\"\n",
        )
        .unwrap();

        let config = AgentConfig {
            api: ApiConfig {
                url: "http://localhost:8080/api/v1".to_string(),
                timeout_seconds: 30,
                retries: 3,
            },
            node: NodeConfig {
                node_id: "testnode".to_string(),
                class: "compute".to_string(),
                tier: AgentTier::Max,
                node_type: "physical".to_string(),
                kind: None,
                display_name: Some("Test Node".to_string()),
                description: None,
                tags: vec![],
                parent_node_id: None,
            },
            collection: CollectionConfig::default(),
            schedule: ScheduleConfig::default(),
            server: ServerConfig {
                enabled: true,
                bind_address: "127.0.0.1".to_string(),
                advertise_address: Some("127.0.0.1".to_string()),
                port: 0,
                tls_enabled: true,
                tls_cert_file: Some(cert_path.display().to_string()),
                tls_key_file: Some(key_path.display().to_string()),
            },
        };

        let state = AppState {
            config: Arc::new(RwLock::new(config)),
            config_path,
            server_secret: "test-secret".to_string(),
            start_time: Instant::now(),
        };

        let result = timeout(
            Duration::from_secs(5),
            start_server(state, async {
                tokio::time::sleep(Duration::from_millis(100)).await;
            }),
        )
        .await;

        assert!(result.is_ok(), "TLS server did not shut down in time");
        assert!(result.unwrap().is_ok(), "TLS server returned an error");
    }
}
