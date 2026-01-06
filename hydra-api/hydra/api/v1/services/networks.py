"""Network management service."""

import ipaddress
from datetime import datetime, timezone
from typing import Any

import structlog
from pymongo import ASCENDING, DESCENDING

from hydra.api.v1.core.exceptions import ConflictError, NotFoundError, ValidationError
from hydra.db.mongodb import MongoDB
from hydra.api.v1.models.networks import (
    CreateNetworkRequest,
    NetworkListParams,
    NetworkType,
    UpdateNetworkRequest,
)
from hydra.api.v1.models.profiles import NetworkProfile

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

    async def get_network(self, network_id: str, include_nodes: bool = False) -> dict:
        """Get a single network by ID."""
        network = await self.db.networks.find_one({"networkId": network_id})
        if not network:
            raise NetworkNotFoundError(network_id)

        result = self._format_network(network)

        if include_nodes:
            nodes = await self._get_network_nodes(network_id)
            result["nodes"] = nodes

        return result

    async def list_networks(self, params: NetworkListParams) -> tuple[list[dict], int]:
        """
        List networks with filters and pagination.

        Returns:
            Tuple of (networks list, total count)
        """
        # Build filter
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
            filter_query["$or"] = [
                {"name": {"$regex": params.search, "$options": "i"}},
                {"networkId": {"$regex": params.search, "$options": "i"}},
                {"cidr": {"$regex": params.search, "$options": "i"}},
            ]

        # Sort
        sort_field_map = {
            "networkId": "networkId",
            "name": "name",
            "createdAt": "createdAt",
            "updatedAt": "updatedAt",
            "nodeCount": "nodeCount",
        }
        sort_field = sort_field_map.get(params.sort_by, "updatedAt")
        sort_direction = DESCENDING if params.sort_order == "desc" else ASCENDING

        # Execute queries
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
    ) -> dict:
        """Create a new network."""
        # Check if network already exists
        existing = await self.db.networks.find_one({"networkId": request.network_id})
        if existing:
            raise NetworkAlreadyExistsError(request.network_id)

        # Validate parent network if specified
        if request.parent_network_id:
            parent = await self.db.networks.find_one({"networkId": request.parent_network_id})
            if not parent:
                raise ValidationError(
                    f"Parent network '{request.parent_network_id}' not found",
                    {"parentNetworkId": request.parent_network_id},
                )

        # Validate router node if specified
        if request.router_node_id:
            router = await self.db.nodes.find_one({"nodeId": request.router_node_id})
            if not router:
                raise ValidationError(
                    f"Router node '{request.router_node_id}' not found",
                    {"routerNodeId": request.router_node_id},
                )

        now = datetime.now(timezone.utc)

        network_doc = {
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

        # Update parent's subnetIds if specified
        if request.parent_network_id:
            await self.db.networks.update_one(
                {"networkId": request.parent_network_id},
                {"$addToSet": {"subnetIds": request.network_id}},
            )

        logger.info("network_created", network_id=request.network_id, type=request.type.value)

        return self._format_network(network_doc)

    async def update_network(self, network_id: str, request: UpdateNetworkRequest) -> dict:
        """Update network metadata."""
        existing = await self.db.networks.find_one({"networkId": network_id})
        if not existing:
            raise NetworkNotFoundError(network_id)

        # Build update
        update_fields: dict[str, Any] = {"updatedAt": datetime.now(timezone.utc)}

        if request.name is not None:
            update_fields["name"] = request.name
        if request.description is not None:
            update_fields["description"] = request.description
        if request.gateway_v4 is not None:
            update_fields["gatewayV4"] = request.gateway_v4
        if request.gateway_v6 is not None:
            update_fields["gatewayV6"] = request.gateway_v6
        if request.router_node_id is not None:
            # Validate router node exists
            if request.router_node_id:
                router = await self.db.nodes.find_one({"nodeId": request.router_node_id})
                if not router:
                    raise ValidationError(
                        f"Router node '{request.router_node_id}' not found",
                        {"routerNodeId": request.router_node_id},
                    )
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

    async def delete_network(self, network_id: str, force: bool = False) -> dict:
        """Delete a network."""
        existing = await self.db.networks.find_one({"networkId": network_id})
        if not existing:
            raise NetworkNotFoundError(network_id)

        # Check for associated nodes
        node_count = existing.get("nodeCount", 0)
        if node_count > 0 and not force:
            raise NetworkHasNodesError(network_id, node_count)

        # Remove from nodes' networkIds
        await self.db.nodes.update_many(
            {"networkIds": network_id},
            {"$pull": {"networkIds": network_id}},
        )

        # Remove from parent's subnetIds
        if existing.get("parentNetworkId"):
            await self.db.networks.update_one(
                {"networkId": existing["parentNetworkId"]},
                {"$pull": {"subnetIds": network_id}},
            )

        # Delete the network
        await self.db.networks.delete_one({"networkId": network_id})

        logger.info("network_deleted", network_id=network_id, force=force)

        return self._format_network(existing)

    async def get_network_nodes(self, network_id: str) -> list[dict]:
        """Get all nodes in a network."""
        network = await self.db.networks.find_one({"networkId": network_id})
        if not network:
            raise NetworkNotFoundError(network_id)

        return await self._get_network_nodes(network_id)

    async def _get_network_nodes(self, network_id: str) -> list[dict]:
        """Internal method to get nodes in a network."""
        nodes = []
        cursor = self.db.nodes.find({"networkIds": network_id})
        async for node in cursor:
            nodes.append({
                "nodeId": node["nodeId"],
                "displayName": node["displayName"],
                "class": node["class"],
                "ipAddresses": [],  # Would need to look up from profiles
            })
        return nodes

    async def process_profile_networks(
        self,
        node_id: str,
        profile_id: str,
        network_profile: NetworkProfile | None,
    ) -> list[str]:
        """
        Extract networks from profile and auto-create/update.

        Returns list of network IDs the node belongs to.
        """
        if not network_profile or not network_profile.interfaces:
            return []

        network_ids: set[str] = set()
        now = datetime.now(timezone.utc)

        for interface in network_profile.interfaces:
            # Skip loopback and link-local interfaces
            if interface.name == "lo" or interface.name.startswith("veth"):
                continue

            # Process IPv4 addresses
            for ip_str in interface.ipv4_addresses:
                try:
                    # Parse the IP address
                    if "/" in ip_str:
                        ip_interface = ipaddress.ip_interface(ip_str)
                        network = ip_interface.network
                    elif interface.netmask:
                        ip = ipaddress.ip_address(ip_str)
                        netmask = ipaddress.ip_address(interface.netmask)
                        prefix_len = bin(int(netmask)).count("1")
                        network = ipaddress.ip_network(f"{ip}/{prefix_len}", strict=False)
                    else:
                        # Default to /24 for IPv4 if no netmask
                        ip = ipaddress.ip_address(ip_str)
                        network = ipaddress.ip_network(f"{ip}/24", strict=False)

                    # Skip localhost and link-local
                    if network.is_loopback or network.is_link_local:
                        continue

                    cidr = str(network)
                    network_id = self._generate_network_id(cidr)
                    network_ids.add(network_id)

                    # Upsert network
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

        # Update node's network associations
        network_id_list = list(network_ids)
        if network_id_list:
            await self.db.nodes.update_one(
                {"nodeId": node_id},
                {"$set": {"networkIds": network_id_list}},
            )

            # Update node counts on networks
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
        # Convert 192.168.1.0/24 to 192-168-1-0-24
        return cidr.replace(".", "-").replace("/", "-")

    def _format_network(self, doc: dict) -> dict:
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
            "nodeCount": doc.get("nodeCount", 0),
            "origin": doc.get("origin", {}),
            "tags": doc.get("tags", []),
            "createdAt": doc.get("createdAt"),
            "updatedAt": doc.get("updatedAt"),
        }

    def _format_network_summary(self, doc: dict) -> dict:
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
