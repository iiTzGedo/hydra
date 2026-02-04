"""Profile management service package.

Re-exports all public symbols that were previously importable from
``hydra.api.v1.services.profiles``.
"""

from .diff import diff_config_files, diff_profiles
from .formatting import format_profile, format_profile_summary
from .network_processing import diff_network_config, process_networks
from .service import ProfileService
from .service_extraction import CRASH_STATUSES, generate_service_id
from .versioning import SECTION_WEIGHTS

__all__ = [
    "ProfileService",
    "generate_service_id",
    "CRASH_STATUSES",
    "SECTION_WEIGHTS",
    "diff_profiles",
    "diff_config_files",
    "diff_network_config",
    "process_networks",
    "format_profile",
    "format_profile_summary",
]
