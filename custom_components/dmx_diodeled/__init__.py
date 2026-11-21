"""The DiodeLED DMX Controller integration."""

import logging
from typing import Any

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .config_flow import _mac_is_well_formed
from .const import DOMAIN
from .discovery import async_start_discovery
from .dmx_controller import DiodLEDController
from .entity import configured_zones, zone_unique_id

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.LIGHT, Platform.NUMBER]

# Home Assistant calls async_setup (and so starts the discovery listener) only
# when a config entry or a YAML key for this domain exists. Accepting an empty
# "dmx_diodeled:" key lets users start discovery before the first controller
# is added.
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

_MAC_HEX_DIGITS = frozenset("0123456789abcdef")


def _canonical_unique_id(unique_id: str | None) -> str | None:
    """Rewrite a version-1 unique ID to the canonical "aa:bb:cc:dd:ee:ff" form.

    Version 1 stored the stripped, lowercased discovery MAC verbatim - bare hex
    (aabbccddeeff) or with whatever separators the firmware broadcast. Version 2
    canonicalizes every accepted spelling (config_flow._mac_canonical_id), so a
    MAC-shaped v1 ID is rewritten; anything else (including non-MAC strings that
    v1 stored before format validation existed) is returned unchanged.
    """
    if not unique_id:
        return unique_id
    digits = unique_id.replace(":", "").replace("-", "")
    if len(digits) == 12 and set(digits).issubset(_MAC_HEX_DIGITS):
        return ":".join(digits[i : i + 2] for i in range(0, 12, 2))
    return unique_id


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate a version 1 entry to the canonical unique ID (version 2).

    Without the rewrite, a rebroadcast from an already-configured controller
    canonicalizes to "aa:bb:cc:dd:ee:ff" and no longer matches the verbatim v1
    unique ID (bare hex or "-"-separated): discovery would offer a duplicate
    entry and the flow's updates={CONF_HOST} path would stop firing. Non-MAC
    unique IDs are kept; the version is always bumped so this runs once.
    """
    if entry.version != 1:
        return True

    unique_id = _canonical_unique_id(entry.unique_id)
    if unique_id is not None and unique_id != entry.unique_id:
        already_used = any(
            other.entry_id != entry.entry_id and other.unique_id == unique_id
            for other in hass.config_entries.async_entries(DOMAIN)
        )
        if already_used:
            # Two v1 entries for the same MAC in different spellings (possible
            # pre-canonicalization). Core would log an error if we shared the
            # canonical ID, so keep this entry's old ID (its device still dedupes
            # by host) and only bump the version.
            _LOGGER.warning(
                "Keeping unique ID %r of entry %s; another entry already uses the"
                " canonical form %r. The device still dedupes by host.",
                entry.unique_id,
                entry.entry_id,
                unique_id,
            )
            hass.config_entries.async_update_entry(entry, version=2)
        else:
            hass.config_entries.async_update_entry(
                entry, unique_id=unique_id, version=2
            )
    else:
        hass.config_entries.async_update_entry(entry, version=2)

    return True


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

    _async_remove_spoofed_mac_connections(hass, entry)
    _async_remove_disabled_zone_entities(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # This listener is the single place entry changes are reloaded (options such
    # as zones, or data such as host/port), so flows must update the entry without
    # scheduling a reload of their own (async_update_and_abort, never
    # async_update_reload_and_abort).
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options or data change.

    This listener is the only place a reload is scheduled, so every kind of
    entry update (a zone change in the options flow, a host/port reconfigure,
    or a discovery-driven host update) reloads exactly once.
    """
    await hass.config_entries.async_reload(entry.entry_id)


def _async_remove_spoofed_mac_connections(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove attacker-chosen strings stored as the device's network-MAC connection.

    Legacy (pre-#160) entries stored whatever string a LAN attacker broadcast as
    the entry's unique ID, and device_info() exposed it to the registry as a
    CONNECTION_NETWORK_MAC connection before format validation existed. Hiding
    such values in device_info() only stops *new* registrations: async_get_or_create
    merges connections and never removes them, so the connection already stored on
    a legacy install would stay in the registry indefinitely and keep affecting
    identity matching. Purge it at setup so a pre-fix install self-heals on the
    first setup/reload.
    """
    # Only legacy entries with a non-MAC unique ID can carry such a connection.
    if not entry.unique_id or _mac_is_well_formed(entry.unique_id.lower()):
        return
    registry = dr.async_get(hass)
    device = registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    if device is None:
        return
    bad_connections = {
        connection
        for connection in device.connections
        if connection[0] == CONNECTION_NETWORK_MAC
        and not _mac_is_well_formed(connection[1].lower())
    }
    if bad_connections:
        registry.async_update_device(
            device.id, new_connections=device.connections - bad_connections
        )


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
