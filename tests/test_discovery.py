import logging
from unittest.mock import AsyncMock, MagicMock
import pytest

from custom_components.dmx_diodeled.discovery import DMXDiscoveryProtocol


def _consume(coro):
    """Consume the coroutine the real task scheduler would have awaited.

    The real ``hass.async_create_task`` schedules the coroutine on the event
    loop; this test double closes it instead so it is never left dangling.
    """
    coro.close()


class MockHomeAssistant:
    def __init__(self):
        # A plain MagicMock would leave the coroutine produced by the async
        # callback neither awaited nor scheduled, which triggers
        # "coroutine was never awaited" RuntimeWarnings. Consume it instead.
        self.async_create_task = MagicMock(side_effect=_consume)


@pytest.mark.asyncio
async def test_dmx_discovery_protocol_valid_payload():
    hass = MockHomeAssistant()
    callback = AsyncMock()

    protocol = DMXDiscoveryProtocol(hass, callback)
    protocol.connection_made(MagicMock())

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
    callback = AsyncMock()

    protocol = DMXDiscoveryProtocol(hass, callback)
    protocol.connection_made(MagicMock())

    payload = b"invalid_data"
    addr = ("192.168.1.50", 43210)

    protocol.datagram_received(payload, addr)

    hass.async_create_task.assert_not_called()


@pytest.mark.asyncio
async def test_dmx_discovery_protocol_wrong_device():
    hass = MockHomeAssistant()
    callback = AsyncMock()

    protocol = DMXDiscoveryProtocol(hass, callback)
    protocol.connection_made(MagicMock())

    payload = b"192.168.1.50,AABBCCDDEEFF,OTHER-DEVICE"
    addr = ("192.168.1.50", 43210)

    protocol.datagram_received(payload, addr)

    hass.async_create_task.assert_not_called()


@pytest.mark.asyncio
async def test_dmx_discovery_protocol_sender_address_authoritative():
    """The packet source address wins over a spoofed IP in the payload."""
    hass = MockHomeAssistant()
    callback = AsyncMock()

    protocol = DMXDiscoveryProtocol(hass, callback)
    protocol.connection_made(MagicMock())

    # The payload claims a different IP than the host the packet arrived from.
    payload = b"10.0.0.99,AABBCCDDEEFF,HF-LPB100"
    addr = ("192.168.1.50", 43210)

    protocol.datagram_received(payload, addr)

    hass.async_create_task.assert_called_once()
    callback.assert_called_once_with("192.168.1.50", "AABBCCDDEEFF")


@pytest.mark.asyncio
async def test_log_injection_is_sanitized(caplog):
    """Crafted UDP payload bytes can never forge log lines (CWE-117)."""
    hass = MockHomeAssistant()
    callback = AsyncMock()

    protocol = DMXDiscoveryProtocol(hass, callback)
    protocol.connection_made(MagicMock())

    # Crafted payload: a raw \n embedded in the claimed-IP field (parts[0])
    # and a raw CR in the MAC field (parts[1]). The packet's sender address
    # differs from the claimed IP, so every sanitization branch is exercised.
    payload = b"10.0.0.9\n9,AA:BB\rCCDD:HFFF,HF-LPB100"
    addr = ("192.168.1.50", 43210)

    with caplog.at_level(
        logging.DEBUG, logger="custom_components.dmx_diodeled.discovery"
    ):
        protocol.datagram_received(payload, addr)

    # The discovery path must have logged; an empty capture (e.g. fast-path
    # reject) would make the security assertions below vacuous.
    assert caplog.records

    # No emitted log record may contain a raw newline or carriage return.
    for record in caplog.records:
        message = record.getMessage()
        assert "\n" not in message and "\r" not in message

    # The escaped forms, never raw control characters, reach the log stream.
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "10.0.0.9\\n9" in logged  # claimed IP escaped
    assert "AA:BB\\rCCDD:HFFF" in logged  # MAC escaped

    # The callback still receives raw (unescaped) values: Home Assistant core
    # needs strict byte sequences for unique_id dedupe; sanitization is a
    # logging-only concern.
    hass.async_create_task.assert_called_once()
    callback.assert_called_once_with("192.168.1.50", "AA:BB\rCCDD:HFFF")
