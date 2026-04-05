//! Hardware information collector.
//!
//! Collects system hardware information including CPU, memory, GPU, and
//! system identification data. Uses platform-specific APIs and commands.

use anyhow::Result;
use serde::Serialize;
use std::process::Command;
use sysinfo::System;
use tracing::debug;

/// System info tuple: (manufacturer, model, serial, bios_vendor, bios_version).
type SystemInfo = (
    Option<String>,
    Option<String>,
    Option<String>,
    Option<String>,
    Option<String>,
);

/// Hardware profile containing system identification, CPU, memory, and GPU information.
#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct HardwareProfile {
    /// System manufacturer (e.g., "Dell", "HP", "Apple")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub system_manufacturer: Option<String>,
    /// System model name
    #[serde(skip_serializing_if = "Option::is_none")]
    pub system_model: Option<String>,
    /// System serial number
    #[serde(skip_serializing_if = "Option::is_none")]
    pub system_serial: Option<String>,
    /// BIOS vendor
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bios_vendor: Option<String>,
    /// BIOS version string
    #[serde(skip_serializing_if = "Option::is_none")]
    pub bios_version: Option<String>,
    /// CPU information
    pub cpu: CpuInfo,
    /// Memory information
    pub memory: MemoryInfo,
    /// List of detected GPUs
    pub gpus: Vec<GpuInfo>,
}

/// CPU information including cores, frequency, and features.
#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct CpuInfo {
    /// CPU model name (e.g., "Intel Core i7-10700K")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    /// CPU vendor (e.g., "GenuineIntel", "AuthenticAMD")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vendor: Option<String>,
    /// Number of physical CPU cores
    pub cores_physical: usize,
    /// Number of logical CPU cores (includes hyperthreading)
    pub cores_logical: usize,
    /// CPU frequency in MHz
    #[serde(skip_serializing_if = "Option::is_none")]
    pub frequency_mhz: Option<u64>,
    /// CPU architecture (e.g., "x86_64", "aarch64")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub architecture: Option<String>,
    /// CPU feature flags (e.g., "sse4_2", "avx2")
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub features: Vec<String>,
}

/// Memory information including capacity and module details.
#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct MemoryInfo {
    /// Total memory in bytes
    pub total_bytes: u64,
    /// Used memory in bytes
    #[serde(skip_serializing_if = "Option::is_none")]
    pub used_bytes: Option<u64>,
    /// Memory type (e.g., "DDR4", "DDR5")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub memory_type: Option<String>,
    /// Memory speed in MHz/MT/s
    #[serde(skip_serializing_if = "Option::is_none")]
    pub speed_mhz: Option<u64>,
    /// Number of memory slots with modules installed
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slots_used: Option<u32>,
    /// Total number of memory slots
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slots_total: Option<u32>,
}

/// GPU information.
#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct GpuInfo {
    /// GPU model name
    pub model: String,
    /// GPU vendor (e.g., "NVIDIA", "AMD", "Intel")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vendor: Option<String>,
    /// GPU memory in bytes
    #[serde(skip_serializing_if = "Option::is_none")]
    pub memory_bytes: Option<u64>,
    /// GPU driver version
    #[serde(skip_serializing_if = "Option::is_none")]
    pub driver_version: Option<String>,
}

/// Collector for hardware information.
pub struct HardwareCollector;

