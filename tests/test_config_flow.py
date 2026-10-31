import types
import unittest.mock
from typing import Any

import pytest
from homeassistant.data_entry_flow import AbortFlow

from custom_components.dmx_diodeled import config_flow
from custom_components.dmx_diodeled.config_flow import (
    DiodLEDConfigFlow,
    DiodLEDOptionsFlow,
)
from custom_components.dmx_diodeled.const import DEFAULT_NAME, DEFAULT_PORT


def _entry(data: dict[str, Any], unique_id: str | None = None) -> Any:
    """A configured entry as the flow sees it."""
    return types.SimpleNamespace(data=dict(data), unique_id=unique_id)


@pytest.fixture
def flow() -> DiodLEDConfigFlow:
    return DiodLEDConfigFlow()


@pytest.fixture
def can_connect() -> Any:
    """Make the controller reachable unless a test says otherwise."""
    with unittest.mock.patch.object(
        config_flow, "_async_can_connect", unittest.mock.AsyncMock(return_value=True)
    ) as mock:
        yield mock


@pytest.mark.asyncio
async def test_user_step_shows_form(flow: DiodLEDConfigFlow) -> None:
    result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_user_step_creates_entry(
    flow: DiodLEDConfigFlow, can_connect: Any
) -> None:
    user_input = {"host": "192.168.1.50", "port": 8899, "name": "Kitchen"}

    result = await flow.async_step_user(user_input)

    assert result["type"] == "create_entry"
    assert result["title"] == "Kitchen"
    assert result["data"] == user_input
    can_connect.assert_awaited_once_with("192.168.1.50", 8899)


@pytest.mark.asyncio
async def test_user_step_unreachable_host_shows_error(
    flow: DiodLEDConfigFlow, can_connect: Any
) -> None:
    """An unreachable controller re-shows the form, keeping what was typed."""
    can_connect.return_value = False
    user_input = {"host": "192.168.1.99", "port": 8899, "name": "Kitchen"}

    result = await flow.async_step_user(user_input)

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["data_schema"]["suggested_values"] == user_input


@pytest.mark.asyncio
async def test_user_step_aborts_for_configured_host(flow: DiodLEDConfigFlow) -> None:
    """Adding the same host twice must not create a second entry."""
    flow.current_entries = [_entry({"host": "192.168.1.50", "port": 8899})]

    with pytest.raises(AbortFlow) as err:
        await flow.async_step_user({"host": "192.168.1.50", "port": 8899})

    assert err.value.reason == "already_configured"


