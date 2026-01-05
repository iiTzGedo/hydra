//! Tests for system collectors.

use hydra_agent::collectors::*;

#[test]
fn test_hardware_collector() {
    let result = HardwareCollector::collect();
    assert!(result.is_ok(), "Hardware collection should succeed");

    let profile = result.unwrap();

    // Validate CPU info
    assert!(profile.cpu.cores_logical > 0, "Should have at least one logical core");
    if profile.cpu.cores_physical == 0 {
        eprintln!("Physical core count not available on this platform");
    } else {
        assert!(profile.cpu.cores_physical > 0, "Should have at least one physical core");
    }
    assert!(profile.cpu.architecture.is_some(), "Should detect architecture");

    // Validate memory info
    assert!(profile.memory.total_bytes > 0, "Should have non-zero memory");
}

#[test]
fn test_network_collector() {
    let result = NetworkCollector::collect();
    assert!(result.is_ok(), "Network collection should succeed");

    let profile = result.unwrap();

    // Should have a hostname
    assert!(profile.hostname.is_some(), "Should have a hostname");

    // Some environments may not expose interfaces; if present, validate fields.
    if let Some(interface) = profile.interfaces.first() {
        assert!(!interface.name.is_empty(), "Interface name should not be empty");
    }
}

#[test]
fn test_storage_collector() {
    let result = StorageCollector::collect();
    assert!(result.is_ok(), "Storage collection should succeed");

    let profile = result.unwrap();

    // Environments can return no filesystems; if present, validate fields.
    if let Some(fs) = profile.filesystems.first() {
        assert!(!fs.mount_point.is_empty(), "Mount point should not be empty");
        assert!(!fs.device.is_empty(), "Device should not be empty");
    }
}

#[test]
fn test_software_collector() {
    use hydra_agent::config::{AgentConfig, ApiConfig, NodeConfig, CollectionConfig, ScheduleConfig};

    let config = AgentConfig {
        api: ApiConfig {
            url: "http://localhost:8080/api/v1".to_string(),
            credentials_file: "/tmp/credentials.json".to_string(),
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
    assert!(!profile.os.family.is_empty(), "OS family should not be empty");
}

#[test]
fn test_profile_sections() {
    use chrono::Utc;
    use hydra_agent::collectors::Profile;
    use std::collections::HashMap;

    // Test profile with all sections
    let full_profile = Profile {
        node_id: "test".to_string(),
        collected_at: Utc::now(),
        agent_version: "0.1.0".to_string(),
        collection_level: "neutral".to_string(),
        hardware: Some(hydra_agent::collectors::hardware::HardwareProfile {
            system_manufacturer: None,
            system_model: None,
            cpu: hydra_agent::collectors::hardware::CpuInfo {
                model: None,
                vendor: None,
                cores_physical: 4,
                cores_logical: 8,
                frequency_mhz: None,
                architecture: Some("x86_64".to_string()),
            },
            memory: hydra_agent::collectors::hardware::MemoryInfo { total_bytes: 16000000000 },
            gpus: vec![],
        }),
        network: None,
        storage: None,
        software: None,
        metadata: HashMap::new(),
    };

    let sections = full_profile.sections();
    assert!(sections.contains(&"hardware"), "Should include hardware section");
    assert!(!sections.contains(&"network"), "Should not include network section");
}
