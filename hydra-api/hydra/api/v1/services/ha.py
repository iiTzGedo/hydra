"""Home Assistant integration service."""

import contextlib
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
import structlog

from hydra.api.v1.core.exceptions import HomeAssistantUnavailableError
from hydra.api.v1.models.ha import HAControlRequest, HADeviceListParams, HASyncRequest
from hydra.api.v1.models.notifications import NotificationSource, NotificationType, SourceComponent
from hydra.api.v1.services.notifications import emit_notification
from hydra.core.config import Settings, get_settings
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class HomeAssistantService:
    """Service for Home Assistant integration.

    This service manages HTTP connections to a Home Assistant instance.
    It supports async context manager usage for automatic resource cleanup:

        async with HomeAssistantService(mongodb) as ha:
            status = await ha.get_status()
    """

    def __init__(self, mongodb: MongoDB, settings: Settings | None = None):
        self.mongodb = mongodb
        self.settings = settings or get_settings()
        self._http_client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "HomeAssistantService":
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[no-untyped-def]
        """Exit async context manager and clean up resources."""
        await self.close()

    @property
    def enabled(self) -> bool:
        """Check if HA integration is enabled."""
        return bool(
            getattr(self.settings, "ha_enabled", False)
            and getattr(self.settings, "ha_url", None)
            and getattr(self.settings, "ha_token", None)
        )

    @property
    def ha_url(self) -> str | None:
        """Get HA URL from settings."""
        return getattr(self.settings, "ha_url", None)

    @property
    def ha_token(self) -> str | None:
        """Get HA token from settings."""
        return getattr(self.settings, "ha_token", None)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for HA API calls."""
        if self._http_client is None or self._http_client.is_closed:
            if not self.enabled:
                raise HomeAssistantUnavailableError("Home Assistant integration is not enabled")

            self._http_client = httpx.AsyncClient(
                base_url=self.ha_url,  # type: ignore[arg-type]
                headers={
                    "Authorization": f"Bearer {self.ha_token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._http_client

    async def _ha_request(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a request to Home Assistant API."""
        try:
            client = await self._get_client()
            response = await client.request(method, endpoint, json=json_data)
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except httpx.ConnectError as e:
            logger.error("ha_connection_error", error=str(e))
            with contextlib.suppress(Exception):
                await emit_notification(
                    NotificationType.IOT_DEVICE_UNREACHABLE,
                    NotificationSource(component=SourceComponent.HYDRA_API, service="ha"),
                    "IoT device unreachable",
                    f"Failed to connect to device: {str(e)}",
                )
            raise HomeAssistantUnavailableError("Unable to connect to Home Assistant")
        except httpx.HTTPStatusError as e:
            logger.error("ha_http_error", status=e.response.status_code, error=str(e))
            raise HomeAssistantUnavailableError(f"Home Assistant returned error: {e.response.status_code}")

    async def get_status(self) -> dict[str, Any]:
        """Get Home Assistant integration status.

        Returns:
            Status dict with enabled, connected, url, lastSync, entityCount, and mappedNodes.
        """
        status = {
            "enabled": self.enabled,
            "connected": False,
            "url": self.ha_url,
            "lastSync": None,
            "entityCount": 0,
            "mappedNodes": 0,
        }

        if not self.enabled:
            return status

        try:
            await self._ha_request("GET", "/api/")
            status["connected"] = True

            states = await self._ha_request("GET", "/api/states")
            status["entityCount"] = len(states) if isinstance(states, list) else 0

            mapped_count = await self.mongodb.nodes.count_documents({
                "tags": "ha-device",
                "status": "active",
            })
            status["mappedNodes"] = mapped_count

            sync_meta = await self.mongodb.db.ha_sync_meta.find_one({"type": "last_sync"})
            if sync_meta:
                status["lastSync"] = sync_meta.get("timestamp")

        except HomeAssistantUnavailableError as e:
            logger.warning("ha_status_check_unavailable", error=str(e))
            status["connected"] = False
            with contextlib.suppress(Exception):
                await emit_notification(
                    NotificationType.IOT_DEVICE_UNREACHABLE,
                    NotificationSource(component=SourceComponent.HYDRA_API, service="ha"),
                    "IoT device unreachable",
                    f"Failed to connect to device: {str(e)}",
                )
        except httpx.TimeoutException:
            logger.warning("ha_status_check_timeout")
            status["connected"] = False
            with contextlib.suppress(Exception):
                await emit_notification(
                    NotificationType.IOT_DEVICE_UNREACHABLE,
                    NotificationSource(component=SourceComponent.HYDRA_API, service="ha"),
                    "IoT device unreachable",
                    "Failed to connect to device: connection timed out",
                )
        except httpx.ConnectError as e:
            logger.warning("ha_status_check_connection_error", error=str(e))
            status["connected"] = False
            with contextlib.suppress(Exception):
                await emit_notification(
                    NotificationType.IOT_DEVICE_UNREACHABLE,
                    NotificationSource(component=SourceComponent.HYDRA_API, service="ha"),
                    "IoT device unreachable",
                    f"Failed to connect to device: {str(e)}",
                )
        except Exception as e:
            logger.error("ha_status_check_unexpected_error", error=str(e), error_type=type(e).__name__)
            status["connected"] = False

        return status

    async def list_devices(
        self, params: HADeviceListParams
    ) -> tuple[list[dict[str, Any]], int]:
        """List Home Assistant devices/entities.

        Args:
            params: Query parameters with domain, area, and mapped filters.

        Returns:
            Tuple of (devices list, total count).

        Raises:
            HomeAssistantUnavailableError: If HA integration is not enabled.
        """
        if not self.enabled:
            raise HomeAssistantUnavailableError("Home Assistant integration is not enabled")

        states = await self._ha_request("GET", "/api/states")

        # Batch fetch all HA-mapped nodes to avoid N+1 queries
        ha_nodes_cursor = self.mongodb.nodes.find(
            {"metadata.haEntityId": {"$exists": True}, "status": "active"},
            {"nodeId": 1, "displayName": 1, "metadata.haEntityId": 1},
        )
        ha_node_map: dict[str, dict[str, Any]] = {}
        async for node in ha_nodes_cursor:
            entity_id = node.get("metadata", {}).get("haEntityId")
            if entity_id:
                ha_node_map[entity_id] = {
                    "nodeId": node["nodeId"],
                    "displayName": node["displayName"],
                }

        devices = []
        for state in states:
            entity_id = state.get("entity_id", "")  # type: ignore[attr-defined]
            domain = entity_id.split(".")[0] if "." in entity_id else ""

            if params.domain and domain != params.domain:
                continue

            area = state.get("attributes", {}).get("area_id")  # type: ignore[attr-defined]
            if params.area and area != params.area:
                continue

            # Look up mapping in memory instead of querying DB
            hydra_node = ha_node_map.get(entity_id)
            has_mapping = hydra_node is not None

            if params.mapped is not None and params.mapped != has_mapping:
                continue

            device = {
                "entityId": entity_id,
                "name": state.get("attributes", {}).get("friendly_name", entity_id),  # type: ignore[attr-defined]
                "domain": domain,
                "area": area,
                "state": state.get("state", "unknown"),  # type: ignore[attr-defined]
                "attributes": state.get("attributes", {}),  # type: ignore[attr-defined]
                "lastUpdated": state.get("last_updated"),  # type: ignore[attr-defined]
            }

            if hydra_node:
                device["hydraNode"] = hydra_node

            devices.append(device)

        total = len(devices)
        devices = devices[params.offset : params.offset + params.limit]

        return devices, total

    async def sync_devices(self, request: HASyncRequest) -> dict[str, Any]:
        """Trigger sync from Home Assistant.

        Fetches entities from HA and optionally creates/updates Hydra nodes
        for each device using bulk operations to avoid N+1 queries.

        Args:
            request: Sync configuration with domains filter and create_nodes flag.

        Returns:
            Sync result with job_id, status, and created/updated counts.

        Raises:
            HomeAssistantUnavailableError: If HA integration is not enabled.
        """
        if not self.enabled:
            raise HomeAssistantUnavailableError("Home Assistant integration is not enabled")

        job_id = f"job-ha-sync-{uuid4().hex[:8]}"
        now = datetime.now(UTC)

        states = await self._ha_request("GET", "/api/states")

        created_nodes = 0
        updated_nodes = 0

        if request.create_nodes:
            # Filter states by domain
            filtered_states = []
            for state in states:
                entity_id = state.get("entity_id", "")  # type: ignore[attr-defined]
                domain = entity_id.split(".")[0] if "." in entity_id else ""
                if request.domains and domain not in request.domains:
                    continue
                filtered_states.append((entity_id, domain, state))

            if filtered_states:
                # Build node IDs to check which ones exist
                node_ids = [
                    f"ha-{domain}-{entity_id.replace('.', '-')}"
                    for entity_id, domain, _ in filtered_states
                ]

                # Batch fetch existing nodes
                existing_cursor = self.mongodb.nodes.find(
                    {"nodeId": {"$in": node_ids}},
                    {"nodeId": 1},
                )
                existing_node_ids = {doc["nodeId"] async for doc in existing_cursor}

                # Build bulk operations
                from pymongo import InsertOne, UpdateOne

                operations = []
                for entity_id, domain, state in filtered_states:
                    node_id = f"ha-{domain}-{entity_id.replace('.', '-')}"
                    friendly_name = state.get("attributes", {}).get("friendly_name", entity_id)  # type: ignore[attr-defined]

                    if node_id in existing_node_ids:
                        operations.append(
                            UpdateOne(
                                {"nodeId": node_id},
                                {
                                    "$set": {
                                        "displayName": friendly_name,
                                        "metadata.haEntityId": entity_id,
                                        "metadata.haState": state.get("state"),  # type: ignore[attr-defined]
                                        "metadata.haLastUpdated": state.get("last_updated"),  # type: ignore[attr-defined]
                                        "updatedAt": now,
                                    }
                                },
                            )
                        )
                        updated_nodes += 1
                    else:
                        operations.append(
                            InsertOne({  # type: ignore[arg-type]
                                "nodeId": node_id,
                                "class": "iot",
                                "type": "logical",
                                "kind": self._domain_to_kind(domain),
                                "displayName": friendly_name,
                                "description": f"Home Assistant {domain} device",
                                "tags": ["ha-device", domain],
                                "status": "active",
                                "metadata": {
                                    "haEntityId": entity_id,
                                    "haState": state.get("state"),  # type: ignore[attr-defined]
                                    "haDomain": domain,
                                    "haLastUpdated": state.get("last_updated"),  # type: ignore[attr-defined]
                                },
                                "registeredAt": now,
                                "updatedAt": now,
                            })
                        )
                        created_nodes += 1

                # Execute bulk operations
                if operations:
                    await self.mongodb.nodes.bulk_write(operations, ordered=False)

        await self.mongodb.db.ha_sync_meta.update_one(
            {"type": "last_sync"},
            {
                "$set": {
                    "timestamp": now,
                    "createdNodes": created_nodes,
                    "updatedNodes": updated_nodes,
                }
            },
            upsert=True,
        )

        logger.info(
            "ha_sync_completed",
            job_id=job_id,
            created=created_nodes,
            updated=updated_nodes,
        )

        return {
            "jobId": job_id,
            "status": "completed",
            "startedAt": now,
            "createdNodes": created_nodes,
            "updatedNodes": updated_nodes,
        }

    async def control_device(self, request: HAControlRequest) -> dict[str, Any]:
        """Control a Home Assistant device.

        Args:
            request: Control request with entity_id, service, and optional data.

        Returns:
            Control result with entity_id, service, success status, and new state.

        Raises:
            HomeAssistantUnavailableError: If HA integration is not enabled.
        """
        if not self.enabled:
            raise HomeAssistantUnavailableError("Home Assistant integration is not enabled")

        entity_id = request.entity_id
        domain = entity_id.split(".")[0] if "." in entity_id else ""

        service_data = {
            "entity_id": entity_id,
            **(request.data or {}),
        }

        try:
            await self._ha_request(
                "POST",
                f"/api/services/{domain}/{request.service}",
                json_data=service_data,
            )

            new_state = await self._ha_request("GET", f"/api/states/{entity_id}")

            return {
                "entityId": entity_id,
                "service": request.service,
                "success": True,
                "newState": {
                    "state": new_state.get("state"),
                    "attributes": new_state.get("attributes", {}),
                },
            }
        except HomeAssistantUnavailableError as e:
            logger.warning("ha_control_unavailable", entity_id=entity_id, error=str(e))
            with contextlib.suppress(Exception):
                await emit_notification(
                    NotificationType.IOT_DEVICE_UNREACHABLE,
                    NotificationSource(component=SourceComponent.HYDRA_API, service="ha"),
                    "IoT device unreachable",
                    f"Failed to connect to device: {str(e)}",
                )
            return {
                "entityId": entity_id,
                "service": request.service,
                "success": False,
                "newState": None,
            }
        except httpx.TimeoutException:
            logger.warning("ha_control_timeout", entity_id=entity_id)
            with contextlib.suppress(Exception):
                await emit_notification(
                    NotificationType.IOT_DEVICE_UNREACHABLE,
                    NotificationSource(component=SourceComponent.HYDRA_API, service="ha"),
                    "IoT device unreachable",
                    f"Failed to connect to device: connection timed out for {entity_id}",
                )
            return {
                "entityId": entity_id,
                "service": request.service,
                "success": False,
                "newState": None,
            }
        except httpx.ConnectError as e:
            logger.warning("ha_control_connection_error", entity_id=entity_id, error=str(e))
            with contextlib.suppress(Exception):
                await emit_notification(
                    NotificationType.IOT_DEVICE_UNREACHABLE,
                    NotificationSource(component=SourceComponent.HYDRA_API, service="ha"),
                    "IoT device unreachable",
                    f"Failed to connect to device: {str(e)}",
                )
            return {
                "entityId": entity_id,
                "service": request.service,
                "success": False,
                "newState": None,
            }
        except Exception as e:
            logger.error("ha_control_unexpected_error", entity_id=entity_id, error=str(e), error_type=type(e).__name__)
            return {
                "entityId": entity_id,
                "service": request.service,
                "success": False,
                "newState": None,
            }

    async def list_areas(self) -> tuple[list[dict[str, Any]], int]:
        """List Home Assistant areas.

        Aggregates area information from entity attributes since the REST API
        does not provide a direct areas endpoint.

        Returns:
            Tuple of (areas list, total count).

        Raises:
            HomeAssistantUnavailableError: If HA integration is not enabled.
        """
        if not self.enabled:
            raise HomeAssistantUnavailableError("Home Assistant integration is not enabled")

        try:
            states = await self._ha_request("GET", "/api/states")

            areas: dict[str, dict[str, Any]] = {}
            for state in states:
                area_id = state.get("attributes", {}).get("area_id")  # type: ignore[attr-defined]
                if area_id:
                    if area_id not in areas:
                        areas[area_id] = {
                            "areaId": area_id,
                            "name": area_id.replace("_", " ").title(),
                            "deviceCount": 0,
                            "entityCount": 0,
                        }
                    areas[area_id]["entityCount"] += 1

            area_list = list(areas.values())
            return area_list, len(area_list)

        except HomeAssistantUnavailableError as e:
            logger.warning("ha_list_areas_unavailable", error=str(e))
            with contextlib.suppress(Exception):
                await emit_notification(
                    NotificationType.IOT_DEVICE_UNREACHABLE,
                    NotificationSource(component=SourceComponent.HYDRA_API, service="ha"),
                    "IoT device unreachable",
                    f"Failed to connect to device: {str(e)}",
                )
            return [], 0
        except httpx.TimeoutException:
            logger.warning("ha_list_areas_timeout")
            with contextlib.suppress(Exception):
                await emit_notification(
                    NotificationType.IOT_DEVICE_UNREACHABLE,
                    NotificationSource(component=SourceComponent.HYDRA_API, service="ha"),
                    "IoT device unreachable",
                    "Failed to connect to device: connection timed out",
                )
            return [], 0
        except httpx.ConnectError as e:
            logger.warning("ha_list_areas_connection_error", error=str(e))
            with contextlib.suppress(Exception):
                await emit_notification(
                    NotificationType.IOT_DEVICE_UNREACHABLE,
                    NotificationSource(component=SourceComponent.HYDRA_API, service="ha"),
                    "IoT device unreachable",
                    f"Failed to connect to device: {str(e)}",
                )
            return [], 0
        except Exception as e:
            logger.error("ha_list_areas_unexpected_error", error=str(e), error_type=type(e).__name__)
            return [], 0

    def _domain_to_kind(self, domain: str) -> str:
        """Map HA domain to Hydra node kind."""
        mapping = {
            "climate": "controller",
            "light": "actuator",
            "switch": "actuator",
            "sensor": "sensor",
            "binary_sensor": "sensor",
            "cover": "actuator",
            "fan": "actuator",
            "lock": "actuator",
            "media_player": "appliance",
            "vacuum": "appliance",
            "camera": "sensor",
        }
        return mapping.get(domain, "sensor")

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
