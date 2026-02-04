"""
Service Dependency Analyzer.

Extracted from tool_handlers.py to reduce file complexity.
Analyzes service dependencies, identifies critical services, single points of failure,
and communication patterns across the infrastructure.
"""

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def _safe_list(val: Any) -> list:
    """Ensure val is iterable as a list."""
    return val if isinstance(val, list) else []


def parse_docker_dependencies(metadata: dict, service_info: dict[str, Any]) -> None:
    """Extract dependencies from Docker/Podman service metadata."""
    env_vars = metadata.get("environment", {})
    networks = metadata.get("networks", [])
    links = metadata.get("links", [])

    for key, value in env_vars.items() if isinstance(env_vars, dict) else []:
        if isinstance(value, str):
            if "_HOST" in key or "_URL" in key or "_ENDPOINT" in key:
                service_info["dependencies"].append({
                    "type": "environment",
                    "target": value,
                    "reference": key,
                })

    if networks:
        service_info["networks"] = networks

    if links:
        service_info["dependencies"].extend([
            {"type": "link", "target": link} for link in links
        ])


def parse_kubernetes_dependencies(metadata: dict, service_info: dict[str, Any]) -> None:
    """Extract dependencies from Kubernetes service metadata."""
    containers = metadata.get("containers", [])
    for container in _safe_list(containers):
        env = container.get("env", [])
        for env_var in _safe_list(env):
            name = env_var.get("name", "")
            value = env_var.get("value", "")
            if "_SERVICE" in name or "_HOST" in name:
                service_info["dependencies"].append({
                    "type": "kubernetes_env",
                    "target": value,
                    "reference": name,
                })


def parse_systemd_dependencies(metadata: dict, service_info: dict[str, Any]) -> None:
    """Extract dependencies from systemd service metadata."""
    config = metadata.get("config", {})
    requires = config.get("Requires", [])
    wants = config.get("Wants", [])
    after = config.get("After", [])

    if requires:
        service_info["dependencies"].extend([
            {"type": "systemd_requires", "target": req} for req in requires
        ])
    if wants:
        service_info["dependencies"].extend([
            {"type": "systemd_wants", "target": want} for want in wants
        ])
    if after:
        service_info["dependencies"].extend([
            {"type": "systemd_after", "target": dep} for dep in after
        ])


_RUNTIME_PARSERS = {
    "docker": parse_docker_dependencies,
    "podman": parse_docker_dependencies,
    "kubernetes": parse_kubernetes_dependencies,
    "systemd": parse_systemd_dependencies,
}


def build_service_entries(services: list[dict]) -> tuple[dict, dict[str, list], dict[str, list]]:
    """Build service info entries and initialize dependency tracking.

    Returns:
        Tuple of (dependency_map, service_deps, service_dependents).
    """
    dependency_map: dict[str, Any] = {
        "services": [],
        "dependencies": [],
        "analysis": {
            "totalServices": len(services),
            "criticalServices": [],
            "isolatedServices": [],
            "singlePointsOfFailure": [],
            "communicationPatterns": [],
        },
    }

    service_deps: dict[str, list] = {}
    service_dependents: dict[str, list] = {}

    for svc in services:
        svc_id = svc.get("serviceId", "")
        runtime = svc.get("runtime", "")

        service_info: dict[str, Any] = {
            "serviceId": svc_id,
            "name": svc.get("name", ""),
            "nodeId": svc.get("nodeId", ""),
            "runtime": runtime,
            "status": svc.get("status", ""),
            "dependencies": [],
            "dependents": [],
        }

        metadata = svc.get("metadata", {})
        parser = _RUNTIME_PARSERS.get(runtime)
        if parser:
            parser(metadata, service_info)

        dependency_map["services"].append(service_info)
        service_deps[svc_id] = service_info["dependencies"]
        service_dependents[svc_id] = []

    return dependency_map, service_deps, service_dependents


def build_dependency_graph(dependency_map: dict, service_dependents: dict[str, list]) -> None:
    """Build dependency edges by matching targets to service names/IDs."""
    for svc_info in dependency_map["services"]:
        svc_id = svc_info["serviceId"]
        for dep in svc_info["dependencies"]:
            target = dep.get("target", "")
            for other_svc in dependency_map["services"]:
                other_id = other_svc["serviceId"]
                other_name = other_svc["name"]
                if other_id != svc_id and (target in other_id or target in other_name):
                    dependency_map["dependencies"].append({
                        "from": svc_id,
                        "to": other_id,
                        "type": dep.get("type", "unknown"),
                    })
                    if other_id not in service_dependents:
                        service_dependents[other_id] = []
                    service_dependents[other_id].append(svc_id)


def analyze_services(
    dependency_map: dict,
    service_deps: dict[str, list],
    service_dependents: dict[str, list],
) -> None:
    """Identify critical services, isolated services, and single points of failure."""
    for svc_info in dependency_map["services"]:
        svc_id = svc_info["serviceId"]
        num_deps = len(service_deps.get(svc_id, []))
        num_dependents = len(service_dependents.get(svc_id, []))

        if num_dependents >= 3:
            dependency_map["analysis"]["criticalServices"].append({
                "serviceId": svc_id,
                "name": svc_info["name"],
                "dependents": num_dependents,
                "reason": "High number of dependent services",
            })

        if num_deps == 0 and num_dependents == 0:
            dependency_map["analysis"]["isolatedServices"].append({
                "serviceId": svc_id,
                "name": svc_info["name"],
            })

        if num_dependents >= 2 and svc_info["status"] == "running":
            dependency_map["analysis"]["singlePointsOfFailure"].append({
                "serviceId": svc_id,
                "name": svc_info["name"],
                "dependents": num_dependents,
                "impact": "High - failure would affect multiple services",
            })


def analyze_network_patterns(dependency_map: dict) -> None:
    """Identify communication patterns from shared networks."""
    network_services: dict[str, list] = {}
    for svc_info in dependency_map["services"]:
        svc_networks = svc_info.get("networks", [])
        for net in svc_networks:
            if net not in network_services:
                network_services[net] = []
            network_services[net].append(svc_info["serviceId"])

    for net, svc_list in network_services.items():
        if len(svc_list) > 1:
            dependency_map["analysis"]["communicationPatterns"].append({
                "network": net,
                "services": svc_list,
                "pattern": "Shared network communication",
            })
