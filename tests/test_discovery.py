import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from custom_components.dmx_diodeled.discovery import DMXDiscoveryProtocol, async_start_discovery

@pytest.mark.asyncio
async def test_dmx_discovery_protocol_valid_payload():
    hass = MagicMock(spec=HomeAssistant)
    hass.async_create_task = MagicMock()
    callback = AsyncMock()

    protocol = DMXDiscoveryProtocol(hass, callback)
    protocol.connection_made(MagicMock())

    payload = b"192.168.1.50,AABBCCDDEEFF,HF-LPB100\n"
    addr = ("192.168.1.50", 43210)

    protocol.datagram_received(payload, addr)

    hass.async_create_task.assert_called_once()
    # The actual callback execution is deferred by async_create_task, but we verify it's scheduled

@pytest.mark.asyncio
async def test_dmx_discovery_protocol_invalid_payload():
    hass = MagicMock(spec=HomeAssistant)
    hass.async_create_task = MagicMock()
    callback = AsyncMock()

    protocol = DMXDiscoveryProtocol(hass, callback)
    protocol.connection_made(MagicMock())

    payload = b"invalid_data"
    addr = ("192.168.1.50", 43210)

    protocol.datagram_received(payload, addr)

    hass.async_create_task.assert_not_called()

@pytest.mark.asyncio
async def test_dmx_discovery_protocol_wrong_device():
    hass = MagicMock(spec=HomeAssistant)
    hass.async_create_task = MagicMock()
    callback = AsyncMock()

    protocol = DMXDiscoveryProtocol(hass, callback)
    protocol.connection_made(MagicMock())

    payload = b"192.168.1.50,AABBCCDDEEFF,OTHER-DEVICE"
    addr = ("192.168.1.50", 43210)

    protocol.datagram_received(payload, addr)

    hass.async_create_task.assert_not_called()
