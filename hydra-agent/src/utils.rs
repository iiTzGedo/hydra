//! Shared utilities, constants, and credential generation for the Hydra agent.

use rand::Rng;

/// Default API key expiry in days (used during registration and login).
pub const API_KEY_DEFAULT_EXPIRY_DAYS: i64 = 90;

/// Days before expiry at which the API key should be renewed automatically.
pub const API_KEY_RENEWAL_THRESHOLD_DAYS: i64 = 7;

/// Generate a random agent username (pattern: agent-XXXXXXXX where X is [0-9A-Z]).
pub fn generate_agent_username() -> String {
    const CHARS: &[u8] = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    let mut rng = rand::thread_rng();
    let suffix: String = (0..8)
        .map(|_| {
            let idx = rng.gen_range(0..CHARS.len());
            CHARS[idx] as char
        })
        .collect();
    format!("agent-{}", suffix)
}

/// Generate a secure random password (32 characters, URL-safe base64).
pub fn generate_agent_password() -> String {
    use rand::RngCore;
    let mut rng = rand::thread_rng();
    let mut bytes = [0u8; 24];
    rng.fill_bytes(&mut bytes);
    base64_encode_urlsafe(&bytes)
}

/// URL-safe base64 encoding without padding.
fn base64_encode_urlsafe(data: &[u8]) -> String {
    const CHARS: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    let mut result = String::with_capacity((data.len() * 4 + 2) / 3);

    for chunk in data.chunks(3) {
        let b0 = chunk[0] as usize;
        let b1 = chunk.get(1).copied().unwrap_or(0) as usize;
        let b2 = chunk.get(2).copied().unwrap_or(0) as usize;

        result.push(CHARS[b0 >> 2] as char);
        result.push(CHARS[((b0 & 0x03) << 4) | (b1 >> 4)] as char);
        if chunk.len() > 1 {
            result.push(CHARS[((b1 & 0x0f) << 2) | (b2 >> 6)] as char);
        }
        if chunk.len() > 2 {
            result.push(CHARS[b2 & 0x3f] as char);
        }
    }
    result
}
