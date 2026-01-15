#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Hydra Agent Install Script for Windows

.DESCRIPTION
    Builds and installs the hydra-agent from source bundle on Windows systems.

.PARAMETER Version
    Version number for binary manifest (required)

.PARAMETER InstallDir
    Installation directory [default: C:\Program Files\Hydra Agent]

.PARAMETER ConfigPath
    Config file path [default: C:\ProgramData\Hydra\agent.toml]

.PARAMETER CreateAlias
    Create 'hydra' alias (copy of hydra-agent.exe)

.PARAMETER AddToPath
    Add installation directory to system PATH

.PARAMETER RegisterToken
    Auto-register with provided token after install

.PARAMETER ApiUrl
    Override API URL in generated config

.PARAMETER SkipRust
    Skip Rust installation check (assume Rust is installed)

.EXAMPLE
    .\install.ps1 -Version 0.3.1

.EXAMPLE
    .\install.ps1 -Version 0.3.1 -CreateAlias -AddToPath

.EXAMPLE
    .\install.ps1 -Version 0.3.1 -RegisterToken "reg_abc123"

.LINK
    https://github.com/yourorg/hydra
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Version,

    [Parameter()]
    [string]$InstallDir = "C:\Program Files\Hydra Agent",

    [Parameter()]
    [string]$ConfigPath = "C:\ProgramData\Hydra\agent.toml",

    [Parameter()]
    [switch]$CreateAlias,

    [Parameter()]
    [switch]$AddToPath,

    [Parameter()]
    [string]$RegisterToken,

    [Parameter()]
    [string]$ApiUrl,

    [Parameter()]
    [switch]$SkipRust
)

# Strict mode
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Configuration
$ConfigDir = Split-Path -Parent $ConfigPath
$VaultDir = "C:\ProgramData\Hydra\vault"
$LogDir = "C:\ProgramData\Hydra\logs"

# Color output functions
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] " -ForegroundColor Blue -NoNewline
    Write-Host $Message
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] " -ForegroundColor Yellow -NoNewline
    Write-Host $Message
}

function Write-Error2 {
    param([string]$Message)
    Write-Host "[ERROR] " -ForegroundColor Red -NoNewline
    Write-Host $Message
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] " -ForegroundColor Green -NoNewline
    Write-Host $Message
}

function Write-Step {
    param([string]$Message)
    Write-Host "[STEP] " -ForegroundColor Cyan -NoNewline
    Write-Host $Message
}

