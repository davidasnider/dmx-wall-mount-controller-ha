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
sys.modules["homeassistant.components.light"] = unittest.mock.MagicMock()
sys.modules["homeassistant.helpers"] = unittest.mock.MagicMock()
sys.modules["homeassistant.helpers.entity_platform"] = unittest.mock.MagicMock()

# Inject relative path for custom_components
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from custom_components.dmx_diodeled.dmx_controller import DiodLEDController  # noqa: E402
from custom_components.dmx_diodeled.const import (  # noqa: E402
    CMD_TYPE_POWER,
    VAL_POWER_ON,
    VAL_POWER_OFF,
)


@pytest.fixture
def controller():
    return DiodLEDController("127.0.0.1", 8899)


def test_power_on_framing(controller):
    packet_on = controller._build_packet(CMD_TYPE_POWER, VAL_POWER_ON)
    assert packet_on.hex() == "55997ebd01ff0212abbfaaaa"  # pragma: allowlist secret


def test_power_off_framing(controller):
    packet_off = controller._build_packet(CMD_TYPE_POWER, VAL_POWER_OFF)
    assert packet_off.hex() == "55997ebd01ff0212a9bdaaaa"  # pragma: allowlist secret


def test_checksum_calculation(controller):
    # CMD_TYPE_RED: [0x08, 0x48], Val: 0xFF
    # Sum: 0x08 + 0x48 + 0xFF = 0x14F. 0x14F % 256 = 0x4F
    packet_red = controller._build_packet([0x08, 0x48], 0xFF)
    assert packet_red[9] == 0x4F
