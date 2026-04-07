"""Tests for the service dependency analyzer."""

from typing import Any

from hydra_mcp.dependency_analyzer import (
    analyze_network_patterns,
    analyze_services,
    build_dependency_graph,
    build_service_entries,
    parse_docker_dependencies,
    parse_kubernetes_dependencies,
    parse_systemd_dependencies,
)


def _make_service(
    service_id: str = "svc-test-a1b2",
    name: str = "test-service",
    node_id: str = "node-01",
    runtime: str = "docker",
    status: str = "running",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "serviceId": service_id,
        "name": name,
        "nodeId": node_id,
        "runtime": runtime,
        "status": status,
        "metadata": metadata or {},
    }


# =============================================================================
# Runtime Dependency Parsers
# =============================================================================


class TestParseDockerDependencies:
    def test_extracts_host_env_vars(self) -> None:
        info: dict[str, Any] = {"dependencies": []}
        metadata = {"environment": {"DB_HOST": "mongo.local", "LOG_LEVEL": "info"}}
        parse_docker_dependencies(metadata, info)
        assert len(info["dependencies"]) == 1
        assert info["dependencies"][0]["target"] == "mongo.local"
        assert info["dependencies"][0]["reference"] == "DB_HOST"

    def test_extracts_url_env_vars(self) -> None:
        info: dict[str, Any] = {"dependencies": []}
        metadata = {"environment": {"API_URL": "http://api:8080"}}
        parse_docker_dependencies(metadata, info)
        assert len(info["dependencies"]) == 1
        assert info["dependencies"][0]["type"] == "environment"

    def test_extracts_endpoint_env_vars(self) -> None:
        info: dict[str, Any] = {"dependencies": []}
        metadata = {"environment": {"REDIS_ENDPOINT": "redis:6379"}}
        parse_docker_dependencies(metadata, info)
        assert len(info["dependencies"]) == 1

    def test_extracts_networks(self) -> None:
        info: dict[str, Any] = {"dependencies": []}
        metadata = {"networks": ["frontend", "backend"]}
        parse_docker_dependencies(metadata, info)
        assert info["networks"] == ["frontend", "backend"]

    def test_extracts_links(self) -> None:
        info: dict[str, Any] = {"dependencies": []}
        metadata = {"links": ["redis", "mongo"]}
        parse_docker_dependencies(metadata, info)
        assert len(info["dependencies"]) == 2
        assert info["dependencies"][0]["type"] == "link"

    def test_empty_metadata(self) -> None:
        info: dict[str, Any] = {"dependencies": []}
        parse_docker_dependencies({}, info)
        assert info["dependencies"] == []

    def test_non_dict_environment_ignored(self) -> None:
        info: dict[str, Any] = {"dependencies": []}
        metadata = {"environment": "not-a-dict"}
        parse_docker_dependencies(metadata, info)
        assert info["dependencies"] == []


class TestParseKubernetesDependencies:
    def test_extracts_service_env_vars(self) -> None:
        info: dict[str, Any] = {"dependencies": []}
        metadata = {
            "containers": [
                {
                    "env": [
                        {"name": "REDIS_SERVICE", "value": "redis-master"},
                        {"name": "LOG_LEVEL", "value": "debug"},
                    ]
                }
            ]
        }
        parse_kubernetes_dependencies(metadata, info)
        assert len(info["dependencies"]) == 1
        assert info["dependencies"][0]["type"] == "kubernetes_env"
        assert info["dependencies"][0]["target"] == "redis-master"

    def test_extracts_host_env_vars(self) -> None:
        info: dict[str, Any] = {"dependencies": []}
        metadata = {"containers": [{"env": [{"name": "DB_HOST", "value": "pg.svc"}]}]}
        parse_kubernetes_dependencies(metadata, info)
        assert len(info["dependencies"]) == 1

    def test_empty_containers(self) -> None:
        info: dict[str, Any] = {"dependencies": []}
        parse_kubernetes_dependencies({"containers": []}, info)
        assert info["dependencies"] == []

    def test_non_list_containers(self) -> None:
        info: dict[str, Any] = {"dependencies": []}
        parse_kubernetes_dependencies({"containers": "invalid"}, info)
        assert info["dependencies"] == []


