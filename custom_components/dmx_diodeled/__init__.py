"""The DiodeLED DMX Controller integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .dmx_controller import DiodLEDController
from .discovery import async_start_discovery
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.const import CONF_MAC
import logging

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.LIGHT]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the DiodeLED DMX Controller component."""

    async def async_discovered_device(ip_address: str, mac_address: str):
        """Handle a discovered device."""
        _LOGGER.debug("Discovered device at %s", ip_address)
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_INTEGRATION_DISCOVERY},
            data={CONF_HOST: ip_address, CONF_MAC: mac_address},
        )

    # Start the background UDP listener
    hass.data.setdefault(DOMAIN, {})
    transport = await async_start_discovery(hass, async_discovered_device)
    if transport:
        hass.data[DOMAIN]["discovery_transport"] = transport

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DiodeLED DMX Controller from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 8899)

    controller = DiodLEDController(host, port)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
