//! Hydra Agent Library
//!
//! This library provides the core functionality for the Hydra infrastructure
//! profiling agent, including system collectors and API client.

pub mod api;
pub mod collectors;
pub mod config;

// Re-export commonly used types
pub use collectors::{collect_profile, Profile};
pub use config::{AgentConfig, Credentials};
