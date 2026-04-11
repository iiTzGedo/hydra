"""Shared icon resolution helpers."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Literal

import httpx

from hydra.api.v1.models.icons import IconDescriptor
from hydra.db.redis import RedisClient

SELFHST_CDN_BASE = "https://cdn.jsdelivr.net/gh/selfhst/icons/svg"
SIMPLE_ICONS_CDN_BASE = "https://cdn.simpleicons.org"
ICON_PROXY_ROUTE_PREFIX = "/api/v1/icons"
ICON_CACHE_TTL_SECONDS = 60 * 60 * 24
MAX_ICON_SVG_BYTES = 256 * 1024

RemoteIconSource = Literal["selfh-st", "simple-icons"]

HYDRA_CUSTOM_ICONS: dict[str, dict[str, str]] = {
    "bare-metal": {"slug": "server", "color": "#0f766e"},
    "vm": {"slug": "monitor", "color": "#2563eb"},
    "lxc": {"slug": "container", "color": "#1d4ed8"},
    "network": {"slug": "network", "color": "#0891b2"},
    "router": {"slug": "router", "color": "#0f766e"},
    "switch": {"slug": "switch", "color": "#0f766e"},
    "firewall": {"slug": "shield", "color": "#dc2626"},
    "group": {"slug": "folder-tree", "color": "#a16207"},
    "documentation": {"slug": "book-open", "color": "#7c3aed"},
    "rss": {"slug": "rss", "color": "#f97316"},
    "clock": {"slug": "clock-3", "color": "#0f766e"},
    "weather": {"slug": "cloud-sun", "color": "#f59e0b"},
    "markdown": {"slug": "square-pen", "color": "#374151"},
    "iframe": {"slug": "app-window", "color": "#0f172a"},
}

# selfh-st icons registry. `dark`/`light` are optional variant slugs for
# theme-aware rendering; when present the frontend will swap to the matching
# variant based on the active theme.
SELFHST_ICONS: dict[str, dict[str, str]] = {
    "proxmox": {"slug": "proxmox", "color": "#E57000", "dark": "proxmox-dark", "light": "proxmox-light"},
    "pfsense": {"slug": "pfsense", "color": "#3E6BA4", "dark": "pfsense-dark", "light": "pfsense-light"},
    "opnsense": {"slug": "opnsense", "color": "#D94F00", "dark": "opnsense-dark", "light": "opnsense-light"},
    "truenas": {"slug": "truenas", "color": "#0095D5"},
    "portainer": {"slug": "portainer", "color": "#13BEF9", "dark": "portainer-dark", "light": "portainer-light"},
    "homeassistant": {"slug": "home-assistant", "color": "#41BDF5", "dark": "home-assistant-dark", "light": "home-assistant-light"},
    "docker": {"slug": "docker", "color": "#2496ED", "dark": "docker-dark", "light": "docker-light"},
    "kubernetes": {"slug": "kubernetes", "color": "#326CE5", "dark": "kubernetes-dark", "light": "kubernetes-light"},
    "terraform": {"slug": "terraform", "color": "#7B42BC"},
    "ansible": {"slug": "ansible", "color": "#EE0000", "dark": "ansible-dark", "light": "ansible-light"},
    "prometheus": {"slug": "prometheus", "color": "#E6522C", "dark": "prometheus-dark", "light": "prometheus-light"},
    "grafana": {"slug": "grafana", "color": "#F46800", "dark": "grafana-dark", "light": "grafana-light"},
    "mongodb": {"slug": "mongodb", "color": "#47A248", "dark": "mongodb-dark", "light": "mongodb-light"},
    "redis": {"slug": "redis", "color": "#DC382D", "dark": "redis-dark", "light": "redis-light"},
    "postgresql": {"slug": "postgresql", "color": "#4169E1", "dark": "postgresql-dark", "light": "postgresql-light"},
    "mysql": {"slug": "mysql", "color": "#4479A1", "dark": "mysql-dark", "light": "mysql-light"},
    "nginx": {"slug": "nginx", "color": "#009639", "dark": "nginx-dark", "light": "nginx-light"},
    "traefik": {"slug": "traefik-proxy", "color": "#24A1C1"},
    "nextcloud": {"slug": "nextcloud", "color": "#0082C9", "dark": "nextcloud-dark", "light": "nextcloud-light"},
    "unifi": {"slug": "unifi", "color": "#0559C9"},
    "mikrotik": {"slug": "mikrotik", "color": "#293239", "dark": "mikrotik-dark", "light": "mikrotik-light"},
    "openwrt": {"slug": "openwrt", "color": "#00B5E2", "dark": "openwrt-dark", "light": "openwrt-light"},
    "synology": {"slug": "synology", "color": "#11465B"},
    "qnap": {"slug": "qnap", "color": "#C41E25"},
}

SIMPLE_ICONS: dict[str, dict[str, str]] = {
    "ansible": {"slug": "ansible", "color": "#EE0000"},
    "docker": {"slug": "docker", "color": "#2496ED"},
    "git": {"slug": "git", "color": "#F05032"},
    "github": {"slug": "github", "color": "#181717"},
    "gitlab": {"slug": "gitlab", "color": "#FC6D26"},
    "kubernetes": {"slug": "kubernetes", "color": "#326CE5"},
    "mongodb": {"slug": "mongodb", "color": "#47A248"},
    "mysql": {"slug": "mysql", "color": "#4479A1"},
    "postgresql": {"slug": "postgresql", "color": "#4169E1"},
    "prometheus": {"slug": "prometheus", "color": "#E6522C"},
    "proxmox": {"slug": "proxmox", "color": "#E57000"},
    "redis": {"slug": "redis", "color": "#DC382D"},
    "ubuntu": {"slug": "ubuntu", "color": "#E95420"},
    "debian": {"slug": "debian", "color": "#A81D33"},
    "fedora": {"slug": "fedora", "color": "#51A2DA"},
    "windows": {"slug": "windows11", "color": "#0078D4"},
    "linux": {"slug": "linux", "color": "#FCC624"},
    "terraform": {"slug": "terraform", "color": "#7B42BC"},
    "nginx": {"slug": "nginx", "color": "#009639"},
    "grafana": {"slug": "grafana", "color": "#F46800"},
    "alpinelinux": {"slug": "alpinelinux", "color": "#0D597F"},
    "archlinux": {"slug": "archlinux", "color": "#1793D1"},
}

ALIASES: dict[str, str] = {
    "command-center": "terminal",
    "debian-gnu-linux": "debian",
    "docs": "documentation",
    "home-assistant": "homeassistant",
    "homeassistantcore": "homeassistant",
    "hass": "homeassistant",
    "linux-kernel": "linux",
    "open-sense": "opnsense",
    "opn-sense": "opnsense",
    "pbs": "proxmox",
    "pf-sense": "pfsense",
    "proxmox-backup-server": "proxmox",
    "proxmox-ve": "proxmox",
    "pve": "proxmox",
    "time-machine": "clock",
    "windows-server": "windows",
    "windowsserver": "windows",
    "alpine": "alpinelinux",
    "arch": "archlinux",
    "k8s": "kubernetes",
    "k3s": "kubernetes",
    "tf": "terraform",
    "traefik-proxy": "traefik",
    "postgres": "postgresql",
    "pg": "postgresql",
    "mariadb": "mysql",
}


class IconAssetError(Exception):
    """Base error raised when Hydra cannot serve a proxied icon asset."""


class IconAssetNotFoundError(IconAssetError):
    """Raised when an external icon cannot be resolved."""


class IconAssetInvalidError(IconAssetError):
    """Raised when a fetched asset is not a safe SVG icon."""


def _normalize_icon_key(value: str | None) -> str:
    if not value:
        return ""

    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not normalized:
        return ""

    compact = normalized.replace("-", "")
    return ALIASES.get(normalized) or ALIASES.get(compact) or normalized


@lru_cache(maxsize=1)
def _known_registry_keys() -> tuple[str, ...]:
    keys = [
        *HYDRA_CUSTOM_ICONS.keys(),
        *SELFHST_ICONS.keys(),
        *SIMPLE_ICONS.keys(),
        *ALIASES.keys(),
    ]
    return tuple(dict.fromkeys(keys))


def _build_candidate_keys(*values: str | None) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def add_candidate(value: str) -> None:
        normalized = _normalize_icon_key(value)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        candidates.append(normalized)

    for value in values:
        normalized = _normalize_icon_key(value)
        if not normalized:
            continue

        add_candidate(normalized)

        parts = [part for part in normalized.split("-") if part]
        for part in parts:
            add_candidate(part)

        compact = normalized.replace("-", "")
        add_candidate(compact)

        for known in _known_registry_keys():
            known_compact = known.replace("-", "")
            if (
                normalized == known
                or normalized.startswith(f"{known}-")
                or normalized.endswith(f"-{known}")
                or f"-{known}-" in normalized
                or compact == known_compact
                or compact.startswith(known_compact)
            ):
                add_candidate(known)

    return candidates


def build_proxied_icon_url(source: RemoteIconSource, slug: str) -> str:
    """Return the stable internal asset URL for a proxied icon."""
    return f"{ICON_PROXY_ROUTE_PREFIX}/{source}/{slug}.svg"


def _build_remote_icon_url(source: RemoteIconSource, slug: str) -> str:
    if source == "selfh-st":
        return f"{SELFHST_CDN_BASE}/{slug}.svg"
    return f"{SIMPLE_ICONS_CDN_BASE}/{slug}"


async def _download_remote_icon_svg(source: RemoteIconSource, slug: str) -> str:
    url = _build_remote_icon_url(source, slug)
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        response = await client.get(
            url,
            headers={"Accept": "image/svg+xml,image/*;q=0.8,*/*;q=0.5"},
        )

    if response.status_code == 404:
        raise IconAssetNotFoundError(f"Icon {source}/{slug} was not found")
    if response.is_error:
        raise IconAssetError(f"Failed to fetch icon {source}/{slug}: HTTP {response.status_code}")

    return response.text


def _validate_svg_payload(payload: str) -> str:
    svg_text = payload.strip()
    svg_lower = svg_text.lower()

    if not svg_text:
        raise IconAssetInvalidError("Icon payload was empty")
    if len(svg_text.encode("utf-8")) > MAX_ICON_SVG_BYTES:
        raise IconAssetInvalidError("Icon payload exceeded size limit")
    if "<svg" not in svg_lower:
        raise IconAssetInvalidError("Icon payload was not SVG")
    if "<script" in svg_lower:
        raise IconAssetInvalidError("Icon payload included disallowed script content")

    return svg_text


async def get_icon_asset_svg(source: RemoteIconSource, slug: str, redis: RedisClient) -> str:
    """Fetch a proxied icon asset, serving Redis-cached SVGs when available."""
    cache_key = f"icons:{source}:{slug}"
    cached = await redis.cache_get(cache_key)
    if cached:
        return cached

    svg_text = _validate_svg_payload(await _download_remote_icon_svg(source, slug))
    await redis.cache_set(cache_key, svg_text, ttl_seconds=ICON_CACHE_TTL_SECONDS)
    return svg_text


def _variant_urls(source: RemoteIconSource, icon: dict[str, str]) -> dict[str, str | None]:
    dark_slug = icon.get("dark")
    light_slug = icon.get("light")
    return {
        "url_dark": build_proxied_icon_url(source, dark_slug) if dark_slug else None,
        "url_light": build_proxied_icon_url(source, light_slug) if light_slug else None,
    }


@lru_cache(maxsize=512)
def resolve_icon_descriptor(*, name: str | None = None, provider: str | None = None, fallback: str = "square") -> dict[str, Any]:
    """Resolve a shared icon descriptor with stable priority ordering."""

    keys = _build_candidate_keys(name, provider)

    for key in keys:
        if key in HYDRA_CUSTOM_ICONS:
            icon = HYDRA_CUSTOM_ICONS[key]
            return IconDescriptor(
                source="hydra",
                slug=icon["slug"],
                label=name or provider or key,
                color=icon.get("color"),
                fallback=fallback,
            ).model_dump(by_alias=True)

    for key in keys:
        if key in SELFHST_ICONS:
            icon = SELFHST_ICONS[key]
            variants = _variant_urls("selfh-st", icon)
            return IconDescriptor(
                source="selfh-st",
                slug=icon["slug"],
                label=name or provider or key,
                url=build_proxied_icon_url("selfh-st", icon["slug"]),
                url_dark=variants["url_dark"],
                url_light=variants["url_light"],
                color=icon.get("color"),
                fallback=fallback,
            ).model_dump(by_alias=True)

    for key in keys:
        if key in SIMPLE_ICONS:
            icon = SIMPLE_ICONS[key]
            return IconDescriptor(
                source="simple-icons",
                slug=icon["slug"],
                label=name or provider or key,
                url=build_proxied_icon_url("simple-icons", icon["slug"]),
                color=icon.get("color"),
                fallback=fallback,
            ).model_dump(by_alias=True)

    return IconDescriptor(
        source="fallback",
        slug=fallback,
        label=name or provider or fallback,
        fallback=fallback,
    ).model_dump(by_alias=True)
