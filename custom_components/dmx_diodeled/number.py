"""Support for the DiodeLED DMX Controller rainbow speed."""

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, LOGGER, SPEED_MAX, SPEED_MIN
from .entity import configured_zones, device_info, zone_unique_id


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DiodeLED DMX Controller rainbow speed numbers."""
    controller = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [DiodLEDSpeed(controller, entry, zone) for zone in configured_zones(entry)]
    )


class DiodLEDSpeed(NumberEntity, RestoreEntity):
    """Playback speed of the built-in Rainbow effect (1 = slowest, 10 = fastest)."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    # Write-only hardware: the value shown is the last one sent.
    _attr_assumed_state = True
    _attr_icon = "mdi:speedometer"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = SPEED_MIN
    _attr_native_max_value = SPEED_MAX
    _attr_native_step = 1

    def __init__(self, controller: Any, entry: ConfigEntry, zone: int = 1) -> None:
        """Initialize the speed number."""
        self._controller = controller
        self._zone = zone
        self._attr_name = "Rainbow speed" if zone == 1 else f"Zone {zone} rainbow speed"
        self._attr_unique_id = zone_unique_id(entry.entry_id, zone, "speed")
        self._attr_device_info = device_info(entry)
        # Unknown until set: the controller cannot report its current speed.
        self._attr_native_value = None

    async def async_added_to_hass(self) -> None:
        """Restore the last speed sent, since the hardware cannot report it."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is None:
            return
        try:
            value = float(last_state.state)
        except ValueError:
            # "unknown" / "unavailable"
            return
        if SPEED_MIN <= value <= SPEED_MAX:
            self._attr_native_value = value

    async def async_set_native_value(self, value: float) -> None:
        """Send the new speed to the controller."""
        speed = int(round(value))
        LOGGER.debug("Setting rainbow speed on zone %s to %s", self._zone, speed)
        try:
            await self._controller.async_send_commands(
                [self._controller.get_speed_command(speed, zone=self._zone)]
            )
        except OSError as err:
            raise HomeAssistantError(
                f"Failed to send command to DMX controller at "
                f"{self._controller.ip}:{self._controller.port}: {err}"
            ) from err
        self._attr_native_value = speed
        self.async_write_ha_state()