impl HardwareCollector {
    /// Collects hardware information from the current system.
    ///
    /// Gathers CPU, memory, GPU, and system identification data using
    /// platform-specific APIs and commands.
    ///
    /// # Returns
    ///
    /// A hardware profile containing all collected data.
    ///
    /// # Errors
    ///
    /// Returns an error if system information cannot be retrieved.
    pub fn collect() -> Result<HardwareProfile> {
        let mut sys = System::new_all();
        sys.refresh_all();

        let cpus = sys.cpus();

        // Determine core counts with container-awareness:
        // 1. Try cgroup limits (containers/LXC/Docker)
        // 2. Fall back to sysinfo
        // 3. Fall back to /proc/cpuinfo processor count
        let sysinfo_physical = sys.physical_core_count().unwrap_or(0);
        let sysinfo_logical = cpus.len();

        let (cores_physical, cores_logical) =
            Self::detect_cpu_cores(sysinfo_physical, sysinfo_logical);

        let cpu_info = CpuInfo {
            model: cpus.first().map(|c| c.brand().to_string()),
            vendor: cpus.first().map(|c| c.vendor_id().to_string()),
            cores_physical,
            cores_logical,
            frequency_mhz: cpus.first().map(|c| c.frequency()),
            architecture: Some(std::env::consts::ARCH.to_string()),
            features: Self::detect_cpu_features(),
        };

        let (memory_type, speed_mhz, slots_used, slots_total) = Self::get_memory_details();

        // Use cgroup memory limit when available and more restrictive than host memory
        let sysinfo_total = sys.total_memory();
        let total_bytes = Self::detect_memory_limit(sysinfo_total);

        let memory_info = MemoryInfo {
            total_bytes,
            used_bytes: Some(sys.used_memory()),
            memory_type,
            speed_mhz,
            slots_used,
            slots_total,
        };

        let gpus = Self::detect_gpus();

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

    /// Determines CPU core counts with container awareness.
    ///
    /// Priority: cgroup limits > sysinfo values > /proc/cpuinfo count.
    /// In containers (LXC, Docker, K8s), cgroup limits reflect the actual
    /// allocated cores rather than the host's physical count.
    fn detect_cpu_cores(sysinfo_physical: usize, sysinfo_logical: usize) -> (usize, usize) {
        #[cfg(target_os = "linux")]
        {
            if let Some(cgroup_cores) = Self::detect_cpu_cores_cgroup() {
                debug!(
                    cgroup_cores,
                    sysinfo_physical, sysinfo_logical, "cgroup CPU limit detected"
                );
                // Use cgroup limit when it's more restrictive than sysinfo
                let logical = if cgroup_cores > 0 && cgroup_cores < sysinfo_logical {
                    cgroup_cores
                } else {
                    sysinfo_logical
                };
                let physical = if cgroup_cores > 0 && cgroup_cores < sysinfo_physical {
                    cgroup_cores
                } else if sysinfo_physical > 0 {
                    sysinfo_physical
                } else {
                    // sysinfo returned 0 — use cgroup or cpuinfo count
                    cgroup_cores.max(1)
                };
                return (physical, logical);
            }
        }

        // No cgroup limits — use sysinfo with /proc/cpuinfo fallback
        let physical = if sysinfo_physical > 0 {
            sysinfo_physical
        } else {
            #[cfg(target_os = "linux")]
            {
                let count = Self::count_cpuinfo_processors();
                if count > 0 {
                    debug!(
                        count,
                        "physical_core_count unavailable, using /proc/cpuinfo processor count"
                    );
                    count
                } else {
                    0
                }
            }
            #[cfg(not(target_os = "linux"))]
            {
                0
            }
        };

        let logical = if sysinfo_logical > 0 {
            sysinfo_logical
        } else {
            physical
        };

        (physical, logical)
    }

    /// Reads CPU core limit from cgroup v2 or v1.
    ///
    /// Returns the effective number of CPU cores allocated to this cgroup,
    /// or None if no cgroup CPU limit is set.
    #[cfg(target_os = "linux")]
    fn detect_cpu_cores_cgroup() -> Option<usize> {
        // cgroup v2: /sys/fs/cgroup/cpu.max contains "quota period" or "max period"
        if let Ok(contents) = std::fs::read_to_string("/sys/fs/cgroup/cpu.max") {
            let parts: Vec<&str> = contents.split_whitespace().collect();
            if parts.len() == 2 && parts[0] != "max" {
                if let (Ok(quota), Ok(period)) = (parts[0].parse::<u64>(), parts[1].parse::<u64>())
                {
                    if period > 0 {
                        let cores = ((quota as f64) / (period as f64)).ceil() as usize;
                        if cores > 0 {
                            return Some(cores);
                        }
                    }
                }
            }
        }

        // cgroup v1: quota and period in separate files
        if let (Ok(quota_str), Ok(period_str)) = (
            std::fs::read_to_string("/sys/fs/cgroup/cpu/cpu.cfs_quota_us"),
            std::fs::read_to_string("/sys/fs/cgroup/cpu/cpu.cfs_period_us"),
        ) {
            if let (Ok(quota), Ok(period)) = (
                quota_str.trim().parse::<i64>(),
                period_str.trim().parse::<u64>(),
            ) {
                // quota of -1 means unlimited
                if quota > 0 && period > 0 {
                    let cores = ((quota as f64) / (period as f64)).ceil() as usize;
                    if cores > 0 {
                        return Some(cores);
                    }
                }
            }
        }

        None
    }

    /// Counts the number of "processor" entries in /proc/cpuinfo.
    /// This reflects the CPUs visible to the kernel/container.
    #[cfg(target_os = "linux")]
    fn count_cpuinfo_processors() -> usize {
        if let Ok(contents) = std::fs::read_to_string("/proc/cpuinfo") {
            return contents
                .lines()
                .filter(|line| line.starts_with("processor"))
                .count();
        }
        0
    }

    /// Returns the effective memory limit, preferring cgroup limits over sysinfo
    /// when available and more restrictive. In containers, sysinfo reports
    /// host memory which doesn't reflect the container's actual allocation.
    fn detect_memory_limit(sysinfo_total: u64) -> u64 {
        #[cfg(target_os = "linux")]
        {
            if let Some(cgroup_limit) = Self::detect_memory_cgroup() {
                if cgroup_limit > 0 && cgroup_limit < sysinfo_total {
                    debug!(
                        cgroup_limit_bytes = cgroup_limit,
                        sysinfo_total_bytes = sysinfo_total,
                        "cgroup memory limit detected, using cgroup value"
                    );
                    return cgroup_limit;
                }
            }
        }
        sysinfo_total
    }

    /// Reads memory limit from cgroup v2 or v1.
    ///
    /// Returns the memory limit in bytes, or None if no limit is set.
    #[cfg(target_os = "linux")]
    fn detect_memory_cgroup() -> Option<u64> {
        // cgroup v2: /sys/fs/cgroup/memory.max contains bytes or "max"
        if let Ok(contents) = std::fs::read_to_string("/sys/fs/cgroup/memory.max") {
            let trimmed = contents.trim();
            if trimmed != "max" {
                if let Ok(limit) = trimmed.parse::<u64>() {
                    return Some(limit);
                }
            }
        }

        // cgroup v1: /sys/fs/cgroup/memory/memory.limit_in_bytes
        if let Ok(contents) = std::fs::read_to_string("/sys/fs/cgroup/memory/memory.limit_in_bytes")
        {
            if let Ok(limit) = contents.trim().parse::<u64>() {
                // cgroup v1 uses a very large value (near u64::MAX) to mean unlimited
                // Treat anything above 2^62 as "unlimited"
                if limit < (1u64 << 62) {
                    return Some(limit);
                }
            }
        }

        None
    }

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
        vec![]
    }

