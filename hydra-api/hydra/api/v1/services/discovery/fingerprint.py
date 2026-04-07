"""Port-based service fingerprinting and device classification."""

from __future__ import annotations

from hydra.api.v1.models.discovery.schemas import Classification, Fingerprint


class FingerprintService:
    """Port-based service fingerprinting and device classification."""

    OUI_VENDOR_MAP: dict[str, str] = {
        "b8:27:eb": "Raspberry Pi Foundation",
        "dc:a6:32": "Raspberry Pi Trading",
        "e4:5f:01": "Raspberry Pi Trading",
        "00:1b:21": "Dell",
        "00:25:90": "Super Micro",
        "00:1c:42": "Parallels",
        "00:1c:b3": "Apple",
        "18:b4:30": "Ubiquiti",
        "d8:b3:70": "Ubiquiti",
        "2c:c8:1b": "Routerboard/MikroTik",
        "48:a9:8a": "TP-Link",
        "00:17:88": "Philips Lighting",
        "ec:fa:bc": "Espressif",
        "24:0a:c4": "Espressif",
    }

    # Well-known port -> service name mapping
    PORT_SERVICE_MAP: dict[int, str] = {
        21: "ftp",
        22: "ssh",
        25: "smtp",
        53: "dns",
        80: "http",
        110: "pop3",
        143: "imap",
        161: "snmp",
        179: "bgp",
        443: "https",
        623: "ipmi",
        1883: "mqtt",
        1900: "ssdp",
        2375: "docker-api",
        2376: "docker-tls",
        3000: "grafana",
        3306: "mysql",
        3389: "rdp",
        5353: "mdns",
        5432: "postgresql",
        5683: "coap",
        6379: "redis",
        6443: "k8s-api",
        8006: "proxmox-web",
        8080: "http-alt",
        8123: "homeassistant",
        8291: "mikrotik-api",
        8443: "https-alt",
        8883: "mqtts",
        9090: "prometheus",
        9100: "node-exporter",
        10001: "ubiquiti-discovery",
        10250: "kubelet",
        27017: "mongodb",
    }

    # Classification rules based on port patterns
    COMPUTE_PORTS: frozenset[int] = frozenset(
        {22, 80, 443, 2375, 2376, 3000, 6443, 8006, 8080, 9090, 9100, 10250}
    )
    NETWORKING_PORTS: frozenset[int] = frozenset({53, 161, 179, 623, 8291})
    IOT_PORTS: frozenset[int] = frozenset({1883, 5353, 5683, 8123, 8883, 10001})

    def fingerprint_device(
        self,
        open_ports: list[int],
        protocols: list[str] | None = None,
        primary_mac: str | None = None,
        raw_vendor: str | None = None,
    ) -> Fingerprint:
        """Generate a fingerprint from open ports and protocols.

        Args:
            open_ports: List of open TCP/UDP ports.
            protocols: List of detected protocols (e.g. mdns, ssdp, snmp).

        Returns:
            A Fingerprint with service hints, OS guess, and sorted data.
        """
        protocols = protocols or []
        service_hints: list[str] = []
        for port in open_ports:
            if port in self.PORT_SERVICE_MAP:
                service_hints.append(self.PORT_SERVICE_MAP[port])

        os_hint = self._guess_os(open_ports)
        mac_oui = self._extract_oui(primary_mac)
        vendor = raw_vendor or self.lookup_vendor(primary_mac)
        device_family = self._guess_device_family(open_ports, protocols, vendor)

        return Fingerprint(
            open_ports=sorted(open_ports),
            service_hints=sorted(set(service_hints)),
            protocols=sorted(set(protocols)),
            os_hint=os_hint,
            vendor=vendor,
            mac_oui=mac_oui,
            device_family=device_family,
        )

    def classify_device(self, fingerprint: Fingerprint) -> Classification:
        """Classify a device based on its fingerprint.

        Args:
            fingerprint: The device fingerprint to classify.

        Returns:
            A Classification with suggested class, type, confidence and signals.
        """
        signals: list[str] = []
        scores: dict[str, float] = {"compute": 0.0, "networking": 0.0, "iot": 0.0}

        for port in fingerprint.open_ports:
            if port in self.COMPUTE_PORTS:
                scores["compute"] += 1
                signals.append(f"port:{port}->compute")
            if port in self.NETWORKING_PORTS:
                scores["networking"] += 1
                signals.append(f"port:{port}->networking")
            if port in self.IOT_PORTS:
                scores["iot"] += 1
                signals.append(f"port:{port}->iot")

        for proto in fingerprint.protocols:
            if proto in ("snmp", "bgp"):
                scores["networking"] += 2
                signals.append(f"proto:{proto}->networking")
            elif proto in ("mqtt", "coap", "mdns-iot"):
                scores["iot"] += 2
                signals.append(f"proto:{proto}->iot")

        # Determine winner
        total = sum(scores.values())
        if total == 0:
            return Classification(
                suggested_class="unknown",
                suggested_type=None,
                confidence=0.0,
                signals=["no-classification-signals"],
                explanation="No recognizable discovery signals were collected.",
                eligible_for_registration=False,
            )

        best_class = max(scores, key=lambda k: scores[k])
        confidence = min(scores[best_class] / max(total, 1), 1.0)

        suggested_type = self._suggest_type(best_class, fingerprint)
        explanation = (
            f"Classified as {best_class} from "
            f"{', '.join(signals[:4]) if signals else 'observed signals'}."
        )

        return Classification(
            suggested_class=best_class,
            suggested_type=suggested_type,
            confidence=round(confidence, 2),
            signals=signals,
            explanation=explanation,
            eligible_for_registration=best_class != "unknown",
        )

    def lookup_vendor(self, primary_mac: str | None) -> str | None:
        """Resolve a vendor from the MAC OUI when available."""
        oui = self._extract_oui(primary_mac)
        if not oui:
            return None
        return self.OUI_VENDOR_MAP.get(oui)

    @staticmethod
    def _extract_oui(primary_mac: str | None) -> str | None:
        if not primary_mac:
            return None
        normalized = primary_mac.lower().replace("-", ":")
        parts = normalized.split(":")
        if len(parts) < 3:
            return None
        return ":".join(parts[:3])

    def _guess_os(self, ports: list[int]) -> str | None:
        """Guess the operating system from open ports.

        Args:
            ports: List of open ports.

        Returns:
            OS hint string or None if indeterminate.
        """
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
        if vendor and "Raspberry Pi" in vendor:
            return "single-board-computer"
        return None

    def _suggest_type(self, device_class: str, fp: Fingerprint) -> str | None:
        """Suggest a specific device type within a class.

        Args:
            device_class: The broad classification (compute, networking, iot).
            fp: The device fingerprint.

        Returns:
            Specific type string or None.
        """
        if device_class == "compute":
            if 8006 in fp.open_ports:
                return "hypervisor"
            if 6443 in fp.open_ports or 10250 in fp.open_ports:
                return "kubernetes-node"
            if 2375 in fp.open_ports or 2376 in fp.open_ports:
                return "docker-host"
            return "server"
        if device_class == "networking":
            if 179 in fp.open_ports:
                return "router"
            if 8291 in fp.open_ports:
                return "mikrotik"
            return "network-device"
        if device_class == "iot":
            if 8123 in fp.open_ports:
                return "home-automation"
            if 1883 in fp.open_ports:
                return "mqtt-device"
            return "sensor"
        return None
