"""Network management service."""

import ipaddress
import re
from datetime import UTC, datetime
from typing import Any

import structlog
from pymongo import ASCENDING, DESCENDING

from hydra.api.v1.core.exceptions import (
    ConflictError,
    NodeNotFoundError,
    NotFoundError,
    ValidationError,
)
from hydra.api.v1.models.networks import (
    CreateNetworkRequest,
    NetworkListParams,
    NetworkType,
    UpdateNetworkRequest,
    UpdateScanConfigRequest,
)
from hydra.api.v1.models.profiles import NetworkProfile
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)


class NetworkNotFoundError(NotFoundError):
    """Network not found."""

    def __init__(self, network_id: str):
        super().__init__("network", network_id)


class NetworkAlreadyExistsError(ConflictError):
    """Network already exists."""

    def __init__(self, network_id: str):
        super().__init__("network", network_id)


class NetworkHasNodesError(ValidationError):
    """Cannot delete network with associated nodes."""

    def __init__(self, network_id: str, node_count: int):
        super().__init__(
            f"Cannot delete network '{network_id}' with {node_count} associated nodes",
            details={"networkId": network_id, "nodeCount": node_count},
        )


class NetworksService:
    """Service for network management operations."""

    def __init__(self, mongodb: MongoDB):
        self.db = mongodb

    async def get_network(self, network_id: str, include_nodes: bool = False) -> dict[str, Any]:
        """Retrieve a single network by its identifier.

        Args:
            network_id: The unique network identifier.
            include_nodes: Whether to include the list of nodes in this network.

        Returns:
            The formatted network document, optionally with nodes.

        Raises:
            NetworkNotFoundError: If no network exists with the given ID.
        """
        network = await self.db.networks.find_one({"networkId": network_id})
        if not network:
            raise NetworkNotFoundError(network_id)

        result = self._format_network(network)

        if include_nodes:
            nodes = await self._get_network_nodes(network_id)
            result["nodes"] = nodes

        return result

    async def list_networks(self, params: NetworkListParams) -> tuple[list[dict[str, Any]], int]:
        """List networks with optional filtering, sorting, and pagination.

        Args:
            params: Query parameters including filters (type, parent_network_id,
                router_node_id, cidr, tags, search), sorting, and pagination.

        Returns:
            A tuple of (list of network summaries, total count).
        """
        filter_query: dict[str, Any] = {}

        if params.type:
            filter_query["type"] = params.type.value
        if params.parent_network_id:
            filter_query["parentNetworkId"] = params.parent_network_id
        if params.router_node_id:
            filter_query["routerNodeId"] = params.router_node_id
        if params.cidr:
            filter_query["cidr"] = params.cidr
        if params.tags:
            filter_query["tags"] = {"$all": params.tags}
        if params.search:
            escaped = re.escape(params.search)
            filter_query["$or"] = [
                {"name": {"$regex": escaped, "$options": "i"}},
                {"networkId": {"$regex": escaped, "$options": "i"}},
                {"cidr": {"$regex": escaped, "$options": "i"}},
            ]

        sort_field_map = {
            "networkId": "networkId",
            "name": "name",
            "createdAt": "createdAt",
            "updatedAt": "updatedAt",
            "nodeCount": "nodeCount",
        }
        sort_field = sort_field_map.get(params.sort_by, "updatedAt")
        sort_direction = DESCENDING if params.sort_order == "desc" else ASCENDING

        total = await self.db.networks.count_documents(filter_query)

        cursor = (
            self.db.networks.find(filter_query)
            .sort(sort_field, sort_direction)
            .skip(params.offset)
            .limit(params.limit)
        )

        networks = []
        async for network in cursor:
            networks.append(self._format_network_summary(network))

        logger.info(
            "networks_listed",
            total=total,
            returned=len(networks),
            filters={k: v for k, v in filter_query.items() if k != "$or"},
        )

        return networks, total

    async def create_network(
        self,
        request: CreateNetworkRequest,
        created_by: str = "manual",
    ) -> dict[str, Any]:
        """Create a new network.

        Args:
            request: Network creation payload with network_id, type, name, cidr, etc.
            created_by: Origin of the creation (manual, auto, etc.).

        Returns:
            The created network document.

        Raises:
            NetworkAlreadyExistsError: If a network with the same ID already exists.
            ValidationError: If parent network or router node does not exist.
        """
        existing = await self.db.networks.find_one({"networkId": request.network_id})
        if existing:
            raise NetworkAlreadyExistsError(request.network_id)

        if request.parent_network_id:
            parent = await self.db.networks.find_one({"networkId": request.parent_network_id})
            if not parent:
                raise NetworkNotFoundError(request.parent_network_id)

        if request.router_node_id:
            router = await self.db.nodes.find_one({"nodeId": request.router_node_id})
            if not router:
                raise NodeNotFoundError(request.router_node_id)

        now = datetime.now(UTC)

        network_doc: dict[str, Any] = {
            "networkId": request.network_id,
            "type": request.type.value,
            "name": request.name,
            "description": request.description,
            "cidr": request.cidr,
            "cidrV6": request.cidr_v6,
            "gatewayV4": request.gateway_v4,
            "gatewayV6": request.gateway_v6,
            "vlanId": request.vlan_id,
            "parentNetworkId": request.parent_network_id,
            "subnetIds": [],
            "routerNodeId": request.router_node_id,
            "dhcp": request.dhcp.model_dump(by_alias=True) if request.dhcp else None,
            "dns": request.dns.model_dump(by_alias=True) if request.dns else None,
            "scanConfig": {
                "status": "unreachable",
                "apiReachable": False,
                "apiReachabilityTest": None,
                "delegateAgentNodeIds": [],
                "delegateAgentTierRequired": "max",
                "userGuidance": None,
            },
            "nodeCount": 0,
            "origin": {
                "createdBy": created_by,
                "sourceNodeId": None,
                "sourceProfileId": None,
            },
            "tags": request.tags,
            "createdAt": now,
            "updatedAt": now,
        }

        await self.db.networks.insert_one(network_doc)

        if request.parent_network_id:
            await self.db.networks.update_one(
                {"networkId": request.parent_network_id},
                {"$addToSet": {"subnetIds": request.network_id}},
            )

        logger.info("network_created", network_id=request.network_id, type=request.type.value)

        return self._format_network(network_doc)

    async def update_network(self, network_id: str, request: UpdateNetworkRequest) -> dict[str, Any]:
        """Update network metadata.

        Args:
            network_id: The unique network identifier.
            request: Update payload with optional name, description, gateways,
                router_node_id, dhcp, dns, and tags.

        Returns:
            The updated network document.

        Raises:
            NetworkNotFoundError: If no network exists with the given ID.
            ValidationError: If specified router node does not exist.
        """
        existing = await self.db.networks.find_one({"networkId": network_id})
        if not existing:
            raise NetworkNotFoundError(network_id)

        update_fields: dict[str, Any] = {"updatedAt": datetime.now(UTC)}

        if request.name is not None:
            update_fields["name"] = request.name
        if request.description is not None:
            update_fields["description"] = request.description
        if request.gateway_v4 is not None:
            update_fields["gatewayV4"] = request.gateway_v4
        if request.gateway_v6 is not None:
            update_fields["gatewayV6"] = request.gateway_v6
        if request.router_node_id is not None:
            if request.router_node_id:
                router = await self.db.nodes.find_one({"nodeId": request.router_node_id})
                if not router:
                    raise NodeNotFoundError(request.router_node_id)
            update_fields["routerNodeId"] = request.router_node_id or None
        if request.dhcp is not None:
            update_fields["dhcp"] = request.dhcp.model_dump(by_alias=True)
        if request.dns is not None:
            update_fields["dns"] = request.dns.model_dump(by_alias=True)
        if request.tags is not None:
            update_fields["tags"] = request.tags

        result = await self.db.networks.update_one(
            {"networkId": network_id},
            {"$set": update_fields},
        )

        if result.modified_count == 0:
            logger.warning("network_update_no_changes", network_id=network_id)

        logger.info("network_updated", network_id=network_id, fields=list(update_fields.keys()))

        return await self.get_network(network_id)

    async def update_scan_config(
        self,
        network_id: str,
        request: UpdateScanConfigRequest,
    ) -> dict[str, Any]:
        """Update a network's scan configuration.

        Args:
            network_id: The network to update.
            request: Scan config fields to update.

        Returns:
            The updated network document.

        Raises:
            NetworkNotFoundError: If no network exists with the given ID.
        """
        existing = await self.db.networks.find_one({"networkId": network_id})
        if not existing:
            raise NetworkNotFoundError(network_id)

        update_fields: dict[str, Any] = {"updatedAt": datetime.now(UTC)}

        if request.status is not None:
            update_fields["scanConfig.status"] = request.status.value
        if request.delegate_agent_node_ids is not None:
            # Validate that referenced nodes exist
            for node_id in request.delegate_agent_node_ids:
                node = await self.db.nodes.find_one({"nodeId": node_id})
                if not node:
                    raise NodeNotFoundError(node_id)
            update_fields["scanConfig.delegateAgentNodeIds"] = (
                request.delegate_agent_node_ids
            )
        if request.delegate_agent_tier_required is not None:
            update_fields["scanConfig.delegateAgentTierRequired"] = (
                request.delegate_agent_tier_required
            )
        if request.user_guidance is not None:
            update_fields["scanConfig.userGuidance"] = request.user_guidance or None

        # Generate guidance for unreachable networks if not explicitly set
        status = request.status.value if request.status else None
        if status == "unreachable" and request.user_guidance is None:
            update_fields["scanConfig.userGuidance"] = (
                "This network is not reachable from the API server. "
                "Configure a delegate agent on a node within this network "
                "to enable discovery scanning."
            )

        await self.db.networks.update_one(
            {"networkId": network_id},
            {"$set": update_fields},
        )

        logger.info(
            "network_scan_config_updated",
            network_id=network_id,
            fields=list(update_fields.keys()),
        )

        return await self.get_network(network_id)

    async def delete_network(self, network_id: str, force: bool = False) -> dict[str, Any]:
        """Delete a network.

        Args:
            network_id: The unique network identifier.
            force: If True, delete even if nodes are associated.

        Returns:
            The deleted network document.

        Raises:
            NetworkNotFoundError: If no network exists with the given ID.
            NetworkHasNodesError: If network has associated nodes and force is False.
        """
        existing = await self.db.networks.find_one({"networkId": network_id})
        if not existing:
            raise NetworkNotFoundError(network_id)

        node_count = existing.get("nodeCount", 0)
        if node_count > 0 and not force:
            raise NetworkHasNodesError(network_id, node_count)

        await self.db.nodes.update_many(
            {"networkIds": network_id},
            {"$pull": {"networkIds": network_id}},
        )

        if existing.get("parentNetworkId"):
            await self.db.networks.update_one(
                {"networkId": existing["parentNetworkId"]},
                {"$pull": {"subnetIds": network_id}},
            )

        await self.db.networks.delete_one({"networkId": network_id})

        logger.info("network_deleted", network_id=network_id, force=force)

        return self._format_network(existing)

    async def get_network_nodes(self, network_id: str) -> list[dict[str, Any]]:
        """Get all nodes in a network.

        Args:
            network_id: The unique network identifier.

        Returns:
            List of node summaries in the network.

        Raises:
            NetworkNotFoundError: If no network exists with the given ID.
        """
        network = await self.db.networks.find_one({"networkId": network_id})
        if not network:
            raise NetworkNotFoundError(network_id)

        return await self._get_network_nodes(network_id)

    async def _get_network_nodes(self, network_id: str) -> list[dict[str, Any]]:
        """Get nodes belonging to a specific network."""
        nodes = []
        cursor = self.db.nodes.find({"networkIds": network_id})
        async for node in cursor:
            nodes.append({
                "nodeId": node["nodeId"],
                "displayName": node["displayName"],
                "class": node["class"],
                "ipAddresses": [],
            })
        return nodes

    async def process_profile_networks(
        self,
        node_id: str,
        profile_id: str,
        network_profile: NetworkProfile | None,
    ) -> list[str]:
        """Extract networks from profile and auto-create/update.

        Args:
            node_id: The node identifier.
            profile_id: The profile identifier.
            network_profile: The network section from the profile.

        Returns:
            List of network IDs the node belongs to.
        """
        if not network_profile or not network_profile.interfaces:
            return []

        network_ids: set[str] = set()
        now = datetime.now(UTC)

        for interface in network_profile.interfaces:
            if interface.name == "lo" or interface.name.startswith("veth"):
                continue

            for ip_str in interface.ipv4_addresses:
                try:
                    if "/" in ip_str:
                        ip_interface = ipaddress.ip_interface(ip_str)
                        network = ip_interface.network
                    elif interface.netmask:
                        ip = ipaddress.ip_address(ip_str)
                        netmask = ipaddress.ip_address(interface.netmask)
                        prefix_len = bin(int(netmask)).count("1")
                        network = ipaddress.ip_network(f"{ip}/{prefix_len}", strict=False)
                    else:
                        ip = ipaddress.ip_address(ip_str)
                        network = ipaddress.ip_network(f"{ip}/24", strict=False)

                    if network.is_loopback or network.is_link_local:
                        continue

                    cidr = str(network)
                    network_id = self._generate_network_id(cidr)
                    network_ids.add(network_id)

                    await self.db.networks.update_one(
                        {"networkId": network_id},
                        {
                            "$set": {
                                "updatedAt": now,
                            },
                            "$setOnInsert": {
                                "networkId": network_id,
                                "type": NetworkType.PHYSICAL.value,
                                "name": f"Network {cidr}",
                                "cidr": cidr,
                                "gatewayV4": interface.gateway or network_profile.default_gateway,
                                "origin": {
                                    "createdBy": "auto",
                                    "sourceNodeId": node_id,
                                    "sourceProfileId": profile_id,
                                },
                                "tags": ["auto-discovered"],
                                "nodeCount": 0,
                                "createdAt": now,
                            },
                        },
                        upsert=True,
                    )

                except (ValueError, TypeError) as e:
                    logger.warning(
                        "invalid_ip_address",
                        node_id=node_id,
                        interface=interface.name,
                        ip=ip_str,
                        error=str(e),
                    )
                    continue

        network_id_list = list(network_ids)
        if network_id_list:
            await self.db.nodes.update_one(
                {"nodeId": node_id},
                {"$set": {"networkIds": network_id_list}},
            )

            for net_id in network_id_list:
                count = await self.db.nodes.count_documents({"networkIds": net_id})
                await self.db.networks.update_one(
                    {"networkId": net_id},
                    {"$set": {"nodeCount": count}},
                )

        logger.info(
            "profile_networks_processed",
            node_id=node_id,
            network_count=len(network_id_list),
            networks=network_id_list,
        )

        return network_id_list

    def _generate_network_id(self, cidr: str) -> str:
        """Generate a network ID from CIDR notation."""
        return cidr.replace(".", "-").replace("/", "-")

    def _format_network(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Format a network document for API response."""
        return {
            "networkId": doc["networkId"],
            "type": doc["type"],
            "name": doc["name"],
            "description": doc.get("description"),
            "cidr": doc.get("cidr"),
            "cidrV6": doc.get("cidrV6"),
            "gatewayV4": doc.get("gatewayV4"),
            "gatewayV6": doc.get("gatewayV6"),
            "vlanId": doc.get("vlanId"),
            "parentNetworkId": doc.get("parentNetworkId"),
            "subnetIds": doc.get("subnetIds", []),
            "routerNodeId": doc.get("routerNodeId"),
            "dhcp": doc.get("dhcp"),
            "dns": doc.get("dns"),
            "scanConfig": doc.get("scanConfig"),
            "nodeCount": doc.get("nodeCount", 0),
            "origin": doc.get("origin", {}),
            "tags": doc.get("tags", []),
            "createdAt": doc.get("createdAt"),
            "updatedAt": doc.get("updatedAt"),
        }

    def _format_network_summary(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Format a network document for list response."""
        return {
            "networkId": doc["networkId"],
            "type": doc["type"],
            "name": doc["name"],
            "cidr": doc.get("cidr"),
            "gatewayV4": doc.get("gatewayV4"),
            "routerNodeId": doc.get("routerNodeId"),
            "nodeCount": doc.get("nodeCount", 0),
            "tags": doc.get("tags", []),
        }
