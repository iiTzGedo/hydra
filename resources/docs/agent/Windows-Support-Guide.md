# Hydra Agent Windows Support Guide

> **Status**: Planned Feature
> **Target Version**: v0.4.0
> **Document Version**: 1.0

This document outlines the implementation plan for adding Windows support to the Hydra Agent, including platform-specific considerations, architectural changes, and integration with existing workflows.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Changes](#architecture-changes)
3. [Platform Abstractions](#platform-abstractions)
4. [Service Management](#service-management)
5. [Credential Vault](#credential-vault)
6. [Collectors](#collectors)
7. [Installation & Distribution](#installation--distribution)
8. [CLI Adaptations](#cli-adaptations)
9. [Testing Strategy](#testing-strategy)
10. [Implementation Phases](#implementation-phases)

---

## Overview

### Current State

The Hydra Agent currently supports:
- Linux (amd64, arm64, armv7)
- macOS (Intel, Apple Silicon)
- FreeBSD (amd64)

### Windows Target Platforms

| Target | Rust Target Triple | Notes |
|--------|-------------------|-------|
| Windows x64 | `x86_64-pc-windows-msvc` | Primary target |
| Windows ARM64 | `aarch64-pc-windows-msvc` | Surface Pro X, etc. |
| Windows x86 (32-bit) | `i686-pc-windows-msvc` | Legacy support |

### Key Differences from Unix

| Aspect | Unix | Windows |
|--------|------|---------|
| Service Management | systemd/launchd/cron | Windows Services / Task Scheduler |
| File Paths | `/etc/hydra/`, `/var/cv/hydra/` | `C:\ProgramData\Hydra\` |
| Binary Extension | None | `.exe` |
| Permissions | POSIX (chmod 700) | NTFS ACLs |
| Shell | bash/zsh | PowerShell / cmd.exe |
| Package Managers | apt/dnf/brew/pkg | winget/chocolatey/scoop |

---

## Architecture Changes

### 1. Platform Abstraction Layer

Create a new `platform` module to abstract OS-specific operations:

```
hydra-agent/src/
├── platform/
│   ├── mod.rs           # Platform detection and trait definitions
│   ├── unix.rs          # Unix-family implementations
│   ├── windows.rs       # Windows implementations
│   └── paths.rs         # Platform-specific path resolution
```

**Core Traits:**

```rust
// src/platform/mod.rs

pub trait PlatformService {
    /// Install as a system service
    fn install_service(&self, config: &ServiceConfig) -> Result<()>;

    /// Uninstall system service
    fn uninstall_service(&self, purge: bool) -> Result<()>;

    /// Start the service
    fn start_service(&self) -> Result<()>;

    /// Stop the service
    fn stop_service(&self) -> Result<()>;

    /// Get service status
    fn service_status(&self) -> Result<ServiceStatus>;

    /// View service logs
    fn view_logs(&self, lines: u32, follow: bool) -> Result<()>;
}

pub trait PlatformPaths {
    /// Default config file path
    fn config_path(&self) -> PathBuf;

    /// Credential vault directory
    fn vault_path(&self) -> PathBuf;

    /// Log directory
    fn log_path(&self) -> PathBuf;

    /// Binary installation directory
    fn install_path(&self) -> PathBuf;
}

pub trait PlatformPermissions {
    /// Set restricted permissions on a file
    fn set_restricted_permissions(&self, path: &Path) -> Result<()>;

    /// Check if running as administrator/root
    fn is_elevated(&self) -> bool;
}
```

### 2. Conditional Compilation Structure

Use `#[cfg(target_os = "...")]` attributes strategically:

```rust
// src/platform/mod.rs

#[cfg(unix)]
mod unix;
#[cfg(unix)]
pub use unix::*;

#[cfg(windows)]
mod windows;
#[cfg(windows)]
pub use windows::*;

// Cross-platform interface
pub fn get_platform() -> Box<dyn Platform> {
    #[cfg(unix)]
    return Box::new(unix::UnixPlatform::new());

    #[cfg(windows)]
    return Box::new(windows::WindowsPlatform::new());
}
```

---

## Service Management

### Windows Services Architecture

Windows services are managed through the Service Control Manager (SCM). The agent needs to:

1. **Register as a Windows Service**
2. **Implement service lifecycle callbacks**
3. **Support recovery options**

### Implementation Using `windows-service` Crate

```toml
# Cargo.toml additions for Windows
[target.'cfg(windows)'.dependencies]
windows-service = "0.6"
winreg = "0.52"
```

**Service Implementation:**

```rust
// src/platform/windows/service.rs

use windows_service::{
    define_windows_service,
    service::{
        ServiceControl, ServiceControlAccept, ServiceExitCode,
        ServiceState, ServiceStatus, ServiceType,
    },
    service_control_handler::{self, ServiceControlHandlerResult},
    service_dispatcher,
};

const SERVICE_NAME: &str = "HydraAgent";
const SERVICE_DISPLAY_NAME: &str = "Hydra Agent";
const SERVICE_DESCRIPTION: &str = "Infrastructure profiling agent for the Hydra platform";

define_windows_service!(ffi_service_main, service_main);

fn service_main(arguments: Vec<OsString>) {
    if let Err(e) = run_service(arguments) {
        // Log error
    }
}

fn run_service(_arguments: Vec<OsString>) -> Result<()> {
    let event_handler = move |control_event| -> ServiceControlHandlerResult {
        match control_event {
            ServiceControl::Stop => {
                // Signal shutdown
                ServiceControlHandlerResult::NoError
            }
            ServiceControl::Interrogate => ServiceControlHandlerResult::NoError,
            _ => ServiceControlHandlerResult::NotImplemented,
        }
    };

    let status_handle = service_control_handler::register(SERVICE_NAME, event_handler)?;

    // Set service as running
    status_handle.set_service_status(ServiceStatus {
        service_type: ServiceType::OWN_PROCESS,
        current_state: ServiceState::Running,
        controls_accepted: ServiceControlAccept::STOP,
        exit_code: ServiceExitCode::Win32(0),
        checkpoint: 0,
        wait_hint: Duration::default(),
        process_id: None,
    })?;

    // Run the agent
    run_agent_loop()?;

    // Set service as stopped
    status_handle.set_service_status(ServiceStatus {
        service_type: ServiceType::OWN_PROCESS,
        current_state: ServiceState::Stopped,
        controls_accepted: ServiceControlAccept::empty(),
        exit_code: ServiceExitCode::Win32(0),
        checkpoint: 0,
        wait_hint: Duration::default(),
        process_id: None,
    })?;

    Ok(())
}
```

### Service Installation

```rust
// src/platform/windows/service.rs

use windows_service::{
    service::{ServiceAccess, ServiceErrorControl, ServiceInfo, ServiceStartType},
    service_manager::{ServiceManager, ServiceManagerAccess},
};

pub fn install_windows_service(config_path: &Path) -> Result<()> {
    let manager = ServiceManager::local_computer(
        None::<&str>,
        ServiceManagerAccess::CREATE_SERVICE,
    )?;

    let binary_path = std::env::current_exe()?;
    let service_binary_path = format!(
        "\"{}\" service run --config \"{}\"",
        binary_path.display(),
        config_path.display()
    );

    let service_info = ServiceInfo {
        name: OsString::from(SERVICE_NAME),
        display_name: OsString::from(SERVICE_DISPLAY_NAME),
        service_type: ServiceType::OWN_PROCESS,
        start_type: ServiceStartType::AutoStart,
        error_control: ServiceErrorControl::Normal,
        executable_path: PathBuf::from(&service_binary_path),
        launch_arguments: vec![],
        dependencies: vec![],
        account_name: None, // LocalSystem
        account_password: None,
    };

    let service = manager.create_service(&service_info, ServiceAccess::CHANGE_CONFIG)?;

    // Set service description
    service.set_description(SERVICE_DESCRIPTION)?;

    // Configure recovery options
    let recovery_actions = vec![
        ServiceAction {
            action_type: ServiceActionType::Restart,
            delay: Duration::from_secs(60),
        },
        ServiceAction {
            action_type: ServiceActionType::Restart,
            delay: Duration::from_secs(120),
        },
        ServiceAction {
            action_type: ServiceActionType::None,
            delay: Duration::default(),
        },
    ];
    service.update_failure_actions(recovery_actions, Duration::from_secs(86400))?;

    Ok(())
}
```

### Task Scheduler Alternative

For users who prefer Task Scheduler over Windows Services:

```rust
// src/platform/windows/scheduler.rs

use std::process::Command;

pub fn create_scheduled_task(
    install_dir: &Path,
    config_path: &Path,
    schedule: &str, // e.g., "HOURLY" or custom trigger
) -> Result<()> {
    let binary_path = install_dir.join("hydra-agent.exe");

    // Delete existing task if present
    let _ = Command::new("schtasks")
        .args(["/Delete", "/TN", "HydraAgent", "/F"])
        .output();

    // Create new scheduled task
    let status = Command::new("schtasks")
        .args([
            "/Create",
            "/TN", "HydraAgent",
            "/TR", &format!("\"{}\" run --once --config \"{}\"",
                binary_path.display(), config_path.display()),
            "/SC", schedule,
            "/RU", "SYSTEM",
            "/RL", "HIGHEST",
            "/F",
        ])
        .status()?;

    if !status.success() {
        return Err(anyhow!("Failed to create scheduled task"));
    }

    Ok(())
}

// Common schedules
pub const SCHEDULE_HOURLY: &str = "HOURLY";
pub const SCHEDULE_DAILY: &str = "DAILY";
pub const SCHEDULE_ON_BOOT: &str = "ONSTART";
```

---

## Credential Vault

### Windows Credential Storage

On Windows, use DPAPI (Data Protection API) for encryption:

```rust
// src/vault/windows.rs

use winapi::um::dpapi::{CryptProtectData, CryptUnprotectData};
use winapi::um::wincrypt::DATA_BLOB;

pub struct WindowsVault {
    vault_dir: PathBuf,
}

impl WindowsVault {
    pub fn new() -> Result<Self> {
        let vault_dir = PathBuf::from(r"C:\ProgramData\Hydra\vault");
        std::fs::create_dir_all(&vault_dir)?;

        // Set restrictive ACLs
        set_admin_only_acl(&vault_dir)?;

        Ok(Self { vault_dir })
    }

    fn encrypt_data(&self, data: &[u8]) -> Result<Vec<u8>> {
        unsafe {
            let mut input_blob = DATA_BLOB {
                cbData: data.len() as u32,
                pbData: data.as_ptr() as *mut u8,
            };

            let mut output_blob = DATA_BLOB {
                cbData: 0,
                pbData: std::ptr::null_mut(),
            };

            if CryptProtectData(
                &mut input_blob,
                std::ptr::null(),
                std::ptr::null_mut(),
                std::ptr::null_mut(),
                std::ptr::null_mut(),
                0,
                &mut output_blob,
            ) == 0 {
                return Err(anyhow!("DPAPI encryption failed"));
            }

            let encrypted = std::slice::from_raw_parts(
                output_blob.pbData,
                output_blob.cbData as usize,
            ).to_vec();

            // Free DPAPI-allocated memory
            winapi::um::winbase::LocalFree(output_blob.pbData as *mut _);

            Ok(encrypted)
        }
    }

    fn decrypt_data(&self, encrypted: &[u8]) -> Result<Vec<u8>> {
        unsafe {
            let mut input_blob = DATA_BLOB {
                cbData: encrypted.len() as u32,
                pbData: encrypted.as_ptr() as *mut u8,
            };

            let mut output_blob = DATA_BLOB {
                cbData: 0,
                pbData: std::ptr::null_mut(),
            };

            if CryptUnprotectData(
                &mut input_blob,
                std::ptr::null_mut(),
                std::ptr::null_mut(),
                std::ptr::null_mut(),
                std::ptr::null_mut(),
                0,
                &mut output_blob,
            ) == 0 {
                return Err(anyhow!("DPAPI decryption failed"));
            }

            let decrypted = std::slice::from_raw_parts(
                output_blob.pbData,
                output_blob.cbData as usize,
            ).to_vec();

            winapi::um::winbase::LocalFree(output_blob.pbData as *mut _);

            Ok(decrypted)
        }
    }
}
```

### Windows File Permissions (ACLs)

```rust
// src/platform/windows/permissions.rs

use windows::Win32::Security::{
    SetSecurityInfo, SECURITY_INFORMATION, SE_FILE_OBJECT,
    DACL_SECURITY_INFORMATION, PROTECTED_DACL_SECURITY_INFORMATION,
};

pub fn set_admin_only_acl(path: &Path) -> Result<()> {
    use std::ptr::null_mut;

    // Create a DACL that only allows Administrators and SYSTEM
    // This is equivalent to chmod 700 on Unix

    let path_wide: Vec<u16> = path.as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();

    unsafe {
        // Use icacls command for simplicity
        let status = std::process::Command::new("icacls")
            .arg(path)
            .args([
                "/inheritance:r",           // Remove inherited permissions
                "/grant:r", "Administrators:(OI)(CI)F",  // Full control for Admins
                "/grant:r", "SYSTEM:(OI)(CI)F",          // Full control for SYSTEM
            ])
            .status()?;

        if !status.success() {
            return Err(anyhow!("Failed to set ACLs on {}", path.display()));
        }
    }

    Ok(())
}
```

---

## Collectors

### Windows-Specific Collectors

#### Hardware Collector

```rust
// src/collectors/hardware_windows.rs

use wmi::{COMLibrary, WMIConnection};
use serde::Deserialize;

#[derive(Deserialize)]
struct Win32_ComputerSystem {
    Manufacturer: String,
    Model: String,
    TotalPhysicalMemory: u64,
    NumberOfProcessors: u32,
}

#[derive(Deserialize)]
struct Win32_Processor {
    Name: String,
    Manufacturer: String,
    NumberOfCores: u32,
    NumberOfLogicalProcessors: u32,
    MaxClockSpeed: u32,
    Architecture: u16,
}

pub fn collect_hardware() -> Result<HardwareProfile> {
    let com_con = COMLibrary::new()?;
    let wmi_con = WMIConnection::new(com_con)?;

    // Query computer system
    let systems: Vec<Win32_ComputerSystem> = wmi_con.query()?;
    let system = systems.first().ok_or_else(|| anyhow!("No system info"))?;

    // Query processor
    let processors: Vec<Win32_Processor> = wmi_con.query()?;
    let processor = processors.first().ok_or_else(|| anyhow!("No CPU info"))?;

    Ok(HardwareProfile {
        system: SystemInfo {
            manufacturer: system.Manufacturer.clone(),
            model: system.Model.clone(),
        },
        cpu: CpuInfo {
            model: processor.Name.clone(),
            vendor: processor.Manufacturer.clone(),
            physical_cores: processor.NumberOfCores,
            logical_cores: processor.NumberOfLogicalProcessors,
            frequency_mhz: processor.MaxClockSpeed,
            architecture: architecture_string(processor.Architecture),
        },
        memory: MemoryInfo {
            total_bytes: system.TotalPhysicalMemory,
        },
        gpus: collect_gpus(&wmi_con)?,
    })
}

fn architecture_string(arch: u16) -> String {
    match arch {
        0 => "x86".to_string(),
        5 => "arm".to_string(),
        9 => "x86_64".to_string(),
        12 => "arm64".to_string(),
        _ => "unknown".to_string(),
    }
}
```

#### Network Collector

```rust
// src/collectors/network_windows.rs

use std::process::Command;

pub fn collect_network() -> Result<NetworkProfile> {
    // Get hostname
    let hostname = hostname::get()?.to_string_lossy().to_string();

    // Get interfaces using Get-NetAdapter PowerShell
    let interfaces = collect_interfaces_powershell()?;

    // Get DNS servers
    let dns_servers = collect_dns_servers()?;

    Ok(NetworkProfile {
        hostname,
        interfaces,
        dns_servers,
    })
}

fn collect_interfaces_powershell() -> Result<Vec<NetworkInterface>> {
    let output = Command::new("powershell")
        .args([
            "-NoProfile",
            "-Command",
            "Get-NetAdapter | Select-Object Name, MacAddress, Status, InterfaceIndex | ConvertTo-Json"
        ])
        .output()?;

    // Parse JSON output
    let adapters: Vec<PowerShellAdapter> = serde_json::from_slice(&output.stdout)?;

    let mut interfaces = Vec::new();
    for adapter in adapters {
        let addresses = collect_addresses_for_interface(adapter.InterfaceIndex)?;
        interfaces.push(NetworkInterface {
            name: adapter.Name,
            mac_address: adapter.MacAddress.replace("-", ":"),
            state: if adapter.Status == "Up" { "up" } else { "down" }.to_string(),
            ipv4_addresses: addresses.ipv4,
            ipv6_addresses: addresses.ipv6,
        });
    }

    Ok(interfaces)
}

fn collect_dns_servers() -> Result<Vec<String>> {
    let output = Command::new("powershell")
        .args([
            "-NoProfile",
            "-Command",
            "Get-DnsClientServerAddress -AddressFamily IPv4 | Select-Object -ExpandProperty ServerAddresses"
        ])
        .output()?;

    let servers: Vec<String> = String::from_utf8_lossy(&output.stdout)
        .lines()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();

    Ok(servers)
}
```

#### Software Collector (Package Managers)

```rust
// src/collectors/software_windows.rs

#[derive(Debug)]
pub struct WindowsPackageManager;

impl WindowsPackageManager {
    /// Enumerate installed programs from registry
    pub fn collect_registry_programs() -> Result<Vec<Package>> {
        let mut packages = Vec::new();

        // 64-bit programs
        let hklm = winreg::RegKey::predef(winreg::HKEY_LOCAL_MACHINE);
        if let Ok(uninstall) = hklm.open_subkey(
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        ) {
            packages.extend(read_registry_packages(&uninstall)?);
        }

        // 32-bit programs on 64-bit Windows
        if let Ok(uninstall) = hklm.open_subkey(
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
        ) {
            packages.extend(read_registry_packages(&uninstall)?);
        }

        // Current user programs
        let hkcu = winreg::RegKey::predef(winreg::HKEY_CURRENT_USER);
        if let Ok(uninstall) = hkcu.open_subkey(
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
        ) {
            packages.extend(read_registry_packages(&uninstall)?);
        }

        Ok(packages)
    }

    /// Collect packages from winget
    pub fn collect_winget_packages() -> Result<Vec<Package>> {
        if !is_winget_available() {
            return Ok(Vec::new());
        }

        let output = Command::new("winget")
            .args(["list", "--disable-interactivity"])
            .output()?;

        parse_winget_output(&output.stdout)
    }

    /// Collect packages from Chocolatey
    pub fn collect_chocolatey_packages() -> Result<Vec<Package>> {
        if !is_choco_available() {
            return Ok(Vec::new());
        }

        let output = Command::new("choco")
            .args(["list", "--local-only", "--limit-output"])
            .output()?;

        parse_choco_output(&output.stdout)
    }

    /// Collect packages from Scoop
    pub fn collect_scoop_packages() -> Result<Vec<Package>> {
        // Scoop is installed per-user
        let scoop_path = dirs::home_dir()
            .map(|h| h.join("scoop").join("shims").join("scoop.cmd"));

        if let Some(path) = scoop_path {
            if path.exists() {
                let output = Command::new(&path)
                    .args(["list"])
                    .output()?;
                return parse_scoop_output(&output.stdout);
            }
        }

        Ok(Vec::new())
    }
}

fn is_winget_available() -> bool {
    Command::new("winget")
        .arg("--version")
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

fn is_choco_available() -> bool {
    Command::new("choco")
        .arg("--version")
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}
```

---

## Installation & Distribution

> **Distribution Model:** Windows follows the same model as Linux (per Some Updates.md):
> - Bundled code distributed via API endpoints (`/agent/download`, `/agent/install`, `/agent/versions`)
> - Source parameter: `source=local|obs` (local storage or S3-compatible object storage)
> - API detects Windows user-agent and returns PowerShell script for `/agent/install`

### Installation Options

#### Option 1: Easy Install (via `/agent/install` endpoint)

```powershell
# Run from PowerShell as Administrator
iex (Invoke-WebRequest -Uri "https://hydra.local/api/v1/agent/install?source=local" -UseBasicParsing).Content
```

This endpoint returns a PowerShell script that:
1. Downloads the bundled agent code from the specified source
2. Extracts to a temporary directory
3. Runs the install script interactively
4. Cleans up temporary files

#### Option 2: Manual Install (via `/agent/download` endpoint)

1. Download: `Invoke-WebRequest -Uri "https://hydra.local/api/v1/agent/download?source=local" -OutFile hydra-agent.zip`
2. Extract: `Expand-Archive hydra-agent.zip -DestinationPath .\hydra-agent`
3. Run: `.\hydra-agent\scripts\install.ps1`

#### Option 3: Development (via Repository)

1. Clone the hydra repository
2. `cd hydra-agent`
3. Run `.\scripts\install.ps1`

### MSI Installer (Optional - Enterprise)

For enterprise deployment, an MSI package can be created using WiX Toolset:

```xml
<!-- installer/windows/hydra-agent.wxs -->
<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi">
    <Product Id="*"
             Name="Hydra Agent"
             Language="1033"
             Version="$(var.Version)"
             Manufacturer="Hydra Project"
             UpgradeCode="YOUR-UNIQUE-GUID-HERE">

        <Package InstallerVersion="500"
                 Compressed="yes"
                 InstallScope="perMachine" />

        <MajorUpgrade DowngradeErrorMessage="A newer version is already installed." />
        <MediaTemplate EmbedCab="yes" />

        <Feature Id="ProductFeature" Title="Hydra Agent" Level="1">
            <ComponentGroupRef Id="ProductComponents" />
            <ComponentRef Id="ConfigComponent" />
            <ComponentRef Id="ServiceComponent" />
        </Feature>

        <!-- Install binary -->
        <ComponentGroup Id="ProductComponents" Directory="INSTALLFOLDER">
            <Component Id="MainExecutable" Guid="*">
                <File Id="HydraAgentExe"
                      Source="$(var.BinaryPath)\hydra-agent.exe"
                      KeyPath="yes" />
            </Component>
        </ComponentGroup>

        <!-- Create ProgramData directories -->
        <DirectoryRef Id="CommonAppDataFolder">
            <Directory Id="HydraDataDir" Name="Hydra">
                <Component Id="ConfigComponent" Guid="*">
                    <File Id="ConfigFile"
                          Source="config\agent.example.toml"
                          Name="agent.toml" />
                    <CreateFolder>
                        <Permission User="Administrators" GenericAll="yes" />
                        <Permission User="SYSTEM" GenericAll="yes" />
                    </CreateFolder>
                </Component>
                <Directory Id="VaultDir" Name="vault">
                    <Component Id="VaultDirComponent" Guid="*">
                        <CreateFolder>
                            <Permission User="Administrators" GenericAll="yes" />
                            <Permission User="SYSTEM" GenericAll="yes" />
                        </CreateFolder>
                    </Component>
                </Directory>
            </Directory>
        </DirectoryRef>

        <!-- Install Windows Service -->
        <Component Id="ServiceComponent" Directory="INSTALLFOLDER" Guid="*">
            <ServiceInstall Id="HydraAgentService"
                          Name="HydraAgent"
                          DisplayName="Hydra Agent"
                          Description="Infrastructure profiling agent for Hydra"
                          Start="auto"
                          Type="ownProcess"
                          ErrorControl="normal"
                          Arguments="service run" />
            <ServiceControl Id="HydraAgentServiceControl"
                          Name="HydraAgent"
                          Start="install"
                          Stop="both"
                          Remove="uninstall"
                          Wait="yes" />
        </Component>

        <!-- Directory structure -->
        <Directory Id="TARGETDIR" Name="SourceDir">
            <Directory Id="ProgramFiles64Folder">
                <Directory Id="INSTALLFOLDER" Name="Hydra Agent" />
            </Directory>
        </Directory>

    </Product>
</Wix>
```

#### 2. PowerShell Install Script

```powershell
# installer/windows/install.ps1

<#
.SYNOPSIS
    Installs Hydra Agent on Windows

.PARAMETER Version
    Version to install (default: latest)

.PARAMETER InstallDir
    Installation directory (default: C:\Program Files\Hydra Agent)

.PARAMETER ConfigPath
    Configuration file path (default: C:\ProgramData\Hydra\agent.toml)

.PARAMETER Token
    Registration token for automatic registration

.PARAMETER NoService
    Don't install as Windows Service

.EXAMPLE
    .\install.ps1 -Version 0.3.1 -Token reg_abc123
#>

param(
    [string]$Version = "latest",
    [string]$InstallDir = "$env:ProgramFiles\Hydra Agent",
    [string]$ConfigPath = "$env:ProgramData\Hydra\agent.toml",
    [string]$Token = "",
    [switch]$NoService
)

$ErrorActionPreference = "Stop"

# Require admin
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Error "This script must be run as Administrator"
    exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Hydra Agent Installer for Windows   " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Detect architecture
$arch = if ([Environment]::Is64BitOperatingSystem) { "windows-amd64" } else { "windows-x86" }
Write-Host "[INFO] Architecture: $arch" -ForegroundColor Blue

# Download binary
$downloadUrl = "https://hydra.local/api/v1/install/hydra-agent-$arch.exe"
if ($Version -ne "latest") {
    $downloadUrl = "https://hydra.local/api/v1/install/hydra-agent-$arch.exe?version=$Version"
}

Write-Host "[INFO] Downloading from: $downloadUrl" -ForegroundColor Blue

$tempFile = Join-Path $env:TEMP "hydra-agent.exe"
Invoke-WebRequest -Uri $downloadUrl -OutFile $tempFile

# Create directories
Write-Host "[INFO] Creating directories..." -ForegroundColor Blue
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path "$env:ProgramData\Hydra" | Out-Null
New-Item -ItemType Directory -Force -Path "$env:ProgramData\Hydra\vault" | Out-Null
New-Item -ItemType Directory -Force -Path "$env:ProgramData\Hydra\logs" | Out-Null

# Set vault permissions (restrict to Administrators and SYSTEM)
$vaultPath = "$env:ProgramData\Hydra\vault"
icacls $vaultPath /inheritance:r
icacls $vaultPath /grant:r "Administrators:(OI)(CI)F"
icacls $vaultPath /grant:r "SYSTEM:(OI)(CI)F"

# Copy binary
Write-Host "[INFO] Installing binary..." -ForegroundColor Blue
Copy-Item $tempFile "$InstallDir\hydra-agent.exe" -Force
Remove-Item $tempFile

# Create default config if not exists
if (-not (Test-Path $ConfigPath)) {
    Write-Host "[INFO] Creating default configuration..." -ForegroundColor Blue
    @"
# Hydra Agent Configuration
# Edit this file with your settings

[node]
node_id = "$env:COMPUTERNAME"
class = "compute"
node_type = "physical"

[api]
url = "https://hydra.local/api/v1"
timeout_seconds = 30
retries = 3

[collection]
level = "neutral"
include_packages = true
include_users = true

[schedule]
enabled = true
interval_seconds = 21600
on_startup = true
"@ | Out-File -FilePath $ConfigPath -Encoding UTF8
}

# Install Windows Service
if (-not $NoService) {
    Write-Host "[INFO] Installing Windows Service..." -ForegroundColor Blue

    # Stop and remove existing service
    $existingService = Get-Service -Name "HydraAgent" -ErrorAction SilentlyContinue
    if ($existingService) {
        Stop-Service -Name "HydraAgent" -Force -ErrorAction SilentlyContinue
        sc.exe delete HydraAgent
        Start-Sleep -Seconds 2
    }

    # Create service
    $binaryPath = "`"$InstallDir\hydra-agent.exe`" service run --config `"$ConfigPath`""
    sc.exe create HydraAgent binPath= $binaryPath start= auto DisplayName= "Hydra Agent"
    sc.exe description HydraAgent "Infrastructure profiling agent for Hydra"

    # Configure recovery (restart on failure)
    sc.exe failure HydraAgent reset= 86400 actions= restart/60000/restart/120000//
}

# Add to PATH
Write-Host "[INFO] Adding to PATH..." -ForegroundColor Blue
$currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
if ($currentPath -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$currentPath;$InstallDir", "Machine")
}

# Register if token provided
if ($Token) {
    Write-Host "[INFO] Registering with token..." -ForegroundColor Blue
    & "$InstallDir\hydra-agent.exe" register --token $Token --config $ConfigPath
    & "$InstallDir\hydra-agent.exe" node register --config $ConfigPath
}

# Start service
if (-not $NoService) {
    Write-Host "[INFO] Starting service..." -ForegroundColor Blue
    Start-Service -Name "HydraAgent"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "[OK] Installation complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Binary:  $InstallDir\hydra-agent.exe"
Write-Host "Config:  $ConfigPath"
Write-Host "Vault:   $env:ProgramData\Hydra\vault"
Write-Host ""

if (-not $Token) {
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Edit config: notepad $ConfigPath"
    Write-Host "  2. Login: hydra-agent login -u <username>"
    Write-Host "  3. Register: hydra-agent register"
    Write-Host "  4. Register node: hydra-agent node register"
    Write-Host "  5. Start service: Start-Service HydraAgent"
}
```

#### 3. Deploy Script Updates

Update `deploy-agent.sh` to include Windows targets:

```bash
# Additional targets in deploy-agent.sh
DEFAULT_TARGETS=(
    # ... existing targets ...
    "x86_64-pc-windows-msvc:windows-amd64"
    "aarch64-pc-windows-msvc:windows-arm64"
)

# Windows-specific build handling
build_windows_target() {
    local rust_target="$1"
    local hydra_target="$2"

    # Windows targets need .exe extension
    local binary_src="target/${rust_target}/release/hydra-agent.exe"

    # Cross-compiling to Windows requires either:
    # 1. cross with appropriate Docker image
    # 2. Native Windows build environment
    # 3. mingw-w64 toolchain

    if [[ "$build_cmd" == "cross" ]]; then
        cross build --release --target "$rust_target"
    else
        # Requires xwin or actual Windows
        cargo build --release --target "$rust_target"
    fi

    # Copy with .exe extension
    cp "$binary_src" "${output_dir}/hydra-agent.exe"
}
```

---

## CLI Adaptations

### Windows-Specific CLI Behavior

```rust
// src/cli/mod.rs

#[cfg(windows)]
pub fn get_default_config_path() -> PathBuf {
    PathBuf::from(r"C:\ProgramData\Hydra\agent.toml")
}

#[cfg(unix)]
pub fn get_default_config_path() -> PathBuf {
    PathBuf::from("/etc/hydra/agent.toml")
}
```

### Service Command for Windows

```rust
// src/cli/service.rs additions

#[cfg(windows)]
impl ServiceCommand {
    pub fn activate_windows(
        install_dir: &Path,
        config_path: &Path,
        no_start: bool,
    ) -> Result<()> {
        use crate::platform::windows::service;

        // Check for admin rights
        if !is_elevated() {
            return Err(anyhow!("Administrator privileges required. Run as Administrator."));
        }

        // Install service
        service::install_windows_service(config_path)?;

        // Start if requested
        if !no_start {
            service::start_service()?;
        }

        println!();
        println!("✓ Windows Service installed successfully!");
        println!("  Service Name: HydraAgent");
        println!("  Config: {}", config_path.display());
        println!();
        println!("Manage with:");
        println!("  Start:   Start-Service HydraAgent");
        println!("  Stop:    Stop-Service HydraAgent");
        println!("  Status:  Get-Service HydraAgent");
        println!("  Logs:    Get-EventLog -LogName Application -Source HydraAgent");

        Ok(())
    }
}

#[cfg(windows)]
fn is_elevated() -> bool {
    use std::ptr;
    use winapi::um::processthreadsapi::GetCurrentProcess;
    use winapi::um::securitybaseapi::GetTokenInformation;
    use winapi::um::processthreadsapi::OpenProcessToken;
    use winapi::um::winnt::{TokenElevation, TOKEN_ELEVATION, TOKEN_QUERY};

    unsafe {
        let mut token_handle = ptr::null_mut();
        if OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut token_handle) == 0 {
            return false;
        }

        let mut elevation = TOKEN_ELEVATION { TokenIsElevated: 0 };
        let mut size = std::mem::size_of::<TOKEN_ELEVATION>() as u32;

        if GetTokenInformation(
            token_handle,
            TokenElevation,
            &mut elevation as *mut _ as *mut _,
            size,
            &mut size,
        ) == 0 {
            return false;
        }

        elevation.TokenIsElevated != 0
    }
}
```

---

## Testing Strategy

### Windows-Specific Tests

```rust
// tests/windows_test.rs

#[cfg(windows)]
mod windows_tests {
    use super::*;

    #[test]
    fn test_registry_package_collection() {
        let packages = WindowsPackageManager::collect_registry_programs().unwrap();
        // Windows should always have some programs installed
        assert!(!packages.is_empty());
    }

    #[test]
    fn test_wmi_hardware_collection() {
        let hardware = collect_hardware_windows().unwrap();
        assert!(!hardware.cpu.model.is_empty());
        assert!(hardware.memory.total_bytes > 0);
    }

    #[test]
    fn test_dpapi_encryption() {
        let vault = WindowsVault::new().unwrap();
        let original = b"test secret data";

        let encrypted = vault.encrypt_data(original).unwrap();
        assert_ne!(encrypted, original);

        let decrypted = vault.decrypt_data(&encrypted).unwrap();
        assert_eq!(decrypted, original);
    }

    #[test]
    fn test_acl_permissions() {
        let temp_dir = std::env::temp_dir().join("hydra_test_acl");
        std::fs::create_dir_all(&temp_dir).unwrap();

        set_admin_only_acl(&temp_dir).unwrap();

        // Verify ACLs (would need admin to fully test)
        std::fs::remove_dir_all(&temp_dir).unwrap();
    }
}
```

---

## Implementation Phases

### Phase W1: Core Platform Abstraction (Week 1-2)

**Tasks:**
- [ ] Create `platform` module with trait definitions
- [ ] Implement Unix platform (refactor existing code)
- [ ] Add Windows platform stubs
- [ ] Update `Cargo.toml` with Windows dependencies
- [ ] Ensure cross-compilation setup works

**Files to create/modify:**
- `src/platform/mod.rs`
- `src/platform/unix.rs`
- `src/platform/windows.rs`
- `src/platform/paths.rs`
- `Cargo.toml`

### Phase W2: Windows Collectors (Week 3-4)

**Tasks:**
- [ ] Implement WMI-based hardware collector
- [ ] Implement PowerShell-based network collector
- [ ] Implement storage collector (Win32_LogicalDisk)
- [ ] Implement software collector (registry + winget + choco)
- [ ] Add Windows-specific tests

**Files to create:**
- `src/collectors/hardware_windows.rs`
- `src/collectors/network_windows.rs`
- `src/collectors/storage_windows.rs`
- `src/collectors/software_windows.rs`
- `tests/collectors_windows_test.rs`

### Phase W3: Credential Vault & Permissions (Week 5)

**Tasks:**
- [ ] Implement DPAPI-based credential encryption
- [ ] Implement NTFS ACL management
- [ ] Port vault operations to Windows paths
- [ ] Add vault tests for Windows

**Files to create/modify:**
- `src/vault/windows.rs`
- `src/platform/windows/permissions.rs`

### Phase W4: Service Management (Week 6-7)

**Tasks:**
- [ ] Implement Windows Service registration
- [ ] Implement service lifecycle (start/stop/status)
- [ ] Implement Task Scheduler alternative
- [ ] Update `service` CLI command for Windows

**Files to create/modify:**
- `src/platform/windows/service.rs`
- `src/platform/windows/scheduler.rs`
- `src/cli/service.rs`

### Phase W5: Installation & Distribution

**Distribution Model:** Same as Linux (per Some Updates.md) - bundled code via API endpoints:
- `GET /api/v1/agent/download?source=local|obs` - Download bundled agent code
- `GET /api/v1/agent/install?source=local|obs` - Remote install script (returns PowerShell for Windows)
- `GET /api/v1/agent/versions?source=local|obs` - List available versions

**Tasks:**
- [ ] Create PowerShell install script (mirrors `install.sh` for Linux)
- [ ] Update `deploy-agent.sh` to include Windows targets in bundle
- [ ] Ensure API `/agent/install` endpoint returns PowerShell script when Windows user-agent detected
- [ ] Optional: Create WiX MSI installer template for enterprise deployment

**Files to create:**
- `scripts/install.ps1` - PowerShell installer (same flow as `install.sh`)
- Optional: `installer/windows/hydra-agent.wxs` - MSI for enterprise

### Phase W6: Testing & Documentation

**Tasks:**
- [ ] Windows-specific unit tests (collectors, vault, service)
- [ ] Integration testing on Windows targets
- [ ] Update `hydra-agent/README.md` with Windows instructions
- [ ] Update API documentation for Windows support
- [ ] Create Windows troubleshooting guide

---

## Appendix

### Required Cargo Dependencies for Windows

```toml
[target.'cfg(windows)'.dependencies]
winapi = { version = "0.3", features = [
    "processthreadsapi",
    "securitybaseapi",
    "wincrypt",
    "dpapi",
    "errhandlingapi",
    "handleapi",
    "winnt",
    "winbase",
] }
windows-service = "0.6"
winreg = "0.52"
wmi = "0.13"

[target.'cfg(windows)'.build-dependencies]
winres = "0.1"  # For embedding Windows resources
```

### Windows Event Logging

```rust
// src/platform/windows/logging.rs

use winapi::um::winnt::EVENTLOG_INFORMATION_TYPE;

pub fn log_to_event_log(message: &str, event_type: u16) -> Result<()> {
    use std::ffi::OsStr;
    use std::os::windows::ffi::OsStrExt;
    use winapi::um::winbase::{
        RegisterEventSourceW, DeregisterEventSource, ReportEventW
    };

    unsafe {
        let source_name: Vec<u16> = OsStr::new("HydraAgent")
            .encode_wide()
            .chain(std::iter::once(0))
            .collect();

        let handle = RegisterEventSourceW(std::ptr::null(), source_name.as_ptr());
        if handle.is_null() {
            return Err(anyhow!("Failed to register event source"));
        }

        let message_wide: Vec<u16> = OsStr::new(message)
            .encode_wide()
            .chain(std::iter::once(0))
            .collect();

        let message_ptr = message_wide.as_ptr();

        ReportEventW(
            handle,
            event_type,
            0,      // category
            0,      // event ID
            std::ptr::null_mut(), // user SID
            1,      // number of strings
            0,      // data size
            &message_ptr as *const _ as *mut _,
            std::ptr::null_mut(),
        );

        DeregisterEventSource(handle);
    }

    Ok(())
}
```

### Useful Windows Commands Reference

| Task | Command |
|------|---------|
| View service status | `Get-Service HydraAgent` |
| Start service | `Start-Service HydraAgent` |
| Stop service | `Stop-Service HydraAgent` |
| View event logs | `Get-EventLog -LogName Application -Source HydraAgent -Newest 50` |
| Check if admin | `([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole("Administrator")` |
| View installed programs | `Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*` |
| Get network adapters | `Get-NetAdapter` |
| Get DNS servers | `Get-DnsClientServerAddress` |
