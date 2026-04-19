import sys
import os
import unittest.mock
import pytest

# Mock Home Assistant modules so tests can run without the full core platform installed
sys.modules["homeassistant"] = unittest.mock.MagicMock()
sys.modules["homeassistant.config_entries"] = unittest.mock.MagicMock()
sys.modules["homeassistant.const"] = unittest.mock.MagicMock()
sys.modules["homeassistant.core"] = unittest.mock.MagicMock()
sys.modules["homeassistant.components"] = unittest.mock.MagicMock()
sys.modules["homeassistant.helpers"] = unittest.mock.MagicMock()
sys.modules["homeassistant.helpers.entity_platform"] = unittest.mock.MagicMock()

# Build a minimal LightEntity stub that won't trip on MagicMock iteration
_light_mod = unittest.mock.MagicMock()
_light_mod.ATTR_BRIGHTNESS = "brightness"
_light_mod.ATTR_RGBW_COLOR = "rgbw_color"
_light_mod.ATTR_RGB_COLOR = "rgb_color"
_light_mod.ATTR_EFFECT = "effect"
_light_mod.ColorMode = unittest.mock.MagicMock()
_light_mod.ColorMode.RGB = "rgb"
_light_mod.LightEntityFeature = unittest.mock.MagicMock()
_light_mod.LightEntityFeature.EFFECT = 4


class _StubLightEntity:
    """Minimal stand-in for homeassistant.components.light.LightEntity."""

    def async_write_ha_state(self):
        pass


_light_mod.LightEntity = _StubLightEntity
sys.modules["homeassistant.components.light"] = _light_mod

# Inject relative path for custom_components
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.dmx_diodeled.light import DiodLEDLight  # noqa: E402


@pytest.fixture
def mock_controller():
    """Create a mock controller that tracks calls."""
    controller = unittest.mock.AsyncMock()
    # Mock the synchronous command generators since they are called directly
    controller.get_rgbw_commands = unittest.mock.Mock(
        side_effect=lambda r, g, b, w: [
            ("RED", r),
            ("GREEN", g),
            ("BLUE", b),
            ("WHITE", w),
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
def light(mock_controller):
    """Create a DiodLEDLight instance with a mock controller."""
    return DiodLEDLight(mock_controller, "Test Light", "test_entry_id")


@pytest.mark.asyncio
async def test_rgb_pure_white_capped(light, mock_controller):
    """Pure white RGB (255,255,255) should be capped to (254, 254, 254)."""
    await light.async_turn_on(rgb_color=(255, 255, 255))

    mock_controller.get_rgbw_commands.assert_called_once_with(254, 254, 254, 0)
    assert light._attr_rgb_color == (254, 254, 254)
    expected_cmds = [("RED", 254), ("GREEN", 254), ("BLUE", 254), ("WHITE", 0)]
    mock_controller.async_send_commands.assert_awaited_once_with(expected_cmds)


@pytest.mark.asyncio
async def test_rgb_mixed_color_no_extraction(light, mock_controller):
    """Mixed RGB values should NOT extract a W component."""
    await light.async_turn_on(rgb_color=(200, 100, 50))

    mock_controller.get_rgbw_commands.assert_called_once_with(200, 100, 50, 0)
    assert light._attr_rgb_color == (200, 100, 50)
    expected_cmds = [("RED", 200), ("GREEN", 100), ("BLUE", 50), ("WHITE", 0)]
    mock_controller.async_send_commands.assert_awaited_once_with(expected_cmds)


@pytest.mark.asyncio
async def test_rgb_pure_red_capped(light, mock_controller):
    """Pure red (255,0,0) should be capped to (254,0,0)."""
    await light.async_turn_on(rgb_color=(255, 0, 0))

    mock_controller.get_rgbw_commands.assert_called_once_with(254, 0, 0, 0)
    assert light._attr_rgb_color == (254, 0, 0)
    expected_cmds = [("RED", 254), ("GREEN", 0), ("BLUE", 0), ("WHITE", 0)]
    mock_controller.async_send_commands.assert_awaited_once_with(expected_cmds)


@pytest.mark.asyncio
async def test_rgb_black_maps_to_all_zeros(light, mock_controller):
    """Black (0,0,0) should map to (0,0,0)."""
    await light.async_turn_on(rgb_color=(0, 0, 0))

    mock_controller.get_rgbw_commands.assert_called_once_with(0, 0, 0, 0)
    assert light._attr_rgb_color == (0, 0, 0)
    expected_cmds = [("RED", 0), ("GREEN", 0), ("BLUE", 0), ("WHITE", 0)]
    mock_controller.async_send_commands.assert_awaited_once_with(expected_cmds)


@pytest.mark.asyncio
async def test_rgbw_conversion_to_rgb(light, mock_controller):
    """RGBW (100, 100, 100, 50) should be converted to RGB (150, 150, 150)."""
    await light.async_turn_on(rgbw_color=(100, 100, 100, 50))

    # (100+50, 100+50, 100+50) = (150, 150, 150)
    mock_controller.get_rgbw_commands.assert_called_once_with(150, 150, 150, 0)
    assert light._attr_rgb_color == (150, 150, 150)
    expected_cmds = [("RED", 150), ("GREEN", 150), ("BLUE", 150), ("WHITE", 0)]
    mock_controller.async_send_commands.assert_awaited_once_with(expected_cmds)
