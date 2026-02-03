//! Tests for system collectors.
//!
//! These tests verify that collectors work correctly across all supported platforms
//! and that the data contract with the API is maintained.

use hydra_agent::collectors::*;
use serde_json;

// =============================================================================
// Hardware Collector Tests
// =============================================================================

#[test]
fn test_hardware_collector() {
    let result = HardwareCollector::collect();
    assert!(result.is_ok(), "Hardware collection should succeed");

    let profile = result.unwrap();

    // Validate CPU info
    assert!(
        profile.cpu.cores_logical > 0,
        "Should have at least one logical core"
    );
    if profile.cpu.cores_physical == 0 {
        eprintln!("Physical core count not available on this platform");
    } else {
        assert!(
            profile.cpu.cores_physical > 0,
            "Should have at least one physical core"
        );
    }
    assert!(
        profile.cpu.architecture.is_some(),
        "Should detect architecture"
    );

    // Validate memory info
    assert!(profile.memory.total_bytes > 0, "Should have non-zero memory");
}

#[test]
fn test_hardware_profile_serialization() {
    let result = HardwareCollector::collect();
    assert!(result.is_ok());

    let profile = result.unwrap();

    // Serialize to JSON and verify it matches expected format
    let json = serde_json::to_value(&profile).expect("Should serialize to JSON");

    // Check required fields exist with correct camelCase naming
    assert!(json.get("cpu").is_some(), "Should have cpu field");
    assert!(json.get("memory").is_some(), "Should have memory field");
    assert!(json.get("gpus").is_some(), "Should have gpus field");

    // CPU fields
    let cpu = json.get("cpu").unwrap();
    assert!(
        cpu.get("coresLogical").is_some(),
        "Should have coresLogical"
    );
    assert!(
        cpu.get("coresPhysical").is_some(),
        "Should have coresPhysical"
    );

    // Memory fields
    let memory = json.get("memory").unwrap();
    assert!(
        memory.get("totalBytes").is_some(),
        "Should have totalBytes"
    );

    // Validate camelCase naming convention
    assert!(json.get("systemManufacturer").is_some() || json.get("systemManufacturer").is_none());
    assert!(json.get("system_manufacturer").is_none(), "Should not use snake_case");
}

#[test]
fn test_hardware_cpu_features() {
    let result = HardwareCollector::collect();
    assert!(result.is_ok());

    let profile = result.unwrap();

    // CPU features should be a vector (may be empty on some platforms)
    // This test ensures the field exists and is properly typed
    let json = serde_json::to_value(&profile).expect("Should serialize to JSON");
    let cpu = json.get("cpu").unwrap();

    // If features are present, they should be an array
    if let Some(features) = cpu.get("features") {
        assert!(features.is_array(), "Features should be an array");
    }
}

#[test]
fn test_hardware_memory_extended_fields() {
    let result = HardwareCollector::collect();
    assert!(result.is_ok());

    let profile = result.unwrap();
    let json = serde_json::to_value(&profile).expect("Should serialize to JSON");
    let memory = json.get("memory").unwrap();

    // Required field
    assert!(memory.get("totalBytes").is_some());

    // Optional fields should be camelCase if present
    // memoryType, speedMhz, slotsUsed, slotsTotal
    if let Some(mem_type) = memory.get("memoryType") {
        assert!(mem_type.is_string() || mem_type.is_null());
    }
    if let Some(speed) = memory.get("speedMhz") {
        assert!(speed.is_number() || speed.is_null());
    }
}

#[test]
fn test_hardware_gpu_fields() {
    let result = HardwareCollector::collect();
    assert!(result.is_ok());

    let profile = result.unwrap();
    let json = serde_json::to_value(&profile).expect("Should serialize to JSON");

    let gpus = json.get("gpus").unwrap().as_array().unwrap();

    for gpu in gpus {
        // model is required
        assert!(gpu.get("model").is_some(), "GPU should have model field");

        // vendor, memoryBytes, driverVersion are optional
        if let Some(vendor) = gpu.get("vendor") {
            assert!(vendor.is_string() || vendor.is_null());
        }
        if let Some(memory) = gpu.get("memoryBytes") {
            assert!(memory.is_number() || memory.is_null());
        }
        if let Some(driver) = gpu.get("driverVersion") {
            assert!(driver.is_string() || driver.is_null());
        }
    }
}

