"""Support for DiodeLED DMX Controller Lights."""

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import CONF_NAME

from .const import DOMAIN, DEFAULT_NAME, LOGGER


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DiodeLED DMX Controller light platform."""
    controller = hass.data[DOMAIN][entry.entry_id]
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)

    async_add_entities([DiodLEDLight(controller, name, entry.entry_id)], True)


class DiodLEDLight(LightEntity):
    """Representation of a DiodeLED DMX Light."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(self, controller, name, entry_id):
        """Initialize the light."""
        self._controller = controller
        self._attr_name = name
        self._attr_unique_id = f"diodeled_dmx_{entry_id}"

        # State tracking (Optimistic)
        self._attr_is_on = False
        self._attr_brightness = 255
        self._attr_rgb_color = (254, 254, 254)
        self._attr_effect = None
        self._attr_effect_list = ["Rainbow"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        # Note: All updates are optimistic.

        # Check for Power-only or command updates
        send_power = not self._attr_is_on
        self._attr_is_on = True

        LOGGER.debug("Turn On call received for %s", self._attr_name)

        commands = []

        if ATTR_BRIGHTNESS in kwargs:
            self._attr_brightness = kwargs[ATTR_BRIGHTNESS]
            LOGGER.debug(
                "Setting brightness on %s to %s", self._attr_name, self._attr_brightness
            )
            commands.append(
                self._controller.get_brightness_command(self._attr_brightness)
            )
            send_power = False

        if ATTR_RGBW_COLOR in kwargs:
            # Conversion logic: Mix W into RGB as the hardware white channel is non-functional
            r, g, b, w = kwargs[ATTR_RGBW_COLOR]
            LOGGER.warning(
                "RGBW color was requested for %s, but the hardware dedicated white channel "
                "is non-functional. Converting to RGB by mixing white channel into RGB.",
                self._attr_name,
            )
            kwargs[ATTR_RGB_COLOR] = (
                min(255, r + w),
                min(255, g + w),
                min(255, b + w),
            )

        if ATTR_RGB_COLOR in kwargs:
            # Clamp values to 254 as hardware forbids 255.
            # Storing clamped values so HA state reflects reality.
            r, g, b = kwargs[ATTR_RGB_COLOR]
            r, g, b = (min(r, 254), min(g, 254), min(b, 254))
            self._attr_rgb_color = (r, g, b)

            LOGGER.debug(
                "Setting RGB on %s to R:%s G:%s B:%s", self._attr_name, r, g, b
            )
            # Send R, G, B commands. White is set to 0 as we use RGB mixing for white.
            commands.extend(self._controller.get_rgbw_commands(r, g, b, 0))
            send_power = False

        if ATTR_EFFECT in kwargs:
            self._attr_effect = kwargs[ATTR_EFFECT]
            if self._attr_effect == "Rainbow":
                LOGGER.debug(
                    "Setting Effect on %s to %s", self._attr_name, self._attr_effect
                )
                cmd = self._controller.get_rainbow_command(True)
                if cmd:
                    commands.append(cmd)
                send_power = False

        if send_power:
            commands.append(self._controller.get_power_command(True))

        if commands:
            await self._controller.async_send_commands(commands)

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        LOGGER.debug("Turn Off call received for %s", self._attr_name)
        await self._controller.async_set_power(False)
        self._attr_is_on = False
        self.async_write_ha_state()

    # Speed control is not a standard attribute for LightEntity
    # We could implement it as a custom service or using effect_list updates.
    # For now, let's just stick to the PRD basics and possibly add speed as a slider later.
