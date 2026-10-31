"""The DiodeLED DMX Controller integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from typing import Any

from .const import DOMAIN
from .dmx_controller import DiodLEDController
from .discovery import async_start_discovery
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.const import CONF_MAC
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from .entity import configured_zones, zone_unique_id
import logging

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.LIGHT, Platform.NUMBER]

# Home Assistant calls async_setup (and so starts the discovery listener) only
# when a config entry or a YAML key for this domain exists. Accepting an empty
# "dmx_diodeled:" key lets users start discovery before the first controller
# is added.
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the DiodeLED DMX Controller component."""

    async def async_discovered_device(ip_address: str, mac_address: str):
        """Handle a discovered device."""
        _LOGGER.debug("Discovered device at %s", ip_address)
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_INTEGRATION_DISCOVERY},
            data={CONF_HOST: ip_address, CONF_MAC: mac_address},
        )

    # Start the background UDP listener (closing any previous one first so a
    # reload does not leak sockets or create duplicate listeners). Discovery
    # state lives under its own "discovery" namespace so integration-internal
    # keys can never collide with per-entry controller keys.
    hass.data.setdefault(DOMAIN, {})
    discovery_state = hass.data[DOMAIN].setdefault("discovery", {})
    previous_transport = discovery_state.pop("transport", None)
    if previous_transport is not None:
        previous_transport.close()

    transport = await async_start_discovery(hass, async_discovered_device)
    if transport:
        discovery_state["transport"] = transport

        def _stop_discovery_listener(_event) -> None:
            """Close the UDP discovery transport on Home Assistant shutdown."""
            transport.close()

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop_discovery_listener)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DiodeLED DMX Controller from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 8899)

    controller = DiodLEDController(host, port)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller

    _async_remove_disabled_zone_entities(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload when the enabled zones change in the options flow.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry so entities match the newly selected zones."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_remove_disabled_zone_entities(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove registry entries for zones that are no longer enabled.

    Without this, a zone switched off in the options would linger as an
    "unavailable" entity forever.
    """
    wanted = {
        zone_unique_id(entry.entry_id, zone, suffix)
        for zone in configured_zones(entry)
        for suffix in ("", "speed")
    }
    registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity_entry.unique_id not in wanted:
            registry.async_remove(entity_entry.entity_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
