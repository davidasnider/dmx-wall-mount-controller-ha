import asyncio
import types
import unittest.mock
import pytest
from typing import Any

from homeassistant.exceptions import HomeAssistantError

from custom_components.dmx_diodeled.light import EFFECT_OFF, DiodLEDLight


@pytest.fixture
def mock_controller() -> Any:
    """Create a mock controller that tracks calls."""
    controller = unittest.mock.AsyncMock()
    controller.ip = "192.0.2.10"
    controller.port = 8899
    # Mock the synchronous command generators since they are called directly
    # Each generator accepts the zone keyword the light passes, like the real one.
    controller.get_rgb_commands = unittest.mock.Mock(
        side_effect=lambda r, g, b, zone=1: [
            ("RED", r),
            ("GREEN", g),
            ("BLUE", b),
        ]
    )
    controller.get_brightness_command = unittest.mock.Mock(
        side_effect=lambda x, zone=1: ("BRIGHTNESS", x)
    )
    controller.get_power_command = unittest.mock.Mock(
        side_effect=lambda x, zone=1: ("POWER", x)
    )
    controller.get_rainbow_command = unittest.mock.Mock(
        side_effect=lambda x, zone=1: ("RAINBOW", x)
    )
    controller.get_speed_command = unittest.mock.Mock(
        side_effect=lambda x, zone=1: ("SPEED", x)
    )
    return controller


@pytest.fixture
def entry() -> Any:
    """A config entry as the light sees it."""
    return types.SimpleNamespace(
        entry_id="test_entry_id",
        data={"host": "192.0.2.10", "name": "Test Light"},
        options={},
        unique_id=None,
    )


@pytest.fixture
def light(mock_controller: Any, entry: Any) -> DiodLEDLight:
    """Create a DiodLEDLight instance with a mock controller."""
    return DiodLEDLight(mock_controller, entry)


@pytest.mark.asyncio
async def test_rgb_pure_white_capped(light: DiodLEDLight, mock_controller: Any) -> None:
    """Pure white RGB (255,255,255) should be capped to (254, 254, 254)."""
    await light.async_turn_on(rgb_color=(255, 255, 255))

    mock_controller.get_rgb_commands.assert_called_once_with(254, 254, 254, zone=1)
    assert light._attr_rgb_color == (254, 254, 254)
    expected_cmds = [("POWER", True), ("RED", 254), ("GREEN", 254), ("BLUE", 254)]
    mock_controller.async_send_commands.assert_awaited_once_with(expected_cmds)


@pytest.mark.asyncio
async def test_rgb_mixed_color_no_extraction(
    light: DiodLEDLight, mock_controller: Any
) -> None:
    """Mixed RGB values should NOT extract a W component."""
    await light.async_turn_on(rgb_color=(200, 100, 50))

    mock_controller.get_rgb_commands.assert_called_once_with(200, 100, 50, zone=1)
    assert light._attr_rgb_color == (200, 100, 50)
    expected_cmds = [("POWER", True), ("RED", 200), ("GREEN", 100), ("BLUE", 50)]
    mock_controller.async_send_commands.assert_awaited_once_with(expected_cmds)


@pytest.mark.asyncio
async def test_rgb_pure_red_capped(light: DiodLEDLight, mock_controller: Any) -> None:
    """Pure red (255,0,0) should be capped to (254,0,0)."""
    await light.async_turn_on(rgb_color=(255, 0, 0))

    mock_controller.get_rgb_commands.assert_called_once_with(254, 0, 0, zone=1)
    assert light._attr_rgb_color == (254, 0, 0)
    expected_cmds = [("POWER", True), ("RED", 254), ("GREEN", 0), ("BLUE", 0)]
    mock_controller.async_send_commands.assert_awaited_once_with(expected_cmds)


