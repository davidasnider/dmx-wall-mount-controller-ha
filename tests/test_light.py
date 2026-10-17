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
    controller.get_rgb_commands = unittest.mock.Mock(
        side_effect=lambda r, g, b: [
            ("RED", r),
            ("GREEN", g),
            ("BLUE", b),
        ]
    )
    controller.get_brightness_command = unittest.mock.Mock(
        side_effect=lambda x: ("BRIGHTNESS", x)
    )
    controller.get_power_command = unittest.mock.Mock(
        side_effect=lambda x: ("POWER", x)
    )
    controller.get_rainbow_command = unittest.mock.Mock(
        side_effect=lambda x: ("RAINBOW", x)
    )
    controller.get_speed_command = unittest.mock.Mock(
        side_effect=lambda x: ("SPEED", x)
    )
    return controller


@pytest.fixture
def light(mock_controller: Any) -> DiodLEDLight:
    """Create a DiodLEDLight instance with a mock controller."""
    return DiodLEDLight(mock_controller, "Test Light", "test_entry_id")


@pytest.mark.asyncio
async def test_rgb_pure_white_capped(light: DiodLEDLight, mock_controller: Any) -> None:
    """Pure white RGB (255,255,255) should be capped to (254, 254, 254)."""
    await light.async_turn_on(rgb_color=(255, 255, 255))

    mock_controller.get_rgb_commands.assert_called_once_with(254, 254, 254)
    assert light._attr_rgb_color == (254, 254, 254)
    expected_cmds = [("RED", 254), ("GREEN", 254), ("BLUE", 254)]
    mock_controller.async_send_commands.assert_awaited_once_with(expected_cmds)


@pytest.mark.asyncio
async def test_rgb_mixed_color_no_extraction(
    light: DiodLEDLight, mock_controller: Any
) -> None:
    """Mixed RGB values should NOT extract a W component."""
    await light.async_turn_on(rgb_color=(200, 100, 50))

    mock_controller.get_rgb_commands.assert_called_once_with(200, 100, 50)
    assert light._attr_rgb_color == (200, 100, 50)
    expected_cmds = [("RED", 200), ("GREEN", 100), ("BLUE", 50)]
    mock_controller.async_send_commands.assert_awaited_once_with(expected_cmds)


@pytest.mark.asyncio
async def test_rgb_pure_red_capped(light: DiodLEDLight, mock_controller: Any) -> None:
    """Pure red (255,0,0) should be capped to (254,0,0)."""
    await light.async_turn_on(rgb_color=(255, 0, 0))

    mock_controller.get_rgb_commands.assert_called_once_with(254, 0, 0)
    assert light._attr_rgb_color == (254, 0, 0)
    expected_cmds = [("RED", 254), ("GREEN", 0), ("BLUE", 0)]
    mock_controller.async_send_commands.assert_awaited_once_with(expected_cmds)


@pytest.mark.asyncio
async def test_rgb_black_maps_to_all_zeros(
    light: DiodLEDLight, mock_controller: Any
) -> None:
    """Black (0,0,0) should map to (0,0,0)."""
    await light.async_turn_on(rgb_color=(0, 0, 0))

    mock_controller.get_rgb_commands.assert_called_once_with(0, 0, 0)
    assert light._attr_rgb_color == (0, 0, 0)
    expected_cmds = [("RED", 0), ("GREEN", 0), ("BLUE", 0)]
    mock_controller.async_send_commands.assert_awaited_once_with(expected_cmds)


@pytest.mark.asyncio
async def test_rgbw_conversion_to_rgb(
    light: DiodLEDLight, mock_controller: Any
) -> None:
    """RGBW (100, 100, 100, 50) should be converted to RGB (150, 150, 150)."""
    await light.async_turn_on(rgbw_color=(100, 100, 100, 50))

    # (100+50, 100+50, 100+50) = (150, 150, 150)
    mock_controller.get_rgb_commands.assert_called_once_with(150, 150, 150)
    assert light._attr_rgb_color == (150, 150, 150)
    expected_cmds = [("RED", 150), ("GREEN", 150), ("BLUE", 150)]
    mock_controller.async_send_commands.assert_awaited_once_with(expected_cmds)


@pytest.mark.asyncio
async def test_turn_off_sends_power_off(
    light: DiodLEDLight, mock_controller: Any
) -> None:
    """Turning off the light should send a power-off command and update state."""
    # Set the light to ON initially to test state change
    light._attr_is_on = True

    await light.async_turn_off()

    mock_controller.get_power_command.assert_called_once_with(False)
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
    mock_controller.get_power_command.assert_called_once_with(False)
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
