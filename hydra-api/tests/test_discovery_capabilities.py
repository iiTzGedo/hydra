"""Tests for Linux capability detection."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from hydra.api.v1.services.discovery.capabilities import (
    capability_status,
    has_cap_net_admin,
    has_cap_net_raw,
    reset_capability_cache,
)


@pytest.fixture(autouse=True)
def clear_cache():
    reset_capability_cache()
    yield
    reset_capability_cache()


class TestHasCapNetRaw:
    def test_present(self):
        # CAP_NET_RAW = bit 13 → 0x2000
        status = "Name:\tpython\nCapEff:\t0000000000002000\n"
        with patch(
            "hydra.api.v1.services.discovery.capabilities._PROC_STATUS"
        ) as mock_path, patch(
            "hydra.api.v1.services.discovery.capabilities.sys.platform", "linux"
        ):
            mock_path.read_text.return_value = status
            assert has_cap_net_raw() is True

    def test_absent(self):
        status = "Name:\tpython\nCapEff:\t0000000000000000\n"
        with patch(
            "hydra.api.v1.services.discovery.capabilities._PROC_STATUS"
        ) as mock_path, patch(
            "hydra.api.v1.services.discovery.capabilities.sys.platform", "linux"
        ):
            mock_path.read_text.return_value = status
            assert has_cap_net_raw() is False

    def test_non_linux(self):
        with patch(
            "hydra.api.v1.services.discovery.capabilities.sys.platform", "darwin"
        ):
            assert has_cap_net_raw() is False

    def test_proc_status_unreadable(self):
        with patch(
            "hydra.api.v1.services.discovery.capabilities._PROC_STATUS"
        ) as mock_path, patch(
            "hydra.api.v1.services.discovery.capabilities.sys.platform", "linux"
        ):
            mock_path.read_text.side_effect = OSError("permission denied")
            assert has_cap_net_raw() is False

    def test_proc_status_malformed(self):
        with patch(
            "hydra.api.v1.services.discovery.capabilities._PROC_STATUS"
        ) as mock_path, patch(
            "hydra.api.v1.services.discovery.capabilities.sys.platform", "linux"
        ):
            mock_path.read_text.return_value = "garbage\nno cap line\n"
            assert has_cap_net_raw() is False

    def test_cached(self):
        status = "CapEff:\t0000000000002000\n"
        with patch(
            "hydra.api.v1.services.discovery.capabilities._PROC_STATUS"
        ) as mock_path, patch(
            "hydra.api.v1.services.discovery.capabilities.sys.platform", "linux"
        ):
            mock_path.read_text.return_value = status
            has_cap_net_raw()
            has_cap_net_raw()
            has_cap_net_raw()
            # Cached after first call
            assert mock_path.read_text.call_count == 1


class TestHasCapNetAdmin:
    def test_present(self):
        # CAP_NET_ADMIN = bit 12 → 0x1000
        status = "CapEff:\t0000000000001000\n"
        with patch(
            "hydra.api.v1.services.discovery.capabilities._PROC_STATUS"
        ) as mock_path, patch(
            "hydra.api.v1.services.discovery.capabilities.sys.platform", "linux"
        ):
            mock_path.read_text.return_value = status
            assert has_cap_net_admin() is True

    def test_both_present(self):
        # Both bits set
        status = "CapEff:\t0000000000003000\n"
        with patch(
            "hydra.api.v1.services.discovery.capabilities._PROC_STATUS"
        ) as mock_path, patch(
            "hydra.api.v1.services.discovery.capabilities.sys.platform", "linux"
        ):
            mock_path.read_text.return_value = status
            assert has_cap_net_raw() is True
            assert has_cap_net_admin() is True


class TestCapabilityStatus:
    def test_full_mode(self):
        with patch(
            "hydra.api.v1.services.discovery.capabilities.has_cap_net_raw",
            return_value=True,
        ), patch(
            "hydra.api.v1.services.discovery.capabilities.has_cap_net_admin",
            return_value=True,
        ):
            status = capability_status()
            assert status["capNetRaw"] is True
            assert status["capNetAdmin"] is True
            assert status["fallbackMode"] == "full"

    def test_tcp_only_mode(self):
        with patch(
            "hydra.api.v1.services.discovery.capabilities.has_cap_net_raw",
            return_value=False,
        ), patch(
            "hydra.api.v1.services.discovery.capabilities.has_cap_net_admin",
            return_value=False,
        ):
            status = capability_status()
            assert status["fallbackMode"] == "tcp-only"

    def test_includes_platform(self):
        status = capability_status()
        assert "platform" in status
        assert isinstance(status["platform"], str)
