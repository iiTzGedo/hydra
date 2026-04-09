"""Home Assistant plugin handler.

Provides discovery, command execution, and health checking for
Home Assistant instances via the HA REST API.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx
import structlog

from hydra.api.v1.services.plugins.base import PluginHandler

logger = structlog.get_logger(__name__)

_NOW = datetime.now(UTC)

# ── Command Definitions ─────────────────────────────────────────────────

_HA_COMMAND_DEFINITIONS: list[dict[str, Any]] = [
    {
        "registryId": "reg::ha::list-entities",
        "category": "ha",
        "action": "list-entities",
        "displayName": "List HA Entities",
        "description": "List all Home Assistant entities and their current states",
        "targetSchema": {},
        "parametersSchema": {
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Filter by entity domain (e.g. light, switch, sensor)",
                },
            },
        },
        "execution": {
            "handler": "ha_list_entities",
            "timeout": 30,
            "deliveryMode": "direct_or_poll",
            "retryable": False,
            "maxRetries": 0,
        },
        "rbac": {
            "minimumRole": "viewer",
            "requiresConfirmation": False,
            "confirmationMessage": None,
            "dangerLevel": "safe",
            "controlPermission": "ha:read",
        },
        "audit": {"logLevel": "minimal", "captureOutput": True, "sensitiveParameters": []},
        "metadata": {"version": "1.0.0", "addedAt": _NOW, "builtIn": False, "deprecated": False},
    },
    {
        "registryId": "reg::ha::get-state",
        "category": "ha",
        "action": "get-state",
        "displayName": "Get Entity State",
        "description": "Get the current state of a specific Home Assistant entity",
        "targetSchema": {
            "required": ["entityId"],
            "properties": {
                "entityId": {
                    "type": "string",
                    "description": "Home Assistant entity ID (e.g. light.living_room)",
                },
            },
        },
        "parametersSchema": None,
        "execution": {
            "handler": "ha_get_state",
            "timeout": 15,
            "deliveryMode": "direct_or_poll",
            "retryable": False,
            "maxRetries": 0,
        },
        "rbac": {
            "minimumRole": "viewer",
            "requiresConfirmation": False,
            "confirmationMessage": None,
            "dangerLevel": "safe",
            "controlPermission": "ha:read",
        },
        "audit": {"logLevel": "minimal", "captureOutput": True, "sensitiveParameters": []},
        "metadata": {"version": "1.0.0", "addedAt": _NOW, "builtIn": False, "deprecated": False},
    },
    {
        "registryId": "reg::ha::call-service",
        "category": "ha",
        "action": "call-service",
        "displayName": "Call HA Service",
        "description": "Call an arbitrary Home Assistant service (e.g. light.turn_on)",
        "targetSchema": {
            "required": ["domain", "service"],
            "properties": {
                "domain": {"type": "string", "description": "Service domain (e.g. light)"},
                "service": {"type": "string", "description": "Service name (e.g. turn_on)"},
            },
        },
        "parametersSchema": {
            "properties": {
                "entityId": {
                    "type": "string",
                    "description": "Target entity ID",
                },
                "serviceData": {
                    "type": "object",
                    "description": "Additional service data payload",
                },
            },
        },
        "execution": {
            "handler": "ha_call_service",
            "timeout": 30,
            "deliveryMode": "direct_or_poll",
            "retryable": False,
            "maxRetries": 0,
        },
        "rbac": {
            "minimumRole": "operator",
            "requiresConfirmation": False,
            "confirmationMessage": None,
            "dangerLevel": "medium",
            "controlPermission": "ha:control",
        },
        "audit": {"logLevel": "standard", "captureOutput": True, "sensitiveParameters": []},
        "metadata": {"version": "1.0.0", "addedAt": _NOW, "builtIn": False, "deprecated": False},
    },
    {
        "registryId": "reg::ha::turn-on",
        "category": "ha",
        "action": "turn-on",
        "displayName": "Turn On Entity",
        "description": "Turn on a Home Assistant entity",
        "targetSchema": {
            "required": ["entityId"],
            "properties": {
                "entityId": {
                    "type": "string",
                    "description": "Entity ID to turn on (e.g. light.living_room)",
                },
            },
        },
        "parametersSchema": {
            "properties": {
                "serviceData": {
                    "type": "object",
                    "description": "Optional service data (e.g. brightness, color_temp)",
                },
            },
        },
        "execution": {
            "handler": "ha_turn_on",
            "timeout": 15,
            "deliveryMode": "direct_or_poll",
            "retryable": False,
            "maxRetries": 0,
        },
        "rbac": {
            "minimumRole": "family",
            "requiresConfirmation": False,
            "confirmationMessage": None,
            "dangerLevel": "safe",
            "controlPermission": "iot:control",
        },
        "audit": {"logLevel": "standard", "captureOutput": True, "sensitiveParameters": []},
        "metadata": {"version": "1.0.0", "addedAt": _NOW, "builtIn": False, "deprecated": False},
    },
    {
        "registryId": "reg::ha::turn-off",
        "category": "ha",
        "action": "turn-off",
        "displayName": "Turn Off Entity",
        "description": "Turn off a Home Assistant entity",
        "targetSchema": {
            "required": ["entityId"],
            "properties": {
                "entityId": {
                    "type": "string",
                    "description": "Entity ID to turn off (e.g. light.living_room)",
                },
            },
        },
        "parametersSchema": None,
        "execution": {
            "handler": "ha_turn_off",
            "timeout": 15,
            "deliveryMode": "direct_or_poll",
            "retryable": False,
            "maxRetries": 0,
        },
        "rbac": {
            "minimumRole": "family",
            "requiresConfirmation": False,
            "confirmationMessage": None,
            "dangerLevel": "safe",
            "controlPermission": "iot:control",
        },
        "audit": {"logLevel": "standard", "captureOutput": True, "sensitiveParameters": []},
        "metadata": {"version": "1.0.0", "addedAt": _NOW, "builtIn": False, "deprecated": False},
    },
    {
        "registryId": "reg::ha::toggle",
        "category": "ha",
        "action": "toggle",
        "displayName": "Toggle Entity",
        "description": "Toggle a Home Assistant entity on or off",
        "targetSchema": {
            "required": ["entityId"],
            "properties": {
                "entityId": {
                    "type": "string",
                    "description": "Entity ID to toggle (e.g. switch.desk_lamp)",
                },
            },
        },
        "parametersSchema": None,
        "execution": {
            "handler": "ha_toggle",
            "timeout": 15,
            "deliveryMode": "direct_or_poll",
            "retryable": False,
            "maxRetries": 0,
        },
        "rbac": {
            "minimumRole": "family",
            "requiresConfirmation": False,
            "confirmationMessage": None,
            "dangerLevel": "safe",
            "controlPermission": "iot:control",
        },
        "audit": {"logLevel": "standard", "captureOutput": True, "sensitiveParameters": []},
        "metadata": {"version": "1.0.0", "addedAt": _NOW, "builtIn": False, "deprecated": False},
    },
]

# ── Manifest ────────────────────────────────────────────────────────────

_HA_MANIFEST: dict[str, Any] = {
    "pluginId": "plg::homeassistant",
    "name": "Home Assistant",
    "version": "1.0.0",
    "description": "Home Assistant integration for entity discovery and control",
    "author": "Hydra Team",
    "classification": "core",
    "category": "infrastructure",
    "touchpoints": {
        "profileEnrichment": False,
        "discoveryProvider": True,
        "commandProvider": True,
        "executionHandler": True,
        "topologyProvider": False,
        "workflowBlockProvider": False,
    },
    "supportedTiers": ["normal", "max"],
    "healthCheckEndpoint": None,
    "contributedCommands": [cmd["registryId"] for cmd in _HA_COMMAND_DEFINITIONS],
    "configSchema": {
        "required": ["url", "token"],
        "properties": {
            "url": {
                "type": "string",
                "description": "Home Assistant base URL (e.g. http://homeassistant.local:8123)",
                "default": "http://homeassistant.local:8123",
            },
            "token": {
                "type": "string",
                "description": "Long-lived access token",
            },
            "verifySsl": {
                "type": "boolean",
                "description": "Verify SSL certificates",
                "default": True,
            },
        },
    },
}


# ── Handler ─────────────────────────────────────────────────────────────


class HomeAssistantHandler(PluginHandler):
    """Plugin handler for Home Assistant instances.

    Communicates with the Home Assistant REST API to discover entities,
    read states, and call services.
    """

    MANIFEST: ClassVar[dict[str, Any]] = _HA_MANIFEST
    COMMAND_DEFINITIONS: ClassVar[list[dict[str, Any]]] = _HA_COMMAND_DEFINITIONS

    # ── Helpers ──────────────────────────────────────────────────────

    def _base_url(self) -> str:
        """Return the configured HA base URL with trailing slash removed."""
        url: str = self.config.get("url", "http://homeassistant.local:8123")
        return url.rstrip("/")

    def _token(self) -> str:
        """Return the long-lived access token from config or credentials."""
        if self.credentials and self.credentials.get("token"):
            return self.credentials["token"]
        return str(self.config.get("token", ""))

    def _verify_ssl(self) -> bool:
        """Return whether SSL verification is enabled."""
        return bool(self.config.get("verifySsl", True))

    def _auth_headers(self) -> dict[str, str]:
        """Build authorization headers for HA REST API requests."""
        return {
            "Authorization": f"Bearer {self._token()}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        timeout: float = 15.0,
    ) -> httpx.Response:
        """Execute an HTTP request against the HA REST API.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API path appended to the base URL (e.g. ``/api/states``).
            json_body: Optional JSON body for POST requests.
            timeout: Request timeout in seconds.

        Returns:
            The httpx Response object.
        """
        url = f"{self._base_url()}{path}"
        async with httpx.AsyncClient(
            verify=self._verify_ssl(),
            timeout=timeout,
        ) as client:
            response = await client.request(
                method,
                url,
                headers=self._auth_headers(),
                json=json_body,
            )
            return response

    # ── Lifecycle ────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Validate connectivity to Home Assistant by calling ``GET /api/``."""
        try:
            resp = await self._request("GET", "/api/")
            if resp.status_code == 200:
                logger.info(
                    "ha_connected",
                    url=self._base_url(),
                    message=resp.json().get("message", ""),
                )
                return True
            logger.warning(
                "ha_connect_failed",
                url=self._base_url(),
                status_code=resp.status_code,
            )
            return False
        except httpx.HTTPError as exc:
            logger.warning("ha_connect_error", url=self._base_url(), error=str(exc))
            return False

    async def health_check(self) -> dict[str, Any]:
        """Check HA instance health via ``GET /api/``."""
        now = datetime.now(UTC)
        try:
            resp = await self._request("GET", "/api/", timeout=10.0)
            if resp.status_code == 200:
                return {
                    "status": "healthy",
                    "lastCheck": now.isoformat(),
                    "consecutiveFailures": 0,
                    "lastError": None,
                    "responseTimeMs": resp.elapsed.total_seconds() * 1000
                    if resp.elapsed
                    else None,
                    "details": resp.json(),
                }
            return {
                "status": "unhealthy",
                "lastCheck": now.isoformat(),
                "consecutiveFailures": 1,
                "lastError": f"HTTP {resp.status_code}",
                "responseTimeMs": None,
            }
        except httpx.HTTPError as exc:
            return {
                "status": "unhealthy",
                "lastCheck": now.isoformat(),
                "consecutiveFailures": 1,
                "lastError": str(exc),
                "responseTimeMs": None,
            }

    # ── Discovery ────────────────────────────────────────────────────

    async def discover_nodes(self) -> list[dict[str, Any]]:
        """Discover Home Assistant entities grouped by domain.

        Calls ``GET /api/states`` and groups entities by their domain
        prefix (e.g. ``light``, ``switch``, ``sensor``).

        Returns:
            A list of discovered resource dicts, one per domain group.
        """
        try:
            resp = await self._request("GET", "/api/states", timeout=30.0)
            if resp.status_code != 200:
                logger.warning(
                    "ha_discover_failed",
                    status_code=resp.status_code,
                )
                return []

            states: list[dict[str, Any]] = resp.json()
        except httpx.HTTPError as exc:
            logger.warning("ha_discover_error", error=str(exc))
            return []

        # Group entities by domain
        domains: dict[str, list[dict[str, Any]]] = {}
        for entity in states:
            entity_id: str = entity.get("entity_id", "")
            domain = entity_id.split(".")[0] if "." in entity_id else "unknown"
            domains.setdefault(domain, []).append(entity)

        # Build discovered resource list
        discovered: list[dict[str, Any]] = []
        now = datetime.now(UTC)
        for domain, entities in sorted(domains.items()):
            discovered.append({
                "resourceType": "ha_domain",
                "domain": domain,
                "source": "homeassistant",
                "discoveredAt": now.isoformat(),
                "entityCount": len(entities),
                "entities": [
                    {
                        "entityId": e.get("entity_id", ""),
                        "state": e.get("state", "unknown"),
                        "friendlyName": e.get("attributes", {}).get("friendly_name", ""),
                        "lastChanged": e.get("last_changed", ""),
                    }
                    for e in entities
                ],
            })

        logger.info(
            "ha_discovery_complete",
            domains=len(domains),
            total_entities=len(states),
        )
        return discovered

    # ── Command Execution ────────────────────────────────────────────

    async def execute_command(
        self,
        command_id: str,
        target: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a Home Assistant command.

        Args:
            command_id: Command registry ID (e.g. ``reg::ha::turn-on``).
            target: Target dict containing entity/domain info.
            params: Additional parameters for the command.

        Returns:
            Result dict with ``success``, ``output``, and optional ``data`` keys.
        """
        dispatch: dict[str, Any] = {
            "reg::ha::list-entities": self._exec_list_entities,
            "reg::ha::get-state": self._exec_get_state,
            "reg::ha::call-service": self._exec_call_service,
            "reg::ha::turn-on": self._exec_turn_on,
            "reg::ha::turn-off": self._exec_turn_off,
            "reg::ha::toggle": self._exec_toggle,
        }

        handler = dispatch.get(command_id)
        if handler is None:
            return {
                "success": False,
                "output": f"Unknown command '{command_id}' for Home Assistant plugin",
            }

        try:
            result: dict[str, Any] = await handler(target, params)
            return result
        except httpx.HTTPError as exc:
            logger.warning(
                "ha_command_error",
                command_id=command_id,
                error=str(exc),
            )
            return {
                "success": False,
                "output": f"HTTP error executing '{command_id}': {exc}",
            }

    async def _exec_list_entities(
        self,
        target: dict[str, Any],  # noqa: ARG002
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """List all HA entities, optionally filtered by domain."""
        resp = await self._request("GET", "/api/states")
        if resp.status_code != 200:
            return {"success": False, "output": f"HTTP {resp.status_code} from HA"}

        entities: list[dict[str, Any]] = resp.json()
        domain_filter = params.get("domain")
        if domain_filter:
            entities = [
                e
                for e in entities
                if e.get("entity_id", "").startswith(f"{domain_filter}.")
            ]

        return {
            "success": True,
            "output": f"Found {len(entities)} entities",
            "data": {
                "count": len(entities),
                "entities": [
                    {
                        "entityId": e.get("entity_id"),
                        "state": e.get("state"),
                        "friendlyName": e.get("attributes", {}).get("friendly_name", ""),
                    }
                    for e in entities
                ],
            },
        }

    async def _exec_get_state(
        self,
        target: dict[str, Any],
        params: dict[str, Any],  # noqa: ARG002
    ) -> dict[str, Any]:
        """Get state of a specific entity."""
        entity_id = target.get("entityId", "")
        if not entity_id:
            return {"success": False, "output": "Missing required target field 'entityId'"}

        resp = await self._request("GET", f"/api/states/{entity_id}")
        if resp.status_code == 404:
            return {"success": False, "output": f"Entity '{entity_id}' not found"}
        if resp.status_code != 200:
            return {"success": False, "output": f"HTTP {resp.status_code} from HA"}

        state_data: dict[str, Any] = resp.json()
        return {
            "success": True,
            "output": f"{entity_id} is {state_data.get('state', 'unknown')}",
            "data": state_data,
        }

    async def _exec_call_service(
        self,
        target: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Call an arbitrary HA service."""
        domain = target.get("domain", "")
        service = target.get("service", "")
        if not domain or not service:
            return {
                "success": False,
                "output": "Missing required target fields 'domain' and 'service'",
            }

        body: dict[str, Any] = {}
        entity_id = params.get("entityId")
        if entity_id:
            body["entity_id"] = entity_id
        service_data = params.get("serviceData")
        if service_data:
            body.update(service_data)

        resp = await self._request("POST", f"/api/services/{domain}/{service}", json_body=body)
        if resp.status_code != 200:
            return {"success": False, "output": f"HTTP {resp.status_code} calling {domain}.{service}"}

        return {
            "success": True,
            "output": f"Called {domain}.{service} successfully",
            "data": resp.json(),
        }

    async def _exec_entity_action(
        self,
        target: dict[str, Any],
        params: dict[str, Any],
        action: str,
    ) -> dict[str, Any]:
        """Shared logic for turn_on, turn_off, and toggle actions."""
        entity_id = target.get("entityId", "")
        if not entity_id:
            return {"success": False, "output": "Missing required target field 'entityId'"}

        domain = entity_id.split(".")[0] if "." in entity_id else "homeassistant"

        body: dict[str, Any] = {"entity_id": entity_id}
        service_data = params.get("serviceData")
        if service_data:
            body.update(service_data)

        resp = await self._request("POST", f"/api/services/{domain}/{action}", json_body=body)
        if resp.status_code != 200:
            return {
                "success": False,
                "output": f"HTTP {resp.status_code} calling {domain}.{action}",
            }

        return {
            "success": True,
            "output": f"Called {domain}.{action} on {entity_id}",
            "data": resp.json(),
        }

    async def _exec_turn_on(
        self,
        target: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Turn on an entity."""
        return await self._exec_entity_action(target, params, "turn_on")

    async def _exec_turn_off(
        self,
        target: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Turn off an entity."""
        return await self._exec_entity_action(target, params, "turn_off")

    async def _exec_toggle(
        self,
        target: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Toggle an entity."""
        return await self._exec_entity_action(target, params, "toggle")