class TestParseSystemdDependencies:
    def test_extracts_requires(self) -> None:
        info: dict[str, Any] = {"dependencies": []}
        metadata = {"config": {"Requires": ["network.target"]}}
        parse_systemd_dependencies(metadata, info)
        assert len(info["dependencies"]) == 1
        assert info["dependencies"][0]["type"] == "systemd_requires"

    def test_extracts_wants(self) -> None:
        info: dict[str, Any] = {"dependencies": []}
        metadata = {"config": {"Wants": ["syslog.target"]}}
        parse_systemd_dependencies(metadata, info)
        assert len(info["dependencies"]) == 1
        assert info["dependencies"][0]["type"] == "systemd_wants"

    def test_extracts_after(self) -> None:
        info: dict[str, Any] = {"dependencies": []}
        metadata = {"config": {"After": ["network-online.target", "mongodb.service"]}}
        parse_systemd_dependencies(metadata, info)
        assert len(info["dependencies"]) == 2
        assert info["dependencies"][0]["type"] == "systemd_after"

    def test_empty_config(self) -> None:
        info: dict[str, Any] = {"dependencies": []}
        parse_systemd_dependencies({"config": {}}, info)
        assert info["dependencies"] == []


# =============================================================================
# build_service_entries
# =============================================================================


class TestBuildServiceEntries:
    def test_empty_services(self) -> None:
        dep_map, deps, dependents = build_service_entries([])
        assert dep_map["analysis"]["totalServices"] == 0
        assert dep_map["services"] == []
        assert deps == {}
        assert dependents == {}

    def test_single_service(self) -> None:
        services = [_make_service()]
        dep_map, deps, dependents = build_service_entries(services)
        assert dep_map["analysis"]["totalServices"] == 1
        assert len(dep_map["services"]) == 1
        assert dep_map["services"][0]["serviceId"] == "svc-test-a1b2"

    def test_docker_metadata_parsed(self) -> None:
        services = [
            _make_service(
                runtime="docker",
                metadata={"environment": {"DB_HOST": "mongo"}, "links": ["redis"]},
            )
        ]
        dep_map, deps, _ = build_service_entries(services)
        svc_deps = deps["svc-test-a1b2"]
        assert len(svc_deps) == 2  # DB_HOST env + redis link

    def test_unknown_runtime_no_parsing(self) -> None:
        services = [_make_service(runtime="custom")]
        dep_map, deps, _ = build_service_entries(services)
        assert deps["svc-test-a1b2"] == []


# =============================================================================
# build_dependency_graph
# =============================================================================


class TestBuildDependencyGraph:
    def test_builds_edges_from_matching_targets(self) -> None:
        services = [
            _make_service(
                service_id="svc-api-a1b2",
                name="api",
                runtime="docker",
                metadata={"environment": {"DB_HOST": "mongo"}},
            ),
            _make_service(
                service_id="svc-mongo-c3d4",
                name="mongo",
            ),
        ]
        dep_map, _, dependents = build_service_entries(services)
        build_dependency_graph(dep_map, dependents)
        assert len(dep_map["dependencies"]) == 1
        assert dep_map["dependencies"][0]["from"] == "svc-api-a1b2"
        assert dep_map["dependencies"][0]["to"] == "svc-mongo-c3d4"

    def test_no_self_dependencies(self) -> None:
        services = [
            _make_service(
                service_id="svc-mongo-a1b2",
                name="mongo",
                runtime="docker",
                metadata={"environment": {"DB_HOST": "mongo"}},
            ),
        ]
        dep_map, _, dependents = build_service_entries(services)
        build_dependency_graph(dep_map, dependents)
        assert len(dep_map["dependencies"]) == 0

    def test_empty_services_no_crash(self) -> None:
        dep_map, _, dependents = build_service_entries([])
        build_dependency_graph(dep_map, dependents)
        assert dep_map["dependencies"] == []


