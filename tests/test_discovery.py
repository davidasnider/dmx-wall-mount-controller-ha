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


class MockHomeAssistant:
    def __init__(self):
        self.async_create_task = unittest.mock.MagicMock()


@pytest.mark.asyncio
async def test_dmx_discovery_protocol_valid_payload():
    hass = MockHomeAssistant()
    callback = unittest.mock.AsyncMock()

    protocol = DMXDiscoveryProtocol(hass, callback)
    protocol.connection_made(unittest.mock.MagicMock())

    payload = b"192.168.1.50,AABBCCDDEEFF,HF-LPB100\n"
    addr = ("192.168.1.50", 43210)

    protocol.datagram_received(payload, addr)

    # The actual callback execution is deferred by async_create_task, but we
    # verify the callback was invoked with the parsed host/MAC values.
    hass.async_create_task.assert_called_once()
    callback.assert_called_once_with("192.168.1.50", "AABBCCDDEEFF")


@pytest.mark.asyncio
async def test_dmx_discovery_protocol_invalid_payload():
    hass = MockHomeAssistant()
    callback = unittest.mock.AsyncMock()

    protocol = DMXDiscoveryProtocol(hass, callback)
    protocol.connection_made(unittest.mock.MagicMock())

    payload = b"invalid_data"
    addr = ("192.168.1.50", 43210)

    protocol.datagram_received(payload, addr)

    hass.async_create_task.assert_not_called()


@pytest.mark.asyncio
async def test_dmx_discovery_protocol_wrong_device():
    hass = MockHomeAssistant()
    callback = unittest.mock.AsyncMock()

    protocol = DMXDiscoveryProtocol(hass, callback)
    protocol.connection_made(unittest.mock.MagicMock())

    payload = b"192.168.1.50,AABBCCDDEEFF,OTHER-DEVICE"
    addr = ("192.168.1.50", 43210)

    protocol.datagram_received(payload, addr)

    hass.async_create_task.assert_not_called()


@pytest.mark.asyncio
async def test_dmx_discovery_protocol_sender_address_authoritative():
    """The packet source address wins over a spoofed IP in the payload."""
    hass = MockHomeAssistant()
    callback = unittest.mock.AsyncMock()

    protocol = DMXDiscoveryProtocol(hass, callback)
    protocol.connection_made(unittest.mock.MagicMock())

    # The payload claims a different IP than the host the packet arrived from.
    payload = b"10.0.0.99,AABBCCDDEEFF,HF-LPB100"
    addr = ("192.168.1.50", 43210)

    protocol.datagram_received(payload, addr)

    hass.async_create_task.assert_called_once()
    callback.assert_called_once_with("192.168.1.50", "AABBCCDDEEFF")
