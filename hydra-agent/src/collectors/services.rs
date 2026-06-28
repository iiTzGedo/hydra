//! Service discovery collector.
//!
//! Discovers running workloads (systemd units, Docker containers, launchd jobs,
//! Windows services, BSD rc services) and emits the top-level `services` profile
//! section the API expects (`ServicesProfile` with `ServiceInfo` entries). This
//! feeds the API's service-extraction pipeline (svc-`<name>`-`<hash>` IDs,
//! state-change and crash detection).

use serde::Serialize;
use serde_json::{json, Map, Value};
use std::process::Command;
use tracing::debug;

/// A discovered service (matches the API `ServiceInfo` model).
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ServiceInfo {
    /// Service / unit / container name.
    pub name: String,
    /// Runtime: `systemd`, `docker`, `launchd`, `windows-service`, `rc`.
    pub runtime: String,
    /// Current state, e.g. `running`, `active`, `failed`, `stopped`.
    pub status: String,
    /// Service version, if known.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub version: Option<String>,
    /// Container image (docker), if applicable.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub image: Option<String>,
    /// Published ports.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub ports: Vec<Value>,
    /// Service endpoints.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub endpoints: Vec<Value>,
    /// Resource usage / limits.
    #[serde(skip_serializing_if = "Map::is_empty")]
    pub resources: Map<String, Value>,
    /// Additional runtime-specific attachments.
    #[serde(skip_serializing_if = "Map::is_empty")]
    pub attachments: Map<String, Value>,
}

impl ServiceInfo {
    fn new(name: impl Into<String>, runtime: &str, status: impl Into<String>) -> Self {
        ServiceInfo {
            name: name.into(),
            runtime: runtime.to_string(),
            status: status.into(),
            version: None,
            image: None,
            ports: Vec::new(),
            endpoints: Vec::new(),
            resources: Map::new(),
            attachments: Map::new(),
        }
    }
}

/// Services profile section.
#[derive(Debug, Clone, Serialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ServicesProfile {
    /// Discovered services across all detected runtimes.
    pub services: Vec<ServiceInfo>,
}

/// Collector for service discovery.
pub struct ServicesCollector;

impl ServicesCollector {
    /// Discover services from the platform's native service manager plus any
    /// container runtimes present. Never fails — missing tools yield an empty
    /// contribution with a debug log.
    pub fn collect() -> ServicesProfile {
        let mut services = collect_native();
        services.extend(collect_docker());
        ServicesProfile { services }
    }
}

/// Run a command and capture stdout if it succeeds.
fn run(cmd: &str, args: &[&str]) -> Option<String> {
    match Command::new(cmd).args(args).output() {
        Ok(out) if out.status.success() => Some(String::from_utf8_lossy(&out.stdout).into_owned()),
        Ok(_) => {
            debug!(command = cmd, "command returned non-zero; skipping");
            None
        }
        Err(e) => {
            debug!(command = cmd, error = %e, "command not available; skipping");
            None
        }
    }
}

// ---------------------------------------------------------------------------
// systemd (Linux)
// ---------------------------------------------------------------------------
#[cfg(target_os = "linux")]
fn collect_native() -> Vec<ServiceInfo> {
    let Some(out) = run(
        "systemctl",
        &[
            "list-units",
            "--type=service",
            "--all",
            "--no-legend",
            "--no-pager",
            "--plain",
        ],
    ) else {
        return Vec::new();
    };

    let mut services = Vec::new();
    for line in out.lines() {
        let fields: Vec<&str> = line.split_whitespace().collect();
        if fields.len() < 4 {
            continue;
        }
        let unit = fields[0];
        let load = fields[1];
        let active = fields[2];
        let sub = fields[3];
        // Only report loaded units that are running or failed (skip inactive noise).
        if load != "loaded" || !(active == "active" || active == "activating" || active == "failed")
        {
            continue;
        }
        let name = unit.strip_suffix(".service").unwrap_or(unit).to_string();
        let mut svc = ServiceInfo::new(name, "systemd", active);
        svc.attachments.insert("subState".to_string(), json!(sub));
        services.push(svc);
    }
    services
}