    #[cfg(target_os = "macos")]
    fn detect_cpu_features() -> Vec<String> {
        if let Ok(output) = Command::new("sysctl")
            .args(["-n", "machdep.cpu.features"])
            .output()
        {
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

    #[cfg(target_os = "linux")]
    fn get_memory_details() -> (Option<String>, Option<u64>, Option<u32>, Option<u32>) {
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
                            speed = s
                                .split_whitespace()
                                .next()
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

    #[cfg(target_os = "linux")]
    fn get_system_info() -> SystemInfo {
        let read_dmi = |path: &str| -> Option<String> {
            match std::fs::read_to_string(path) {
                Ok(s) => {
                    let trimmed = s.trim().to_string();
                    if trimmed.is_empty() {
                        None
                    } else {
                        Some(trimmed)
                    }
                }
                Err(e) => {
                    debug!(path, error = %e, "DMI file not accessible (expected in containers)");
                    None
                }
            }
        };

        let manufacturer = read_dmi("/sys/class/dmi/id/sys_vendor");
        let model = read_dmi("/sys/class/dmi/id/product_name");
        let serial = read_dmi("/sys/class/dmi/id/product_serial");
        let bios_vendor = read_dmi("/sys/class/dmi/id/bios_vendor");
        let bios_version = read_dmi("/sys/class/dmi/id/bios_version");
        (manufacturer, model, serial, bios_vendor, bios_version)
    }

    #[cfg(target_os = "windows")]
    fn get_system_info() -> SystemInfo {
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
    fn get_system_info() -> SystemInfo {
        let manufacturer = Some("Apple".to_string());
        let mut model = None;
        let mut serial = None;

        if let Ok(output) = Command::new("system_profiler")
            .args(["SPHardwareDataType"])
            .output()
        {
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
    fn get_system_info() -> SystemInfo {
        let manufacturer = Command::new("sysctl")
            .args(["-n", "hw.vendor"])
            .output()
            .ok()
            .filter(|o| o.status.success())
            .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string());
        let model = Command::new("sysctl")
            .args(["-n", "hw.product"])
            .output()
            .ok()
            .filter(|o| o.status.success())
            .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string());
        (manufacturer, model, None, None, None)
    }

    #[cfg(not(any(
        target_os = "linux",
        target_os = "windows",
        target_os = "macos",
        target_os = "freebsd",
        target_os = "openbsd",
        target_os = "netbsd"
    )))]
    fn get_system_info() -> SystemInfo {
        (System::name(), System::host_name(), None, None, None)
    }

