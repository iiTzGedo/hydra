//! Software information collector.

use anyhow::Result;
use serde::Serialize;
use sysinfo::System;

use crate::config::AgentConfig;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SoftwareProfile {
    pub os: OsInfo,
    pub packages: Vec<Package>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub package_count: Option<usize>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct OsInfo {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub version: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub kernel_version: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub architecture: Option<String>,
    pub family: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Package {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub version: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub manager: Option<String>,
}

pub struct SoftwareCollector;

impl SoftwareCollector {
    /// Collect software information.
    pub fn collect(config: &AgentConfig) -> Result<SoftwareProfile> {
        let os_info = OsInfo {
            name: System::name().unwrap_or_else(|| "Unknown".to_string()),
            version: System::os_version(),
            kernel_version: System::kernel_version(),
            architecture: Some(std::env::consts::ARCH.to_string()),
            family: std::env::consts::OS.to_string(),
        };

        let packages = if config.collection.include_packages {
            Self::collect_packages()?
        } else {
            vec![]
        };

        let package_count = if packages.is_empty() {
            None
        } else {
            Some(packages.len())
        };

        Ok(SoftwareProfile {
            os: os_info,
            packages,
            package_count,
        })
    }

    #[cfg(target_os = "linux")]
    fn collect_packages() -> Result<Vec<Package>> {
        let mut packages = Vec::new();

        // Try dpkg (Debian/Ubuntu)
        if let Ok(output) = std::process::Command::new("dpkg-query")
            .args(["-W", "-f=${Package} ${Version}\n"])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    let parts: Vec<&str> = line.splitn(2, ' ').collect();
                    if parts.len() >= 1 {
                        packages.push(Package {
                            name: parts[0].to_string(),
                            version: parts.get(1).map(|v| v.to_string()),
                            manager: Some("dpkg".to_string()),
                        });
                    }
                }
                return Ok(packages);
            }
        }

        // Try rpm (RHEL/Fedora)
        if let Ok(output) = std::process::Command::new("rpm")
            .args(["-qa", "--queryformat", "%{NAME} %{VERSION}\n"])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    let parts: Vec<&str> = line.splitn(2, ' ').collect();
                    if parts.len() >= 1 {
                        packages.push(Package {
                            name: parts[0].to_string(),
                            version: parts.get(1).map(|v| v.to_string()),
                            manager: Some("rpm".to_string()),
                        });
                    }
                }
                return Ok(packages);
            }
        }

        // Try pacman (Arch)
        if let Ok(output) = std::process::Command::new("pacman")
            .args(["-Q"])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    let parts: Vec<&str> = line.splitn(2, ' ').collect();
                    if parts.len() >= 1 {
                        packages.push(Package {
                            name: parts[0].to_string(),
                            version: parts.get(1).map(|v| v.to_string()),
                            manager: Some("pacman".to_string()),
                        });
                    }
                }
                return Ok(packages);
            }
        }

        Ok(packages)
    }

    #[cfg(target_os = "macos")]
    fn collect_packages() -> Result<Vec<Package>> {
        let mut packages = Vec::new();

        // Try Homebrew
        if let Ok(output) = std::process::Command::new("brew")
            .args(["list", "--versions"])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    let parts: Vec<&str> = line.splitn(2, ' ').collect();
                    if parts.len() >= 1 {
                        packages.push(Package {
                            name: parts[0].to_string(),
                            version: parts.get(1).map(|v| v.to_string()),
                            manager: Some("brew".to_string()),
                        });
                    }
                }
            }
        }

        Ok(packages)
    }

    /// Collect packages on Windows.
    #[cfg(target_os = "windows")]
    fn collect_packages() -> Result<Vec<Package>> {
        use std::process::Command;

        let mut packages = Vec::new();

        // Try to list installed programs via PowerShell (most reliable)
        if let Ok(output) = Command::new("powershell")
            .args([
                "-NoProfile",
                "-Command",
                "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*, \
                 HKLM:\\Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* 2>$null | \
                 Where-Object { $_.DisplayName } | \
                 Select-Object DisplayName, DisplayVersion | \
                 ForEach-Object { \"$($_.DisplayName)|$($_.DisplayVersion)\" }",
            ])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    let parts: Vec<&str> = line.splitn(2, '|').collect();
                    if !parts.is_empty() && !parts[0].is_empty() {
                        packages.push(Package {
                            name: parts[0].trim().to_string(),
                            version: parts.get(1).map(|v| v.trim().to_string()).filter(|v| !v.is_empty()),
                            manager: Some("windows".to_string()),
                        });
                    }
                }
            }
        }

        // Also try winget if available
        if let Ok(output) = Command::new("winget")
            .args(["list", "--disable-interactivity"])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                let lines: Vec<&str> = stdout.lines().collect();
                // Skip header lines
                for line in lines.iter().skip(2) {
                    let parts: Vec<&str> = line.split_whitespace().collect();
                    if parts.len() >= 2 {
                        // Check if this package is already in the list
                        let name = parts[0].to_string();
                        if !packages.iter().any(|p| p.name == name) {
                            packages.push(Package {
                                name,
                                version: Some(parts[1].to_string()),
                                manager: Some("winget".to_string()),
                            });
                        }
                    }
                }
            }
        }

        // Also try chocolatey if available
        if let Ok(output) = Command::new("choco")
            .args(["list", "--local-only", "--limit-output"])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    let parts: Vec<&str> = line.split('|').collect();
                    if parts.len() >= 2 {
                        packages.push(Package {
                            name: parts[0].to_string(),
                            version: Some(parts[1].to_string()),
                            manager: Some("chocolatey".to_string()),
                        });
                    }
                }
            }
        }

        Ok(packages)
    }

    /// Collect packages on FreeBSD.
    #[cfg(target_os = "freebsd")]
    fn collect_packages() -> Result<Vec<Package>> {
        let mut packages = Vec::new();

        // Use pkg to list installed packages
        if let Ok(output) = std::process::Command::new("pkg")
            .args(["query", "%n %v"])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    let parts: Vec<&str> = line.splitn(2, ' ').collect();
                    if !parts.is_empty() {
                        packages.push(Package {
                            name: parts[0].to_string(),
                            version: parts.get(1).map(|v| v.to_string()),
                            manager: Some("pkg".to_string()),
                        });
                    }
                }
            }
        }

        Ok(packages)
    }

    /// Collect packages on OpenBSD.
    #[cfg(target_os = "openbsd")]
    fn collect_packages() -> Result<Vec<Package>> {
        let mut packages = Vec::new();

        // Use pkg_info to list installed packages
        if let Ok(output) = std::process::Command::new("pkg_info")
            .args(["-q"])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    // OpenBSD format: name-version
                    if let Some(idx) = line.rfind('-') {
                        packages.push(Package {
                            name: line[..idx].to_string(),
                            version: Some(line[idx + 1..].to_string()),
                            manager: Some("pkg_info".to_string()),
                        });
                    } else {
                        packages.push(Package {
                            name: line.to_string(),
                            version: None,
                            manager: Some("pkg_info".to_string()),
                        });
                    }
                }
            }
        }

        Ok(packages)
    }

    /// Collect packages on NetBSD.
    #[cfg(target_os = "netbsd")]
    fn collect_packages() -> Result<Vec<Package>> {
        let mut packages = Vec::new();

        // Use pkg_info to list installed packages
        if let Ok(output) = std::process::Command::new("pkg_info")
            .args(["-a"])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    // NetBSD format: name-version description
                    let parts: Vec<&str> = line.splitn(2, ' ').collect();
                    if !parts.is_empty() {
                        let name_ver = parts[0];
                        if let Some(idx) = name_ver.rfind('-') {
                            packages.push(Package {
                                name: name_ver[..idx].to_string(),
                                version: Some(name_ver[idx + 1..].to_string()),
                                manager: Some("pkg_info".to_string()),
                            });
                        } else {
                            packages.push(Package {
                                name: name_ver.to_string(),
                                version: None,
                                manager: Some("pkg_info".to_string()),
                            });
                        }
                    }
                }
            }
        }

        Ok(packages)
    }

    /// Fallback for other platforms.
    #[cfg(not(any(
        target_os = "linux",
        target_os = "macos",
        target_os = "windows",
        target_os = "freebsd",
        target_os = "openbsd",
        target_os = "netbsd"
    )))]
    fn collect_packages() -> Result<Vec<Package>> {
        Ok(vec![])
    }
}
