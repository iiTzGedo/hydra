"""Plugin management services package."""

from .ansible import AnsibleHandler  # noqa: F401
from .base import PluginHandler  # noqa: F401
from .docker import DockerPluginHandler  # noqa: F401
from .homeassistant import HomeAssistantHandler  # noqa: F401
from .prometheus import PrometheusHandler  # noqa: F401
from .proxmox import ProxmoxHandler  # noqa: F401
from .service import PluginService  # noqa: F401
from .terraform import TerraformPlugin  # noqa: F401

# Registry mapping pluginId → handler class.
PLUGIN_REGISTRY: dict[str, type[PluginHandler]] = {
    "plg::docker": DockerPluginHandler,
    "plg::proxmox": ProxmoxHandler,
    "plg::homeassistant": HomeAssistantHandler,
    "plg::prometheus": PrometheusHandler,
    "plg::ansible": AnsibleHandler,
    "plg::terraform": TerraformPlugin,
}

__all__ = ["PluginHandler", "PluginService", "PLUGIN_REGISTRY"]