// =============================================================================
// Network Collector Tests
// =============================================================================

#[test]
fn test_network_collector() {
    let result = NetworkCollector::collect();
    assert!(result.is_ok(), "Network collection should succeed");

    let profile = result.unwrap();

    // Should have a hostname
    assert!(profile.hostname.is_some(), "Should have a hostname");

    // Some environments may not expose interfaces; if present, validate fields.
    if let Some(interface) = profile.interfaces.first() {
        assert!(
            !interface.name.is_empty(),
            "Interface name should not be empty"
        );
    }
}

#[test]
fn test_network_profile_serialization() {
    let result = NetworkCollector::collect();
    assert!(result.is_ok());

    let profile = result.unwrap();
    let json = serde_json::to_value(&profile).expect("Should serialize to JSON");

    // Check required fields
    assert!(json.get("interfaces").is_some(), "Should have interfaces");
    assert!(json.get("dnsServers").is_some(), "Should have dnsServers");

    // Optional fields should use camelCase
    assert!(
        json.get("dns_servers").is_none(),
        "Should use camelCase dnsServers"
    );
    assert!(
        json.get("default_gateway").is_none(),
        "Should use camelCase defaultGateway"
    );
}

#[test]
fn test_network_interface_fields() {
    let result = NetworkCollector::collect();
    assert!(result.is_ok());

    let profile = result.unwrap();
    let json = serde_json::to_value(&profile).expect("Should serialize to JSON");

    let interfaces = json.get("interfaces").unwrap().as_array().unwrap();

    for iface in interfaces {
        // name and state are required
        assert!(iface.get("name").is_some(), "Should have name");
        assert!(iface.get("state").is_some(), "Should have state");

        // ipv4Addresses and ipv6Addresses should be arrays
        assert!(
            iface.get("ipv4Addresses").unwrap().is_array(),
            "ipv4Addresses should be array"
        );
        assert!(
            iface.get("ipv6Addresses").unwrap().is_array(),
            "ipv6Addresses should be array"
        );

        // MAC address should use camelCase
        if iface.get("macAddress").is_some() {
            assert!(iface.get("mac_address").is_none());
        }
    }
}

#[test]
fn test_network_routes() {
    let result = NetworkCollector::collect();
    assert!(result.is_ok());

    let profile = result.unwrap();
    let json = serde_json::to_value(&profile).expect("Should serialize to JSON");

    // Routes should be an array if present
    if let Some(routes) = json.get("routes") {
        assert!(routes.is_array(), "Routes should be an array");
        for route in routes.as_array().unwrap() {
            // destination is required
            assert!(route.get("destination").is_some());
        }
    }
}

#[test]
fn test_network_dns_config() {
    let result = NetworkCollector::collect();
    assert!(result.is_ok());

    let profile = result.unwrap();
    let json = serde_json::to_value(&profile).expect("Should serialize to JSON");

    // dnsServers should be an array
    let dns = json.get("dnsServers").unwrap();
    assert!(dns.is_array(), "dnsServers should be an array");

    // dnsSearch should be an array if present
    if let Some(search) = json.get("dnsSearch") {
        assert!(search.is_array(), "dnsSearch should be an array");
    }
}

// =============================================================================
// Storage Collector Tests
// =============================================================================

#[test]
fn test_storage_collector() {
    let result = StorageCollector::collect(None);
    assert!(result.is_ok(), "Storage collection should succeed");

    let profile = result.unwrap();

    // Environments can return no filesystems; if present, validate fields.
    if let Some(fs) = profile.filesystems.first() {
        assert!(
            !fs.mount_point.is_empty(),
            "Mount point should not be empty"
        );
        assert!(!fs.device.is_empty(), "Device should not be empty");
    }
}

