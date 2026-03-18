//! Storage information collector.
//!
//! Collects block device and filesystem information using the sysinfo
//! library and platform-specific commands for extended details.

use anyhow::Result;
use serde::Serialize;
use sysinfo::Disks;

/// Storage profile containing block devices and filesystems.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct StorageProfile {
    /// List of physical block devices
    pub block_devices: Vec<BlockDevice>,
    /// List of mounted filesystems
    pub filesystems: Vec<Filesystem>,
    /// Total storage capacity in bytes
    #[serde(skip_serializing_if = "Option::is_none")]
    pub total_capacity_bytes: Option<u64>,
}

/// Block device information.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BlockDevice {
    /// Device name (e.g., "/dev/sda", "PhysicalDrive0")
    pub name: String,
    /// Device size in bytes
    #[serde(skip_serializing_if = "Option::is_none")]
    pub size_bytes: Option<u64>,
    /// Device type (e.g., "disk", "removable")
    #[serde(skip_serializing_if = "Option::is_none", rename = "type")]
    pub device_type: Option<String>,
    /// Device model name
    #[serde(skip_serializing_if = "Option::is_none")]
    pub model: Option<String>,
    /// Device serial number
    #[serde(skip_serializing_if = "Option::is_none")]
    pub serial: Option<String>,
    /// Whether the device is rotational (HDD) or not (SSD)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rotational: Option<bool>,
    /// Bus transport type (e.g., "sata", "nvme", "usb")
    #[serde(skip_serializing_if = "Option::is_none")]
    pub transport: Option<String>,
}

/// Filesystem information.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Filesystem {
    /// Mount point path
    pub mount_point: String,
    /// Device backing this filesystem
    pub device: String,
    /// Filesystem type (e.g., "ext4", "ntfs", "apfs")
    pub fs_type: String,
    /// Total filesystem size in bytes
    #[serde(skip_serializing_if = "Option::is_none")]
    pub size_bytes: Option<u64>,
    /// Used space in bytes
    #[serde(skip_serializing_if = "Option::is_none")]
    pub used_bytes: Option<u64>,
    /// Mount options
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub options: Vec<String>,
}

struct ExtendedBlockInfo {
    model: Option<String>,
    serial: Option<String>,
    rotational: Option<bool>,
    transport: Option<String>,
}

/// Collector for storage information.
pub struct StorageCollector;

impl StorageCollector {
    /// Collects storage information from the current system.
    ///
    /// Gathers block device details and mounted filesystem information
    /// using the sysinfo library and platform-specific commands.
    ///
    /// The `node_kind` parameter controls how total capacity is calculated:
    /// - For container-based nodes (`docker`, `kubernetes-pod`, `lxc`), all
    ///   filesystems count toward capacity since overlay/bind mounts ARE the
    ///   node's storage.
    /// - For all other nodes, virtual/overlay filesystems are excluded to avoid
    ///   double-counting storage that references the same underlying block device.
    ///
    /// # Returns
    ///
    /// A storage profile containing devices and filesystems.
    ///
    /// # Errors
    ///
    /// Returns an error if storage information cannot be retrieved.
    pub fn collect(node_kind: Option<&str>) -> Result<StorageProfile> {
        let is_container_node = matches!(node_kind, Some("docker" | "kubernetes-pod" | "lxc"));
        let disks = Disks::new_with_refreshed_list();

        let mut block_devices = Vec::new();
        let mut filesystems = Vec::new();
        let mut total_capacity: u64 = 0;
        let mut seen_devices = std::collections::HashSet::new();

        let extended_info = Self::get_block_device_info();

        for disk in disks.list() {
            let name = disk.name().to_string_lossy().to_string();
            let mount_point = disk.mount_point().to_string_lossy().to_string();
            let fs_type = disk.file_system().to_string_lossy().to_string();
            let total_space = disk.total_space();
            let available_space = disk.available_space();
            let used_space = total_space.saturating_sub(available_space);

            if !seen_devices.contains(&name) {
                seen_devices.insert(name.clone());

                let ext = extended_info.get(&name);

                block_devices.push(BlockDevice {
                    name: name.clone(),
                    size_bytes: Some(total_space),
                    device_type: if disk.is_removable() {
                        Some("removable".to_string())
                    } else {
                        Some("disk".to_string())
                    },
                    model: ext.and_then(|e| e.model.clone()),
                    serial: ext.and_then(|e| e.serial.clone()),
                    rotational: ext.and_then(|e| e.rotational),
                    transport: ext.and_then(|e| e.transport.clone()),
                });
            }

            filesystems.push(Filesystem {
                mount_point: mount_point.clone(),
                device: name,
                fs_type: fs_type.clone(),
                size_bytes: Some(total_space),
                used_bytes: Some(used_space),
                options: vec![],
            });

            // For container-based nodes (docker, k8s-pod), overlay IS the real
            // storage—count everything. For all other nodes, exclude virtual/overlay
            // filesystems that reference the same underlying block device to avoid
            // double-counting.
            if is_container_node || !Self::is_virtual_filesystem(&fs_type, &mount_point) {
                total_capacity += total_space;
            }
        }

        Ok(StorageProfile {
            block_devices,
            filesystems,
            total_capacity_bytes: if total_capacity > 0 {
                Some(total_capacity)
            } else {
                None
            },
        })
    }