    #[cfg(target_os = "linux")]
    fn detect_gpus() -> Vec<GpuInfo> {
        let mut gpus = Vec::new();

        if let Ok(output) = Command::new("lspci").output() {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    if line.contains("VGA compatible controller")
                        || line.contains("3D controller")
                        || line.contains("Display controller")
                    {
                        if let Some(colon_pos) = line.find(": ") {
                            let device_info = &line[colon_pos + 2..];
                            let (vendor, model) = Self::parse_gpu_info(device_info);
                            gpus.push(GpuInfo {
                                model,
                                vendor,
                                memory_bytes: None,
                                driver_version: None,
                            });
                        }
                    }
                }
            }
        }

        if let Ok(output) = Command::new("nvidia-smi")
            .args(["--query-gpu=name", "--format=csv,noheader"])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    let model = line.trim().to_string();
                    if !model.is_empty() && !gpus.iter().any(|g| g.model.contains(&model)) {
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

        gpus
    }

    #[cfg(target_os = "macos")]
    fn detect_gpus() -> Vec<GpuInfo> {
        let mut gpus = Vec::new();

        if let Ok(output) = Command::new("system_profiler")
            .args(["SPDisplaysDataType", "-json"])
            .output()
        {
            if output.status.success() {
                if let Ok(json) = serde_json::from_slice::<serde_json::Value>(&output.stdout) {
                    if let Some(displays) =
                        json.get("SPDisplaysDataType").and_then(|d| d.as_array())
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

    #[cfg(target_os = "windows")]
    fn detect_gpus() -> Vec<GpuInfo> {
        let mut gpus = Vec::new();

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

    #[cfg(any(target_os = "freebsd", target_os = "openbsd", target_os = "netbsd"))]
    fn detect_gpus() -> Vec<GpuInfo> {
        let mut gpus = Vec::new();

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
                        current_vendor = line
                            .split('=')
                            .nth(1)
                            .map(|s| s.trim().trim_matches('\'').to_string());
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

    #[cfg(target_os = "linux")]
    fn parse_gpu_info(info: &str) -> (Option<String>, String) {
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
                if let Some(bracket_pos) = info.find('[') {
                    if let Some(end_pos) = info.find(']') {
                        model = info[bracket_pos + 1..end_pos].to_string();
                    }
                } else {
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
