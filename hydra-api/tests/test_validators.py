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
    assert not validators.validate_tag("prod-web")
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
