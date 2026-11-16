import asyncio
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
async def test_user_step_trims_whitespace(
    flow: DiodLEDConfigFlow, can_connect: Any
) -> None:
    """Whitespace around host and name should be stripped."""
    user_input = {"host": "  192.168.1.50  ", "port": 8899, "name": "  Kitchen  "}

    result = await flow.async_step_user(user_input)

    assert result["type"] == "create_entry"
    assert result["title"] == "Kitchen"
    assert result["data"]["host"] == "192.168.1.50"
    assert result["data"]["name"] == "Kitchen"
    can_connect.assert_awaited_once_with("192.168.1.50", 8899)


@pytest.mark.asyncio
async def test_user_step_rejects_whitespace_only_host(
    flow: DiodLEDConfigFlow, can_connect: Any
) -> None:
    """A whitespace-only host must not be stored or dialed."""
    result = await flow.async_step_user(
        {"host": "   ", "port": 8899, "name": "Kitchen"}
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}
    can_connect.assert_not_awaited()


@pytest.mark.asyncio
async def test_user_step_whitespace_only_name_falls_back_to_default(
    flow: DiodLEDConfigFlow, can_connect: Any
) -> None:
    """A whitespace-only name must not become an empty entry title."""
    result = await flow.async_step_user(
        {"host": "192.168.1.50", "port": 8899, "name": "   "}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_NAME
    assert result["data"]["name"] == DEFAULT_NAME
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
    # The MAC is normalized to the canonical unique ID before it is used.
    assert flow.unique_id == "aa:bb:cc:dd:ee:ff"


@pytest.mark.asyncio
async def test_discovery_updates_host_of_known_mac(flow: DiodLEDConfigFlow) -> None:
    """A known MAC (broadcast bare-hex) at a new address updates that entry's
    host and aborts; it matches the canonically stored unique ID."""
    hass = unittest.mock.MagicMock()
    hass.config_entries.async_reload = unittest.mock.AsyncMock()
    flow.hass = hass

    entry = _entry({"host": "192.168.1.50"}, unique_id="aa:bb:cc:dd:ee:ff")
    entry.entry_id = "entry1"
    # Stands in for the update listener registered by async_setup_entry, which
    # is the single place this integration schedules a reload.
    entry._update_listeners = [unittest.mock.AsyncMock()]
    flow.current_entries = [entry]

    with pytest.raises(AbortFlow) as err:
        await flow.async_step_integration_discovery(
            {"host": "192.168.1.77", "mac": "AABBCCDDEEFF"}
        )

    assert err.value.reason == "already_configured"
    assert entry.data["host"] == "192.168.1.77"

    # Let the fire-and-forget listener task run before counting reloads. The
    # flow must not schedule an extra core reload on top of the one the
    # listener performs (core's _abort_if_unique_id_configured defaults to
    # reload_on_update=True, which would double-reload the entry).
    for _ in range(3):
        await asyncio.sleep(0)
    hass.config_entries.async_reload.assert_not_awaited()


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
async def test_discovery_malformed_mac_is_not_stored_as_unique_id(
    flow: DiodLEDConfigFlow,
) -> None:
    """A UDP-discovered MAC that is not a 48-bit hex address must not become the
    entry's unique ID. The discovery MAC is untrusted UDP input, and a unique ID
    becomes the device's network-MAC connection in HA's registry — an attacker on
    the LAN must not be able to choose that identity string (e.g. another
    registered device's MAC, which would merge devices). The flow must fall back
    to host-based identification. (format_mac() itself does not raise on such
    values; this is identity hardening, not a crash fix.)
    """
    for bad_mac in ("not-a-mac", "AABBCCDDEEFF00", "zz:11:22:33:44:55"):
        flow.unique_id = None
        result = await flow.async_step_integration_discovery(
            {"host": "192.0.2.50", "mac": bad_mac}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "discovery_confirm"
        assert flow.unique_id is None


@pytest.mark.asyncio
async def test_discovery_mac_separators_still_accepted(
    flow: DiodLEDConfigFlow,
) -> None:
    """A colon-separated MAC is still a valid unique ID (format_mac accepts it),
    normalized exactly as before."""
    result = await flow.async_step_integration_discovery(
        {"host": "192.0.2.50", "mac": " AA:BB:CC:DD:EE:FF "}
    )

    assert result["step_id"] == "discovery_confirm"
    assert flow.unique_id == "aa:bb:cc:dd:ee:ff"


@pytest.mark.asyncio
async def test_discovery_mac_spelling_variants_share_one_unique_id(
    flow: DiodLEDConfigFlow,
) -> None:
    """ ":" and "-" spellings (and bare hex) of the same MAC normalize to one
    canonical unique ID, so a device always dedupes regardless of how its
    firmware spells the MAC."""
    for mac in ("AA-BB-CC-DD-EE-FF", "aa:bb:cc:dd:ee:ff", "AABBCCDDEEFF"):
        flow.unique_id = None
        result = await flow.async_step_integration_discovery(
            {"host": "192.0.2.50", "mac": mac}
        )

        assert result["step_id"] == "discovery_confirm"
        assert flow.unique_id == "aa:bb:cc:dd:ee:ff"


@pytest.mark.asyncio
async def test_discovery_dash_mac_matches_colon_stored_entry(
    flow: DiodLEDConfigFlow,
) -> None:
    """A "-"-separated broadcast must dedupe to an entry whose unique ID was
    stored from the ":" spelling of the same MAC."""
    flow.current_entries = [
        _entry({"host": "192.0.2.50"}, unique_id="aa:bb:cc:dd:ee:ff")
    ]

    with pytest.raises(AbortFlow) as err:
        await flow.async_step_integration_discovery(
            {"host": "192.0.2.50", "mac": "AA-BB-CC-DD-EE-FF"}
        )

    assert err.value.reason == "already_configured"


@pytest.mark.asyncio
async def test_discovery_mixed_or_odd_mac_separators_rejected(
    flow: DiodLEDConfigFlow,
) -> None:
    """Only a consistent separator layout is accepted; mixed or misplaced
    separators fall back to host-based identification like any non-MAC."""
    for bad_mac in ("a:abbccddeeff", "aa-bb-cc-dd-ee-f:f", ":aa:bb:cc:dd:ee:ff"):
        flow.unique_id = None
        result = await flow.async_step_integration_discovery(
            {"host": "192.0.2.50", "mac": bad_mac}
        )

        assert result["step_id"] == "discovery_confirm"
        assert flow.unique_id is None


@pytest.mark.asyncio
async def test_discovery_malformed_mac_still_dedupes_by_host(
    flow: DiodLEDConfigFlow,
) -> None:
    """With no usable unique ID, a repeat broadcast for the same host aborts
    just like one with a valid MAC."""
    flow.current_entries = [_entry({"host": "192.0.2.50", "port": DEFAULT_PORT})]

    with pytest.raises(AbortFlow) as err:
        await flow.async_step_integration_discovery(
            {"host": "192.0.2.50", "mac": "not-a-mac"}
        )

    assert err.value.reason == "already_configured"


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
async def test_reconfigure_trims_whitespace(can_connect: Any) -> None:
    """Whitespace around host should be stripped on reconfigure."""
    entry = _entry({"host": "192.168.1.50", "port": 8899, "name": "Kitchen"})

    result = await _reconfigure_flow(entry).async_step_reconfigure(
        {"host": "  10.1.1.87  ", "port": 8899}
    )

    assert result == {"type": "abort", "reason": "reconfigure_successful"}
    assert entry.data == {"host": "10.1.1.87", "port": 8899, "name": "Kitchen"}
    can_connect.assert_awaited_once_with("10.1.1.87", 8899)


@pytest.mark.asyncio
async def test_reconfigure_rejects_whitespace_only_host(can_connect: Any) -> None:
    """A whitespace-only host must not be stored or dialed on reconfigure."""
    entry = _entry({"host": "192.168.1.50", "port": 8899})

    result = await _reconfigure_flow(entry).async_step_reconfigure(
        {"host": "   ", "port": 8899}
    )

    assert result["errors"] == {"base": "cannot_connect"}
    assert entry.data == {"host": "192.168.1.50", "port": 8899}
    can_connect.assert_not_awaited()


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
