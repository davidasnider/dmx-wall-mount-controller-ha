import sys
import os
import unittest.mock
import pytest
from typing import Any

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
def controller() -> DiodLEDController:
    return DiodLEDController("127.0.0.1", 8899)


def test_power_on_framing(controller: DiodLEDController) -> None:
    packet_on = controller._build_packet(CMD_TYPE_POWER, VAL_POWER_ON)
    assert packet_on.hex() == "55997ebd01ff0212abbfaaaa"  # pragma: allowlist secret


def test_power_off_framing(controller: DiodLEDController) -> None:
    packet_off = controller._build_packet(CMD_TYPE_POWER, VAL_POWER_OFF)
    assert packet_off.hex() == "55997ebd01ff0212a9bdaaaa"  # pragma: allowlist secret


def test_zone_framing_broadcast(controller: DiodLEDController) -> None:
    """Test packet framing for broadcast candidate bytes 0x00 and 0x04."""
    packet_bcast_00 = controller._build_packet(CMD_TYPE_POWER, VAL_POWER_ON, zone=0x00)
    assert packet_bcast_00[4] == 0x00
    assert (
        packet_bcast_00.hex() == "55997ebd00ff0212abbfaaaa"
    )  # pragma: allowlist secret

    packet_bcast_04 = controller._build_packet(CMD_TYPE_POWER, VAL_POWER_ON, zone=0x04)
    assert packet_bcast_04[4] == 0x04
    assert (
        packet_bcast_04.hex() == "55997ebd04ff0212abbfaaaa"
    )  # pragma: allowlist secret


def test_zone_framing_zones(controller: DiodLEDController) -> None:
    """Test packet framing for specific zones 0x01, 0x02, and 0x03."""
    packet_z1 = controller._build_packet(CMD_TYPE_POWER, VAL_POWER_ON, zone=0x01)
    assert packet_z1[4] == 0x01
    assert packet_z1.hex() == "55997ebd01ff0212abbfaaaa"  # pragma: allowlist secret

    packet_z2 = controller._build_packet(CMD_TYPE_POWER, VAL_POWER_ON, zone=0x02)
    assert packet_z2[4] == 0x02
    assert packet_z2.hex() == "55997ebd02ff0212abbfaaaa"  # pragma: allowlist secret

    packet_z3 = controller._build_packet(CMD_TYPE_POWER, VAL_POWER_ON, zone=0x03)
    assert packet_z3[4] == 0x03
    assert packet_z3.hex() == "55997ebd03ff0212abbfaaaa"  # pragma: allowlist secret


def test_checksum_calculation(controller: DiodLEDController) -> None:
    # CMD_TYPE_RED: [0x08, 0x48], Val: 0xFF
    # Value is capped at 0xFE (254).
    # Sum: 0x08 + 0x48 + 0xFE = 0x14E. 0x14E % 256 = 0x4E
    packet_red = controller._build_packet([0x08, 0x48], 0xFF)
    assert packet_red[9] == 0x4E


@pytest.mark.asyncio
@unittest.mock.patch("asyncio.open_connection")
@unittest.mock.patch("asyncio.sleep")
async def test_async_send_commands_chunking(
    mock_sleep: Any, mock_open_connection: Any, controller: DiodLEDController
) -> None:
    """Test that commands are chunked correctly at CMD_CHUNK_SIZE boundaries."""
    # Create 20 mock commands. With the current chunk size of 1,
    # we should see 20 connection opens and 20 writes.

    commands = [([0x08, 0x00], i) for i in range(20)]

    mock_reader = unittest.mock.AsyncMock()
    mock_writer = unittest.mock.AsyncMock()
    mock_writer.write = unittest.mock.Mock()
    mock_writer.close = unittest.mock.Mock()
    mock_open_connection.return_value = (mock_reader, mock_writer)

    await controller.async_send_commands(commands)

    # Assert connection was opened for each command (since chunk size is 1)
    assert mock_open_connection.call_count == 20
    assert mock_writer.write.call_count == 20

    # In each write, payload should have exactly 1 command (12 bytes)
    for i in range(20):
        write_arg = mock_writer.write.call_args_list[i][0][0]
        assert len(write_arg) == 12