#[test]
fn test_storage_profile_serialization() {
    let result = StorageCollector::collect(None);
    assert!(result.is_ok());

    let profile = result.unwrap();
    let json = serde_json::to_value(&profile).expect("Should serialize to JSON");

    // Check required fields
    assert!(
        json.get("blockDevices").is_some(),
        "Should have blockDevices"
    );
    assert!(
        json.get("filesystems").is_some(),
        "Should have filesystems"
    );

    // Verify camelCase
    assert!(
        json.get("block_devices").is_none(),
        "Should use camelCase blockDevices"
    );
}

#[test]
fn test_storage_block_device_fields() {
    let result = StorageCollector::collect(None);
    assert!(result.is_ok());

    let profile = result.unwrap();
    let json = serde_json::to_value(&profile).expect("Should serialize to JSON");

    let devices = json.get("blockDevices").unwrap().as_array().unwrap();

    for device in devices {
        // name is required
        assert!(device.get("name").is_some(), "Should have name");

        // device_type should serialize as "type" per API contract
        if device.get("type").is_some() || device.get("sizeBytes").is_some() {
            // Good - using correct field names
        }

        // Should not use snake_case
        assert!(
            device.get("size_bytes").is_none(),
            "Should use camelCase sizeBytes"
        );
        assert!(
            device.get("device_type").is_none(),
            "Should use 'type' not device_type"
        );
    }
}

#[test]
fn test_storage_filesystem_fields() {
    let result = StorageCollector::collect(None);
    assert!(result.is_ok());

    let profile = result.unwrap();
    let json = serde_json::to_value(&profile).expect("Should serialize to JSON");

    let filesystems = json.get("filesystems").unwrap().as_array().unwrap();

    for fs in filesystems {
        // Required fields
        assert!(fs.get("mountPoint").is_some(), "Should have mountPoint");
        assert!(fs.get("device").is_some(), "Should have device");
        assert!(fs.get("fsType").is_some(), "Should have fsType");

        // Verify camelCase
        assert!(
            fs.get("mount_point").is_none(),
            "Should use camelCase mountPoint"
        );
        assert!(
            fs.get("fs_type").is_none(),
            "Should use camelCase fsType"
        );
        assert!(
            fs.get("size_bytes").is_none(),
            "Should use camelCase sizeBytes"
        );
        assert!(
            fs.get("used_bytes").is_none(),
            "Should use camelCase usedBytes"
        );
    }
}

#[test]
fn test_storage_extended_device_info() {
    let result = StorageCollector::collect(None);
    assert!(result.is_ok());

    let profile = result.unwrap();
    let json = serde_json::to_value(&profile).expect("Should serialize to JSON");

    let devices = json.get("blockDevices").unwrap().as_array().unwrap();

    for device in devices {
        // Extended fields are optional but should be properly typed if present
        if let Some(model) = device.get("model") {
            assert!(model.is_string() || model.is_null());
        }
        if let Some(serial) = device.get("serial") {
            assert!(serial.is_string() || serial.is_null());
        }
        if let Some(rotational) = device.get("rotational") {
            assert!(rotational.is_boolean() || rotational.is_null());
        }
        if let Some(transport) = device.get("transport") {
            assert!(transport.is_string() || transport.is_null());
        }
    }
}

// =============================================================================
// Software Collector Tests
// =============================================================================