# Check if running as Administrator
function Test-Administrator {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Detect system architecture
function Get-SystemInfo {
    Write-Step "Detecting system..."

    $arch = $env:PROCESSOR_ARCHITECTURE
    $os = [System.Environment]::OSVersion

    switch ($arch) {
        "AMD64" { $normalizedArch = "amd64" }
        "x86" { $normalizedArch = "x86" }
        "ARM64" { $normalizedArch = "arm64" }
        default { $normalizedArch = $arch.ToLower() }
    }

    Write-Info "Operating System: Windows $($os.Version)"
    Write-Info "Architecture: $normalizedArch"

    # Validate supported platform
    if ($normalizedArch -ne "amd64") {
        Write-Error2 "Unsupported architecture: $normalizedArch"
        Write-Error2 "Currently only Windows x64 (amd64) is supported"
        exit 1
    }

    Write-Success "Platform supported: windows-$normalizedArch"
    return $normalizedArch
}

# Check and install Visual C++ Build Tools if needed
function Test-BuildTools {
    Write-Step "Checking build tools..."

    # Check for Visual Studio or Build Tools
    $vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"

    if (Test-Path $vsWhere) {
        $vsInstall = & $vsWhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null
        if ($vsInstall) {
            Write-Info "Visual Studio Build Tools found: $vsInstall"
            Write-Success "Build tools ready"
            return $true
        }
    }

    # Check for standalone build tools
    $buildToolsPath = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools"
    if (Test-Path $buildToolsPath) {
        Write-Info "Visual Studio Build Tools found"
        Write-Success "Build tools ready"
        return $true
    }

    Write-Warn "Visual C++ Build Tools not found"
    Write-Warn "Please install from: https://visualstudio.microsoft.com/visual-cpp-build-tools/"
    Write-Warn "Select 'Desktop development with C++' workload"

    $response = Read-Host "Continue anyway? (y/N)"
    if ($response -ne "y" -and $response -ne "Y") {
        exit 1
    }

    return $false
}

# Check and install Rust toolchain
function Test-Rust {
    Write-Step "Checking Rust toolchain..."

    if ($SkipRust) {
        Write-Info "Skipping Rust check (user requested)"
        return
    }

    # Check for rustup
    $rustup = Get-Command rustup -ErrorAction SilentlyContinue
    if ($rustup) {
        Write-Info "Rustup found"

        # Update to latest stable
        Write-Info "Updating to latest stable Rust..."
        & rustup update stable --quiet 2>$null

        $rustVersion = & rustc --version 2>$null
        $cargoVersion = & cargo --version 2>$null

        Write-Info "Rust version: $rustVersion"
        Write-Info "Cargo version: $cargoVersion"
        Write-Success "Rust toolchain ready"
        return
    }

    # Check for cargo without rustup
    $cargo = Get-Command cargo -ErrorAction SilentlyContinue
    if ($cargo) {
        Write-Info "Cargo found (standalone installation)"
        $cargoVersion = & cargo --version 2>$null
        Write-Info "Cargo version: $cargoVersion"
        Write-Success "Rust toolchain ready"
        return
    }

    # Rust not found - offer to install
    Write-Warn "Rust not found. Installing via rustup..."

    $rustupInit = "$env:TEMP\rustup-init.exe"

    try {
        Write-Info "Downloading rustup-init.exe..."
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri "https://win.rustup.rs/x86_64" -OutFile $rustupInit -UseBasicParsing

        Write-Info "Running rustup-init..."
        & $rustupInit -y --default-toolchain stable

        # Refresh PATH
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")

        # Verify installation
        $cargo = Get-Command cargo -ErrorAction SilentlyContinue
        if (-not $cargo) {
            Write-Error2 "Rust installation failed"
            exit 1
        }

        $rustVersion = & rustc --version 2>$null
        Write-Info "Rust installed: $rustVersion"
        Write-Success "Rust toolchain ready"
    }
    finally {
        if (Test-Path $rustupInit) {
            Remove-Item $rustupInit -Force
        }
    }
}

# Build the agent
function Build-Agent {
    Write-Step "Building hydra-agent..."

    # Set up build environment
    $env:CARGO_TERM_COLOR = "always"

    # Build with release profile
    Write-Info "Running cargo build --release..."

    $buildProcess = Start-Process -FilePath "cargo" -ArgumentList "build", "--release" -NoNewWindow -Wait -PassThru

    if ($buildProcess.ExitCode -ne 0) {
        Write-Error2 "Build failed with exit code: $($buildProcess.ExitCode)"
        exit 1
    }

    # Verify binary exists
    $binaryPath = "target\release\hydra-agent.exe"
    if (-not (Test-Path $binaryPath)) {
        Write-Error2 "Binary not found at $binaryPath"
        exit 1
    }

    $binaryInfo = Get-Item $binaryPath
    $sizeMB = [math]::Round($binaryInfo.Length / 1MB, 2)
    Write-Info "Binary size: ${sizeMB}MB"

    Write-Success "Build completed successfully"
}

# Install the binary
function Install-Binary {
    Write-Step "Installing binary..."

    # Create install directory
    if (-not (Test-Path $InstallDir)) {
        Write-Info "Creating directory: $InstallDir"
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }

    # Copy binary
    $sourcePath = "target\release\hydra-agent.exe"
    $destPath = Join-Path $InstallDir "hydra-agent.exe"

    Write-Info "Installing to: $destPath"
    Copy-Item -Path $sourcePath -Destination $destPath -Force

    # Create alias
    if ($CreateAlias) {
        $aliasPath = Join-Path $InstallDir "hydra.exe"
        Write-Info "Creating alias: hydra.exe -> hydra-agent.exe"
        Copy-Item -Path $destPath -Destination $aliasPath -Force
    }

    # Verify installation
    if (-not (Test-Path $destPath)) {
        Write-Error2 "Binary installation failed"
        exit 1
    }

    Write-Success "Binary installed successfully"

    # Show version
    try {
        $versionOutput = & $destPath --version 2>$null
        Write-Info "Installed: $versionOutput"
    }
    catch {
        # Ignore version check errors
    }
}

# Setup directories
function Initialize-Directories {
    Write-Step "Setting up directories..."

    # Create config directory
    if (-not (Test-Path $ConfigDir)) {
        Write-Info "Creating config directory: $ConfigDir"
        New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null
    }

    # Create vault directory with restricted permissions
    if (-not (Test-Path $VaultDir)) {
        Write-Info "Creating vault directory: $VaultDir"
        New-Item -ItemType Directory -Path $VaultDir -Force | Out-Null

        # Set ACL - Administrators and SYSTEM only
        Write-Info "Setting secure permissions on vault directory..."
        try {
            $acl = Get-Acl $VaultDir
            $acl.SetAccessRuleProtection($true, $false)  # Disable inheritance
            $acl.Access | ForEach-Object { $acl.RemoveAccessRule($_) } | Out-Null

            # Add Administrators
            $adminRule = New-Object System.Security.AccessControl.FileSystemAccessRule(
                "Administrators", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow"
            )
            $acl.AddAccessRule($adminRule)

            # Add SYSTEM
            $systemRule = New-Object System.Security.AccessControl.FileSystemAccessRule(
                "SYSTEM", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow"
            )
            $acl.AddAccessRule($systemRule)

            Set-Acl -Path $VaultDir -AclObject $acl
            Write-Success "Vault directory secured"
        }
        catch {
            Write-Warn "Failed to set ACL: $_"
        }
    }

    # Create log directory
    if (-not (Test-Path $LogDir)) {
        Write-Info "Creating log directory: $LogDir"
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    }

    Write-Success "Directories created"
}

# Setup configuration
function Initialize-Config {
    Write-Step "Setting up configuration..."

    if (Test-Path $ConfigPath) {
        Write-Info "Configuration already exists at: $ConfigPath"
        return
    }

    # Look for example config
    $exampleConfig = $null
    if (Test-Path "agent.example.toml") {
        $exampleConfig = "agent.example.toml"
    }
    elseif (Test-Path "config\agent.example.toml") {
        $exampleConfig = "config\agent.example.toml"
    }

    if ($exampleConfig) {
        Write-Info "Copying example config to: $ConfigPath"
        Copy-Item -Path $exampleConfig -Destination $ConfigPath -Force
        Set-ApiUrl
        Write-Success "Configuration created"
        Write-Warn "Please edit $ConfigPath before starting the agent"
    }
    else {
        # Create minimal config
        Write-Info "Creating minimal configuration..."

        $minimalConfig = @"
# Hydra Agent Configuration
# Edit this file with your settings

[node]
node_id = "CHANGE_ME"           # Unique node identifier
class = "compute"               # compute, networking, iot
node_type = "physical"          # physical, logical

[api]
url = "https://hydra.local/api/v1"
timeout_seconds = 30
retries = 3

[collection]
level = "neutral"               # minimal, neutral, full
include_packages = true
include_users = true

[schedule]
enabled = true
interval_seconds = 21600        # 6 hours
on_startup = true
"@

        Set-Content -Path $ConfigPath -Value $minimalConfig -Encoding UTF8
        Set-ApiUrl
        Write-Success "Minimal configuration created"
        Write-Warn "Please edit $ConfigPath with your settings"
    }
}

# Set API URL in config
function Set-ApiUrl {
    if (-not $ApiUrl) {
        return
    }

    if (-not (Test-Path $ConfigPath)) {
        return
    }

    Write-Info "Setting API URL in config: $ApiUrl"

    $content = Get-Content -Path $ConfigPath -Raw
    $content = $content -replace 'url\s*=\s*"[^"]*"', "url = `"$ApiUrl`""
    Set-Content -Path $ConfigPath -Value $content -Encoding UTF8
}

# Add to PATH
function Add-ToPath {
    if (-not $AddToPath) {
        return
    }

    Write-Step "Adding to PATH..."

    $currentPath = [Environment]::GetEnvironmentVariable("PATH", "Machine")

    if ($currentPath -like "*$InstallDir*") {
        Write-Info "Already in PATH"
        return
    }

    try {
        $newPath = "$currentPath;$InstallDir"
        [Environment]::SetEnvironmentVariable("PATH", $newPath, "Machine")

        # Update current session
        $env:PATH = "$env:PATH;$InstallDir"

        Write-Success "Added to system PATH"
        Write-Info "Restart your terminal to use 'hydra-agent' from anywhere"
    }
    catch {
        Write-Warn "Failed to update PATH: $_"
        Write-Warn "You may need to add '$InstallDir' to PATH manually"
    }
}

# Register with token
function Register-Agent {
    if (-not $RegisterToken) {
        return
    }

    Write-Step "Registering agent with token..."

    $agentPath = Join-Path $InstallDir "hydra-agent.exe"

    try {
        & $agentPath register --token $RegisterToken
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Agent registered successfully"
        }
        else {
            Write-Warn "Registration failed. You can register manually later with:"
            Write-Warn "  hydra-agent register --token <token>"
        }
    }
    catch {
        Write-Warn "Registration failed: $_"
        Write-Warn "You can register manually later with:"
        Write-Warn "  hydra-agent register --token <token>"
    }
}

# Cleanup build artifacts
function Remove-BuildArtifacts {
    Write-Step "Cleaning up..."

    if (Test-Path "target") {
        Write-Info "Removing build artifacts..."
        Remove-Item -Path "target" -Recurse -Force -ErrorAction SilentlyContinue
    }

    Write-Success "Cleanup complete"
}

# Print completion summary
function Write-Summary {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Success "   Hydra Agent Installation Complete!"
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Info "Binary:  $(Join-Path $InstallDir 'hydra-agent.exe')"
    if ($CreateAlias) {
        Write-Info "Alias:   $(Join-Path $InstallDir 'hydra.exe')"
    }
    Write-Info "Config:  $ConfigPath"
    Write-Info "Vault:   $VaultDir"
    Write-Info "Version: $Version"
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor White
    Write-Host ""
    Write-Host "  1. Edit configuration:"
    Write-Host "     notepad $ConfigPath" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  2. Login (if not using token):"
    Write-Host "     hydra-agent login -u <username>" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  3. Register agent account:"
    Write-Host "     hydra-agent register" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  4. Register this node:"
    Write-Host "     hydra-agent node register" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  5. Install as Windows Service:"
    Write-Host "     hydra-agent service install" -ForegroundColor Gray
    Write-Host "     hydra-agent service start" -ForegroundColor Gray
    Write-Host ""
    Write-Host "For help:"
    Write-Host "  hydra-agent --help" -ForegroundColor Gray
    Write-Host ""
}

# Main function
function Main {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "   Hydra Agent Installer v$Version" -ForegroundColor White
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""

    # Check administrator privileges
    if (-not (Test-Administrator)) {
        Write-Error2 "This script requires Administrator privileges"
        Write-Error2 "Please run PowerShell as Administrator"
        exit 1
    }

    # Run installation steps
    $null = Get-SystemInfo
    $null = Test-BuildTools
    Test-Rust
    Build-Agent
    Install-Binary
    Initialize-Directories
    Initialize-Config
    Add-ToPath
    Register-Agent
    Remove-BuildArtifacts
    Write-Summary
}

# Run main
Main
