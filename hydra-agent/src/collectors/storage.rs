//! Storage information collector.

use anyhow::Result;
use serde::Serialize;
use sysinfo::Disks;

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct StorageProfile {
    pub block_devices: Vec<BlockDevice>,
    pub filesystems: Vec<Filesystem>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub total_capacity_bytes: Option<u64>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BlockDevice {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub size_bytes: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub device_type: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Filesystem {
    pub mount_point: String,
    pub device: String,
    pub fs_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub size_bytes: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub used_bytes: Option<u64>,
}

pub struct StorageCollector;

impl StorageCollector {
    /// Collect storage information.
    pub fn collect() -> Result<StorageProfile> {
        let disks = Disks::new_with_refreshed_list();

        let mut block_devices = Vec::new();
        let mut filesystems = Vec::new();
        let mut total_capacity: u64 = 0;
        let mut seen_devices = std::collections::HashSet::new();

        for disk in disks.list() {
            let name = disk.name().to_string_lossy().to_string();
            let mount_point = disk.mount_point().to_string_lossy().to_string();
            let fs_type = disk.file_system().to_string_lossy().to_string();
            let total_space = disk.total_space();
            let available_space = disk.available_space();
            let used_space = total_space.saturating_sub(available_space);

            // Track unique block devices
            if !seen_devices.contains(&name) {
                seen_devices.insert(name.clone());
                block_devices.push(BlockDevice {
                    name: name.clone(),
                    size_bytes: Some(total_space),
                    device_type: if disk.is_removable() {
                        Some("removable".to_string())
                    } else {
                        Some("fixed".to_string())
                    },
                });
            }

            filesystems.push(Filesystem {
                mount_point,
                device: name,
                fs_type,
                size_bytes: Some(total_space),
                used_bytes: Some(used_space),
            });

            total_capacity += total_space;
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
}
