//! Hydra Agent Library
//!
//! This library provides the core functionality for the Hydra infrastructure
//! profiling agent, including system collectors and API client.
//!
//! ## Cross-Platform Support
//!
//! The agent supports multiple platforms:
//! - Linux (x86_64, ARM64, ARMv7)
//! - macOS (x86_64, ARM64)
//! - Windows (x86_64)
//! - FreeBSD, OpenBSD, NetBSD
//!
//! Platform-specific functionality is abstracted through the `platform` module.

pub mod api;
pub mod cli;
pub mod collectors;
pub mod config;
pub mod platform;
pub mod vault;

// Re-export commonly used types
pub use collectors::{collect_profile, Profile};
pub use config::{AgentConfig, Credentials};
pub use platform::{paths::Paths, Platform};
pub use vault::Vault;