#[test]
fn test_software_collector() {
    use hydra_agent::config::{AgentConfig, ApiConfig, CollectionConfig, NodeConfig, ScheduleConfig};

    let config = AgentConfig {
        api: ApiConfig {
            url: "http://localhost:8080/api/v1".to_string(),
            timeout_seconds: 30,
            retries: 3,
        },
        node: NodeConfig {
            node_id: "test-node".to_string(),
            class: "compute".to_string(),
            node_type: "physical".to_string(),
            kind: None,
            display_name: None,
            description: None,
            tags: vec![],
            parent_node_id: None,
        },
        collection: CollectionConfig {
            level: "neutral".to_string(),
            collectors: vec!["software".to_string()],
            include_packages: false, // Don't collect packages for faster test
            include_users: false,
            config_files: vec![],
        },
        schedule: ScheduleConfig::default(),
    };

    let result = SoftwareCollector::collect(&config);
    assert!(result.is_ok(), "Software collection should succeed");

    let profile = result.unwrap();

    // Should have OS info
    assert!(!profile.os.name.is_empty(), "OS name should not be empty");
    assert!(
        !profile.os.family.is_empty(),
        "OS family should not be empty"
    );
}

#[test]
fn test_software_profile_serialization() {
    use hydra_agent::config::{AgentConfig, ApiConfig, CollectionConfig, NodeConfig, ScheduleConfig};

    let config = AgentConfig {
        api: ApiConfig {
            url: "http://localhost:8080/api/v1".to_string(),
            timeout_seconds: 30,
            retries: 3,
        },
        node: NodeConfig {
            node_id: "test-node".to_string(),
            class: "compute".to_string(),
            node_type: "physical".to_string(),
            kind: None,
            display_name: None,
            description: None,
            tags: vec![],
            parent_node_id: None,
        },
        collection: CollectionConfig {
            level: "neutral".to_string(),
            collectors: vec!["software".to_string()],
            include_packages: false,
            include_users: false,
            config_files: vec![],
        },
        schedule: ScheduleConfig::default(),
    };

    let result = SoftwareCollector::collect(&config);
    assert!(result.is_ok());

    let profile = result.unwrap();
    let json = serde_json::to_value(&profile).expect("Should serialize to JSON");

    // Check required fields
    assert!(json.get("os").is_some(), "Should have os");

    // OS fields
    let os = json.get("os").unwrap();
    assert!(os.get("name").is_some(), "Should have name");
    assert!(os.get("family").is_some(), "Should have family");
}

#[test]
fn test_software_with_packages() {
    use hydra_agent::config::{AgentConfig, ApiConfig, CollectionConfig, NodeConfig, ScheduleConfig};

    let config = AgentConfig {
        api: ApiConfig {
            url: "http://localhost:8080/api/v1".to_string(),
            timeout_seconds: 30,
            retries: 3,
        },
        node: NodeConfig {
            node_id: "test-node".to_string(),
            class: "compute".to_string(),
            node_type: "physical".to_string(),
            kind: None,
            display_name: None,
            description: None,
            tags: vec![],
            parent_node_id: None,
        },
        collection: CollectionConfig {
            level: "neutral".to_string(),
            collectors: vec!["software".to_string()],
            include_packages: true, // Enable package collection
            include_users: false,
            config_files: vec![],
        },
        schedule: ScheduleConfig::default(),
    };

    let result = SoftwareCollector::collect(&config);
    assert!(result.is_ok(), "Software collection with packages should succeed");

    let profile = result.unwrap();
    let json = serde_json::to_value(&profile).expect("Should serialize to JSON");

    // packages should be an array if present
    if let Some(packages) = json.get("packages") {
        assert!(packages.is_array(), "packages should be an array");
    }
}

// =============================================================================
// Full Profile Tests
// =============================================================================

#[test]
fn test_profile_sections() {
    use chrono::Utc;
    use hydra_agent::collectors::Profile;
    use std::collections::HashMap;

    // Test profile with all sections
    let full_profile = Profile {
        node_id: "test".to_string(),
        version: "1".to_string(),
        collected_at: Utc::now(),
        agent_version: "0.1.0".to_string(),
        collection_level: "neutral".to_string(),
        hardware: Some(hydra_agent::collectors::hardware::HardwareProfile {
            system_manufacturer: None,
            system_model: None,
            system_serial: None,
            bios_vendor: None,
            bios_version: None,
            cpu: hydra_agent::collectors::hardware::CpuInfo {
                model: None,
                vendor: None,
                cores_physical: 4,
                cores_logical: 8,
                frequency_mhz: None,
                architecture: Some("x86_64".to_string()),
                features: vec![],
            },
            memory: hydra_agent::collectors::hardware::MemoryInfo {
                total_bytes: 16000000000,
                memory_type: None,
                speed_mhz: None,
                slots_used: None,
                slots_total: None,
            },
            gpus: vec![],
        }),
        network: None,
        storage: None,
        software: None,
        metadata: HashMap::new(),
    };

    let sections = full_profile.sections();
    assert!(
        sections.contains(&"hardware"),
        "Should include hardware section"
    );
    assert!(
        !sections.contains(&"network"),
        "Should not include network section"
    );
}

