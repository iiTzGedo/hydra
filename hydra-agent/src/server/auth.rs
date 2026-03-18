//! Bearer token authentication middleware for the control server.
//!
//! All endpoints require a valid `Authorization: Bearer <secret>` header.
//! The secret is compared using constant-time equality to prevent timing attacks.

use axum::{
    body::Body,
    extract::State,
    http::{Request, StatusCode},
    middleware::Next,
    response::{IntoResponse, Response},
    Json,
};
use subtle::ConstantTimeEq;

use super::models::ErrorResponse;
use super::state::AppState;

/// Middleware that validates the Bearer token against the server secret.
pub async fn auth_middleware(
    State(state): State<AppState>,
    request: Request<Body>,
    next: Next,
) -> Response {
    let auth_header = request
        .headers()
        .get("authorization")
        .and_then(|v| v.to_str().ok());

    let token = match auth_header {
        Some(header) if header.starts_with("Bearer ") => &header[7..],
        _ => {
            return (
                StatusCode::UNAUTHORIZED,
                Json(ErrorResponse::new(
                    "UNAUTHORIZED",
                    "Missing or malformed Authorization header",
                )),
            )
                .into_response();
        }
    };

    // Constant-time comparison to prevent timing attacks
    let expected = state.server_secret.as_bytes();
    let provided = token.as_bytes();

    if expected.len() != provided.len() || expected.ct_eq(provided).unwrap_u8() != 1 {
        return (
            StatusCode::UNAUTHORIZED,
            Json(ErrorResponse::new("UNAUTHORIZED", "Invalid server secret")),
        )
            .into_response();
    }

    next.run(request).await
}
