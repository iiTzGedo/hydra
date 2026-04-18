"""Performance benchmark for the API-direct scanner.

Spec §2.9.3 budget: an idle ``/24`` (254 hosts) must complete in under
15 seconds. This test is **opt-in** via ``RUN_PERF_TESTS=1`` because:

- It depends on local network speed and host load
- It scans a TEST-NET-1 subnet (``192.0.2.0/24``) which is reserved for
  documentation / examples (RFC 5737) and never reachable, so all
  254 hosts time out
- The runtime is bound by ``port_timeout`` × ``ports`` ÷ ``concurrency``;
  defaults give ~7s on a healthy machine

Run with:
    RUN_PERF_TESTS=1 uv run pytest tests/test_discovery_perf.py -v
"""

from __future__ import annotations

import os
import time

import pytest

from hydra.api.v1.services.discovery.scanner import scan_subnet


@pytest.mark.perf
@pytest.mark.skipif(
    os.environ.get("RUN_PERF_TESTS") != "1",
    reason="Set RUN_PERF_TESTS=1 to run perf benchmarks",
)
@pytest.mark.asyncio
async def test_scan_24_under_15_seconds():
    """Spec §2.9.3 — full /24 scan completes in under 15 s on idle subnet."""
    start = time.monotonic()
    # 192.0.2.0/24 is RFC 5737 TEST-NET-1, guaranteed unroutable.
    result = await scan_subnet(
        "192.0.2.0/24",
        port_tier="tier1",
        port_timeout=0.5,
        concurrency=128,
    )
    elapsed = time.monotonic() - start

    assert result["hosts"] == [], "TEST-NET-1 should yield zero alive hosts"
    assert elapsed < 15.0, (
        f"Scan took {elapsed:.2f}s, exceeds spec §2.9.3 budget of 15s"
    )
