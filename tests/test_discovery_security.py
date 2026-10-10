import sys
import os
import unittest.mock
from collections import deque

import pytest

# Mock Home Assistant modules so tests can run without the full core platform installed
sys.modules["homeassistant"] = unittest.mock.MagicMock()
sys.modules["homeassistant.config_entries"] = unittest.mock.MagicMock()
sys.modules["homeassistant.const"] = unittest.mock.MagicMock()
sys.modules["homeassistant.core"] = unittest.mock.MagicMock()
sys.modules["homeassistant.components"] = unittest.mock.MagicMock()
sys.modules["homeassistant.components.light"] = unittest.mock.MagicMock()
sys.modules["homeassistant.helpers"] = unittest.mock.MagicMock()
sys.modules["homeassistant.helpers.entity_platform"] = unittest.mock.MagicMock()

# Inject relative path for custom_components
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.dmx_diodeled.discovery import DMXDiscoveryProtocol  # noqa: E402


def _consume(coro):
    coro.close()


class MockHomeAssistant:
    def __init__(self):
        self.async_create_task = unittest.mock.MagicMock(side_effect=_consume)


def _make_protocol():
    """Create a protocol wired to a fresh mock hass, ready for datagrams."""
    hass = MockHomeAssistant()
    callback = unittest.mock.AsyncMock()

    protocol = DMXDiscoveryProtocol(hass, callback)
    protocol.connection_made(unittest.mock.MagicMock())

    return hass, callback, protocol


def _send(protocol, mac_address: str) -> None:
    """Send a discovery datagram for the given MAC from 192.168.1.50."""
    payload = f"192.168.1.50,{mac_address},HF-LPB100\n".encode("utf-8")
    addr = ("192.168.1.50", 43210)
    protocol.datagram_received(payload, addr)


@pytest.mark.asyncio
async def test_dmx_discovery_deduplication():
    """Test that discovery tasks are deduplicated to prevent event loop starvation."""
    hass, callback, protocol = _make_protocol()

    payload = b"192.168.1.50,AABBCCDDEEFF,HF-LPB100\n"
    addr = ("192.168.1.50", 43210)

    # Send the same payload 5 times
    for _ in range(5):
        protocol.datagram_received(payload, addr)

    # Only one task should have been created
    hass.async_create_task.assert_called_once()
    callback.assert_called_once_with("192.168.1.50", "AABBCCDDEEFF")


@pytest.mark.asyncio
async def test_dmx_discovery_oversized_mac_rejected():
    """MAC fields longer than 64 chars must be dropped before task creation."""
    hass, callback, protocol = _make_protocol()

    mac = "A" * 65
    payload = f"192.168.1.50,{mac},HF-LPB100\n".encode("utf-8")
    addr = ("192.168.1.50", 43210)

    protocol.datagram_received(payload, addr)

    hass.async_create_task.assert_not_called()
    callback.assert_not_called()


@pytest.mark.asyncio
async def test_dmx_discovery_oversized_packet_rejected():
    """UDP packets larger than 1024 bytes must be dropped immediately."""
    hass, callback, protocol = _make_protocol()

    payload = b"A" * 1025
    addr = ("192.168.1.50", 43210)
    protocol.datagram_received(payload, addr)

    hass.async_create_task.assert_not_called()
    callback.assert_not_called()


@pytest.mark.asyncio
async def test_dmx_discovery_unique_mac_flood_is_rate_limited():
    """A rotating-unique-MAC flood must not spawn unbounded discovery tasks.

    The dedup cache alone only bounds memory: with unique MACs every packet
    is first-seen. The sliding-window rate limit caps task (and therefore
    config-entry flow) creation, which is what actually bounds event-loop work.
    """
    hass, callback, protocol = _make_protocol()

    max_tasks = DMXDiscoveryProtocol._MAX_TASKS_PER_WINDOW

    # Send 1005 packets with rotating unique MACs.
    for i in range(1005):
        _send(protocol, f"AA{i:08X}")

    # Task creation is bounded by the rate limit instead of being 1:1 with
    # incoming packets.
    assert hass.async_create_task.call_count == max_tasks

    # Devices are only cached once a task was created for them, so the dedup
    # cache stays small under the flood.
    assert len(protocol._seen_devices) == max_tasks


@pytest.mark.asyncio
async def test_dmx_discovery_cache_evicts_oldest():
    """At the cap, the oldest dedup entries are evicted; recent ones stay."""
    hass, callback, protocol = _make_protocol()

    cap = DMXDiscoveryProtocol._SEEN_CACHE_CAP
    # Fill the dedup cache to its cap with synthetic entries (oldest first).
    for i in range(cap):
        protocol._seen_devices[(f"AA{i:06X}", "192.168.1.50")] = None
    oldest_key = ("AA000000", "192.168.1.50")
    recent_key = (f"AA{cap - 1:06X}", "192.168.1.50")

    # A fresh device must be accepted by evicting the oldest entry, not by
    # clearing the whole cache.
    _send(protocol, "NEWDEVICE1")

    assert hass.async_create_task.call_count == 1
    assert len(protocol._seen_devices) == cap
    assert oldest_key not in protocol._seen_devices
    # Recently seen devices must remain deduplicated across the cap boundary.
    assert recent_key in protocol._seen_devices

    # A duplicate of a recently seen device stays suppressed.
    _send(protocol, recent_key[0])
    hass.async_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_dmx_discovery_rate_limited_device_retried_after_window():
    """A device dropped by the rate limit is discovered once the window clears."""
    hass, callback, protocol = _make_protocol()

    max_tasks = DMXDiscoveryProtocol._MAX_TASKS_PER_WINDOW

    # Fill the sliding window with unique MACs.
    for i in range(max_tasks):
        _send(protocol, f"AA{i:08X}")
    assert hass.async_create_task.call_count == max_tasks

    # The next device is dropped by the rate limit and not marked as seen.
    _send(protocol, "B0B0B0B0")
    assert hass.async_create_task.call_count == max_tasks

    # Let the rate-limit window elapse, then let the device broadcast again.
    elapsed = protocol._RATE_LIMIT_WINDOW_SECONDS + 1
    protocol._task_times = deque(t - elapsed for t in protocol._task_times)
    _send(protocol, "B0B0B0B0")

    assert hass.async_create_task.call_count == max_tasks + 1
    callback.assert_any_call("192.168.1.50", "B0B0B0B0")