# =============================================================================
# analyze_services
# =============================================================================


class TestAnalyzeServices:
    def test_identifies_critical_services(self) -> None:
        """Services with >= 3 dependents are critical."""
        services = [
            _make_service(service_id="svc-db-a1b2", name="database"),
            _make_service(service_id="svc-a-0001", name="svc-a"),
            _make_service(service_id="svc-b-0002", name="svc-b"),
            _make_service(service_id="svc-c-0003", name="svc-c"),
        ]
        dep_map, deps, dependents = build_service_entries(services)
        dependents["svc-db-a1b2"] = ["svc-a-0001", "svc-b-0002", "svc-c-0003"]
        analyze_services(dep_map, deps, dependents)
        critical = dep_map["analysis"]["criticalServices"]
        assert len(critical) == 1
        assert critical[0]["serviceId"] == "svc-db-a1b2"

    def test_identifies_isolated_services(self) -> None:
        """Services with no deps and no dependents are isolated."""
        services = [_make_service(service_id="svc-lonely-a1b2", name="lonely")]
        dep_map, deps, dependents = build_service_entries(services)
        analyze_services(dep_map, deps, dependents)
        isolated = dep_map["analysis"]["isolatedServices"]
        assert len(isolated) == 1
        assert isolated[0]["serviceId"] == "svc-lonely-a1b2"

    def test_identifies_single_points_of_failure(self) -> None:
        """Running services with >= 2 dependents are SPOFs."""
        services = [
            _make_service(service_id="svc-db-a1b2", name="database", status="running"),
        ]
        dep_map, deps, dependents = build_service_entries(services)
        dependents["svc-db-a1b2"] = ["svc-a", "svc-b"]
        analyze_services(dep_map, deps, dependents)
        spofs = dep_map["analysis"]["singlePointsOfFailure"]
        assert len(spofs) == 1
        assert spofs[0]["serviceId"] == "svc-db-a1b2"

    def test_stopped_service_not_spof(self) -> None:
        """Stopped services are not flagged as SPOFs."""
        services = [
            _make_service(service_id="svc-db-a1b2", name="database", status="stopped"),
        ]
        dep_map, deps, dependents = build_service_entries(services)
        dependents["svc-db-a1b2"] = ["svc-a", "svc-b"]
        analyze_services(dep_map, deps, dependents)
        spofs = dep_map["analysis"]["singlePointsOfFailure"]
        assert len(spofs) == 0


# =============================================================================
# analyze_network_patterns
# =============================================================================


class TestAnalyzeNetworkPatterns:
    def test_identifies_shared_networks(self) -> None:
        dep_map: dict[str, Any] = {
            "services": [
                {"serviceId": "svc-a", "networks": ["frontend"]},
                {"serviceId": "svc-b", "networks": ["frontend"]},
                {"serviceId": "svc-c", "networks": ["backend"]},
            ],
            "analysis": {"communicationPatterns": []},
        }
        analyze_network_patterns(dep_map)
        patterns = dep_map["analysis"]["communicationPatterns"]
        assert len(patterns) == 1
        assert patterns[0]["network"] == "frontend"
        assert set(patterns[0]["services"]) == {"svc-a", "svc-b"}

    def test_no_patterns_for_single_service_networks(self) -> None:
        dep_map: dict[str, Any] = {
            "services": [
                {"serviceId": "svc-a", "networks": ["isolated"]},
            ],
            "analysis": {"communicationPatterns": []},
        }
        analyze_network_patterns(dep_map)
        assert dep_map["analysis"]["communicationPatterns"] == []

    def test_services_without_networks(self) -> None:
        dep_map: dict[str, Any] = {
            "services": [
                {"serviceId": "svc-a"},
                {"serviceId": "svc-b"},
            ],
            "analysis": {"communicationPatterns": []},
        }
        analyze_network_patterns(dep_map)
        assert dep_map["analysis"]["communicationPatterns"] == []
