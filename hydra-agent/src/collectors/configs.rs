//! Configuration file tracking collector.
//!
//! Hashes the configuration files listed in `[collection] config_files` so the
//! API can detect added/removed/changed config files across profiles. Only file
//! metadata and a SHA256 digest are recorded — never file contents — so no
//! secrets leave the node.

use chrono::{DateTime, Utc};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::path::Path;
use tracing::debug;

/// Metadata for a single tracked configuration file.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ConfigFile {
    /// Absolute path of the configuration file.
    pub path: String,
    /// Hex-encoded SHA256 digest of the file contents.
    pub hash: String,
    /// File size in bytes.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub size_bytes: Option<u64>,
    /// Last modification time (UTC).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub modified_at: Option<DateTime<Utc>>,
}

/// Configuration files profile section.
#[derive(Debug, Clone, Serialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ConfigsProfile {
    /// Tracked configuration files (only those that exist and are readable).
    pub files: Vec<ConfigFile>,
}

/// Collector for tracked configuration files.
pub struct ConfigsCollector;

impl ConfigsCollector {
    /// Hash each configured path. Missing or unreadable paths are skipped with a
    /// debug log rather than failing the whole profile.
    pub fn collect(paths: &[String]) -> ConfigsProfile {
        let mut files = Vec::new();
        for path in paths {
            match Self::hash_file(path) {
                Some(file) => files.push(file),
                None => debug!(path = %path, "tracked config file missing or unreadable; skipping"),
            }
        }
        ConfigsProfile { files }
    }

    fn hash_file(path: &str) -> Option<ConfigFile> {
        let p = Path::new(path);
        let data = std::fs::read(p).ok()?;
        let metadata = std::fs::metadata(p).ok();

        let mut hasher = Sha256::new();
        hasher.update(&data);
        let hash = format!("{:x}", hasher.finalize());

        let size_bytes = metadata.as_ref().map(|m| m.len());
        let modified_at = metadata
            .and_then(|m| m.modified().ok())
            .map(DateTime::<Utc>::from);

        Some(ConfigFile {
            path: path.to_string(),
            hash,
            size_bytes,
            modified_at,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hashes_existing_file_and_skips_missing() {
        let dir = std::env::temp_dir();
        let path = dir.join(format!("hydra-configs-test-{}.conf", std::process::id()));
        std::fs::write(&path, b"hydra-test-config").expect("write temp file");
        let path_str = path.to_string_lossy().to_string();

        let profile =
            ConfigsCollector::collect(&[path_str.clone(), "/nonexistent/hydra/xyz".to_string()]);

        let _ = std::fs::remove_file(&path);

        assert_eq!(profile.files.len(), 1, "only the existing file is recorded");
        let f = &profile.files[0];
        assert_eq!(f.path, path_str);
        assert_eq!(f.hash.len(), 64, "full hex SHA256");
        assert_eq!(f.size_bytes, Some("hydra-test-config".len() as u64));
        assert!(f.modified_at.is_some());
    }
}