// ---------------------------------------------------------------------------
// launchd (macOS)
// ---------------------------------------------------------------------------
#[cfg(target_os = "macos")]
fn collect_native() -> Vec<ServiceInfo> {
    let Some(out) = run("launchctl", &["list"]) else {
        return Vec::new();
    };
    let mut services = Vec::new();
    // Columns: PID  Status  Label
    for line in out.lines().skip(1) {
        let fields: Vec<&str> = line.split_whitespace().collect();
        if fields.len() < 3 {
            continue;
        }
        let pid = fields[0];
        let label = fields[2..].join(" ");
        let status = if pid != "-" { "running" } else { "loaded" };
        let mut svc = ServiceInfo::new(label, "launchd", status);
        if pid != "-" {
            svc.attachments.insert("pid".to_string(), json!(pid));
        }
        services.push(svc);
    }
    services
}

// ---------------------------------------------------------------------------
// Windows services
// ---------------------------------------------------------------------------
#[cfg(target_os = "windows")]
fn collect_native() -> Vec<ServiceInfo> {
    let Some(out) = run(
        "powershell",
        &[
            "-NoProfile",
            "-Command",
            "Get-Service | ForEach-Object { \"$($_.Name)|$($_.Status)|$($_.DisplayName)\" }",
        ],
    ) else {
        return Vec::new();
    };
    let mut services = Vec::new();
    for line in out.lines() {
        let parts: Vec<&str> = line.trim().splitn(3, '|').collect();
        if parts.len() < 2 || parts[0].is_empty() {
            continue;
        }
        let status = parts[1].to_ascii_lowercase();
        let mut svc = ServiceInfo::new(parts[0], "windows-service", status);
        if let Some(display) = parts.get(2) {
            if !display.is_empty() {
                svc.attachments
                    .insert("displayName".to_string(), json!(display));
            }
        }
        services.push(svc);
    }
    services
}

// ---------------------------------------------------------------------------
// rc (FreeBSD / OpenBSD / NetBSD)
// ---------------------------------------------------------------------------
#[cfg(any(
    target_os = "freebsd",
    target_os = "openbsd",
    target_os = "netbsd"
))]
fn collect_native() -> Vec<ServiceInfo> {
    let Some(out) = run("service", &["-e"]) else {
        return Vec::new();
    };
    let mut services = Vec::new();
    for line in out.lines() {
        let path = line.trim();
        if path.is_empty() {
            continue;
        }
        let name = path.rsplit('/').next().unwrap_or(path);
        services.push(ServiceInfo::new(name, "rc", "enabled"));
    }
    services
}

#[cfg(not(any(
    target_os = "linux",
    target_os = "macos",
    target_os = "windows",
    target_os = "freebsd",
    target_os = "openbsd",
    target_os = "netbsd"
)))]
fn collect_native() -> Vec<ServiceInfo> {
    Vec::new()
}

// ---------------------------------------------------------------------------
// Docker (any platform with the docker CLI + a reachable daemon)
// ---------------------------------------------------------------------------
fn collect_docker() -> Vec<ServiceInfo> {
    let Some(out) = run("docker", &["ps", "--no-trunc", "--format", "{{json .}}"]) else {
        return Vec::new();
    };
    let mut services = Vec::new();
    for line in out.lines() {
        let Ok(obj) = serde_json::from_str::<Value>(line) else {
            continue;
        };
        let name = obj
            .get("Names")
            .and_then(Value::as_str)
            .unwrap_or("")
            .split(',')
            .next()
            .unwrap_or("")
            .to_string();
        if name.is_empty() {
            continue;
        }
        let status = obj
            .get("State")
            .and_then(Value::as_str)
            .unwrap_or("running")
            .to_string();
        let mut svc = ServiceInfo::new(name, "docker", status);
        svc.image = obj
            .get("Image")
            .and_then(Value::as_str)
            .map(str::to_string);
        if let Some(ports) = obj.get("Ports").and_then(Value::as_str) {
            if !ports.is_empty() {
                for mapping in ports.split(',') {
                    svc.ports.push(json!({ "mapping": mapping.trim() }));
                }
            }
        }
        if let Some(s) = obj.get("Status").and_then(Value::as_str) {
            svc.attachments.insert("statusText".to_string(), json!(s));
        }
        services.push(svc);
    }
    services
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn collect_does_not_panic_and_returns_profile() {
        // Whatever the host has, collection must succeed and produce valid data.
        let profile = ServicesCollector::collect();
        for svc in &profile.services {
            assert!(!svc.name.is_empty());
            assert!(!svc.runtime.is_empty());
            assert!(!svc.status.is_empty());
        }
    }

    #[test]
    fn service_info_new_defaults_are_empty() {
        let svc = ServiceInfo::new("nginx", "systemd", "active");
        assert_eq!(svc.name, "nginx");
        assert_eq!(svc.runtime, "systemd");
        assert!(svc.ports.is_empty());
        assert!(svc.resources.is_empty());
    }
}
