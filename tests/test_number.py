import types
import unittest.mock
from typing import Any

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.dmx_diodeled.number import DiodLEDSpeed


@pytest.fixture
def mock_controller() -> Any:
    controller = unittest.mock.AsyncMock()
    controller.ip = "192.0.2.10"
    controller.port = 8899
    controller.get_speed_command = unittest.mock.Mock(
        side_effect=lambda speed, zone=1: ("SPEED", speed, zone)
    )
    return controller


@pytest.fixture
def entry() -> Any:
    return types.SimpleNamespace(
        entry_id="test_entry_id",
        data={"host": "192.0.2.10", "name": "Test Light"},
        options={},
        unique_id=None,
    )


@pytest.fixture
def speed(mock_controller: Any, entry: Any) -> DiodLEDSpeed:
    return DiodLEDSpeed(mock_controller, entry)


def test_speed_range_and_identity(speed: DiodLEDSpeed) -> None:
    assert (speed._attr_native_min_value, speed._attr_native_max_value) == (1, 10)
    assert speed._attr_native_step == 1
    assert speed._attr_assumed_state is True
    assert speed._attr_name == "Rainbow speed"
    assert speed._attr_unique_id == "diodeled_dmx_test_entry_id_speed"
    assert speed._attr_device_info["identifiers"] == {("dmx_diodeled", "test_entry_id")}
    # Unknown until set: the hardware cannot report it.
    assert speed._attr_native_value is None


def test_other_zone_naming(mock_controller: Any, entry: Any) -> None:
    speed = DiodLEDSpeed(mock_controller, entry, zone=3)

    assert speed._attr_name == "Zone 3 rainbow speed"
    assert speed._attr_unique_id == "diodeled_dmx_test_entry_id_zone_3_speed"


@pytest.mark.asyncio
async def test_set_value_sends_speed_to_zone(mock_controller: Any, entry: Any) -> None:
    speed = DiodLEDSpeed(mock_controller, entry, zone=2)

    await speed.async_set_native_value(7.0)

    mock_controller.async_send_commands.assert_awaited_once_with([("SPEED", 7, 2)])
    assert speed._attr_native_value == 7


@pytest.mark.asyncio
async def test_set_value_failure_keeps_previous_value(
    speed: DiodLEDSpeed, mock_controller: Any
) -> None:
    speed._attr_native_value = 3
    mock_controller.async_send_commands.side_effect = OSError("Connection refused")

    with pytest.raises(HomeAssistantError, match="192.0.2.10:8899"):
        await speed.async_set_native_value(9)

    assert speed._attr_native_value == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "expected"),
    [("6.0", 6.0), ("unknown", None), ("unavailable", None), ("42", None)],
)
async def test_restore_last_speed(
    speed: DiodLEDSpeed, state: str, expected: float | None
) -> None:
    speed.async_get_last_state = unittest.mock.AsyncMock(
        return_value=types.SimpleNamespace(state=state)
    )

    await speed.async_added_to_hass()

    assert speed._attr_native_value == expected