@pytest.mark.asyncio
async def test_rgb_black_maps_to_all_zeros(
    light: DiodLEDLight, mock_controller: Any
) -> None:
    """Black (0,0,0) should map to (0,0,0)."""
    await light.async_turn_on(rgb_color=(0, 0, 0))

    mock_controller.get_rgb_commands.assert_called_once_with(0, 0, 0, zone=1)
    assert light._attr_rgb_color == (0, 0, 0)
    expected_cmds = [("POWER", True), ("RED", 0), ("GREEN", 0), ("BLUE", 0)]
    mock_controller.async_send_commands.assert_awaited_once_with(expected_cmds)


@pytest.mark.asyncio
async def test_rgbw_conversion_to_rgb(
    light: DiodLEDLight, mock_controller: Any
) -> None:
    """RGBW (100, 100, 100, 50) should be converted to RGB (150, 150, 150)."""
    await light.async_turn_on(rgbw_color=(100, 100, 100, 50))

    # (100+50, 100+50, 100+50) = (150, 150, 150)
    mock_controller.get_rgb_commands.assert_called_once_with(150, 150, 150, zone=1)
    assert light._attr_rgb_color == (150, 150, 150)
    expected_cmds = [("POWER", True), ("RED", 150), ("GREEN", 150), ("BLUE", 150)]
    mock_controller.async_send_commands.assert_awaited_once_with(expected_cmds)


@pytest.mark.asyncio
async def test_turn_off_sends_power_off(
    light: DiodLEDLight, mock_controller: Any
) -> None:
    """Turning off the light should send a power-off command and update state."""
    # Set the light to ON initially to test state change
    light._attr_is_on = True

    await light.async_turn_off()

    mock_controller.get_power_command.assert_called_once_with(False, zone=1)
    mock_controller.async_send_commands.assert_awaited_once_with([("POWER", False)])
    assert light._attr_is_on is False


def test_light_icon_and_effect_list(light: DiodLEDLight) -> None:
    """Test entity icon and effect_list initialization."""
    assert light._attr_icon == "mdi:led-strip-variant"
    assert light._attr_effect_list == [EFFECT_OFF, "Rainbow"]


def test_light_state_is_assumed(light: DiodLEDLight) -> None:
    """The write-only controller cannot report state, so it is assumed."""
    assert light._attr_assumed_state is True


@pytest.mark.asyncio
async def test_effect_clear_with_effect_off(
    light: DiodLEDLight, mock_controller: Any
) -> None:
    """Selecting EFFECT_OFF ('off') should clear the active effect on hardware."""
    light._attr_effect = "Rainbow"
    light._attr_is_on = True

    await light.async_turn_on(effect=EFFECT_OFF)

    assert light._attr_effect is None
    mock_controller.get_power_command.assert_called_once_with(False, zone=1)
    mock_controller.async_send_commands.assert_awaited_once_with([("POWER", False)])


@pytest.mark.asyncio
async def test_effect_off_on_already_off_light_sends_nothing(
    light: DiodLEDLight, mock_controller: Any
) -> None:
    """Selecting EFFECT_OFF while the light is off must be a hardware no-op."""
    light._attr_effect = "Rainbow"  # stale state; async_turn_off does not clear it
    light._attr_is_on = False

    await light.async_turn_on(effect=EFFECT_OFF)

    assert light._attr_effect is None
    assert light._attr_is_on is False
    mock_controller.get_power_command.assert_not_called()
    mock_controller.async_send_commands.assert_not_awaited()


