//! Software information collector.
//!
//! Collects operating system details and installed packages using
//! platform-specific package managers.

use anyhow::Result;
use serde::Serialize;
use sysinfo::System;

use crate::config::AgentConfig;

/// Software profile containing OS, package, and user information.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SoftwareProfile {
    /// Operating system information
    pub os: OsInfo,
    /// List of installed packages
    pub packages: Vec<Package>,
    /// Total number of packages (if collected)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub package_count: Option<usize>,
}

/// Operating system information.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct OsInfo {
    /// OS name (e.g., "Ubuntu", "Windows 11")
    pub name: String,
    /// OS version string
    #[serde(skip_serializing_if = "Option::is_none")]
    pub version: Option<String>,
    /// Kernel version
    #[serde(skip_serializing_if = "Option::is_none")]
    pub kernel_version: Option<String>,
    /// System architecture (e.g., "x86_64")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub architecture: Option<String>,
    /// OS family (e.g., "linux", "windows", "macos")
    pub family: String,
}

/// Package information.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Package {
    /// Package name
    pub name: String,
    /// Package version
    #[serde(skip_serializing_if = "Option::is_none")]
    pub version: Option<String>,
    /// Package manager (e.g., "dpkg", "rpm", "brew")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub manager: Option<String>,
}

/// Collector for software information.
pub struct SoftwareCollector;

impl SoftwareCollector {
    /// Collects software information from the current system.
    ///
    /// Gathers operating system details and optionally enumerates installed
    /// packages based on configuration.
    ///
    /// # Arguments
    ///
    /// * `config` - Agent configuration specifying collection options
    ///
    /// # Returns
    ///
    /// A software profile containing OS and package information.
    ///
    /// # Errors
    ///
    /// Returns an error if system information cannot be retrieved.
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

        if let Ok(output) = std::process::Command::new("dpkg-query")
            .args(["-W", "-f=${Package} ${Version}\n"])
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
                            manager: Some("dpkg".to_string()),
                        });
                    }
                }
                return Ok(packages);
            }
        }

        if let Ok(output) = std::process::Command::new("rpm")
            .args(["-qa", "--queryformat", "%{NAME} %{VERSION}\n"])
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
                            manager: Some("rpm".to_string()),
                        });
                    }
                }
                return Ok(packages);
            }
        }

        if let Ok(output) = std::process::Command::new("pacman").args(["-Q"]).output() {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    let parts: Vec<&str> = line.splitn(2, ' ').collect();
                    if !parts.is_empty() {
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

        // Alpine Linux
        if let Ok(output) = std::process::Command::new("apk")
            .args(["info", "-v"])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    let line = line.trim();
                    if line.is_empty() {
                        continue;
                    }
                    // apk info -v outputs "name-version" format
                    // Find the last hyphen that separates name from version
                    if let Some(idx) = line.rfind('-') {
                        packages.push(Package {
                            name: line[..idx].to_string(),
                            version: Some(line[idx + 1..].to_string()),
                            manager: Some("apk".to_string()),
                        });
                    } else {
                        packages.push(Package {
                            name: line.to_string(),
                            version: None,
                            manager: Some("apk".to_string()),
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

        if let Ok(output) = std::process::Command::new("brew")
            .args(["list", "--versions"])
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
                            manager: Some("brew".to_string()),
                        });
                    }
                }
            }
        }

        Ok(packages)
    }

    #[cfg(target_os = "windows")]
    fn collect_packages() -> Result<Vec<Package>> {
        use std::collections::HashSet;
        use std::process::Command;

        let mut packages = Vec::new();
        let mut seen_names: HashSet<String> = HashSet::new();

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
                        let name = parts[0].trim().to_string();
                        seen_names.insert(name.clone());
                        packages.push(Package {
                            name,
                            version: parts.get(1).map(|v| v.trim().to_string()).filter(|v| !v.is_empty()),
                            manager: Some("windows".to_string()),
                        });
                    }
                }
            }
        }

        if let Ok(output) = Command::new("winget")
            .args(["list", "--disable-interactivity"])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                let lines: Vec<&str> = stdout.lines().collect();
                for line in lines.iter().skip(2) {
                    let parts: Vec<&str> = line.split_whitespace().collect();
                    if parts.len() >= 2 {
                        let name = parts[0].to_string();
                        if seen_names.insert(name.clone()) {
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

    #[cfg(target_os = "freebsd")]
    fn collect_packages() -> Result<Vec<Package>> {
        let mut packages = Vec::new();

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

    #[cfg(target_os = "openbsd")]
    fn collect_packages() -> Result<Vec<Package>> {
        let mut packages = Vec::new();

        if let Ok(output) = std::process::Command::new("pkg_info").args(["-q"]).output() {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
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

    #[cfg(target_os = "netbsd")]
    fn collect_packages() -> Result<Vec<Package>> {
        let mut packages = Vec::new();

        if let Ok(output) = std::process::Command::new("pkg_info").args(["-a"]).output() {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
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
