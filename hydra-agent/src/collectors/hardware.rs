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
    #[serde(skip_serializing_if = "Option::is_none")]
    pub system_serial: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bios_vendor: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bios_version: Option<String>,
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
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub features: Vec<String>,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct MemoryInfo {
    pub total_bytes: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub memory_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub speed_mhz: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slots_used: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slots_total: Option<u32>,
}

#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct GpuInfo {
    pub model: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vendor: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub memory_bytes: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub driver_version: Option<String>,
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
            features: Self::detect_cpu_features(),
        };

        // Memory information (extended info from platform-specific sources)
        let (memory_type, speed_mhz, slots_used, slots_total) = Self::get_memory_details();
        let memory_info = MemoryInfo {
            total_bytes: sys.total_memory(),
            memory_type,
            speed_mhz,
            slots_used,
            slots_total,
        };

        // GPU information
        let gpus = Self::detect_gpus();

        // System information (with BIOS/serial data)
        let (system_manufacturer, system_model, system_serial, bios_vendor, bios_version) =
            Self::get_system_info();

        Ok(HardwareProfile {
            system_manufacturer,
            system_model,
            system_serial,
            bios_vendor,
            bios_version,
            cpu: cpu_info,
            memory: memory_info,
            gpus,
        })
    }

    /// Detect CPU features/flags.
    #[cfg(target_os = "linux")]
    fn detect_cpu_features() -> Vec<String> {
        if let Ok(contents) = std::fs::read_to_string("/proc/cpuinfo") {
            for line in contents.lines() {
                if line.starts_with("flags") || line.starts_with("Features") {
                    if let Some(flags) = line.split(':').nth(1) {
                        return flags.split_whitespace().map(String::from).collect();
                    }
                }
            }
        }
        vec![]
    }

    #[cfg(target_os = "windows")]
    fn detect_cpu_features() -> Vec<String> {
        // Windows: use CPUID or WMI - simplified for now
        vec![]
    }

    #[cfg(target_os = "macos")]
    fn detect_cpu_features() -> Vec<String> {
        if let Ok(output) = Command::new("sysctl").args(["-n", "machdep.cpu.features"]).output() {
            if output.status.success() {
                return String::from_utf8_lossy(&output.stdout)
                    .split_whitespace()
                    .map(String::from)
                    .collect();
            }
        }
        vec![]
    }

    #[cfg(not(any(target_os = "linux", target_os = "windows", target_os = "macos")))]
    fn detect_cpu_features() -> Vec<String> {
        vec![]
    }

    /// Get extended memory details.
    #[cfg(target_os = "linux")]
    fn get_memory_details() -> (Option<String>, Option<u64>, Option<u32>, Option<u32>) {
        // Try dmidecode for detailed memory info (requires root)
        if let Ok(output) = Command::new("dmidecode").args(["-t", "memory"]).output() {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                let mut mem_type = None;
                let mut speed = None;
                let mut slots_used = 0u32;
                let mut slots_total = 0u32;

                for line in stdout.lines() {
                    let trimmed = line.trim();
                    if trimmed.starts_with("Type:") && !trimmed.contains("Unknown") {
                        mem_type = trimmed.split(':').nth(1).map(|s| s.trim().to_string());
                    } else if trimmed.starts_with("Speed:") && trimmed.contains("MT/s") {
                        if let Some(s) = trimmed.split(':').nth(1) {
                            speed = s.trim().split_whitespace().next()
                                .and_then(|n| n.parse().ok());
                        }
                    } else if trimmed.starts_with("Memory Device") {
                        slots_total += 1;
                    } else if trimmed.starts_with("Size:") && !trimmed.contains("No Module") {
                        slots_used += 1;
                    }
                }

                return (mem_type, speed, Some(slots_used), Some(slots_total));
            }
        }
        (None, None, None, None)
    }

    #[cfg(target_os = "windows")]
    fn get_memory_details() -> (Option<String>, Option<u64>, Option<u32>, Option<u32>) {
        if let Ok(output) = Command::new("powershell")
            .args([
                "-NoProfile", "-Command",
                "Get-WmiObject Win32_PhysicalMemory | Select-Object MemoryType, Speed | ForEach-Object { \"$($_.MemoryType)|$($_.Speed)\" }"
            ])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                if let Some(line) = stdout.lines().next() {
                    let parts: Vec<&str> = line.split('|').collect();
                    let mem_type = parts.first().and_then(|t| {
                        match t.trim() {
                            "24" => Some("DDR3".to_string()),
                            "26" => Some("DDR4".to_string()),
                            "34" => Some("DDR5".to_string()),
                            _ => None,
                        }
                    });
                    let speed = parts.get(1).and_then(|s| s.trim().parse().ok());
                    return (mem_type, speed, None, None);
                }
            }
        }
        (None, None, None, None)
    }

    #[cfg(not(any(target_os = "linux", target_os = "windows")))]
    fn get_memory_details() -> (Option<String>, Option<u64>, Option<u32>, Option<u32>) {
        (None, None, None, None)
    }

    /// Get system information including BIOS details.
    #[cfg(target_os = "linux")]
    fn get_system_info() -> (Option<String>, Option<String>, Option<String>, Option<String>, Option<String>) {
        let manufacturer = std::fs::read_to_string("/sys/class/dmi/id/sys_vendor")
            .ok().map(|s| s.trim().to_string());
        let model = std::fs::read_to_string("/sys/class/dmi/id/product_name")
            .ok().map(|s| s.trim().to_string());
        let serial = std::fs::read_to_string("/sys/class/dmi/id/product_serial")
            .ok().map(|s| s.trim().to_string());
        let bios_vendor = std::fs::read_to_string("/sys/class/dmi/id/bios_vendor")
            .ok().map(|s| s.trim().to_string());
        let bios_version = std::fs::read_to_string("/sys/class/dmi/id/bios_version")
            .ok().map(|s| s.trim().to_string());
        (manufacturer, model, serial, bios_vendor, bios_version)
    }

    #[cfg(target_os = "windows")]
    fn get_system_info() -> (Option<String>, Option<String>, Option<String>, Option<String>, Option<String>) {
        let mut manufacturer = None;
        let mut model = None;
        let mut serial = None;
        let mut bios_vendor = None;
        let mut bios_version = None;

        if let Ok(output) = Command::new("powershell")
            .args(["-NoProfile", "-Command",
                "Get-WmiObject Win32_ComputerSystem | Select-Object Manufacturer, Model | ForEach-Object { \"$($_.Manufacturer)|$($_.Model)\" }"])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                if let Some(line) = stdout.lines().next() {
                    let parts: Vec<&str> = line.split('|').collect();
                    manufacturer = parts.first().map(|s| s.trim().to_string());
                    model = parts.get(1).map(|s| s.trim().to_string());
                }
            }
        }

        if let Ok(output) = Command::new("powershell")
            .args(["-NoProfile", "-Command",
                "Get-WmiObject Win32_BIOS | Select-Object Manufacturer, SMBIOSBIOSVersion, SerialNumber | ForEach-Object { \"$($_.Manufacturer)|$($_.SMBIOSBIOSVersion)|$($_.SerialNumber)\" }"])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                if let Some(line) = stdout.lines().next() {
                    let parts: Vec<&str> = line.split('|').collect();
                    bios_vendor = parts.first().map(|s| s.trim().to_string());
                    bios_version = parts.get(1).map(|s| s.trim().to_string());
                    serial = parts.get(2).map(|s| s.trim().to_string());
                }
            }
        }

        (manufacturer, model, serial, bios_vendor, bios_version)
    }

    #[cfg(target_os = "macos")]
    fn get_system_info() -> (Option<String>, Option<String>, Option<String>, Option<String>, Option<String>) {
        let manufacturer = Some("Apple".to_string());
        let mut model = None;
        let mut serial = None;

        if let Ok(output) = Command::new("system_profiler").args(["SPHardwareDataType"]).output() {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    if line.contains("Model Name:") || line.contains("Model Identifier:") {
                        model = line.split(':').nth(1).map(|s| s.trim().to_string());
                    } else if line.contains("Serial Number") {
                        serial = line.split(':').nth(1).map(|s| s.trim().to_string());
                    }
                }
            }
        }

        (manufacturer, model, serial, None, None)
    }

    #[cfg(any(target_os = "freebsd", target_os = "openbsd", target_os = "netbsd"))]
    fn get_system_info() -> (Option<String>, Option<String>, Option<String>, Option<String>, Option<String>) {
        // BSD systems - use sysctl where available
        let manufacturer = Command::new("sysctl").args(["-n", "hw.vendor"]).output()
            .ok().filter(|o| o.status.success())
            .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string());
        let model = Command::new("sysctl").args(["-n", "hw.product"]).output()
            .ok().filter(|o| o.status.success())
            .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string());
        (manufacturer, model, None, None, None)
    }

    #[cfg(not(any(
        target_os = "linux", target_os = "windows", target_os = "macos",
        target_os = "freebsd", target_os = "openbsd", target_os = "netbsd"
    )))]
    fn get_system_info() -> (Option<String>, Option<String>, Option<String>, Option<String>, Option<String>) {
        (System::name(), System::host_name(), None, None, None)
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
                            gpus.push(GpuInfo { model, vendor, memory_bytes: None, driver_version: None });
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
                                memory_bytes: None,
                                driver_version: None,
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
                                    memory_bytes: None,
                                    driver_version: None,
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
                                    memory_bytes: None,
                                    driver_version: None,
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
                            memory_bytes: None,
                            driver_version: None,
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
                                memory_bytes: None,
                                driver_version: None,
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
                                memory_bytes: None,
                                driver_version: None,
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
