"""Shared helpers for DiodeLED DMX Controller entities."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)

from .config_flow import _mac_is_well_formed
from .const import CONF_ZONES, DEFAULT_NAME, DEFAULT_ZONES, DOMAIN, MANUFACTURER, MODEL


def configured_zones(entry: ConfigEntry) -> list[int]:
    """Return the zones enabled for an entry, in ascending order."""
    return sorted(int(zone) for zone in entry.options.get(CONF_ZONES, DEFAULT_ZONES))


def zone_unique_id(entry_id: str, zone: int, suffix: str = "") -> str:
    """Build an entity unique ID.

    Zone 1 keeps the pre-zone ID (``diodeled_dmx_<entry_id>``) so existing
    installs keep their entity ID, history and customizations.
    """
    base = f"diodeled_dmx_{entry_id}"
    if zone != 1:
        base = f"{base}_zone_{zone}"
    return f"{base}_{suffix}" if suffix else base


def device_info(entry: ConfigEntry) -> DeviceInfo:
    """Describe the controller so all of an entry's entities share one device."""
    info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=MANUFACTURER,
        model=MODEL,
        name=entry.data.get(CONF_NAME, DEFAULT_NAME),
        # The HF-LPB100 Wi-Fi module serves its settings page on port 80.
        configuration_url=f"http://{entry.data[CONF_HOST]}",
    )
    # Discovered entries use the controller's MAC as their unique ID; manual
    # entries have none.
    # SECURITY: Legacy (pre-v2) entries stored the discovery MAC verbatim, so a
    # LAN attacker could have made an arbitrary string the entry's unique ID,
    # and migration keeps such IDs. Only a well-formed 48-bit MAC may be
    # exposed to the registry as a network-MAC connection; anything else keeps
    # its unique ID (for dedupe) but presents no MAC, like a manual entry.
    if entry.unique_id and _mac_is_well_formed(entry.unique_id.lower()):
        info["connections"] = {(CONNECTION_NETWORK_MAC, format_mac(entry.unique_id))}
    return info