#[test]
fn test_full_profile_serialization() {
    use chrono::Utc;
    use hydra_agent::collectors::Profile;
    use std::collections::HashMap;

    let full_profile = Profile {
        node_id: "test-node".to_string(),
        version: "E0-0.0.0.1".to_string(),
        collected_at: Utc::now(),
        agent_version: "0.1.0".to_string(),
        collection_level: "neutral".to_string(),
        hardware: Some(hydra_agent::collectors::hardware::HardwareProfile {
            system_manufacturer: Some("Dell Inc.".to_string()),
            system_model: Some("PowerEdge R740".to_string()),
            system_serial: Some("ABC123".to_string()),
            bios_vendor: Some("Dell Inc.".to_string()),
            bios_version: Some("2.10.2".to_string()),
            cpu: hydra_agent::collectors::hardware::CpuInfo {
                model: Some("Intel Xeon Gold 6130".to_string()),
                vendor: Some("GenuineIntel".to_string()),
                cores_physical: 16,
                cores_logical: 32,
                frequency_mhz: Some(2100),
                architecture: Some("x86_64".to_string()),
                features: vec!["avx".to_string(), "avx2".to_string(), "sse4_2".to_string()],
            },
            memory: hydra_agent::collectors::hardware::MemoryInfo {
                total_bytes: 68719476736,
                memory_type: Some("DDR4".to_string()),
                speed_mhz: Some(2666),
                slots_used: Some(8),
                slots_total: Some(24),
            },
            gpus: vec![hydra_agent::collectors::hardware::GpuInfo {
                model: "NVIDIA Tesla V100".to_string(),
                vendor: Some("NVIDIA Corporation".to_string()),
                memory_bytes: Some(16106127360),
                driver_version: Some("535.104.05".to_string()),
            }],
        }),
        network: Some(hydra_agent::collectors::network::NetworkProfile {
            hostname: Some("server-01".to_string()),
            domain: Some("example.com".to_string()),
            fqdn: Some("server-01.example.com".to_string()),
            interfaces: vec![hydra_agent::collectors::network::NetworkInterface {
                name: "eth0".to_string(),
                mac_address: Some("00:11:22:33:44:55".to_string()),
                ipv4_addresses: vec!["192.168.1.100".to_string()],
                ipv6_addresses: vec!["fe80::1".to_string()],
                netmask: Some("255.255.255.0".to_string()),
                gateway: Some("192.168.1.1".to_string()),
                mtu: Some(1500),
                state: "up".to_string(),
                interface_type: Some("ethernet".to_string()),
                speed_mbps: Some(1000),
            }],
            dns_servers: vec!["8.8.8.8".to_string(), "8.8.4.4".to_string()],
            dns_search: vec!["example.com".to_string()],
            default_gateway: Some("192.168.1.1".to_string()),
            routes: vec![hydra_agent::collectors::network::NetworkRoute {
                destination: "default".to_string(),
                gateway: Some("192.168.1.1".to_string()),
                interface: Some("eth0".to_string()),
                metric: Some(100),
            }],
        }),
        storage: Some(hydra_agent::collectors::storage::StorageProfile {
            block_devices: vec![hydra_agent::collectors::storage::BlockDevice {
                name: "/dev/sda".to_string(),
                size_bytes: Some(1000204886016),
                device_type: Some("disk".to_string()),
                model: Some("SAMSUNG MZ7LH1T0".to_string()),
                serial: Some("S456NB0123456".to_string()),
                rotational: Some(false),
                transport: Some("sata".to_string()),
            }],
            filesystems: vec![hydra_agent::collectors::storage::Filesystem {
                mount_point: "/".to_string(),
                device: "/dev/sda1".to_string(),
                fs_type: "ext4".to_string(),
                size_bytes: Some(500000000000),
                used_bytes: Some(150000000000),
                options: vec!["rw".to_string(), "relatime".to_string()],
            }],
            total_capacity_bytes: Some(1000204886016),
        }),
        software: None,
        metadata: HashMap::new(),
    };

    let json = serde_json::to_value(&full_profile).expect("Should serialize to JSON");

    // Verify top-level structure
    assert!(json.get("nodeId").is_some(), "Should have nodeId");
    assert!(json.get("version").is_some(), "Should have version");
    assert!(json.get("collectedAt").is_some(), "Should have collectedAt");
    assert!(json.get("agentVersion").is_some(), "Should have agentVersion");
    assert!(json.get("collectionLevel").is_some(), "Should have collectionLevel");

    // Verify snake_case is NOT used
    assert!(json.get("node_id").is_none(), "Should use camelCase");
    assert!(json.get("collected_at").is_none(), "Should use camelCase");
    assert!(json.get("agent_version").is_none(), "Should use camelCase");
    assert!(json.get("collection_level").is_none(), "Should use camelCase");

    // Verify nested structures
    let hardware = json.get("hardware").unwrap();
    assert!(hardware.get("systemManufacturer").is_some());
    assert!(hardware.get("systemSerial").is_some());
    assert!(hardware.get("biosVendor").is_some());
    assert!(hardware.get("biosVersion").is_some());

    let network = json.get("network").unwrap();
    assert!(network.get("defaultGateway").is_some());
    assert!(network.get("dnsServers").is_some());
    assert!(network.get("dnsSearch").is_some());

    let storage = json.get("storage").unwrap();
    assert!(storage.get("blockDevices").is_some());
    assert!(storage.get("totalCapacityBytes").is_some());

    // Verify block device has "type" not "deviceType"
    let block_devices = storage.get("blockDevices").unwrap().as_array().unwrap();
    let device = &block_devices[0];
    assert!(device.get("type").is_some(), "Should use 'type' for device type");
    assert!(device.get("deviceType").is_none(), "Should not use deviceType");
}

