"""Tests for shared icon resolution and proxying."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from hydra.api.v1.services.icons import (
    IconAssetInvalidError,
    IconAssetNotFoundError,
    resolve_icon_descriptor,
)


def test_resolve_icon_descriptor_uses_internal_proxy_url_for_external_icons():
    """Industry/provider icons should resolve to Hydra-served proxy URLs."""
    icon = resolve_icon_descriptor(
        name="Proxmox VE",
        provider="proxmox",
        fallback="plug",
    )

    assert icon["source"] == "selfh-st"
    assert icon["slug"] == "proxmox"
    assert icon["url"] == "/api/v1/icons/selfh-st/proxmox.svg"
    assert icon["fallback"] == "plug"


def test_resolve_icon_descriptor_extracts_known_platform_keys():
    """Versioned platform strings should still resolve to their vendor icon."""
    icon = resolve_icon_descriptor(
        provider="Ubuntu 24.04.2 LTS",
        fallback="server",
    )

    assert icon["source"] == "simple-icons"
    assert icon["slug"] == "ubuntu"
    assert icon["url"] == "/api/v1/icons/simple-icons/ubuntu.svg"


@pytest.mark.asyncio
async def test_get_icon_asset_uses_cache_when_available(
    client: AsyncClient,
    mock_redis,
):
    """The icon proxy should return a cached SVG without hitting the remote source."""
    mock_redis.cache_get = AsyncMock(return_value="<svg viewBox='0 0 24 24'></svg>")
    mock_redis.cache_set = AsyncMock()

    with patch(
        "hydra.api.v1.services.icons._download_remote_icon_svg",
        new=AsyncMock(),
    ) as download_icon:
        response = await client.get("/api/v1/icons/simple-icons/ubuntu.svg")

    assert response.status_code == 200
    assert response.text == "<svg viewBox='0 0 24 24'></svg>"
    assert response.headers["content-type"].startswith("image/svg+xml")
    download_icon.assert_not_awaited()
    mock_redis.cache_set.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_icon_asset_fetches_and_caches_remote_svg(
    client: AsyncClient,
    mock_redis,
):
    """The icon proxy should fetch, validate, and cache external SVG assets."""
    svg_text = "<svg viewBox='0 0 24 24'><path d='M0 0h24v24H0z'/></svg>"
    mock_redis.cache_get = AsyncMock(return_value=None)
    mock_redis.cache_set = AsyncMock()

    with patch(
        "hydra.api.v1.services.icons._download_remote_icon_svg",
        new=AsyncMock(return_value=svg_text),
    ) as download_icon:
        response = await client.get("/api/v1/icons/selfh-st/proxmox.svg")

    assert response.status_code == 200
    assert response.text == svg_text
    download_icon.assert_awaited_once_with("selfh-st", "proxmox")
    mock_redis.cache_set.assert_awaited_once_with(
        "icons:selfh-st:proxmox",
        svg_text,
        ttl_seconds=60 * 60 * 24,
    )


@pytest.mark.asyncio
async def test_get_icon_asset_returns_not_found_for_missing_icons(
    client: AsyncClient,
    mock_redis,
):
    """Missing external icons should return a 404 instead of a broken proxy response."""
    mock_redis.cache_get = AsyncMock(return_value=None)

    with patch(
        "hydra.api.v1.services.icons._download_remote_icon_svg",
        new=AsyncMock(side_effect=IconAssetNotFoundError("missing")),
    ):
        response = await client.get("/api/v1/icons/simple-icons/not-a-real-icon.svg")

    assert response.status_code == 404
    assert response.json()["detail"] == "missing"


@pytest.mark.asyncio
async def test_get_icon_asset_rejects_invalid_svg_payloads(
    client: AsyncClient,
    mock_redis,
):
    """Unexpected or unsafe payloads should fail closed."""
    mock_redis.cache_get = AsyncMock(return_value=None)

    with patch(
        "hydra.api.v1.services.icons._download_remote_icon_svg",
        new=AsyncMock(side_effect=IconAssetInvalidError("bad svg")),
    ):
        response = await client.get("/api/v1/icons/simple-icons/ubuntu.svg")

    assert response.status_code == 502
    assert response.json()["detail"] == "bad svg"