    /// Returns true if the filesystem is virtual/overlay and should not count
    /// toward total physical capacity. These filesystems typically reference
    /// the same underlying block device and would cause double-counting.
    fn is_virtual_filesystem(fs_type: &str, mount_point: &str) -> bool {
        matches!(
            fs_type,
            "overlay" | "overlay2" | "tmpfs" | "devtmpfs" | "squashfs" | "fuse.snapfuse"
        ) || mount_point.starts_with("/var/lib/docker/")
            || mount_point.starts_with("/snap/")
    }

    #[cfg(target_os = "linux")]
    fn get_block_device_info() -> std::collections::HashMap<String, ExtendedBlockInfo> {
        use std::process::Command;
        let mut info = std::collections::HashMap::new();

        // Use JSON output to handle multi-word model names correctly
        if let Ok(output) = Command::new("lsblk")
            .args(["-o", "NAME,MODEL,SERIAL,ROTA,TRAN", "-n", "-d", "-J"])
            .output()
        {
            if output.status.success() {
                if let Ok(json) = serde_json::from_slice::<serde_json::Value>(&output.stdout) {
                    if let Some(devices) = json.get("blockdevices").and_then(|d| d.as_array()) {
                        for device in devices {
                            let name_raw = device
                                .get("name")
                                .and_then(|n| n.as_str())
                                .unwrap_or_default();
                            if name_raw.is_empty() {
                                continue;
                            }
                            let name = format!("/dev/{}", name_raw);

                            let model = device
                                .get("model")
                                .and_then(|v| v.as_str())
                                .map(|s| s.trim().to_string())
                                .filter(|s| !s.is_empty());
                            let serial = device
                                .get("serial")
                                .and_then(|v| v.as_str())
                                .map(|s| s.trim().to_string())
                                .filter(|s| !s.is_empty());
                            let rotational = device.get("rota").and_then(|v| v.as_bool());
                            let transport = device
                                .get("tran")
                                .and_then(|v| v.as_str())
                                .map(|s| s.trim().to_string())
                                .filter(|s| !s.is_empty());

                            info.insert(
                                name,
                                ExtendedBlockInfo {
                                    model,
                                    serial,
                                    rotational,
                                    transport,
                                },
                            );
                        }
                    }
                }
            }
        }

        // Fallback to key-value pairs if JSON is not supported (older lsblk)
        if info.is_empty() {
            if let Ok(output) = Command::new("lsblk")
                .args(["-o", "NAME,MODEL,SERIAL,ROTA,TRAN", "-n", "-d", "-P"])
                .output()
            {
                if output.status.success() {
                    let stdout = String::from_utf8_lossy(&output.stdout);
                    for line in stdout.lines() {
                        let mut name = String::new();
                        let mut model = None;
                        let mut serial = None;
                        let mut rotational = None;
                        let mut transport = None;

                        // Parse KEY="VALUE" pairs
                        for pair in line.split_whitespace() {
                            if let Some((key, val)) = pair.split_once('=') {
                                let val = val.trim_matches('"');
                                match key {
                                    "NAME" => name = format!("/dev/{}", val),
                                    "MODEL" if !val.is_empty() => model = Some(val.to_string()),
                                    "SERIAL" if !val.is_empty() => serial = Some(val.to_string()),
                                    "ROTA" => {
                                        rotational = match val {
                                            "0" => Some(false),
                                            "1" => Some(true),
                                            _ => None,
                                        }
                                    }
                                    "TRAN" if !val.is_empty() => transport = Some(val.to_string()),
                                    _ => {}
                                }
                            }
                        }

                        if !name.is_empty() {
                            info.insert(
                                name,
                                ExtendedBlockInfo {
                                    model,
                                    serial,
                                    rotational,
                                    transport,
                                },
                            );
                        }
                    }
                }
            }
        }

        info
    }

    #[cfg(target_os = "windows")]
    fn get_block_device_info() -> std::collections::HashMap<String, ExtendedBlockInfo> {
        use std::process::Command;
        let mut info = std::collections::HashMap::new();

        if let Ok(output) = Command::new("powershell")
            .args([
                "-NoProfile", "-Command",
                "Get-PhysicalDisk | Select-Object DeviceId, FriendlyName, SerialNumber, MediaType, BusType | \
                 ForEach-Object { \"$($_.DeviceId)|$($_.FriendlyName)|$($_.SerialNumber)|$($_.MediaType)|$($_.BusType)\" }"
            ])
            .output()
        {
            if output.status.success() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    let parts: Vec<&str> = line.split('|').collect();
                    if parts.len() < 5 {
                        continue;
                    }

                    let name = format!("PhysicalDrive{}", parts[0].trim());
                    let model = Some(parts[1].trim().to_string()).filter(|s| !s.is_empty());
                    let serial = Some(parts[2].trim().to_string()).filter(|s| !s.is_empty());
                    let rotational = match parts[3].trim() {
                        "HDD" => Some(true),
                        "SSD" | "SCM" => Some(false),
                        _ => None,
                    };
                    let transport = Some(parts[4].trim().to_string()).filter(|s| !s.is_empty());

                    info.insert(name, ExtendedBlockInfo {
                        model,
                        serial,
                        rotational,
                        transport,
                    });
                }
            }
        }

        info
    }

    #[cfg(not(any(target_os = "linux", target_os = "windows")))]
    fn get_block_device_info() -> std::collections::HashMap<String, ExtendedBlockInfo> {
        std::collections::HashMap::new()
    }
}