@pytest.mark.asyncio
async def test_discovery_offers_new_controller(flow: DiodLEDConfigFlow) -> None:
    result = await flow.async_step_integration_discovery(
        {"host": "192.168.1.50", "mac": " AABBCCDDEEFF "}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"] == {"host": "192.168.1.50"}
    # The MAC is normalized before it is used as the unique ID.
    assert flow.unique_id == "aabbccddeeff"


@pytest.mark.asyncio
async def test_discovery_updates_host_of_known_mac(flow: DiodLEDConfigFlow) -> None:
    """A known MAC at a new address updates that entry's host and aborts."""
    entry = _entry({"host": "192.168.1.50"}, unique_id="aabbccddeeff")
    flow.current_entries = [entry]

    with pytest.raises(AbortFlow) as err:
        await flow.async_step_integration_discovery(
            {"host": "192.168.1.77", "mac": "AABBCCDDEEFF"}
        )

    assert err.value.reason == "already_configured"
    assert entry.data["host"] == "192.168.1.77"


@pytest.mark.asyncio
async def test_discovery_aborts_for_manually_added_host(
    flow: DiodLEDConfigFlow,
) -> None:
    """A manual entry has no unique ID, so it must be matched by host."""
    flow.current_entries = [_entry({"host": "192.168.1.50", "port": 8899})]

    with pytest.raises(AbortFlow) as err:
        await flow.async_step_integration_discovery(
            {"host": "192.168.1.50", "mac": "AABBCCDDEEFF"}
        )

    assert err.value.reason == "already_configured"


@pytest.mark.asyncio
async def test_discovery_confirm_creates_entry(flow: DiodLEDConfigFlow) -> None:
    await flow.async_step_integration_discovery(
        {"host": "192.168.1.50", "mac": "AABBCCDDEEFF"}
    )

    result = await flow.async_step_discovery_confirm({})

    assert result["type"] == "create_entry"
    assert result["title"] == "DiodeLED DMX (192.168.1.50)"
    assert result["data"] == {
        "host": "192.168.1.50",
        "port": DEFAULT_PORT,
        "name": DEFAULT_NAME,
    }


@pytest.mark.asyncio
async def test_can_connect_reports_unreachable_controller() -> None:
    with unittest.mock.patch.object(
        config_flow.DiodLEDController,
        "async_check_connection",
        unittest.mock.AsyncMock(side_effect=OSError("refused")),
    ):
        assert await config_flow._async_can_connect("192.0.2.1", 8899) is False


@pytest.mark.asyncio
async def test_can_connect_reports_reachable_controller() -> None:
    with unittest.mock.patch.object(
        config_flow.DiodLEDController,
        "async_check_connection",
        unittest.mock.AsyncMock(return_value=None),
    ):
        assert await config_flow._async_can_connect("192.0.2.1", 8899) is True


def _reconfigure_flow(entry: Any, others: list[Any] | None = None) -> DiodLEDConfigFlow:
    flow = DiodLEDConfigFlow()
    flow.context["entry"] = entry
    flow.current_entries = [entry, *(others or [])]
    return flow


@pytest.mark.asyncio
async def test_reconfigure_shows_current_values() -> None:
    entry = _entry({"host": "192.168.1.50", "port": 8899})

    result = await _reconfigure_flow(entry).async_step_reconfigure()

    assert result["step_id"] == "reconfigure"
    assert result["data_schema"]["suggested_values"] == {
        "host": "192.168.1.50",
        "port": 8899,
    }


@pytest.mark.asyncio
async def test_reconfigure_updates_host(can_connect: Any) -> None:
    entry = _entry({"host": "192.168.1.50", "port": 8899, "name": "Kitchen"})

    result = await _reconfigure_flow(entry).async_step_reconfigure(
        {"host": "10.1.1.87", "port": 8899}
    )

    assert result == {"type": "abort", "reason": "reconfigure_successful"}
    assert entry.data == {"host": "10.1.1.87", "port": 8899, "name": "Kitchen"}


@pytest.mark.asyncio
async def test_reconfigure_same_host_is_allowed(can_connect: Any) -> None:
    """Saving the entry's own host unchanged must not abort as a duplicate."""
    entry = _entry({"host": "192.168.1.50", "port": 8899})

    result = await _reconfigure_flow(entry).async_step_reconfigure(
        {"host": "192.168.1.50", "port": 8899}
    )

    assert result["reason"] == "reconfigure_successful"


@pytest.mark.asyncio
async def test_reconfigure_to_another_entrys_host_aborts(can_connect: Any) -> None:
    entry = _entry({"host": "192.168.1.50", "port": 8899})
    other = _entry({"host": "192.168.1.60", "port": 8899})

    with pytest.raises(AbortFlow) as err:
        await _reconfigure_flow(entry, [other]).async_step_reconfigure(
            {"host": "192.168.1.60", "port": 8899}
        )

    assert err.value.reason == "already_configured"
    assert entry.data["host"] == "192.168.1.50"


@pytest.mark.asyncio
async def test_reconfigure_unreachable_host_shows_error(can_connect: Any) -> None:
    can_connect.return_value = False
    entry = _entry({"host": "192.168.1.50", "port": 8899})

    result = await _reconfigure_flow(entry).async_step_reconfigure(
        {"host": "192.168.1.99", "port": 8899}
    )

    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data["host"] == "192.168.1.50"


def _options_flow(options: dict[str, Any]) -> DiodLEDOptionsFlow:
    flow = DiodLEDOptionsFlow()
    flow.config_entry = types.SimpleNamespace(options=options)
    return flow


def test_options_flow_is_registered() -> None:
    assert isinstance(
        DiodLEDConfigFlow.async_get_options_flow(None), DiodLEDOptionsFlow
    )


@pytest.mark.asyncio
async def test_options_default_to_zone_one() -> None:
    result = await _options_flow({}).async_step_init()

    assert result["step_id"] == "init"
    # Defaults are the multi_select string keys.
    schema_dict = config_flow.vol.Schema.call_args[0][0]
    (zones_key,) = schema_dict
    config_flow.vol.Required.assert_called_with("zones", default=["1"])
    assert zones_key is config_flow.vol.Required.return_value


@pytest.mark.asyncio
async def test_options_store_zones_as_sorted_ints() -> None:
    result = await _options_flow({}).async_step_init({"zones": ["3", "1"]})

    assert result == {"type": "create_entry", "data": {"zones": [1, 3]}}


@pytest.mark.asyncio
async def test_options_require_a_zone() -> None:
    result = await _options_flow({"zones": [1]}).async_step_init({"zones": []})

    assert result["errors"] == {"base": "no_zones"}
