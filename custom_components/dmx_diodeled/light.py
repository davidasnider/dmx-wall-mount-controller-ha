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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.const import CONF_NAME, STATE_ON

from .const import DOMAIN, DEFAULT_NAME, LOGGER

# Local copy of HA core's light EFFECT_OFF ("off",
# homeassistant/components/light/const.py). Defined here instead of imported
# because HA only exposes it from 2024.2, while hacs.json declares a
# 2024.1.0 minimum; importing it would raise ImportError on HA 2024.1.x and
# make the light entity disappear silently during platform setup.
EFFECT_OFF = "off"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DiodeLED DMX Controller light platform."""
    controller = hass.data[DOMAIN][entry.entry_id]
    name = entry.data.get(CONF_NAME, DEFAULT_NAME)

    async_add_entities([DiodLEDLight(controller, name, entry.entry_id)], True)


class DiodLEDLight(LightEntity, RestoreEntity):
    """Representation of a DiodeLED DMX Light."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    # The controller is write-only: it never reports its state, so the state
    # shown is the last one sent. assumed_state makes the UI offer separate
    # on/off controls so users can resync a light that drifted.
    _attr_assumed_state = True
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_icon = "mdi:led-strip-variant"

    def __init__(self, controller: Any, name: str, entry_id: str) -> None:
        """Initialize the light."""
        self._controller = controller
        self._attr_name = name
        self._attr_unique_id = f"diodeled_dmx_{entry_id}"

        # State tracking (Optimistic)
        self._attr_is_on = False
        self._attr_brightness = 255
        self._attr_rgb_color = (254, 254, 254)
        self._attr_effect = None
        self._attr_effect_list = [EFFECT_OFF, "Rainbow"]

    async def async_added_to_hass(self) -> None:
        """Restore the last known state, since the hardware cannot report it."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is None:
            return

        # Nothing is sent to the hardware here: the controller keeps its own
        # output across a Home Assistant restart.
        self._attr_is_on = last_state.state == STATE_ON
        attributes = last_state.attributes
        # HA only reports brightness/color/effect while the light is on, so
        # these are absent after an "off" state and the defaults are kept.
        if (brightness := attributes.get(ATTR_BRIGHTNESS)) is not None:
            self._attr_brightness = brightness
        if (rgb_color := attributes.get(ATTR_RGB_COLOR)) is not None:
            # Restored attributes come back from JSON as a list.
            self._attr_rgb_color = tuple(rgb_color)
        effect = attributes.get(ATTR_EFFECT)
        if effect in self._attr_effect_list and effect != EFFECT_OFF:
            self._attr_effect = effect

    async def _async_send_commands(self, commands: list) -> None:
        """Send commands, re-raising network failures as HomeAssistantError."""
        try:
            await self._controller.async_send_commands(commands)
        except OSError as err:
            # asyncio.TimeoutError and ConnectionRefusedError are OSError
            # subclasses on the supported Python versions.
            raise HomeAssistantError(
                f"Failed to send command to DMX controller at "
                f"{self._controller.ip}:{self._controller.port}: {err}"
            ) from err

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on.

        Note (intended behavior): an explicit ``turn_on(effect=EFFECT_OFF)``
        ("off") is the one kwarg combination that does not power on a light
        that is already off — it only clears the stored effect state. On a
        light that is on, clearing an active effect does power it off, since
        no "rainbow off" command exists on the hardware.
        """
        # Note: All updates are optimistic. The new state is built in local
        # variables and only applied once the commands were sent, so a failed
        # send does not leave HA showing a state the hardware never reached.

        # Check for Power-only or command updates.
        # Capture the pre-call power state: branches that reason about the
        # hardware (e.g. clearing an effect) need to know whether the light
        # was on before this call.
        was_on = self._attr_is_on
        send_power = not was_on
        is_on = True
        brightness = self._attr_brightness
        rgb_color = self._attr_rgb_color
        effect = self._attr_effect

        LOGGER.debug("Turn On call received for %s", self._attr_name)

        commands = []

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            LOGGER.debug("Setting brightness on %s to %s", self._attr_name, brightness)
            commands.append(self._controller.get_brightness_command(brightness))
            send_power = False

        if ATTR_RGBW_COLOR in kwargs:
            # Conversion logic: Mix W into RGB as the hardware white channel is non-functional
            r, g, b, w = kwargs[ATTR_RGBW_COLOR]
            LOGGER.debug(
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
            rgb_color = (r, g, b)

            LOGGER.debug(
                "Setting RGB on %s to R:%s G:%s B:%s", self._attr_name, r, g, b
            )
            # Send only R, G, B commands: the hardware white channel is
            # non-functional (white is mixed into RGB instead), so a white
            # command would only cost one more connection and throttle delay.
            commands.extend(self._controller.get_rgb_commands(r, g, b))
            send_power = False

        if ATTR_EFFECT in kwargs:
            had_effect = effect not in (None, EFFECT_OFF)
            effect = kwargs[ATTR_EFFECT]
            if effect == "Rainbow":
                LOGGER.debug("Setting Effect on %s to %s", self._attr_name, effect)
                cmd = self._controller.get_rainbow_command(True)
                if cmd:
                    commands.append(cmd)
                send_power = False
            elif effect == EFFECT_OFF:
                # No "rainbow off" command exists (get_rainbow_command(False) -> None);
                # mirror async_set_rainbow(False): stop the effect by powering off.
                if had_effect and was_on:
                    is_on = False
                    commands.append(self._controller.get_power_command(False))
                elif not was_on:
                    # Light is already off (possibly with a stale effect state,
                    # since async_turn_off does not clear _attr_effect): send
                    # nothing and do not power it on. Keep HA's state consistent
                    # with the hardware instead of reporting the light as on.
                    is_on = False
                effect = None
                send_power = False
                LOGGER.debug("Clearing effect on %s", self._attr_name)

        if send_power:
            commands.append(self._controller.get_power_command(True))

        if commands:
            await self._async_send_commands(commands)

        self._attr_is_on = is_on
        self._attr_brightness = brightness
        self._attr_rgb_color = rgb_color
        self._attr_effect = effect
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        LOGGER.debug("Turn Off call received for %s", self._attr_name)
        await self._async_send_commands([self._controller.get_power_command(False)])
        self._attr_is_on = False
        self.async_write_ha_state()

    # Speed control is not a standard attribute for LightEntity
    # We could implement it as a custom service or using effect_list updates.
    # For now, let's just stick to the PRD basics and possibly add speed as a slider later.
