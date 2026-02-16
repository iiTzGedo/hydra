import pytest

from hydra.api.v1.core import validators


def test_validate_node_id_strict():
    assert validators.validate_node_id_strict("node")
    assert validators.validate_node_id_strict("node-1")
    assert not validators.validate_node_id_strict("Node-1")
    assert not validators.validate_node_id_strict("1node")
    assert not validators.validate_node_id_strict("node1")


def test_validate_tag():
    assert validators.validate_tag("prod")
    assert validators.validate_tag("prod_web")
    assert validators.validate_tag("prod:web")
    assert validators.validate_tag("prod-web")
    assert not validators.validate_tag("prod--web")
    assert not validators.validate_tag("Prod")


def test_validate_network_id():
    assert validators.validate_network_id("corpnet")
    assert validators.validate_network_id("corp-net")
    assert validators.validate_network_id("a1net")
    assert not validators.validate_network_id("net-1")
    assert not validators.validate_network_id("corp_net")


def test_validate_ipv4():
    assert validators.validate_ipv4("192.168.0.1")
    assert validators.validate_ipv4("0.0.0.0")
    assert not validators.validate_ipv4("999.0.0.1")


def test_validate_cidr():
    assert validators.validate_cidr("192.168.0.0/24")
    assert validators.validate_cidr("10.0.0.1/32")
    assert not validators.validate_cidr("10.0.0.1/33")


def test_validate_profile_version():
    assert validators.validate_profile_version("E0-0.0.0.1")
    assert validators.validate_profile_version("E12-0.A.1.F")
    assert not validators.validate_profile_version("E1-0.0.0.10")
    assert not validators.validate_profile_version("e1-0.0.0.1")


def test_validate_service_id():
    # Format: svc-<name>-<4 char hash>
    assert validators.validate_service_id("svc-nginx-1a2b")
    assert validators.validate_service_id("svc-my-service-9Z9z")
    assert validators.validate_service_id("svc-my_service-abcd")
    # Invalid formats
    assert not validators.validate_service_id("svc::nginx::1a2b")  # Wrong delimiter
    assert not validators.validate_service_id("svc-nginx-abc")  # Hash too short
    assert not validators.validate_service_id("svc-NGINX-abcd")  # Uppercase name


def test_validate_agent_username():
    assert validators.validate_agent_username("agent-ABCDEFG1")
    assert not validators.validate_agent_username("agent-abc12345")


def test_validate_node_id_with_warning_lenient_legacy():
    is_valid, warning = validators.validate_node_id("1node", strict=False)
    assert is_valid is True
    assert warning is not None
    assert "deprecated format" in warning


def test_node_id_validator_factory_strict_and_lenient():
    strict_validator = validators.node_id_validator(strict=True)
    lenient_validator = validators.node_id_validator(strict=False)

    assert strict_validator("server-01") == "server-01"
    with pytest.raises(ValueError):
        strict_validator("1server")

    assert lenient_validator("proxmox-01") == "proxmox-01"


def test_tags_validator_factory():
    tags_validator = validators.tags_validator()
    assert tags_validator(None) is None
    assert tags_validator(["prod", "prod:web"]) == ["prod", "prod:web"]
    with pytest.raises(ValueError):
        tags_validator(["invalid tag"])


def test_network_and_profile_validator_factories():
    network_validator = validators.network_id_validator()
    profile_validator = validators.profile_version_validator()

    assert network_validator("corp-net") == "corp-net"
    with pytest.raises(ValueError):
        network_validator("corp_net")

    assert profile_validator("E0-0.0.0.1") == "E0-0.0.0.1"
    with pytest.raises(ValueError):
        profile_validator("E0-0.0.0.10")


def test_validation_patterns_registry_contains_expected_keys():
    assert "tag" in validators.VALIDATION_PATTERNS
    assert validators.VALIDATION_PATTERNS["tag"] == validators.TAG_PATTERN
    assert "profile_version" in validators.VALIDATION_PATTERNS