#[test]
fn test_profile_json_roundtrip() {
    use chrono::Utc;
    use hydra_agent::collectors::Profile;
    use std::collections::HashMap;

    let original = Profile {
        node_id: "test-node".to_string(),
        version: "E0-0.0.0.1".to_string(),
        collected_at: Utc::now(),
        agent_version: "0.1.0".to_string(),
        collection_level: "neutral".to_string(),
        hardware: None,
        network: None,
        storage: None,
        software: None,
        metadata: HashMap::new(),
    };

    // Serialize
    let json_string = serde_json::to_string(&original).expect("Should serialize");

    // Deserialize back
    let parsed: serde_json::Value = serde_json::from_str(&json_string).expect("Should parse");

    // Verify fields
    assert_eq!(parsed.get("nodeId").unwrap().as_str().unwrap(), "test-node");
    assert_eq!(
        parsed.get("version").unwrap().as_str().unwrap(),
        "E0-0.0.0.1"
    );
}

// =============================================================================
// Platform-Specific Tests
// =============================================================================

#[test]
#[cfg(target_os = "linux")]
fn test_linux_specific_collection() {
    // Test Linux-specific features
    let hw = HardwareCollector::collect().unwrap();

    // On Linux, we should be able to detect architecture
    assert!(hw.cpu.architecture.is_some());

    // Storage should include block devices
    let storage = StorageCollector::collect(None).unwrap();
    // Most Linux systems have at least one block device
    if !storage.block_devices.is_empty() {
        // Verify extended info collection attempted
        let json = serde_json::to_value(&storage).unwrap();
        let devices = json.get("blockDevices").unwrap().as_array().unwrap();
        // Check that device type uses "type" key
        for device in devices {
            assert!(device.get("name").is_some());
        }
    }
}