@pytest.mark.asyncio
async def test_effect_off_with_no_active_effect_keeps_light_on(
    light: DiodLEDLight, mock_controller: Any
) -> None:
    """Selecting EFFECT_OFF while on (solid color, no active effect) must stay a hardware no-op and keep the light on."""
    light._attr_effect = None
    light._attr_is_on = True

    await light.async_turn_on(effect=EFFECT_OFF)

    assert light._attr_effect is None
    assert light._attr_is_on is True
    mock_controller.get_power_command.assert_not_called()
    mock_controller.async_send_commands.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [OSError("Connection refused"), asyncio.TimeoutError()]
)
async def test_turn_on_send_failure_keeps_previous_state(
    light: DiodLEDLight, mock_controller: Any, error: Exception
) -> None:
    """A failed send raises HomeAssistantError and leaves the state unchanged."""
    mock_controller.async_send_commands.side_effect = error

    with pytest.raises(HomeAssistantError, match="192.0.2.10:8899"):
        await light.async_turn_on(brightness=100, rgb_color=(1, 2, 3), effect="Rainbow")

    assert light._attr_is_on is False
    assert light._attr_brightness == 255
    assert light._attr_rgb_color == (254, 254, 254)
    assert light._attr_effect is None


@pytest.mark.asyncio
async def test_turn_off_send_failure_keeps_light_on(
    light: DiodLEDLight, mock_controller: Any
) -> None:
    """A failed power-off raises HomeAssistantError and keeps the light on."""
    light._attr_is_on = True
    mock_controller.async_send_commands.side_effect = OSError("Connection refused")

    with pytest.raises(HomeAssistantError):
        await light.async_turn_off()

    assert light._attr_is_on is True


@pytest.mark.asyncio
async def test_restore_last_on_state(light: DiodLEDLight, mock_controller: Any) -> None:
    """After a restart the last on state, brightness, color and effect return."""
    light.async_get_last_state = unittest.mock.AsyncMock(
        return_value=types.SimpleNamespace(
            state="on",
            # Restored attributes come back from JSON, so colors are lists.
            attributes={
                "brightness": 128,
                "rgb_color": [10, 20, 30],
                "effect": "Rainbow",
            },
        )
    )

    await light.async_added_to_hass()

    assert light._attr_is_on is True
    assert light._attr_brightness == 128
    assert light._attr_rgb_color == (10, 20, 30)
    assert light._attr_effect == "Rainbow"
    # Restoring state must not send anything to the hardware.
    mock_controller.async_send_commands.assert_not_awaited()


@pytest.mark.asyncio
async def test_restore_last_off_state_keeps_defaults(light: DiodLEDLight) -> None:
    """An off state has no color attributes, so the defaults are kept."""
    light._attr_is_on = True
    light.async_get_last_state = unittest.mock.AsyncMock(
        return_value=types.SimpleNamespace(
            state="off",
            attributes={"brightness": None, "rgb_color": None, "effect": None},
        )
    )

    await light.async_added_to_hass()

    assert light._attr_is_on is False
    assert light._attr_brightness == 255
    assert light._attr_rgb_color == (254, 254, 254)
    assert light._attr_effect is None


@pytest.mark.asyncio
async def test_restore_ignores_unknown_effect(light: DiodLEDLight) -> None:
    """An effect that is not in the effect list is not restored."""
    light.async_get_last_state = unittest.mock.AsyncMock(
        return_value=types.SimpleNamespace(state="on", attributes={"effect": "Strobe"})
    )

    await light.async_added_to_hass()

    assert light._attr_is_on is True
    assert light._attr_effect is None


@pytest.mark.asyncio
async def test_no_previous_state_keeps_defaults(light: DiodLEDLight) -> None:
    """Without a previous state the light starts off with default values."""
    await light.async_added_to_hass()

    assert light._attr_is_on is False
    assert light._attr_brightness == 255
    assert light._attr_rgb_color == (254, 254, 254)


@pytest.mark.asyncio
async def test_turn_on_sends_power_even_when_believed_on(
    light: DiodLEDLight, mock_controller: Any
) -> None:
    """Regression: HA's state can be stale (restored "on" while the lights are
    off), so a plain turn_on must always send power-on."""
    light._attr_is_on = True

    await light.async_turn_on()

    mock_controller.async_send_commands.assert_awaited_once_with([("POWER", True)])
    assert light._attr_is_on is True


