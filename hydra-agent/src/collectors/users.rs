//! User account and SSH key collector.
//!
//! Produces the top-level `users` profile section the API expects
//! (`UsersProfile` with `users` and `sshKeys`). Enumerates real (non-service)
//! local accounts and computes SHA256 fingerprints for SSH host keys and each
//! account's `authorized_keys`. Only public-key fingerprints are recorded —
//! never private keys or key material.

use serde::Serialize;
use sha2::{Digest, Sha256};
use tracing::debug;

/// Local user account information (matches the API `UserInfo` model).
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct UserInfo {
    /// Account name.
    pub username: String,
    /// User ID (Unix).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub uid: Option<u32>,
    /// Primary group ID (Unix).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gid: Option<u32>,
    /// Home directory.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub home: Option<String>,
    /// Login shell.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub shell: Option<String>,
    /// Group names the account belongs to.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub groups: Vec<String>,
}

/// SSH public key fingerprint (matches the API `SshKey` model).
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SshKey {
    /// Account the key is associated with, or "(host)" for host keys.
    pub username: String,
    /// Key algorithm, e.g. `ssh-ed25519`.
    pub key_type: String,
    /// `SHA256:...` fingerprint of the public key.
    pub fingerprint: String,
    /// Optional key comment.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub comment: Option<String>,
}

/// Users profile section.
#[derive(Debug, Clone, Serialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct UsersProfile {
    /// Enumerated local accounts.
    pub users: Vec<UserInfo>,
    /// SSH public-key fingerprints (host keys + per-account authorized_keys).
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub ssh_keys: Vec<SshKey>,
}

/// Collector for local user accounts and SSH key fingerprints.
pub struct UsersCollector;

impl UsersCollector {
    /// Collect the users section. Returns an empty section (rather than failing)
    /// when enumeration is unavailable on the platform.
    pub fn collect() -> UsersProfile {
        let users = Self::collect_users();
        let ssh_keys = Self::collect_ssh_keys(&users);
        UsersProfile { users, ssh_keys }
    }

    #[cfg(unix)]
    fn collect_users() -> Vec<UserInfo> {
        let passwd = match std::fs::read_to_string("/etc/passwd") {
            Ok(contents) => contents,
            Err(e) => {
                debug!(error = %e, "could not read /etc/passwd; users section empty");
                return Vec::new();
            }
        };
        let gid_names = Self::group_names_by_gid();
        let member_groups = Self::supplementary_groups();

        let mut users = Vec::new();
        for line in passwd.lines() {
            let fields: Vec<&str> = line.split(':').collect();
            if fields.len() < 7 {
                continue;
            }
            let username = fields[0].to_string();
            let uid: Option<u32> = fields[2].parse().ok();
            let gid: Option<u32> = fields[3].parse().ok();
            let home = Some(fields[5].to_string()).filter(|s| !s.is_empty());
            let shell = Some(fields[6].to_string()).filter(|s| !s.is_empty());

            // Keep real login accounts: root plus UID >= 1000 with a login shell.
            let is_real = uid == Some(0)
                || (uid.map(|u| u >= 1000).unwrap_or(false)
                    && shell.as_deref().map(is_login_shell).unwrap_or(false));
            if !is_real {
                continue;
            }

            let mut groups = Vec::new();
            if let Some(g) = gid.and_then(|g| gid_names.get(&g)) {
                groups.push(g.clone());
            }
            if let Some(extra) = member_groups.get(&username) {
                for g in extra {
                    if !groups.contains(g) {
                        groups.push(g.clone());
                    }
                }
            }

            users.push(UserInfo {
                username,
                uid,
                gid,
                home,
                shell,
                groups,
            });
        }
        users
    }

    /// Map primary GID -> group name from /etc/group.
    #[cfg(unix)]
    fn group_names_by_gid() -> std::collections::HashMap<u32, String> {
        let mut map = std::collections::HashMap::new();
        if let Ok(group) = std::fs::read_to_string("/etc/group") {
            for line in group.lines() {
                let f: Vec<&str> = line.split(':').collect();
                if f.len() >= 3 {
                    if let Ok(gid) = f[2].parse::<u32>() {
                        map.insert(gid, f[0].to_string());
                    }
                }
            }
        }
        map
    }

    /// Map username -> supplementary group names from /etc/group membership lists.
    #[cfg(unix)]
    fn supplementary_groups() -> std::collections::HashMap<String, Vec<String>> {
        let mut map: std::collections::HashMap<String, Vec<String>> = std::collections::HashMap::new();
        if let Ok(group) = std::fs::read_to_string("/etc/group") {
            for line in group.lines() {
                let f: Vec<&str> = line.split(':').collect();
                if f.len() >= 4 && !f[3].is_empty() {
                    let group_name = f[0].to_string();
                    for member in f[3].split(',') {
                        map.entry(member.to_string())
                            .or_default()
                            .push(group_name.clone());
                    }
                }
            }
        }
        map
    }

