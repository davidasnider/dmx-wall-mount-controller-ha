import types
from typing import Any

import pytest
from homeassistant.data_entry_flow import AbortFlow

from custom_components.dmx_diodeled.config_flow import DiodLEDConfigFlow
from custom_components.dmx_diodeled.const import DEFAULT_NAME, DEFAULT_PORT


def _entry(data: dict[str, Any], unique_id: str | None = None) -> Any:
    """A configured entry as the flow sees it."""
    return types.SimpleNamespace(data=dict(data), unique_id=unique_id)


@pytest.fixture
def flow() -> DiodLEDConfigFlow:
    return DiodLEDConfigFlow()


@pytest.mark.asyncio
async def test_user_step_shows_form(flow: DiodLEDConfigFlow) -> None:
    result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_user_step_creates_entry(flow: DiodLEDConfigFlow) -> None:
    user_input = {"host": "192.168.1.50", "port": 8899, "name": "Kitchen"}

    result = await flow.async_step_user(user_input)

    assert result["type"] == "create_entry"
    assert result["title"] == "Kitchen"
    assert result["data"] == user_input


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