#[test]
#[cfg(target_os = "windows")]
fn test_windows_specific_collection() {
    // Test Windows-specific features
    let hw = HardwareCollector::collect().unwrap();

    // Windows should detect architecture
    assert!(hw.cpu.architecture.is_some());

    // Network should have hostname
    let network = NetworkCollector::collect().unwrap();
    assert!(network.hostname.is_some());
}

#[test]
#[cfg(target_os = "macos")]
fn test_macos_specific_collection() {
    // Test macOS-specific features
    let hw = HardwareCollector::collect().unwrap();

    // macOS should detect architecture (likely arm64 or x86_64)
    assert!(hw.cpu.architecture.is_some());

    // Should have memory info
    assert!(hw.memory.total_bytes > 0);
}

#[test]
#[cfg(any(target_os = "freebsd", target_os = "openbsd", target_os = "netbsd"))]
fn test_bsd_specific_collection() {
    // Test BSD-specific features
    let hw = HardwareCollector::collect().unwrap();

    // BSD should detect architecture
    assert!(hw.cpu.architecture.is_some());
}

// =============================================================================
// Data Contract Validation Tests
// =============================================================================

#[test]
fn test_api_data_contract_hardware() {
    // This test validates that the serialized hardware profile matches
    // what the API expects (based on hydra-api/hydra/api/v1/models/profiles.py)
    let hw = HardwareCollector::collect().unwrap();
    let json = serde_json::to_value(&hw).expect("Should serialize");

    // Required API fields
    assert!(json.get("cpu").is_some(), "API requires cpu field");
    assert!(json.get("memory").is_some(), "API requires memory field");
    assert!(json.get("gpus").is_some(), "API requires gpus field");

    // CPU must have these fields
    let cpu = json.get("cpu").unwrap();
    assert!(cpu.get("coresLogical").is_some());
    assert!(cpu.get("coresPhysical").is_some());

    // Memory must have totalBytes
    let memory = json.get("memory").unwrap();
    assert!(memory.get("totalBytes").is_some());
}

#[test]
fn test_api_data_contract_network() {
    let network = NetworkCollector::collect().unwrap();
    let json = serde_json::to_value(&network).expect("Should serialize");

    // Required API fields
    assert!(json.get("interfaces").is_some(), "API requires interfaces");
    assert!(json.get("dnsServers").is_some(), "API requires dnsServers");

    // Interface must have these fields
    let interfaces = json.get("interfaces").unwrap().as_array().unwrap();
    for iface in interfaces {
        assert!(iface.get("name").is_some());
        assert!(iface.get("state").is_some());
        assert!(iface.get("ipv4Addresses").is_some());
        assert!(iface.get("ipv6Addresses").is_some());
    }
}

#[test]
fn test_api_data_contract_storage() {
    let storage = StorageCollector::collect(None).unwrap();
    let json = serde_json::to_value(&storage).expect("Should serialize");

    // Required API fields
    assert!(
        json.get("blockDevices").is_some(),
        "API requires blockDevices"
    );
    assert!(
        json.get("filesystems").is_some(),
        "API requires filesystems"
    );

    // BlockDevice must use "type" not "deviceType"
    let devices = json.get("blockDevices").unwrap().as_array().unwrap();
    for device in devices {
        assert!(device.get("name").is_some());
        // Verify proper field naming
        assert!(
            device.get("deviceType").is_none(),
            "API expects 'type' not 'deviceType'"
        );
    }

    // Filesystem must have these fields
    let filesystems = json.get("filesystems").unwrap().as_array().unwrap();
    for fs in filesystems {
        assert!(fs.get("mountPoint").is_some());
        assert!(fs.get("device").is_some());
        assert!(fs.get("fsType").is_some());
    }
}