@pytest.mark.asyncio
async def test_turn_on_after_restored_on_state_sends_power(
    light: DiodLEDLight, mock_controller: Any
) -> None:
    """Regression: after a restart restores "on", pressing ON must reach the hardware."""
    light.async_get_last_state = unittest.mock.AsyncMock(
        return_value=types.SimpleNamespace(state="on", attributes={})
    )
    await light.async_added_to_hass()

    await light.async_turn_on()

    mock_controller.async_send_commands.assert_awaited_once_with([("POWER", True)])


@pytest.mark.asyncio
async def test_power_is_sent_before_color_and_brightness(
    light: DiodLEDLight, mock_controller: Any
) -> None:
    """The hardware drops color/brightness commands while off, so power goes first."""
    await light.async_turn_on(brightness=255, rgb_color=(10, 20, 30))

    mock_controller.async_send_commands.assert_awaited_once_with(
        [("POWER", True), ("BRIGHTNESS", 255), ("RED", 10), ("GREEN", 20), ("BLUE", 30)]
    )


@pytest.mark.asyncio
async def test_power_is_sent_before_rainbow_effect(
    light: DiodLEDLight, mock_controller: Any
) -> None:
    await light.async_turn_on(effect="Rainbow")

    mock_controller.async_send_commands.assert_awaited_once_with(
        [("POWER", True), ("RAINBOW", True)]
    )
    assert light._attr_effect == "Rainbow"


def test_zone_one_light_uses_device_name_and_legacy_unique_id(
    light: DiodLEDLight,
) -> None:
    """Zone 1 keeps the pre-zone unique ID so existing entities are preserved."""
    assert light._attr_name is None
    assert light._attr_unique_id == "diodeled_dmx_test_entry_id"


@pytest.mark.asyncio
async def test_other_zone_light_targets_its_zone(
    mock_controller: Any, entry: Any
) -> None:
    light = DiodLEDLight(mock_controller, entry, zone=2)

    assert light._attr_name == "Zone 2"
    assert light._attr_unique_id == "diodeled_dmx_test_entry_id_zone_2"

    await light.async_turn_on(rgb_color=(1, 2, 3))
    await light.async_turn_off()

    mock_controller.get_power_command.assert_any_call(True, zone=2)
    mock_controller.get_power_command.assert_any_call(False, zone=2)
    mock_controller.get_rgb_commands.assert_called_once_with(1, 2, 3, zone=2)


def test_device_info_for_manual_entry(light: DiodLEDLight) -> None:
    info = light._attr_device_info

    assert info["identifiers"] == {("dmx_diodeled", "test_entry_id")}
    assert info["manufacturer"] == "DiodeLED"
    assert info["model"] == "DI-DMX-WIFI-WMUS-3Z-WH"
    assert info["name"] == "Test Light"
    assert info["configuration_url"] == "http://192.0.2.10"
    # Manual entries have no MAC.
    assert "connections" not in info


def test_device_info_for_discovered_entry_has_mac(
    mock_controller: Any, entry: Any
) -> None:
    entry.unique_id = "aabbccddeeff"

    info = DiodLEDLight(mock_controller, entry)._attr_device_info

    assert info["connections"] == {("mac", "aa:bb:cc:dd:ee:ff")}


@pytest.mark.asyncio
async def test_setup_entry_creates_one_light_per_enabled_zone(
    mock_controller: Any, entry: Any
) -> None:
    from custom_components.dmx_diodeled import light as light_platform

    entry.options = {"zones": [1, 3]}
    hass = types.SimpleNamespace(
        data={"dmx_diodeled": {"test_entry_id": mock_controller}}
    )
    add_entities = unittest.mock.Mock()

    await light_platform.async_setup_entry(hass, entry, add_entities)

    lights = add_entities.call_args[0][0]
    assert [entity._zone for entity in lights] == [1, 3]
