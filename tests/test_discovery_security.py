import asyncio
import logging
import sys
import os
import unittest.mock
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


@pytest.mark.asyncio
async def test_dmx_discovery_deduplication():
    """Test that discovery tasks are deduplicated to prevent event loop starvation."""
    hass = MockHomeAssistant()
    callback = unittest.mock.AsyncMock()

    protocol = DMXDiscoveryProtocol(hass, callback)
    protocol.connection_made(unittest.mock.MagicMock())

    payload = b"192.168.1.50,AABBCCDDEEFF,HF-LPB100\n"
    addr = ("192.168.1.50", 43210)

    # Send the same payload 5 times
    for _ in range(5):
        protocol.datagram_received(payload, addr)

    # Only one task should have been created
    hass.async_create_task.assert_called_once()
    callback.assert_called_once_with("192.168.1.50", "AABBCCDDEEFF")


@pytest.mark.asyncio
async def test_dmx_discovery_cache_cap():
    """Test that the seen devices cache is capped to prevent memory leaks."""
    hass = MockHomeAssistant()
    callback = unittest.mock.AsyncMock()

    protocol = DMXDiscoveryProtocol(hass, callback)
    protocol.connection_made(unittest.mock.MagicMock())

    # Send 1005 unique payloads
    for i in range(1005):
        mac = f"AA000000{i:04X}"
        payload = f"192.168.1.50,{mac},HF-LPB100\n".encode("utf-8")
        addr = ("192.168.1.50", 43210)
        protocol.datagram_received(payload, addr)

    # Cache clears when len > 1000, so it clears after 1001 items.
    # 1001st item clears the cache and gets added. (size 1)
    # 1002, 1003, 1004, 1005 get added. (size 1+4 = 5) Wait, let's trace:
    # After 1000 items, len is 1000.
    # Item 1001: len(seen) is 1000 (not > 1000), added, len is 1001.
    # Item 1002: len(seen) is 1001 (> 1000), clears cache, added, len is 1.
    # Item 1003: added, len 2
    # Item 1004: added, len 3
    # Item 1005: added, len 4

    assert len(protocol._seen_devices) == 4
    assert hass.async_create_task.call_count == 1005
