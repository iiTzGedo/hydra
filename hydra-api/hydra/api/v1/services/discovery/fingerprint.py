"""Multi-signal device fingerprinting and classification engine.

Implements additive confidence scoring per the Phase 2D specification:
- Port-based signals contribute specific boosts per device class
- MAC vendor (OUI) signals boost classification
- Protocol detection (mDNS, SSDP, SNMP, LLDP) provides strong signals
- Confidence is capped at 0.95 (never 100% from network probing alone)
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import structlog

from hydra.api.v1.models.discovery.schemas import (
    Classification,
    DetailedPort,
    Fingerprint,
    LldpDetail,
    MdnsDetail,
    PortInference,
    ProtocolDetails,
    SnmpDetail,
    SsdpDetail,
)

_logger = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def _get_mac_lookup() -> Any:
    """Lazy-import ``mac-vendor-lookup`` to avoid the IEEE download at startup.

    Returns a configured ``MacLookup`` instance on success, ``None`` if the
    library is missing or its OUI database cannot be loaded.
    """
    try:
        from mac_vendor_lookup import MacLookup
    except ImportError:
        return None
    try:
        # ``MacLookup`` lazily loads its OUI cache on first ``lookup()`` call,
        # so we don't need to pre-warm it here. Pre-warming via
        # ``load_vendors()`` returns an unawaited coroutine in the async
        # variant which the caller never sees.
        return MacLookup()
    except Exception as exc:  # noqa: BLE001
        _logger.debug("fingerprint.mac_vendor_lookup_unavailable", error=str(exc))
        return None


def _lookup_vendor_lib(primary_mac: str) -> str | None:
    """Look up a MAC vendor via the offline ``mac-vendor-lookup`` IEEE DB.

    Returns ``None`` when the library is missing, the OUI is unknown, or
    the synchronous ``lookup()`` cannot run inside the current event loop
    (the library spins up its own loop, which fails when one is already
    running). Callers should never see an exception from this helper.
    """
    lookup = _get_mac_lookup()
    if lookup is None:
        return None
    try:
        result = lookup.lookup(primary_mac)
    except Exception:  # noqa: BLE001 — third-party lib; never break callers
        return None
    # Some versions of the lib return a coroutine (the AsyncMacLookup
    # variant) when called from a thread that already has an event loop.
    # We can't await here, so close the coroutine to silence the
    # "never awaited" warning and treat it as "no result".
    if not isinstance(result, str):
        if hasattr(result, "close"):
            result.close()
        return None
    return result

# ── Port Lists (aligned with scanner.py) ─────────────────────────────

# Tier 1: Always scanned (~32 ports covering core infrastructure services)
TIER1_PORTS: frozenset[int] = frozenset({
    22, 23, 25, 53, 80, 110, 143, 161, 389, 443, 445,
    554, 623, 993, 995, 1194, 1433, 1883, 1900, 2375,
    2376, 3306, 3389, 5353, 5432, 5683, 5900, 6379,
    8006, 8080, 8123, 8443,
})

# Tier 2: Extended scan (~70 additional ports for deeper fingerprinting)
TIER2_PORTS: frozenset[int] = frozenset({
    21, 69, 111, 135, 179, 427, 500, 514, 515, 548,
    587, 631, 636, 873, 902, 993, 1080, 1521, 1723,
    2049, 2222, 2379, 2380, 3000, 3128, 3260, 3478, 4243,
    4505, 4506, 5000, 5001, 5060, 5222, 5269, 5601, 5672,
    5984, 6000, 6443, 6633, 6667, 6881, 7001, 7070, 7077,
    7443, 7474, 8000, 8008, 8081, 8088, 8090, 8139, 8181,
    8291, 8333, 8444, 8500, 8834, 8883, 8888, 8983,
    9000, 9001, 9042, 9090, 9092, 9100, 9200, 9300,
    9418, 9443, 9999, 10000, 10001, 10250, 10255,
    11211, 15672, 19132, 25565, 27017, 27018, 28017,
    32400, 49152, 50000, 51820, 61616,
})


# ── OUI Vendor Map ────────────────────────────────────────────────────

OUI_VENDOR_MAP: dict[str, str] = {
    # Compute / Server
    "b8:27:eb": "Raspberry Pi Foundation",
    "dc:a6:32": "Raspberry Pi Trading",
    "e4:5f:01": "Raspberry Pi Trading",
    "d8:3a:dd": "Raspberry Pi Trading",
    "2c:cf:67": "Raspberry Pi Trading",
    "00:1b:21": "Dell",
    "f8:bc:12": "Dell",
    "00:25:90": "Super Micro",
    "ac:1f:6b": "Super Micro",
    "00:1c:42": "Parallels",
    "00:50:56": "VMware",
    "00:0c:29": "VMware",
    "f4:ce:46": "Hewlett Packard Enterprise",
    "3c:d9:2b": "HP",
    "00:1e:67": "Intel",
    "a4:bf:01": "Intel",
    "48:21:0b": "Intel",
    "00:1a:2b": "Hardkernel (ODROID)",
    # Networking
    "18:b4:30": "Ubiquiti",
    "d8:b3:70": "Ubiquiti",
    "fc:ec:da": "Ubiquiti",
    "24:5a:4c": "Ubiquiti",
    "74:ac:b9": "Ubiquiti",
    "2c:c8:1b": "MikroTik",
    "6c:3b:6b": "MikroTik",
    "48:a9:8a": "TP-Link",
    "50:c7:bf": "TP-Link",
    "b0:be:76": "TP-Link",
    "20:e5:2a": "Netgear",
    "c4:04:15": "Netgear",
    "00:1b:2f": "Netgear",
    "00:17:c5": "Cisco",
    "00:1a:a1": "Cisco",
    "f8:c2:88": "Cisco",
    "c8:b5:ad": "Cisco Meraki",
    "00:05:85": "Juniper",
    "88:e9:a4": "Juniper",
    "70:4d:7b": "Aruba",
    "00:09:0f": "Fortinet",
    "70:4c:a5": "Arista",
    # IoT / Smart Home
    "00:17:88": "Philips Hue",
    "ec:b5:fa": "Philips Hue",
    "00:1c:b3": "Apple",
    "ac:de:48": "Apple",
    "ec:fa:bc": "Espressif",
    "24:0a:c4": "Espressif",
    "a4:cf:12": "Espressif",
    "30:ae:a4": "Espressif",
    "84:cc:a8": "Espressif",
    "e8:db:84": "Espressif",
    "c4:5b:be": "Shelly (Allterco)",
    "98:cd:ac": "Shelly (Allterco)",
    "34:94:54": "Espressif (Sonoff/iTead)",
    "a0:20:a6": "Tuya",
    "d8:f1:5b": "Tuya",
    "fc:e8:06": "Amazon (Echo/Ring)",
    "44:00:49": "Amazon (Echo/Ring)",
    "f4:f5:d8": "Google (Nest/Chromecast)",
    "54:60:09": "Google (Nest/Chromecast)",
    "f8:0f:f9": "Google (Nest/Chromecast)",
    "48:b0:2d": "Sonos",
    "5c:aa:fd": "Sonos",
}

# Vendor categories for classification
_COMPUTE_VENDORS = frozenset({
    "Raspberry Pi Foundation", "Raspberry Pi Trading", "Dell", "Super Micro",
    "Parallels", "VMware", "Hewlett Packard Enterprise", "HP", "Intel",
    "Lenovo", "Hardkernel (ODROID)",
})
_NETWORKING_VENDORS = frozenset({
    "Ubiquiti", "MikroTik", "TP-Link", "Netgear", "Cisco", "Cisco Meraki",
    "Juniper", "Aruba", "Fortinet", "Arista",
})
_IOT_VENDORS = frozenset({
    "Philips Hue", "Espressif", "Shelly (Allterco)",
    "Espressif (Sonoff/iTead)", "Tuya",
    "Amazon (Echo/Ring)", "Google (Nest/Chromecast)", "Sonos",
})
_SBC_VENDORS = frozenset({
    "Raspberry Pi Foundation", "Raspberry Pi Trading", "Hardkernel (ODROID)",
})


# ── Classification Signal Definitions ──────────────────────────────────

# Each signal: (signal_name, target_class, confidence_boost, description)
# Applied in classify_device based on matching conditions.


class FingerprintService:
    """Multi-signal device fingerprinting and additive-confidence classification."""

    # Well-known port -> service name mapping (covers all tier1+tier2 ports)
    PORT_SERVICE_MAP: dict[int, str] = {
        21: "ftp",
        22: "ssh",
        23: "telnet",
        25: "smtp",
        53: "dns",
        69: "tftp",
        80: "http",
        110: "pop3",
        111: "rpcbind",
        135: "msrpc",
        143: "imap",
        161: "snmp",
        179: "bgp",
        389: "ldap",
        427: "svrloc",
        443: "https",
        445: "smb",
        500: "isakmp",
        514: "syslog",
        515: "lpd",
        548: "afp",
        554: "rtsp",
        587: "submission",
        623: "ipmi",
        631: "ipp",
        636: "ldaps",
        873: "rsync",
        902: "vmware-auth",
        993: "imaps",
        995: "pop3s",
        1080: "socks",
        1194: "openvpn",
        1433: "mssql",
        1521: "oracle",
        1723: "pptp",
        1883: "mqtt",
        1900: "ssdp",
        2049: "nfs",
        2222: "ssh-alt",
        2375: "docker-api",
        2376: "docker-tls",
        2379: "etcd-client",
        2380: "etcd-peer",
        3000: "grafana",
        3128: "squid-proxy",
        3260: "iscsi",
        3306: "mysql",
        3389: "rdp",
        3478: "stun",
        4243: "docker-alt",
        4505: "salt-publish",
        4506: "salt-return",
        5000: "upnp",
        5001: "synology-https",
        5060: "sip",
        5222: "xmpp",
        5269: "xmpp-server",
        5353: "mdns",
        5432: "postgresql",
        5601: "kibana",
        5672: "amqp",
        5683: "coap",
        5900: "vnc",
        5984: "couchdb",
        6000: "x11",
        6379: "redis",
        6443: "k8s-api",
        6633: "openflow",
        6667: "irc",
        6881: "bittorrent",
        7001: "weblogic",
        7070: "realserver",
        7077: "spark-master",
        7443: "https-alt",
        7474: "neo4j",
        8000: "http-alt",
        8006: "proxmox-web",
        8008: "http-alt",
        8080: "http-alt",
        8081: "http-alt",
        8088: "http-alt",
        8090: "http-alt",
        8123: "homeassistant",
        8139: "puppet",
        8181: "http-alt",
        8291: "mikrotik-api",
        8333: "bitcoin",
        8443: "https-alt",
        8444: "https-alt",
        8500: "consul",
        8834: "nessus",
        8883: "mqtts",
        8888: "http-alt",
        8983: "solr",
        9000: "sonarqube",
        9001: "portainer",
        9042: "cassandra",
        9090: "prometheus",
        9092: "kafka",
        9100: "node-exporter",
        9200: "elasticsearch",
        9300: "elasticsearch-transport",
        9418: "git-daemon",
        9443: "https-alt",
        9999: "http-alt",
        10000: "webmin",
        10001: "ubiquiti-discovery",
        10250: "kubelet",
        10255: "kubelet-readonly",
        11211: "memcached",
        15672: "rabbitmq-mgmt",
        19132: "minecraft-bedrock",
        25565: "minecraft-java",
        27017: "mongodb",
        27018: "mongodb-shard",
        28017: "mongodb-web",
        32400: "plex",
        49152: "upnp-nat",
        50000: "jenkins-agent",
        51820: "wireguard",
        61616: "activemq",
    }

    # Banner-based inference rules: port -> (service, banner_regex -> PortInference)
    # Used to populate DetailedPort.inference when banners are available.
    _BANNER_PARSERS: dict[int, tuple[str, str]] = {
        22: ("ssh", r"SSH-[\d.]+-(.+?)(?:\s|$)"),
        80: ("http", r"^(.+?)(?:/[\d.]+)?$"),
        443: ("https", r"^(.+?)(?:/[\d.]+)?$"),
        161: ("snmp", r"(.+)"),
        1883: ("mqtt", r"(.+)"),
        3306: ("mysql", r"^([\d.]+)"),
        5432: ("postgresql", r"^([\d.]+)"),
        8006: ("proxmox", r"^(.+?)(?:/[\d.]+)?$"),
        8080: ("http", r"^(.+?)(?:/[\d.]+)?$"),
        8123: ("homeassistant", r"(.+)"),
        8443: ("https", r"^(.+?)(?:/[\d.]+)?$"),
        27017: ("mongodb", r"^([\d.]+)"),
    }

    @classmethod
    def infer_from_port(
        cls,
        port: int,
        banner: str | None = None,
    ) -> PortInference | None:
        """Derive a PortInference from a port number and optional banner.

        Uses PORT_SERVICE_MAP for the application name and _BANNER_PARSERS
        to extract version information from banner strings.
        """
        service = cls.PORT_SERVICE_MAP.get(port)
        if not service:
            return None

        application = service
        version: str | None = None

        if banner and port in cls._BANNER_PARSERS:
            _, pattern = cls._BANNER_PARSERS[port]
            match = re.search(pattern, banner)
            if match:
                captured = match.group(1).strip()
                # Check if captured looks like a version (digits and dots)
                if re.match(r"^\d", captured):
                    version = captured
                else:
                    application = captured

        os_hint: str | None = None
        if port == 22 and banner:
            if "ubuntu" in banner.lower() or "debian" in banner.lower():
                os_hint = "linux"
            elif "windows" in banner.lower():
                os_hint = "windows"
        elif port == 3389:
            os_hint = "windows"

        return PortInference(
            os=os_hint,
            application=application,
            version=version,
        )

    def fingerprint_device(
        self,
        open_ports: list[int],
        protocols: list[str] | None = None,
        primary_mac: str | None = None,
        raw_vendor: str | None = None,
        banners: dict[str, str] | None = None,
        protocol_data: dict[str, Any] | None = None,
    ) -> Fingerprint:
        """Generate a fingerprint from open ports and protocols.

        Args:
            open_ports: List of open TCP/UDP ports.
            protocols: List of detected protocols (e.g. mdns, ssdp, snmp).
            primary_mac: MAC address for vendor lookup.
            raw_vendor: Pre-resolved vendor name.
            banners: Port-keyed banner strings from banner grabbing.
            protocol_data: Structured protocol discovery results
                (keys: ``mdns``, ``ssdp``, ``snmp``, ``lldp``).

        Returns:
            A Fingerprint with detailed ports, service hints, and metadata.
        """
        protocols = protocols or []
        banners = banners or {}
        service_hints: list[str] = []
        detailed_ports: list[DetailedPort] = []

        for port in sorted(set(open_ports)):
            service_name = self.PORT_SERVICE_MAP.get(port)
            if service_name:
                service_hints.append(service_name)
            banner = banners.get(str(port))
            inference = self.infer_from_port(port, banner)
            detailed_ports.append(
                DetailedPort(
                    port=port,
                    protocol="tcp",
                    state="open",
                    service=service_name,
                    banner=banner,
                    inference=inference,
                )
            )

        os_hint = self._guess_os(open_ports)
        mac_oui = self._extract_oui(primary_mac)
        vendor = raw_vendor or self.lookup_vendor(primary_mac)
        device_family = self._guess_device_family(open_ports, protocols, vendor)
        protocol_details = self._build_protocol_details(protocols, protocol_data)

        return Fingerprint(
            open_ports=detailed_ports,
            port_numbers=sorted(set(open_ports)),
            service_hints=sorted(set(service_hints)),
            protocols=protocol_details,
            http_responses=[],
            os_hint=os_hint,
            vendor=vendor,
            mac_oui=mac_oui,
            device_family=device_family,
        )

    def classify_device(
        self,
        fingerprint: Fingerprint,
        primary_mac: str | None = None,
        hostname: str | None = None,
    ) -> Classification:
        """Classify a device using additive confidence scoring.

        Signal boosts are summed per class. The class with the highest total
        wins. Confidence = min(winner_score, 0.95). This matches the spec's
        requirement for additive scoring with a 0.95 cap.

        Args:
            fingerprint: The device fingerprint to classify.
            primary_mac: MAC address for vendor-based signals.
            hostname: Hostname for suggested node ID derivation.

        Returns:
            Classification with additive confidence (capped at 0.95).
        """
        signals: list[str] = []
        scores: dict[str, float] = {"compute": 0.0, "networking": 0.0, "iot": 0.0}

        port_set = frozenset(fingerprint.port_numbers)
        vendor = fingerprint.vendor
        proto = fingerprint.protocols

        # ── Port-Based Signals ─────────────────────────────────────────
        if 22 in port_set:
            os_hint = fingerprint.os_hint
            if os_hint == "linux" or os_hint is None:
                scores["compute"] += 0.3
                signals.append("ssh+linux->compute(+0.3)")

        if 8006 in port_set:
            scores["compute"] += 0.4
            signals.append("port:8006->compute(+0.4)")

        if 6443 in port_set or 10250 in port_set:
            scores["compute"] += 0.3
            signals.append("port:k8s->compute(+0.3)")

        if 2375 in port_set or 2376 in port_set:
            scores["compute"] += 0.3
            signals.append("port:docker->compute(+0.3)")

        if any(p in port_set for p in (80, 443, 8080, 9090, 9100, 3000)):
            scores["compute"] += 0.1
            signals.append("port:web-services->compute(+0.1)")

        if 3389 in port_set:
            scores["compute"] += 0.2
            signals.append("port:rdp->compute(+0.2)")

        if 179 in port_set:
            scores["networking"] += 0.3
            signals.append("port:bgp->networking(+0.3)")

        if 8291 in port_set:
            scores["networking"] += 0.3
            signals.append("port:mikrotik->networking(+0.3)")

        if 623 in port_set:
            scores["networking"] += 0.2
            signals.append("port:ipmi->networking(+0.2)")

        if 53 in port_set:
            scores["networking"] += 0.1
            signals.append("port:dns->networking(+0.1)")

        if 161 in port_set:
            scores["networking"] += 0.2
            signals.append("port:snmp->networking(+0.2)")

        if 8123 in port_set:
            scores["iot"] += 0.4
            signals.append("port:8123->iot(+0.4)")

        if 1883 in port_set or 8883 in port_set:
            scores["iot"] += 0.2
            signals.append("port:mqtt->iot(+0.2)")

        if 5683 in port_set:
            scores["iot"] += 0.2
            signals.append("port:coap->iot(+0.2)")

        if 10001 in port_set:
            scores["iot"] += 0.1
            signals.append("port:ubiquiti-discovery->iot(+0.1)")

        # ── Protocol Signals ───────────────────────────────────────────
        if proto and proto.snmp:
            scores["networking"] += 0.4
            signals.append("proto:snmp->networking(+0.4)")

        if proto and proto.lldp:
            scores["networking"] += 0.3
            signals.append("proto:lldp->networking(+0.3)")

        if proto and proto.mdns and proto.mdns.services:
            mdns_services = {s.lower() for s in proto.mdns.services}
            if any("_hue._tcp" in s for s in mdns_services):
                scores["iot"] += 0.5
                signals.append("mdns:_hue._tcp->iot(+0.5)")
            if any("_homekit._tcp" in s for s in mdns_services):
                scores["iot"] += 0.3
                signals.append("mdns:_homekit._tcp->iot(+0.3)")
            if any("_esphomelib._tcp" in s for s in mdns_services):
                scores["iot"] += 0.4
                signals.append("mdns:_esphomelib._tcp->iot(+0.4)")
            if any("_matter._tcp" in s or "_matterc._udp" in s for s in mdns_services):
                scores["iot"] += 0.3
                signals.append("mdns:_matter->iot(+0.3)")
            if any("_googlecast._tcp" in s for s in mdns_services):
                scores["iot"] += 0.3
                signals.append("mdns:_googlecast._tcp->iot(+0.3)")
            if any("_shelly._tcp" in s for s in mdns_services):
                scores["iot"] += 0.4
                signals.append("mdns:_shelly._tcp->iot(+0.4)")

        if proto and proto.ssdp and proto.ssdp.device_type and "ZonePlayer" in proto.ssdp.device_type:
            scores["iot"] += 0.5
            signals.append("ssdp:sonos->iot(+0.5)")

        # ── MAC Vendor Signals ─────────────────────────────────────────
        if vendor:
            if vendor in _SBC_VENDORS:
                scores["compute"] += 0.3
                signals.append(f"mac:{vendor}->compute(+0.3)")
            elif vendor in _COMPUTE_VENDORS:
                scores["compute"] += 0.2
                signals.append(f"mac:{vendor}->compute(+0.2)")
            elif vendor in _NETWORKING_VENDORS:
                scores["networking"] += 0.2
                signals.append(f"mac:{vendor}->networking(+0.2)")
            elif vendor in _IOT_VENDORS:
                scores["iot"] += 0.3
                signals.append(f"mac:{vendor}->iot(+0.3)")

        # ── Determine Winner ───────────────────────────────────────────
        max_score = max(scores.values())
        if max_score == 0:
            return Classification(
                suggested_class="unknown",
                suggested_type=None,
                suggested_kind=None,
                suggested_node_id=None,
                suggested_display_name=None,
                confidence=0.0,
                signals=["no-classification-signals"],
                explanation="No recognizable discovery signals were collected.",
                eligible_for_registration=False,
            )

        best_class = max(scores, key=lambda k: scores[k])
        confidence = min(max_score, 0.95)

        port_numbers = fingerprint.port_numbers
        suggested_type = self._suggest_type(best_class, port_numbers)
        suggested_kind = self._suggest_kind(best_class, port_numbers, vendor)
        suggested_node_id = self._suggest_node_id(hostname, suggested_kind, primary_mac)
        suggested_display_name = self._suggest_display_name(
            hostname, vendor, suggested_kind,
        )
        top_signals = ", ".join(s.split("->")[0] for s in signals[:4])
        explanation = (
            f"Classified as {best_class} ({confidence:.0%} confidence) from "
            f"{top_signals or 'observed signals'}."
        )

        return Classification(
            suggested_class=best_class,
            suggested_type=suggested_type,
            suggested_kind=suggested_kind,
            suggested_node_id=suggested_node_id,
            suggested_display_name=suggested_display_name,
            confidence=round(confidence, 2),
            signals=signals,
            explanation=explanation,
            eligible_for_registration=best_class != "unknown",
        )

    # ── Vendor Lookup ──────────────────────────────────────────────────

    def lookup_vendor(self, primary_mac: str | None) -> str | None:
        """Resolve a vendor from the MAC OUI when available.

        Resolution order:
        1. Inline ``OUI_VENDOR_MAP`` — fast, covers the OUIs we have
           classification rules for.
        2. ``mac-vendor-lookup`` library — broad IEEE coverage (~30k OUIs)
           for vendor strings we don't classify but still want to surface.

        Returns ``None`` if both lookups fail.
        """
        if not primary_mac:
            return None
        oui = self._extract_oui(primary_mac)
        if not oui:
            return None
        # Prefer our curated map (classification depends on the canonical name)
        vendor = OUI_VENDOR_MAP.get(oui)
        if vendor:
            return vendor
        return _lookup_vendor_lib(primary_mac)

    @staticmethod
    def _extract_oui(primary_mac: str | None) -> str | None:
        if not primary_mac:
            return None
        normalized = primary_mac.lower().replace("-", ":")
        parts = normalized.split(":")
        if len(parts) < 3:
            return None
        return ":".join(parts[:3])

    # ── OS / Device Family Hints ───────────────────────────────────────

    def _guess_os(self, ports: list[int]) -> str | None:
        """Guess the operating system from open ports."""
        if 3389 in ports:
            return "windows"
        if 22 in ports and 3389 not in ports:
            return "linux"
        if any(p in ports for p in (8123, 1883)):
            return "embedded"
        return None

    @staticmethod
    def _guess_device_family(
        ports: list[int],
        protocols: list[str],
        vendor: str | None,
    ) -> str | None:
        normalized_protocols = {protocol.lower() for protocol in protocols}
        if any(port in ports for port in (8006, 6443, 10250)):
            return "infrastructure"
        if any(port in ports for port in (1883, 8123, 5683)):
            return "smart-home"
        if "ssdp" in normalized_protocols or "mdns" in normalized_protocols:
            return "discovery-advertising"
        if vendor and vendor in _SBC_VENDORS:
            return "single-board-computer"
        return None

    # ── Type / Kind / Name Derivation ──────────────────────────────────

    def _suggest_type(self, device_class: str, port_numbers: list[int]) -> str | None:
        """Suggest a specific device type within a class."""
        if device_class == "compute":
            if 8006 in port_numbers:
                return "hypervisor"
            if 6443 in port_numbers or 10250 in port_numbers:
                return "kubernetes-node"
            if 2375 in port_numbers or 2376 in port_numbers:
                return "docker-host"
            return "server"
        if device_class == "networking":
            if 179 in port_numbers:
                return "router"
            if 8291 in port_numbers:
                return "mikrotik"
            return "network-device"
        if device_class == "iot":
            if 8123 in port_numbers:
                return "home-automation"
            if 1883 in port_numbers:
                return "mqtt-device"
            return "sensor"
        return None

    @staticmethod
    def _suggest_kind(
        device_class: str,
        port_numbers: list[int],
        vendor: str | None,
    ) -> str | None:
        """Suggest a device kind (more specific than type)."""
        if device_class == "compute":
            if 8006 in port_numbers:
                return "hypervisor"
            if 6443 in port_numbers:
                return "k8s-node"
            if vendor and vendor in _SBC_VENDORS:
                return "sbc"
            return "server"
        if device_class == "networking":
            if 179 in port_numbers:
                return "router"
            if 8291 in port_numbers:
                return "router"
            return "switch"
        if device_class == "iot":
            if 8123 in port_numbers:
                return "hub"
            if 1883 in port_numbers:
                return "mqtt-device"
            return "sensor"
        return None

    @staticmethod
    def _suggest_node_id(
        hostname: str | None,
        kind: str | None,
        primary_mac: str | None,
    ) -> str | None:
        """Derive a suggested nodeId from hostname or kind+MAC."""
        if hostname:
            node_id = hostname.lower().replace(" ", "-").replace("_", "-")
            node_id = re.sub(r"[^a-z0-9.-]", "", node_id)[:63]
            if node_id:
                return node_id
        if kind and primary_mac:
            mac_suffix = primary_mac.lower().replace(":", "").replace("-", "")[-4:]
            return f"{kind}-{mac_suffix}"
        return None

    @staticmethod
    def _suggest_display_name(
        hostname: str | None,
        vendor: str | None,
        kind: str | None,
    ) -> str | None:
        """Derive a human-readable display name."""
        if hostname:
            return hostname
        parts = [p for p in (vendor, kind) if p]
        if parts:
            return " ".join(parts).title()
        return None

    # ── Protocol Detail Builder ────────────────────────────────────────

    @staticmethod
    def _build_protocol_details(
        protocols: list[str],
        protocol_data: dict[str, Any] | None = None,
    ) -> ProtocolDetails | None:
        """Convert a flat protocol list into structured ProtocolDetails.

        When ``protocol_data`` is provided (from actual protocol discovery
        or banner grabbing), the structured data is used to populate detail
        models with real values.  Otherwise flat protocol names are mapped
        to placeholder detail objects so the classifier can still detect them.

        Args:
            protocols: Flat list of detected protocol names.
            protocol_data: Structured data keyed by protocol name with
                sub-dicts matching the detail model fields.  Example::

                    {
                        "snmp": {"sysDescr": "...", "sysName": "..."},
                        "mdns": {"services": [...], "hostname": "..."},
                    }
        """
        if not protocols and not protocol_data:
            return None

        proto_set = {p.lower() for p in protocols}
        data = protocol_data or {}

        # ── mDNS ──────────────────────────────────────────────────────
        mdns: MdnsDetail | None = None
        if "mdns" in data:
            d = data["mdns"]
            mdns = MdnsDetail(
                services=d.get("services", []),
                hostname=d.get("hostname"),
                txt_records=d.get("txtRecords", d.get("txt_records", {})),
            )
        elif "mdns" in proto_set:
            mdns = MdnsDetail(services=[], hostname=None, txt_records={})

        # ── SSDP ──────────────────────────────────────────────────────
        ssdp: SsdpDetail | None = None
        if "ssdp" in data:
            d = data["ssdp"]
            ssdp = SsdpDetail(
                server=d.get("server"),
                location=d.get("location"),
                usn=d.get("usn"),
                device_type=d.get("deviceType", d.get("device_type")),
            )
        elif "ssdp" in proto_set:
            ssdp = SsdpDetail(server=None, location=None, usn=None, device_type=None)

        # ── SNMP ──────────────────────────────────────────────────────
        snmp: SnmpDetail | None = None
        if "snmp" in data:
            d = data["snmp"]
            snmp = SnmpDetail(
                sys_descr=d.get("sysDescr", d.get("sys_descr")),
                sys_name=d.get("sysName", d.get("sys_name")),
                sys_object_id=d.get("sysObjectID", d.get("sys_object_id")),
            )
        elif "snmp" in proto_set or "bgp" in proto_set:
            snmp = SnmpDetail(sys_descr=None, sys_name=None, sys_object_id=None)

        # ── LLDP ──────────────────────────────────────────────────────
        lldp: LldpDetail | None = None
        if "lldp" in data:
            d = data["lldp"]
            lldp = LldpDetail(
                chassis_id=d.get("chassisId", d.get("chassis_id")),
                port_id=d.get("portId", d.get("port_id")),
                system_name=d.get("systemName", d.get("system_name")),
                system_description=d.get(
                    "systemDescription", d.get("system_description"),
                ),
            )

        if not any([mdns, ssdp, snmp, lldp]):
            return None

        return ProtocolDetails(mdns=mdns, ssdp=ssdp, snmp=snmp, lldp=lldp)