    #[cfg(windows)]
    fn collect_users() -> Vec<UserInfo> {
        use std::process::Command;
        let output = Command::new("powershell")
            .args([
                "-NoProfile",
                "-Command",
                "Get-LocalUser | Where-Object { $_.Enabled } | ForEach-Object { $_.Name }",
            ])
            .output();
        match output {
            Ok(out) if out.status.success() => String::from_utf8_lossy(&out.stdout)
                .lines()
                .map(|l| l.trim())
                .filter(|l| !l.is_empty())
                .map(|name| UserInfo {
                    username: name.to_string(),
                    uid: None,
                    gid: None,
                    home: None,
                    shell: None,
                    groups: Vec::new(),
                })
                .collect(),
            _ => {
                debug!("Get-LocalUser unavailable; users section empty");
                Vec::new()
            }
        }
    }

    #[cfg(not(any(unix, windows)))]
    fn collect_users() -> Vec<UserInfo> {
        Vec::new()
    }

    /// Collect SSH public-key fingerprints: host keys plus each account's
    /// authorized_keys. No-op on non-Unix platforms.
    #[cfg(unix)]
    fn collect_ssh_keys(users: &[UserInfo]) -> Vec<SshKey> {
        let mut keys = Vec::new();

        // Host keys: /etc/ssh/ssh_host_*_key.pub
        if let Ok(entries) = std::fs::read_dir("/etc/ssh") {
            for entry in entries.flatten() {
                let path = entry.path();
                let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
                if name.starts_with("ssh_host_") && name.ends_with(".pub") {
                    if let Ok(contents) = std::fs::read_to_string(&path) {
                        if let Some(key) = parse_pubkey_line(&contents, "(host)") {
                            keys.push(key);
                        }
                    }
                }
            }
        }

        // Per-account authorized_keys
        for user in users {
            let Some(home) = &user.home else { continue };
            let auth = std::path::Path::new(home).join(".ssh").join("authorized_keys");
            if let Ok(contents) = std::fs::read_to_string(&auth) {
                for line in contents.lines() {
                    let trimmed = line.trim();
                    if trimmed.is_empty() || trimmed.starts_with('#') {
                        continue;
                    }
                    if let Some(key) = parse_pubkey_line(trimmed, &user.username) {
                        keys.push(key);
                    }
                }
            }
        }
        keys
    }

    #[cfg(not(unix))]
    fn collect_ssh_keys(_users: &[UserInfo]) -> Vec<SshKey> {
        Vec::new()
    }
}

/// True for interactive login shells (excludes nologin/false service shells).
#[cfg(unix)]
fn is_login_shell(shell: &str) -> bool {
    !(shell.ends_with("nologin") || shell.ends_with("/false") || shell.is_empty())
}

/// Parse an OpenSSH public key line ("type base64 [comment]") into an [`SshKey`]
/// with a `SHA256:` fingerprint, mirroring `ssh-keygen -l` output.
#[cfg(unix)]
fn parse_pubkey_line(line: &str, username: &str) -> Option<SshKey> {
    use base64::engine::general_purpose::{STANDARD as B64, STANDARD_NO_PAD};
    use base64::Engine;

    let mut parts = line.split_whitespace();
    let key_type = parts.next()?.to_string();
    let blob_b64 = parts.next()?;
    let comment = {
        let rest: Vec<&str> = parts.collect();
        if rest.is_empty() {
            None
        } else {
            Some(rest.join(" "))
        }
    };

    let blob = B64.decode(blob_b64).ok()?;
    let digest = Sha256::digest(&blob);
    let fingerprint = format!("SHA256:{}", STANDARD_NO_PAD.encode(digest));

    Some(SshKey {
        username: username.to_string(),
        key_type,
        fingerprint,
        comment,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[cfg(unix)]
    #[test]
    fn parses_pubkey_into_sha256_fingerprint() {
        use base64::engine::general_purpose::STANDARD as B64;
        use base64::Engine;
        // A valid (if synthetic) 51-byte ed25519-shaped key blob so base64 decode
        // succeeds; this validates parsing + the SHA256 fingerprint form.
        let blob = vec![7u8; 51];
        let line = format!("ssh-ed25519 {} user@example", B64.encode(&blob));
        let key = parse_pubkey_line(&line, "alice").expect("parses");
        assert_eq!(key.username, "alice");
        assert_eq!(key.key_type, "ssh-ed25519");
        assert!(key.fingerprint.starts_with("SHA256:"));
        assert_eq!(key.comment.as_deref(), Some("user@example"));
    }

    #[cfg(unix)]
    #[test]
    fn collect_returns_some_real_users() {
        // On a real Unix host /etc/passwd has at least root.
        let profile = UsersCollector::collect();
        assert!(
            profile.users.iter().any(|u| u.uid == Some(0)),
            "root account should be present"
        );
    }
}
