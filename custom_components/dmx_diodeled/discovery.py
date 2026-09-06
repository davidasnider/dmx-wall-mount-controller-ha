import asyncio
import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class DMXDiscoveryProtocol(asyncio.DatagramProtocol):
    """Protocol for DMX Controller UDP Discovery."""

    def __init__(self, hass: HomeAssistant, callback):
        self.hass = hass
        self.callback = callback
        self.transport = None

    def connection_made(self, transport):
        """Handle connection established."""
        self.transport = transport
        _LOGGER.debug("DMX Discovery UDP listener started on port 48899")

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle received datagram."""
        try:
            payload = data.decode("utf-8", errors="ignore").strip()
            _LOGGER.debug("Received UDP payload: %s from %s", payload, addr)
            parts = payload.split(",")
            if len(parts) >= 3 and "HF-LPB100" in parts[2]:
                # Use the packet source address as the authoritative host: the
                # IP embedded in the payload can be spoofed by any host on the
                # network.
                ip_address = addr[0]
                mac_address = parts[1]
                if ip_address != parts[0]:
                    _LOGGER.warning(
                        "Discovered device claimed IP %s but packet arrived from %s; using sender address",
                        parts[0],
                        ip_address,
                    )
                _LOGGER.info(
                    "Discovered DMX Controller at %s (MAC: %s)", ip_address, mac_address
                )
                self.hass.async_create_task(self.callback(ip_address, mac_address))
        except Exception:
            _LOGGER.exception("Error parsing UDP payload from %s", addr)


async def async_start_discovery(
    hass: HomeAssistant, callback
) -> asyncio.DatagramTransport | None:
    """Start the UDP discovery listener."""
    loop = asyncio.get_running_loop()
    try:
        transport, _ = await loop.create_datagram_endpoint(
            lambda: DMXDiscoveryProtocol(hass, callback),
            local_addr=("0.0.0.0", 48899),
            reuse_port=True,
        )
        return transport
    except Exception:
        _LOGGER.exception("Failed to start UDP listener on port 48899")
        return None
