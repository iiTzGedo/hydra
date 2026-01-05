# Hydra Agent

Lightweight, cross-platform infrastructure profiling agent for the Hydra platform. Written in Rust for minimal resource usage and maximum portability.

## Features

- **Cross-platform support**: Linux, macOS, Windows, FreeBSD, OpenBSD, NetBSD
- **Lightweight**: Single static binary with minimal dependencies
- **Comprehensive profiling**: Hardware, network, storage, and software information
- **Package detection**: Supports multiple package managers per platform
- **Secure communication**: TLS-encrypted API communication

## Quick Start

### Prerequisites

- Rust 1.75+ (install via [rustup](https://rustup.rs/))
- For Windows: Visual Studio Build Tools
- For cross-compilation: appropriate target toolchains

### Building

```bash
# Navigate to hydra-agent directory
cd hydra-agent

# Build in debug mode
cargo build

# Build optimized release binary
cargo build --release

# The binary will be at target/release/hydra-agent (or .exe on Windows)
```

### Cross-Compilation

```bash
# Add target for different platforms
rustup target add x86_64-unknown-linux-musl      # Linux (static)
rustup target add x86_64-pc-windows-msvc         # Windows
rustup target add x86_64-apple-darwin            # macOS Intel
rustup target add aarch64-apple-darwin           # macOS Apple Silicon
rustup target add x86_64-unknown-freebsd         # FreeBSD

# Build for specific target
cargo build --release --target x86_64-unknown-linux-musl
```

## Configuration

Create a configuration file at `/etc/hydra/agent.toml` (Linux/macOS/BSD) or `C:\ProgramData\Hydra\agent.toml` (Windows):

```toml
[api]
url = "https://hydra-api.example.com/api/v1"
credentials_file = "/etc/hydra/credentials.json"
timeout_seconds = 30
retries = 3

[node]
node_id = "my-server-01"
class = "compute"           # compute, networking, or iot
node_type = "physical"      # physical or logical
kind = "bare-metal"         # bare-metal, vm, lxc, docker, etc.
display_name = "My Server"
description = "Production web server"
tags = ["production", "web"]

[collection]
level = "neutral"           # shallow, neutral, or deep
collectors = ["hardware", "network", "storage", "software"]
include_packages = true
include_users = true
config_files = ["/etc/nginx/nginx.conf"]

[schedule]
enabled = true
interval_seconds = 86400    # 24 hours
on_startup = true
```

## Usage

### Register a Node

First, obtain a registration token from the Hydra API, then register:

```bash
hydra-agent --config /etc/hydra/agent.toml --register --token "reg_your_token_here"
```

This creates a credentials file with access and refresh tokens.

### Collect and Submit Profile

```bash
# Run once
hydra-agent --config /etc/hydra/agent.toml --once

# Run as service (will use schedule from config)
hydra-agent --config /etc/hydra/agent.toml

# Verbose output
hydra-agent --config /etc/hydra/agent.toml --once --verbose
```

### Command Line Options

```
Options:
  -c, --config <CONFIG>  Path to configuration file [default: /etc/hydra/agent.toml]
      --once             Run once and exit (don't schedule)
      --register         Register this node with the API
      --token <TOKEN>    Registration token (required for --register)
  -v, --verbose          Verbose output
  -h, --help             Print help
  -V, --version          Print version
```

## Testing

### Running Tests

```bash
# Run all tests
cargo test

# Run with verbose output
cargo test -- --nocapture

# Run specific test
cargo test test_hardware_collector

# Run tests with coverage (requires cargo-tarpaulin)
cargo install cargo-tarpaulin
cargo tarpaulin --out Html
```

### Test Structure

```
tests/
├── collectors_test.rs  # Tests for system collectors
└── config_test.rs      # Tests for configuration loading
```

### Example Test Output

```bash
$ cargo test
   Compiling hydra-agent v0.1.0
    Finished test [unoptimized + debuginfo] target(s)
     Running unittests src/lib.rs

running 8 tests
test tests::collectors_test::test_hardware_collector ... ok
test tests::collectors_test::test_network_collector ... ok
test tests::collectors_test::test_software_collector ... ok
test tests::collectors_test::test_storage_collector ... ok
test tests::collectors_test::test_profile_sections ... ok
test tests::config_test::test_load_valid_config ... ok
test tests::config_test::test_load_minimal_config ... ok
test tests::config_test::test_credentials_save_and_load ... ok

test result: ok. 8 passed; 0 failed; 0 ignored
```

## Platform-Specific Details

### Linux
- Supports dpkg (Debian/Ubuntu), rpm (RHEL/Fedora), and pacman (Arch) package managers
- DNS servers read from `/etc/resolv.conf`
- Uses procfs for detailed system information

### macOS
- Supports Homebrew package manager
- DNS servers read from `/etc/resolv.conf`

### Windows
- Enumerates installed programs from registry
- Supports winget and Chocolatey if available
- DNS servers obtained via `netsh` and `ipconfig`

### BSD (FreeBSD, OpenBSD, NetBSD)
- FreeBSD: Uses pkg package manager
- OpenBSD/NetBSD: Uses pkg_info
- DNS servers read from `/etc/resolv.conf`

## Collected Information

### Hardware Profile
- System manufacturer and model
- CPU: model, vendor, physical/logical cores, frequency, architecture
- Memory: total bytes
- GPUs (when available)

### Network Profile
- Hostname
- Network interfaces: name, MAC address, IPv4/IPv6 addresses, state
- DNS servers

### Storage Profile
- Block devices: name, size, type
- Filesystems: mount point, device, type, size, usage

### Software Profile
- OS: name, version, kernel version, architecture, family
- Installed packages (optional, per package manager)

## Security

- Credentials are stored in a separate JSON file with restricted permissions
- All API communication uses HTTPS/TLS
- No sensitive information (passwords, keys) is collected
- Config file hashes are computed for change detection, not full contents

## Development

### Project Structure

```
hydra-agent/
├── src/
│   ├── main.rs           # CLI entry point
│   ├── lib.rs            # Library exports
│   ├── api/
│   │   └── mod.rs        # API client for Hydra API
│   ├── collectors/
│   │   ├── mod.rs        # Collector orchestration
│   │   ├── hardware.rs   # Hardware info collection
│   │   ├── network.rs    # Network info collection
│   │   ├── storage.rs    # Storage info collection
│   │   └── software.rs   # Software info collection
│   └── config/
│       └── mod.rs        # Configuration management
├── tests/
│   ├── collectors_test.rs
│   └── config_test.rs
├── Cargo.toml
└── README.md
```

### Adding a New Collector

1. Create a new module in `src/collectors/`
2. Define a `*Profile` struct with the data to collect
3. Implement a `*Collector::collect()` function
4. Add platform-specific implementations using `#[cfg(target_os = "...")]`
5. Register the collector in `src/collectors/mod.rs`
6. Add tests in `tests/`

## License

Apache-2.0
