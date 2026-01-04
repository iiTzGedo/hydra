//! Hardware information collector.

use anyhow::Result;
use serde::Serialize;
use std::process::Command;
use sysinfo::System;

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct HardwareProfile {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub system_manufacturer: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub system_model: Option<String>,
    pub cpu: CpuInfo,
    pub memory: MemoryInfo,
    pub gpus: Vec<GpuInfo>,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct CpuInfo {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vendor: Option<String>,
    pub cores_physical: usize,
    pub cores_logical: usize,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub frequency_mhz: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub architecture: Option<String>,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct MemoryInfo {
    pub total_bytes: u64,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct GpuInfo {
    pub model: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vendor: Option<String>,
}

pub struct HardwareCollector;

impl HardwareCollector {
    /// Collect hardware information.
    pub fn collect() -> Result<HardwareProfile> {
        let mut sys = System::new_all();
        sys.refresh_all();

        // CPU information
        let cpus = sys.cpus();
        let cpu_info = CpuInfo {
            model: cpus.first().map(|c| c.brand().to_string()),
            vendor: cpus.first().map(|c| c.vendor_id().to_string()),
            cores_physical: sys.physical_core_count().unwrap_or(0),
            cores_logical: cpus.len(),
            frequency_mhz: cpus.first().map(|c| c.frequency()),
            architecture: Some(std::env::consts::ARCH.to_string()),
        };

        // Memory information
        let memory_info = MemoryInfo {
            total_bytes: sys.total_memory(),
        };

        // GPU information
        let gpus = Self::detect_gpus();

        // System information
        let system_manufacturer = System::name();
        let system_model = System::host_name();

        Ok(HardwareProfile {
            system_manufacturer,
            system_model,
            cpu: cpu_info,
            memory: memory_info,
            gpus,
        })
    }

    /// Detect GPUs on Linux using lspci.
    #[cfg(target_os = "linux")]
    fn detect_gpus() -> Vec<GpuInfo> {
        let mut gpus = Vec::new();

        // Try lspci for general GPU detection
        if let Ok(output) = Command::new("lspci").output() {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    // Look for VGA or 3D controllers
                    if line.contains("VGA compatible controller")
                        || line.contains("3D controller")
                        || line.contains("Display controller")
                    {
                        // Extract vendor and model from the line
                        // Format: "XX:XX.X VGA compatible controller: Vendor Model"
                        if let Some(colon_pos) = line.find(": ") {
                            let device_info = &line[colon_pos + 2..];
                            let (vendor, model) = Self::parse_gpu_info(device_info);
                            gpus.push(GpuInfo { model, vendor });
                        }
                    }
                }
            }
        }

        // Try nvidia-smi for NVIDIA GPUs (more detailed info)
        if let Ok(output) = Command::new("nvidia-smi")
            .args(["--query-gpu=name", "--format=csv,noheader"])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    let model = line.trim().to_string();
                    if !model.is_empty() {
                        // Check if we already have this GPU from lspci
                        if !gpus.iter().any(|g| g.model.contains(&model)) {
                            gpus.push(GpuInfo {
                                model,
                                vendor: Some("NVIDIA".to_string()),
                            });
                        }
                    }
                }
            }
        }

        gpus
    }

    /// Detect GPUs on macOS using system_profiler.
    #[cfg(target_os = "macos")]
    fn detect_gpus() -> Vec<GpuInfo> {
        let mut gpus = Vec::new();

        if let Ok(output) = Command::new("system_profiler")
            .args(["SPDisplaysDataType", "-json"])
            .output()
        {
            if output.status.success() {
                if let Ok(json) = serde_json::from_slice::<serde_json::Value>(&output.stdout) {
                    if let Some(displays) = json.get("SPDisplaysDataType").and_then(|d| d.as_array())
                    {
                        for display in displays {
                            if let Some(model) = display.get("sppci_model").and_then(|m| m.as_str())
                            {
                                let vendor = display
                                    .get("sppci_vendor")
                                    .and_then(|v| v.as_str())
                                    .map(|s| s.to_string());
                                gpus.push(GpuInfo {
                                    model: model.to_string(),
                                    vendor,
                                });
                            }
                        }
                    }
                }
            }
        }

        // Fallback to plain text parsing
        if gpus.is_empty() {
            if let Ok(output) = Command::new("system_profiler")
                .args(["SPDisplaysDataType"])
                .output()
            {
                if output.status.success() {
                    let stdout = String::from_utf8_lossy(&output.stdout);
                    for line in stdout.lines() {
                        if line.contains("Chipset Model:") {
                            if let Some(model) = line.split(':').nth(1) {
                                gpus.push(GpuInfo {
                                    model: model.trim().to_string(),
                                    vendor: Some("Apple".to_string()),
                                });
                            }
                        }
                    }
                }
            }
        }

        gpus
    }

    /// Detect GPUs on Windows using wmic.
    #[cfg(target_os = "windows")]
    fn detect_gpus() -> Vec<GpuInfo> {
        let mut gpus = Vec::new();

        // Use PowerShell to get GPU info (more reliable than wmic)
        if let Ok(output) = Command::new("powershell")
            .args([
                "-NoProfile",
                "-Command",
                "Get-WmiObject Win32_VideoController | Select-Object Name, AdapterCompatibility | ForEach-Object { \"$($_.Name)|$($_.AdapterCompatibility)\" }",
            ])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    let parts: Vec<&str> = line.splitn(2, '|').collect();
                    if !parts.is_empty() && !parts[0].is_empty() {
                        gpus.push(GpuInfo {
                            model: parts[0].trim().to_string(),
                            vendor: parts.get(1).map(|v| v.trim().to_string()),
                        });
                    }
                }
            }
        }

        // Fallback to wmic
        if gpus.is_empty() {
            if let Ok(output) = Command::new("wmic")
                .args(["path", "win32_videocontroller", "get", "name"])
                .output()
            {
                if output.status.success() {
                    let stdout = String::from_utf8_lossy(&output.stdout);
                    for line in stdout.lines().skip(1) {
                        let model = line.trim();
                        if !model.is_empty() {
                            gpus.push(GpuInfo {
                                model: model.to_string(),
                                vendor: None,
                            });
                        }
                    }
                }
            }
        }

        gpus
    }

    /// Detect GPUs on BSD systems using pciconf.
    #[cfg(any(
        target_os = "freebsd",
        target_os = "openbsd",
        target_os = "netbsd"
    ))]
    fn detect_gpus() -> Vec<GpuInfo> {
        let mut gpus = Vec::new();

        // FreeBSD uses pciconf
        if let Ok(output) = Command::new("pciconf").args(["-lv"]).output() {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                let mut current_vendor = None;
                let mut is_display = false;

                for line in stdout.lines() {
                    if line.contains("class") && (line.contains("display") || line.contains("vga"))
                    {
                        is_display = true;
                    } else if line.contains("vendor") && is_display {
                        current_vendor = line.split('=').nth(1).map(|s| s.trim().trim_matches('\'').to_string());
                    } else if line.contains("device") && is_display {
                        if let Some(model) = line.split('=').nth(1) {
                            gpus.push(GpuInfo {
                                model: model.trim().trim_matches('\'').to_string(),
                                vendor: current_vendor.take(),
                            });
                            is_display = false;
                        }
                    } else if line.is_empty() {
                        is_display = false;
                        current_vendor = None;
                    }
                }
            }
        }

        gpus
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
    fn detect_gpus() -> Vec<GpuInfo> {
        Vec::new()
    }

    /// Parse GPU vendor and model from a device info string.
    #[cfg(target_os = "linux")]
    fn parse_gpu_info(info: &str) -> (Option<String>, String) {
        // Common patterns: "NVIDIA Corporation GeForce GTX 1080"
        //                  "Advanced Micro Devices, Inc. [AMD/ATI] Navi 10"
        //                  "Intel Corporation UHD Graphics 630"
        let known_vendors = [
            ("NVIDIA", "NVIDIA"),
            ("Advanced Micro Devices", "AMD"),
            ("AMD/ATI", "AMD"),
            ("Intel", "Intel"),
            ("Matrox", "Matrox"),
            ("ASPEED", "ASPEED"),
        ];

        let mut vendor = None;
        let mut model = info.to_string();

        for (pattern, name) in &known_vendors {
            if info.contains(pattern) {
                vendor = Some(name.to_string());
                // Try to extract just the model name
                if let Some(bracket_pos) = info.find('[') {
                    if let Some(end_pos) = info.find(']') {
                        model = info[bracket_pos + 1..end_pos].to_string();
                    }
                } else {
                    // Remove vendor prefix
                    model = info.replace(pattern, "").trim().to_string();
                    if model.starts_with("Corporation ") {
                        model = model.replace("Corporation ", "");
                    }
                    if model.starts_with(", Inc. ") {
                        model = model.replace(", Inc. ", "");
                    }
                }
                break;
            }
        }

        (vendor, model.trim().to_string())
    }
}
